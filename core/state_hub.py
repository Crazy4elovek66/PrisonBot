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

DOMAIN_TTL_SEC: Dict[str, float] = {
    "player": 45.0,
    "prisons": 90.0,
    "boss": 30.0,
    "katala": 60.0,
    "poker": 90.0,
    "fartovy": 60.0,
    "wheel": 120.0,
    "zaruby": 90.0,
    "social": 120.0,
    "menyala": 60.0,
    "notifications": 30.0,
    "raids": 120.0,
    "wardrobe": 120.0,
}

MUTATION_DEPENDENCIES: Dict[str, Tuple[str, ...]] = {
    "prison_completed": ("player", "prisons", "boss", "zaruby"),
    "prison_action": ("player", "prisons", "boss", "zaruby"),
    "boss_finished": ("player", "boss", "zaruby"),
    "boss_claimed": ("player", "boss", "zaruby"),
    "boss_summoned": ("player", "boss", "zaruby"),
    "boss_config_updated": ("boss",),
    "katala_played": ("player", "katala"),
    "poker_played": ("player", "poker"),
    "fartovy_spun": ("player", "fartovy", "zaruby"),
    "wheel_spun": ("player", "wheel"),
    "zarub_updated": ("player", "zaruby"),
    "zarub_started": ("player", "zaruby"),
    "zarub_claimed": ("player", "zaruby"),
    "social_changed": ("social", "player", "zaruby"),
    "menyala_changed": ("player", "menyala"),
    "routine_action": ("player", "zaruby"),
    "maintenance_recovered": tuple(DOMAIN_TTL_SEC.keys()),
}


@dataclass
class DomainState:
    name: str
    stale_after_sec: float = 60.0
    updated_at: Optional[str] = None
    monotonic_ts: float = 0.0
    revision: int = 0
    dirty: bool = True
    data: Any = None
    last_error: Optional[str] = None


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


