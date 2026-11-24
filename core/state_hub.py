import asyncio
import copy
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

VOLATILE_KEYS = {"generatedAt", "updatedAt", "serverTime", "_cachedAt", "timestamp"}


def _strip_volatile(obj: Any) -> Any:
    """Рекурсивно удаляет эфемерные временные метки для честного сравнения payload по содержимому."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in VOLATILE_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile(item) for item in obj]
    return obj


def compute_fingerprint(data: Any) -> str:
    """Вычисляет детерминированный SHA-1 хеш содержимого среза."""
    cleaned = _strip_volatile(data)
    raw = json.dumps(cleaned, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


@dataclass
class SliceEntry:
    name: str
    data: Any
    version: int
    fingerprint: str
    updated_at: str
    monotonic_ts: float
    source_tag: Optional[str] = None


class LiveStateHub:
    """
    Центральное потокобезопасное (asyncio) хранилище актуального live-состояния по аккаунтам и срезам:
    - Дедуплицирует неизменившиеся данные по fingerprint.
    - Инкрементирует монотонную версию только при реальном изменении данных.
    - Транслирует события slice_update подключенным SSE-подписчикам через ограниченные очереди asyncio.Queue.
    - Обеспечивает single-flight дедупликацию параллельных обновлений одного и того же среза.
    """

    SUPPORTED_SLICES = (
        "profile",
        "state",
        "boss",
        "prisons",
        "friends",
        "friend_requests",
        "friends_stats",
        "radar",
        "routine",
        "collections",
        "config",
    )

    def __init__(self) -> None:
        self._slices: Dict[int, Dict[str, SliceEntry]] = {}
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}
        self._in_flight: Dict[str, asyncio.Task] = {}
        self._versions_global: Dict[int, int] = {}

    def clear(self, account_id: Optional[int] = None) -> None:
        """Очищает кэш срезов (используется при сбросе состояния в тестах или смене аккаунта)."""
        if account_id is None:
            self._slices.clear()
            self._versions_global.clear()
        else:
            self._slices.pop(account_id, None)
            self._versions_global.pop(account_id, None)

    def get_slice(
        self,
        account_id: int,
        slice_name: str,
        max_age_seconds: Optional[float] = None,
        source_tag: Optional[str] = None,
    ) -> Optional[SliceEntry]:
        entry = self._slices.get(account_id, {}).get(slice_name)
        if entry is None:
            return None
        if source_tag is not None and entry.source_tag != source_tag:
            return None
        if max_age_seconds is not None and (time.monotonic() - entry.monotonic_ts) > max_age_seconds:
            return None
        return entry

    def get_versions(self, account_id: int) -> Dict[str, int]:
        acc_slices = self._slices.get(account_id, {})
        return {name: entry.version for name, entry in acc_slices.items()}

    def get_snapshot(self, account_id: int) -> Dict[str, Any]:
        acc_slices = self._slices.get(account_id, {})
        return {
            "type": "snapshot",
            "accountId": account_id,
            "versions": {k: e.version for k, e in acc_slices.items()},
            "updatedAt": {k: e.updated_at for k, e in acc_slices.items()},
            "slices": {k: copy.deepcopy(e.data) for k, e in acc_slices.items()},
        }

    def get_delta(self, account_id: int, client_versions: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        client_versions = client_versions or {}
        acc_slices = self._slices.get(account_id, {})
        changed: Dict[str, Any] = {}
        updated_at: Dict[str, str] = {}
        for name, entry in acc_slices.items():
            if entry.version > int(client_versions.get(name, 0) or 0):
                changed[name] = copy.deepcopy(entry.data)
                updated_at[name] = entry.updated_at
        return {
            "accountId": account_id,
            "versions": {k: e.version for k, e in acc_slices.items()},
            "updatedAt": updated_at,
            "changed": changed,
        }

    def update_slice(
        self,
        account_id: int,
        slice_name: str,
        data: Any,
        source_tag: Optional[str] = None,
    ) -> Tuple[bool, SliceEntry]:
        """
        Сохраняет срез в кэш. Если содержимое изменилось, увеличивает version и уведомляет подписчиков.
        Возвращает (changed: bool, entry: SliceEntry).
        """
        acc_map = self._slices.setdefault(account_id, {})
        now_iso = datetime.now(timezone.utc).isoformat()
        now_mono = time.monotonic()
        fp = compute_fingerprint(data)

        existing = acc_map.get(slice_name)
        if existing is not None and existing.fingerprint == fp and (source_tag is None or existing.source_tag == source_tag):
            existing.updated_at = now_iso
            existing.monotonic_ts = now_mono
            return False, existing

        new_version = (existing.version + 1) if existing is not None else 1
        entry = SliceEntry(
            name=slice_name,
            data=copy.deepcopy(data),
            version=new_version,
            fingerprint=fp,
            updated_at=now_iso,
            monotonic_ts=now_mono,
            source_tag=source_tag,
        )
        acc_map[slice_name] = entry
        self._broadcast(
            account_id,
            {
                "type": "slice_update",
                "accountId": account_id,
                "slice": slice_name,
                "version": entry.version,
                "updatedAt": entry.updated_at,
                "data": copy.deepcopy(entry.data),
            },
        )
        return True, entry

    def patch_profile_resources(self, account_id: int, **changes: Any) -> bool:
        """
        Точечно обновляет ресурсы (energy, maxEnergy, cigarettes, rubles и т.д.) в прогретых срезах profile/state
        без ожидания тяжелого внешнего init-запроса.
        """
        if not changes:
            return False
        updated_any = False

        prof_entry = self.get_slice(account_id, "profile")
        if prof_entry is not None and isinstance(prof_entry.data, dict):
            patched = copy.deepcopy(prof_entry.data)
            target_profile = patched.get("profile") if isinstance(patched.get("profile"), dict) else None
            for k, v in changes.items():
                if v is None:
                    continue
                if target_profile is not None:
                    target_profile[k] = v
                if k in patched or target_profile is None:
                    patched[k] = v
            changed, _ = self.update_slice(account_id, "profile", patched, source_tag=prof_entry.source_tag)
            updated_any = updated_any or changed

        state_entry = self.get_slice(account_id, "state")
        if state_entry is not None and isinstance(state_entry.data, dict):
            patched_state = copy.deepcopy(state_entry.data)
            snap = patched_state.get("snapshot") if isinstance(patched_state.get("snapshot"), dict) else None
            key_map = {
                "energy": "energy",
                "maxEnergy": "max_energy",
                "cigarettes": "cigarettes",
                "rubles": "rubles",
                "authority": "authority",
                "toiletPaper": "toilet_paper",
                "soap": "soap",
                "sugar": "sugar",
                "matches": "matches",
            }
            for api_key, val in changes.items():
                if val is None:
                    continue
                if snap is not None and api_key in key_map:
                    snap[key_map[api_key]] = val
            changed_st, _ = self.update_slice(account_id, "state", patched_state, source_tag=state_entry.source_tag)
            updated_any = updated_any or changed_st

        return updated_any

    def subscribe(self, account_id: int = 1, maxsize: int = 32) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.setdefault(account_id, set()).add(q)
        return q

    def unsubscribe(self, account_id: int, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(account_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subscribers.pop(account_id, None)

    def _broadcast(self, account_id: int, event: Dict[str, Any]) -> None:
        subs = list(self._subscribers.get(account_id, ()))
        for q in subs:
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(event)
            except Exception:
                pass

    async def run_single_flight(self, key: str, coro_fn: Callable[[], Awaitable[T]]) -> T:
        """
        Гарантирует, что при одновременных запросах одного и того же ключа выполняется
        ровно одна корутина, а остальные ожидают её результата.
        """
        existing_task = self._in_flight.get(key)
        if existing_task is not None and not existing_task.done():
            return await existing_task

        task = asyncio.create_task(coro_fn())
        self._in_flight[key] = task
        try:
            return await task
        finally:
            if self._in_flight.get(key) is task:
                self._in_flight.pop(key, None)


state_hub = LiveStateHub()