@dataclass
class PresetRunState:
    preset_id: int
    current_step: int = 0
    total_steps: int = 0
    active_boss_id: Optional[int] = None
    status: str = "idle"  # idle | running | completed | stopped | failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "presetId": self.preset_id,
            "currentStep": self.current_step,
            "totalSteps": self.total_steps,
            "activeBossId": self.active_boss_id,
            "status": self.status,
            "isRunning": self.status == "running",
        }


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
        "talents",
        "presets",
        "prisons",
        "friends",
        "friend_requests",
        "friends_stats",
        "social",
        "radar",
        "routine",
        "collections",
        "notifications",
        "config",
        "zaruby",
        "menyala",
    )

    def __init__(self) -> None:
        self._slices: Dict[int, Dict[str, SliceEntry]] = {}
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}
        self._in_flight: Dict[str, asyncio.Task] = {}
        self._versions_global: Dict[int, int] = {}
        self._preset_runs: Dict[int, PresetRunState] = {}
        self._domain_revisions: Dict[int, Dict[str, int]] = {}
        self._invalidation_callbacks: List[Callable[[int, List[str], Optional[Dict[str, Any]], str], Any]] = []
        self._domains: Dict[int, Dict[str, DomainState]] = {}
        self._domain_locks: Dict[Tuple[int, str], asyncio.Lock] = {}
        self._domain_fetchers: Dict[str, Callable[[int], Awaitable[Any]]] = {}
        self._wakeup_callbacks: List[Callable[[str, Optional[datetime]], Any]] = []
        self._state_revision: Dict[int, int] = {}

    def clear(self, account_id: Optional[int] = None) -> None:
        """Очищает кэш срезов (используется при сбросе состояния в тестах или смене аккаунта)."""
        if account_id is None:
            self._slices.clear()
            self._versions_global.clear()
            self._preset_runs.clear()
            self._domain_revisions.clear()
            self._domains.clear()
            self._state_revision.clear()
        else:
            self._slices.pop(account_id, None)
            self._versions_global.pop(account_id, None)
            self._preset_runs.pop(account_id, None)
            self._domain_revisions.pop(account_id, None)
            self._domains.pop(account_id, None)
            self._state_revision.pop(account_id, None)

    def register_invalidation_callback(
        self,
        cb: Callable[[int, List[str], Optional[Dict[str, Any]], str], Any],
    ) -> None:
        if cb not in self._invalidation_callbacks:
            self._invalidation_callbacks.append(cb)

    def get_domain_revisions(self, account_id: int) -> Dict[str, int]:
        return dict(self._domain_revisions.get(account_id, {}))

    def invalidate_slice(self, account_id: int, slice_name: str) -> None:
        acc_map = self._slices.get(account_id)
        if acc_map is not None:
            acc_map.pop(slice_name, None)

    def get_preset_state(self, account_id: int) -> Optional[PresetRunState]:
        return self._preset_runs.get(account_id)

    def set_preset_state(
        self,
        account_id: int,
        preset_id: Optional[int],
        *,
        current_step: int = 0,
        total_steps: int = 0,
        active_boss_id: Optional[int] = None,
        status: str = "idle",
        presets_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[PresetRunState]:
        """Обновляет runtime-состояние активного пресета и транслирует срез presets подписчикам."""
        if preset_id is None or status == "idle":
            self._preset_runs.pop(account_id, None)
            state_obj: Optional[PresetRunState] = None
        else:
            state_obj = PresetRunState(
                preset_id=int(preset_id),
                current_step=int(current_step),
                total_steps=int(total_steps),
                active_boss_id=active_boss_id,
                status=status,
            )
            self._preset_runs[account_id] = state_obj

        if presets_list is not None:
            self.update_slice(
                account_id,
                "presets",
                {
                    "success": True,
                    "activeRun": state_obj.to_dict() if state_obj else None,
                    "presets": presets_list,
                },
            )
        return state_obj

    def clear_preset_state(self, account_id: int) -> None:
        self._preset_runs.pop(account_id, None)

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

    @staticmethod
    def _server_now_ts() -> float:
        try:
            from client.http_client import get_game_now_ts
            return round(get_game_now_ts(), 3)
        except Exception:
            return round(time.time(), 3)

    def get_snapshot(self, account_id: int) -> Dict[str, Any]:
        acc_slices = self._slices.get(account_id, {})
        return {
            "type": "snapshot",
            "accountId": account_id,
            "server_now_ts": self._server_now_ts(),
            "versions": {k: e.version for k, e in acc_slices.items()},
            "revisions": self.get_domain_revisions(account_id),
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
            "server_now_ts": self._server_now_ts(),
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
        if slice_name == "collections" and existing is not None and isinstance(existing.data, dict) and isinstance(data, dict):
            old_cols = existing.data.get("collections") or []
            new_cols = data.get("collections") or []
            if old_cols and not new_cols:
                return False, existing
        if existing is not None and existing.fingerprint == fp and (source_tag is None or existing.source_tag == source_tag):
            existing.updated_at = now_iso
            existing.monotonic_ts = now_mono
            return False, existing

        if slice_name == "profile" and isinstance(data, dict):
            prof_obj = data.get("profile") if isinstance(data.get("profile"), dict) else {}
            cur_obj = data.get("currencies") if isinstance(data.get("currencies"), dict) else {}
            is_valid_prof = bool(prof_obj.get("id") or int(prof_obj.get("level") or 0) > 0)
            if is_valid_prof and cur_obj:
                try:
                    loop = asyncio.get_running_loop()
                    from core.config import MSK_TZ
                    from core.database import ensure_daily_resource_baseline
                    day_msk = datetime.now(MSK_TZ).strftime("%Y-%m-%d")
                    loop.create_task(ensure_daily_resource_baseline(day_msk, cur_obj))
                except Exception:
                    pass

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
            if isinstance(patched.get("currencies"), dict):
                for rk in ("cigarettes", "sugar", "rubles", "paper", "soap"):
                    if rk in changes and changes[rk] is not None:
                        patched["currencies"][rk] = changes[rk]
                rd = patched.get("resource_deltas")
                if isinstance(rd, dict) and isinstance(rd.get("baseline"), dict):
                    base_map = rd["baseline"]
                    new_deltas = {}
                    for rk in ("cigarettes", "sugar", "rubles", "paper", "soap"):
                        if rk in base_map and rk in patched["currencies"]:
                            try:
                                new_deltas[rk] = int(patched["currencies"][rk]) - int(base_map[rk])
                            except (TypeError, ValueError):
                                pass
                    if len(new_deltas) == 5:
                        rd["deltas"] = new_deltas
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

    @staticmethod
    def _is_valid_talents_payload(data: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(data, dict) or not data:
            return False
        req = int(data.get("requiredDamage") or data.get("next_point_damage") or 0)
        cur = int(data.get("currentDamage") or data.get("damage") or 0)
        spent = int(data.get("spentPoints") or 0)
        unspent = int(data.get("unspentPoints") or data.get("free_points") or 0)
        total = int(data.get("totalPoints") if data.get("totalPoints") is not None else (data.get("points") if data.get("points") is not None else (spent + unspent)))
        return req > 0 or total > 0 or unspent > 0 or cur > 0

    def merge_talents_state(
        self,
        account_id: int,
        incoming: Optional[Dict[str, Any]],
        *,
        allow_damage_zero: bool = False,
        source_tag: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Защищённо обновляет срез talents: никогда не затирает валидные данные нулевым или пустым пакетом.
        При allow_damage_zero=True (нет активного боя) обнуляет только currentDamage, сохраняя target и очки.
        """
        existing_entry = self.get_slice(account_id, "talents")
        existing_data = copy.deepcopy(existing_entry.data) if (existing_entry and isinstance(existing_entry.data, dict)) else None

        if allow_damage_zero and existing_data and self._is_valid_talents_payload(existing_data):
            merged = copy.deepcopy(existing_data)
            merged["currentDamage"] = 0
            self.update_slice(account_id, "talents", merged, source_tag=source_tag or (existing_entry.source_tag if existing_entry else None))
            return merged

        if not self._is_valid_talents_payload(incoming):
            return existing_data

        inc = copy.deepcopy(incoming)
        assert isinstance(inc, dict)
        req = int(inc.get("requiredDamage") or inc.get("next_point_damage") or 0)
        cur = int(inc.get("currentDamage") or inc.get("damage") or 0)
        spent = int(inc.get("spentPoints") or 0)
        unspent = int(inc.get("unspentPoints") if inc.get("unspentPoints") is not None else (inc.get("free_points") or 0))
        total = int(inc.get("totalPoints") if inc.get("totalPoints") is not None else (inc.get("points") if inc.get("points") is not None else (spent + unspent)))

        if existing_data:
            if req <= 0 and int(existing_data.get("requiredDamage") or 0) > 0:
                req = int(existing_data["requiredDamage"])
            if total <= 0 and int(existing_data.get("totalPoints") or 0) > 0:
                total = int(existing_data["totalPoints"])
                spent = int(existing_data.get("spentPoints") or spent)
                unspent = int(existing_data.get("unspentPoints") or unspent)

        normalized = {
            **inc,
            "currentDamage": cur,
            "requiredDamage": max(0, req),
            "spentPoints": max(0, spent),
            "unspentPoints": max(0, unspent),
            "totalPoints": max(0, total),
        }
        self.update_slice(account_id, "talents", normalized, source_tag=source_tag)
        return normalized

    def emit_change(
        self,
        account_id: int,
        domains: List[str],
        patch: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Атомарно фиксирует изменения по доменам с монотонным revision,
        мержит частичный patch (с защитой от затирания), вызывает колбэки инвалидации и рассылает domain_sync в SSE.
        """
        if not domains:
            domains = []
        revs = self._domain_revisions.setdefault(account_id, {})
        domain_revs: Dict[str, int] = {}
        for d in domains:
            revs[d] = revs.get(d, 0) + 1
            domain_revs[d] = revs[d]

        safe_patch: Dict[str, Any] = copy.deepcopy(patch) if isinstance(patch, dict) else {}

        if isinstance(safe_patch.get("talents"), dict):
            merged_talents = self.merge_talents_state(account_id, safe_patch["talents"])
            if merged_talents is not None:
                safe_patch["talents"] = merged_talents

        if isinstance(safe_patch.get("profile"), dict):
            self.patch_profile_resources(account_id, **safe_patch["profile"])

        for dom_key in ("boss", "prison", "routine", "config", "notifications"):
            if isinstance(safe_patch.get(dom_key), dict):
                existing = self.get_slice(account_id, dom_key)
                if existing is not None and isinstance(existing.data, dict):
                    merged = copy.deepcopy(existing.data)
                    merged.update(safe_patch[dom_key])
                    self.update_slice(account_id, dom_key, merged, source_tag=existing.source_tag)

        for cb in list(self._invalidation_callbacks):
            try:
                cb(account_id, list(domains), safe_patch, reason)
            except Exception as cb_err:
                logger.debug("invalidation callback error: %s", cb_err)

        ts = time.time()
        event = {
            "type": "domain_sync",
            "accountId": account_id,
            "server_now_ts": self._server_now_ts(),
            "domains": list(domains),
            "revisions": domain_revs,
            "ts": ts,
            "patch": safe_patch,
            "reason": reason,
        }
        self._broadcast(account_id, event)

        if "social" in domains and isinstance(safe_patch.get("social"), dict):
            social_evt = {
                "type": "social_updated",
                "accountId": account_id,
                "server_now_ts": self._server_now_ts(),
                "revision": domain_revs.get("social", 1),
                "ts": ts,
                **safe_patch["social"],
            }
            self._broadcast(account_id, social_evt)

        return event

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

    def get_domain_state(self, account_id: int, domain: str) -> DomainState:
        acc_doms = self._domains.setdefault(account_id, {})
        if domain not in acc_doms:
            acc_doms[domain] = DomainState(
                name=domain,
                stale_after_sec=DOMAIN_TTL_SEC.get(domain, 60.0),
            )
        return acc_doms[domain]

    def set_domain_data(self, account_id: int, domain: str, data: Any) -> DomainState:
        dom = self.get_domain_state(account_id, domain)
        dom.data = copy.deepcopy(data)
        dom.updated_at = datetime.now(timezone.utc).isoformat()
        dom.monotonic_ts = time.monotonic()
        dom.dirty = False
        dom.last_error = None
        dom.revision += 1
        revs = self._domain_revisions.setdefault(account_id, {})
        revs[domain] = max(revs.get(domain, 0), dom.revision)
        self._state_revision[account_id] = self._state_revision.get(account_id, 0) + 1
        return dom

    def mark_dirty(self, account_id: int, *domains: str) -> List[str]:
        marked: List[str] = []
        for d in domains:
            if not d:
                continue
            dom = self.get_domain_state(account_id, d)
            dom.dirty = True
            dom.revision += 1
            revs = self._domain_revisions.setdefault(account_id, {})
            revs[d] = max(revs.get(d, 0), dom.revision)
            marked.append(d)
        if marked:
            self._state_revision[account_id] = self._state_revision.get(account_id, 0) + 1
        return marked

    def register_domain_fetcher(self, domain: str, fetcher: Callable[[int], Awaitable[Any]]) -> None:
        self._domain_fetchers[domain] = fetcher

    def register_wakeup_callback(self, cb: Callable[[str, Optional[datetime]], Any]) -> None:
        if cb not in self._wakeup_callbacks:
            self._wakeup_callbacks.append(cb)

    async def ensure_domain_fresh(
        self,
        account_id: int,
        domain: str,
        force: bool = False,
        fetcher: Optional[Callable[[], Awaitable[Any]]] = None,
    ) -> Any:
        """
        Single-flight обновление домена с per-domain asyncio.Lock.
        При ошибке (сеть / техработы / пустой ответ) строго сохраняет последний валидный кэш.
        """
        dom = self.get_domain_state(account_id, domain)
        age = time.monotonic() - dom.monotonic_ts if dom.monotonic_ts > 0 else float("inf")
        needs_refresh = force or dom.dirty or dom.data is None or age > dom.stale_after_sec
        if not needs_refresh:
            return copy.deepcopy(dom.data)

        lock_key = (account_id, domain)
        lock = self._domain_locks.get(lock_key)
        if lock is None:
            lock = asyncio.Lock()
            self._domain_locks[lock_key] = lock

        async def _do_fetch():
            async with lock:
                # Double-check after acquiring lock
                cur_dom = self.get_domain_state(account_id, domain)
                cur_age = time.monotonic() - cur_dom.monotonic_ts if cur_dom.monotonic_ts > 0 else float("inf")
                if not force and not cur_dom.dirty and cur_dom.data is not None and cur_age <= cur_dom.stale_after_sec:
                    return copy.deepcopy(cur_dom.data)
                fn = fetcher or (
                    (lambda: self._domain_fetchers[domain](account_id))
                    if domain in self._domain_fetchers
                    else None
                )
                if fn is None:
                    return copy.deepcopy(cur_dom.data)
                try:
                    fresh = await fn()
                    if fresh is None:
                        return copy.deepcopy(cur_dom.data)
                    self.set_domain_data(account_id, domain, fresh)
                    if domain in self.SUPPORTED_SLICES:
                        self.update_slice(account_id, domain, fresh)
                    return copy.deepcopy(fresh)
                except Exception as e:
                    cur_dom.last_error = str(e)
                    logger.debug("ensure_domain_fresh(%s) error (preserving cached): %s", domain, e)
                    return copy.deepcopy(cur_dom.data)

        return await self.run_single_flight(f"domain:{account_id}:{domain}:{'force' if force else 'fresh'}", _do_fetch)

    def notify_mutation(
        self,
        account_id: int,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        reason: str = "",
        extra_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Событийная кросс-инвалидация зависимых доменов при мутации любого воркера или ручного POST-роута.
        """
        deps = list(MUTATION_DEPENDENCIES.get(event_type, ()))
        if extra_domains:
            for ed in extra_domains:
                if ed and ed not in deps:
                    deps.append(ed)
        if deps:
            self.mark_dirty(account_id, *deps)
        evt = self.emit_change(
            account_id=account_id,
            domains=deps,
            patch=payload,
            reason=reason or event_type,
        )
        # Пробуждение зависимых воркеров при ключевых событиях
        wake_targets: List[str] = []
        if event_type in ("prison_completed", "prison_action"):
            wake_targets.extend(["boss", "zaruby"])
        elif event_type in ("fartovy_spun", "social_changed", "routine_action"):
            wake_targets.append("zaruby")
        for target in wake_targets:
            for cb in list(self._wakeup_callbacks):
                try:
                    cb(target, datetime.now(timezone.utc))
                except Exception:
                    pass
        return evt

    def push_notification(
        self,
        account_id: int,
        notification: Dict[str, Any],
        unread_count: Optional[int] = None,
        counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Мгновенно публикует новое уведомление в SSE-поток (event: notification)."""
        revs = self._domain_revisions.setdefault(account_id, {})
        rev = int(revs.get("notifications", 0)) + 1
        revs["notifications"] = rev
        evt: Dict[str, Any] = {
            "type": "notification",
            "account_id": account_id,
            "server_now_ts": self._server_now_ts(),
            "notification": dict(notification or {}),
            "revision": rev,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if unread_count is not None:
            evt["unread_count"] = int(unread_count)
        if counts is not None:
            evt["counts"] = dict(counts)
        self._broadcast(account_id, evt)
        return evt

    def get_domains_telemetry(self, account_id: int) -> Dict[str, Any]:
        now_mono = time.monotonic()
        domains_out: Dict[str, Any] = {}
        for d_name, ttl in DOMAIN_TTL_SEC.items():
            dom = self.get_domain_state(account_id, d_name)
            age = round(max(0.0, now_mono - dom.monotonic_ts), 1) if dom.monotonic_ts > 0 else None
            domains_out[d_name] = {
                "updated_at": dom.updated_at,
                "age_sec": age,
                "dirty": dom.dirty,
                "revision": dom.revision,
                "stale_after_sec": ttl,
                "last_error": dom.last_error,
            }
        revs = {d_name: domains_out[d_name]["revision"] for d_name in DOMAIN_TTL_SEC}
        revs.update(self.get_domain_revisions(account_id))
        return {
            "state_revision": self._state_revision.get(account_id, 0),
            "domain_revisions": revs,
            "domains": domains_out,
        }

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
