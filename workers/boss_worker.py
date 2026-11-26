import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import httpx
from sqlalchemy import select

from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active, is_night_mode_active
from core.server_health import server_health_monitor, GameMaintenanceError
from core.models import ActionLog, FriendStats, BossFriendDamageLog, BossPreset, BossBattleSnapshot
from client.api.boss import BossAPI, _load_bosses_catalog, FALLBACK_BOSSES
from workers.routine_worker import parse_iso_utc
from bot.notifier import TelegramNotifier
from core.drop_parser import DropParser

logger = logging.getLogger(__name__)

MELEE_CONFIG = {
    "punchChest": {
        "last_time_key": "lastPunchChestTime",
        "cooldown_key": "punchChestCooldownSec",
        "default_cooldown": 28800,
    },
    "kickBalls": {
        "last_time_key": "lastKickBallsTime",
        "cooldown_key": "kickBallsCooldownSec",
        "default_cooldown": 28800,
    },
    "pokeEyes": {
        "last_time_key": "lastPokeEyesTime",
        "cooldown_key": "pokeEyesCooldownSec",
        "default_cooldown": 28800,
    },
    "kneeEar": {
        "last_time_key": "lastKneeEarTime",
        "cooldown_key": "kneeEarCooldownSec",
        "default_cooldown": 28800,
    },
}


MODE_ALIASES = {
    "пацанский": "pacansky",
    "блатной": "blotnoy",
    "авторитетный": "avtoritetny",
    "воровской": "vorovskoy",
    "в одного": "odin",
    "бригадный": "brigade",
}


def _normalize_boss_mode(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    m = str(mode).strip().lower()
    return MODE_ALIASES.get(m, m)


def resolve_catalog_boss_max_hp(
    boss_id: Optional[int] = None,
    boss_name: Optional[str] = None,
    mode: Optional[str] = None,
    catalog: Optional[List[Dict[str, Any]]] = None,
) -> Optional[int]:
    """Возвращает эталонное max_hp босса для указанного режима из bosses_catalog.json."""
    items = catalog if catalog is not None else FALLBACK_BOSSES
    if not items:
        return None
    norm_mode = _normalize_boss_mode(mode) or "pacansky"
    norm_name = str(boss_name or "").strip().lower()
    target = None
    for b in items:
        if not isinstance(b, dict):
            continue
        if boss_id is not None and b.get("id") is not None and int(b.get("id")) == int(boss_id):
            target = b
            break
        if norm_name and str(b.get("name") or b.get("title") or "").strip().lower() == norm_name:
            target = b
            break
    if not target:
        return None
    modes = target.get("modes") if isinstance(target.get("modes"), dict) else {}
    m_obj = modes.get(norm_mode) if isinstance(modes.get(norm_mode), dict) else None
    if m_obj and m_obj.get("hp") and int(m_obj["hp"]) > 1:
        return int(m_obj["hp"])
    base_hp = target.get("baseHp") or target.get("hp")
    if base_hp and int(base_hp) > 1:
        return int(base_hp)
    return None


def resolve_defeat_boss_hp(
    *,
    server_payload: Optional[Dict[str, Any]] = None,
    battle: Optional[Dict[str, Any]] = None,
    snapshot: Optional[Dict[str, Any]] = None,
    boss_id: Optional[int] = None,
    boss_name: Optional[str] = None,
    mode: Optional[str] = None,
    catalog: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Приоритетный каскад определения (remaining_hp, max_hp, hp_percent, hp_known) при поражении от босса:
    1. Валидные ненулевые поля результата боя с сервера.
    2. Каталожное max_hp + total_damage от сервера.
    3. Последний живой снимок активного боя (память / SQLite).
    """
    def _pick_pos(sources: List[Optional[Dict[str, Any]]], keys: Tuple[str, ...], min_val: int = 1) -> Optional[int]:
        for src in sources:
            if not isinstance(src, dict):
                continue
            for k in keys:
                val = src.get(k)
                if val is not None:
                    try:
                        iv = int(val)
                        if iv >= min_val:
                            return iv
                    except (TypeError, ValueError):
                        continue
        return None

    sources = [server_payload, battle]
    server_rem = _pick_pos(sources, ("remainingHp", "remaining_hp", "currentHp", "current_hp", "hp", "health", "bossHp", "boss_hp"), min_val=1)
    server_max = _pick_pos(sources, ("maxHp", "max_hp", "maxHealth", "max_health"), min_val=2)
    total_damage = _pick_pos(sources, ("totalDamage", "total_damage", "raidDamage", "damage"), min_val=0)
    personal_damage = _pick_pos(sources, ("personalDamage", "personal_damage", "myDamage", "my_damage"), min_val=1)

    norm_mode = _normalize_boss_mode(mode)
    catalog_max = resolve_catalog_boss_max_hp(boss_id=boss_id, boss_name=boss_name, mode=mode, catalog=catalog)
    resolved_max = server_max or catalog_max

    rem_hp: Optional[int] = None
    max_hp: Optional[int] = resolved_max

    # 1. Прямые валидные данные сервера
    if server_rem is not None and resolved_max is not None and server_rem <= resolved_max:
        rem_hp = server_rem
    # 2. Расчет через каталог/max_hp + total_damage
    elif total_damage is not None and resolved_max is not None and 0 <= total_damage < resolved_max:
        calc_rem = resolved_max - total_damage
        if calc_rem > 0:
            rem_hp = calc_rem
    # 3. Последний живой снимок активного боя
    elif isinstance(snapshot, dict):
        snap_bid = snapshot.get("boss_id")
        snap_bname = str(snapshot.get("boss_name") or "").strip().lower()
        snap_mode = _normalize_boss_mode(snapshot.get("mode"))
        id_match = (boss_id is not None and snap_bid is not None and int(boss_id) == int(snap_bid))
        name_match = (bool(boss_name) and bool(snap_bname) and str(boss_name).strip().lower() == snap_bname)
        mode_match = (not norm_mode or not snap_mode or norm_mode == snap_mode)
        if (id_match or name_match or (boss_id is None and not boss_name)) and mode_match:
            snap_rem = int(snapshot.get("current_hp") or 0)
            snap_max = int(snapshot.get("max_hp") or 0)
            if snap_max <= 1 and resolved_max and resolved_max > 1:
                snap_max = resolved_max
            if snap_rem > 0 and snap_max > 1:
                if total_damage is not None and 0 <= total_damage < snap_max:
                    snap_rem = min(snap_rem, max(1, snap_max - total_damage))
                rem_hp = snap_rem
                max_hp = snap_max
                if personal_damage is None and snapshot.get("personal_damage"):
                    personal_damage = int(snapshot["personal_damage"])

    # Защитный инвариант: remaining_hp при поражении строго > 0, max_hp строго > 1
    if rem_hp is not None and rem_hp > 0 and max_hp is not None and max_hp > 1:
        hp_percent = round((rem_hp / max_hp) * 100.0, 1)
        return {
            "remaining_hp": int(rem_hp),
            "max_hp": int(max_hp),
            "hp_percent": hp_percent,
            "hp_known": True,
            "personal_damage": personal_damage,
        }

    return {
        "remaining_hp": None,
        "max_hp": int(max_hp) if (max_hp is not None and max_hp > 1) else None,
        "hp_percent": None,
        "hp_known": False,
        "personal_damage": personal_damage,
    }


class BossWorker:
    """
    Воркер автоматического мониторинга и непрерывного конвейерного ведения боя с боссами:
    1. Сбор наград за поверженных боссов (state == 'reward', hasReward, unclaimedRewards, currentHp <= 0).
    2. Ожидание завершения 'reward_processing' и немедленный призыв следующего босса в том же цикле.
    3. Поддержка пресетов (ручной и по расписанию МСК) и бесконечной очереди config.boss_targets.
    4. Корректная оценка доступности боссов с учетом prisons_data и режима боя.
    5. Серия готовых бесплатных рукопашных ударов и немедленный переход к следующему боссу при убийстве.
    """

    def __init__(
        self,
        account_id: int,
        boss_api: BossAPI,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
        prison_api: Optional[Any] = None,
        player_api: Optional[Any] = None,
        state_hub: Optional[Any] = None,
        on_activity_change: Optional[Callable[[bool], Any]] = None,
        on_melee_reschedule: Optional[Callable[[float], Any]] = None,
    ):
        self.account_id = account_id
        self.api = boss_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.prison_api = prison_api
        self.player_api = player_api
        self.state_hub = state_hub
        self.on_activity_change = on_activity_change
        self.on_melee_reschedule = on_melee_reschedule
        self.is_paused: bool = False
        self._cycle_lock = asyncio.Lock()
        self.melee_ready_at: Dict[str, float] = {w: 0.0 for w in MELEE_CONFIG}
        self._last_active_boss_id: Optional[int] = None
        self._last_active_boss_name: Optional[str] = None
        self._last_active_boss_mode: Optional[str] = None
        self._last_live_battle_snapshot: Optional[Dict[str, Any]] = None
        self._notified_victory_keys: Set[str] = set()
        self._battle_started_at_by_session: Dict[str, float] = {}
        self._last_battle_started_at: Optional[float] = None

    async def _save_live_battle_snapshot(
        self,
        battle: Optional[Dict[str, Any]],
        boss_name: Optional[str] = None,
        override_hp: Optional[int] = None,
    ) -> None:
        """Сохраняет последний валидный снимок живого боя (current_hp > 0, max_hp > 1) в память и SQLite."""
        if not isinstance(battle, dict):
            return
        cur_hp = int(override_hp if override_hp is not None else (battle.get("currentHp") or 0))
        max_hp = int(battle.get("maxHp") or 0)
        b_id = battle.get("bossId") or self._last_active_boss_id
        b_mode = battle.get("mode") or self._last_active_boss_mode
        b_name = boss_name or battle.get("title") or battle.get("bossName") or self._last_active_boss_name
        if max_hp <= 1:
            cat_max = resolve_catalog_boss_max_hp(boss_id=b_id, boss_name=b_name, mode=b_mode)
            if cat_max:
                max_hp = cat_max
        if cur_hp <= 0 or max_hp <= 1:
            return

        snap = {
            "boss_id": int(b_id) if b_id is not None else None,
            "boss_name": str(b_name) if b_name else None,
            "mode": str(b_mode) if b_mode else None,
            "session_id": str(battle.get("sessionId")) if battle.get("sessionId") is not None else None,
            "current_hp": cur_hp,
            "max_hp": max_hp,
            "total_damage": int(battle.get("totalDamage") or 0),
            "personal_damage": int(battle.get("personalDamage") or 0),
            "ends_at": str(battle.get("endsAt")) if battle.get("endsAt") else None,
        }
        self._last_live_battle_snapshot = snap
        if not self.db_engine:
            return
        try:
            async with get_session(self.db_engine) as session:
                stmt = select(BossBattleSnapshot).where(BossBattleSnapshot.account_id == self.account_id)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing is None:
                    existing = BossBattleSnapshot(account_id=self.account_id, **snap)
                    session.add(existing)
                else:
                    for k, v in snap.items():
                        setattr(existing, k, v)
                await session.commit()
        except Exception as e:
            logger.debug("Ошибка сохранения снимка боя: %s", e)

    async def _load_live_battle_snapshot(self) -> Optional[Dict[str, Any]]:
        """Загружает последний валидный снимок живого боя из памяти или SQLite."""
        if self._last_live_battle_snapshot and self._last_live_battle_snapshot.get("current_hp", 0) > 0:
            return self._last_live_battle_snapshot
        if not self.db_engine:
            return None
        try:
            async with get_session(self.db_engine) as session:
                stmt = select(BossBattleSnapshot).where(BossBattleSnapshot.account_id == self.account_id)
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row and int(row.current_hp or 0) > 0 and int(row.max_hp or 0) > 1:
                    snap = {
                        "boss_id": row.boss_id,
                        "boss_name": row.boss_name,
                        "mode": row.mode,
                        "session_id": row.session_id,
                        "current_hp": int(row.current_hp),
                        "max_hp": int(row.max_hp),
                        "total_damage": int(row.total_damage or 0),
                        "personal_damage": int(row.personal_damage or 0),
                        "ends_at": row.ends_at,
                    }
                    self._last_live_battle_snapshot = snap
                    return snap
        except Exception as e:
            logger.debug("Ошибка загрузки снимка боя: %s", e)
        return None

    async def _clear_live_battle_snapshot(self) -> None:
        """Очищает снимок боя строго после фиксации его исхода."""
        self._last_live_battle_snapshot = None
        if not self.db_engine:
            return
        try:
            async with get_session(self.db_engine) as session:
                stmt = select(BossBattleSnapshot).where(BossBattleSnapshot.account_id == self.account_id)
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row is not None:
                    await session.delete(row)
                    await session.commit()
        except Exception as e:
            logger.debug("Ошибка очистки снимка боя: %s", e)

    async def _jitter(self) -> None:
        if self.enable_jitter:
            delay = random.uniform(settings.JITTER_MIN_SEC, settings.JITTER_MAX_SEC)
            await asyncio.sleep(delay)

    async def _transition_pause(self) -> None:
        if self.enable_jitter:
            await asyncio.sleep(random.uniform(1.0, 2.5))

    async def _log_action(
        self,
        action_type: str,
        endpoint: str,
        status_code: int = 200,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            async with get_session(self.db_engine) as session:
                log_entry = ActionLog(
                    account_id=self.account_id,
                    action_type=action_type,
                    endpoint=endpoint,
                    status_code=status_code,
                    success=success,
                    details=details or {},
                )
                session.add(log_entry)
        except Exception as e:
            logger.error(f"Не удалось записать ActionLog ({action_type}): {e}")

    @staticmethod
    def _extract_battle(bootstrap: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Нормализует состояние боя из ответа /api/boss/bootstrap (session | currentBattle | activeBoss)."""
        if not isinstance(bootstrap, dict):
            return "idle", None
        state = str(bootstrap.get("state") or "idle").lower()
        battle = None
        for key in ("session", "currentBattle", "activeBoss"):
            cand = bootstrap.get(key)
            if isinstance(cand, dict) and cand:
                battle = cand
                break
        return state, battle

    @staticmethod
    def _normalize_boss_target(item: Any) -> Optional[Dict[str, Any]]:
        if isinstance(item, dict):
            if not item.get("enabled", True):
                return None
            raw_id = item.get("bossId") if item.get("bossId") is not None else (item.get("boss_id") if item.get("boss_id") is not None else item.get("id"))
            if raw_id is None:
                return None
            try:
                b_id = int(raw_id)
            except (ValueError, TypeError):
                return None
            return {
                "bossId": b_id,
                "mode": str(item.get("mode") or "pacansky"),
                "limit": int(item.get("limit") or 7),
                "name": item.get("name") or item.get("bossName"),
                "enabled": True,
            }
        if isinstance(item, (int, str)) and str(item).strip().isdigit():
            return {
                "bossId": int(item),
                "mode": "pacansky",
                "limit": 7,
                "name": None,
                "enabled": True,
            }
        return None

    async def _fetch_bootstrap_ready(self) -> Dict[str, Any]:
        """Получает bootstrap; при промежуточном статусе 'reward_processing' ждёт и повторяет запрос."""
        bootstrap = await self.api.get_bootstrap()
        for _ in range(3):
            if not isinstance(bootstrap, dict):
                break
            state = str(bootstrap.get("state") or "").lower()
            if state != "reward_processing":
                break
            retry_ms = int(bootstrap.get("retryAfterMs") or 1000)
            wait_sec = min(2.5, max(0.2, retry_ms / 1000.0)) if self.enable_jitter else 0.01
            await asyncio.sleep(wait_sec)
            bootstrap = await self.api.get_bootstrap()
        return bootstrap if isinstance(bootstrap, dict) else {}

    async def _fetch_prisons_safe(self) -> Optional[Any]:
        from client.api.prison import fetch_enriched_prisons_list
        from core.state_hub import state_hub

        entry = state_hub.get_slice(self.account_id, "prisons", max_age_seconds=90.0)
        dom = state_hub.get_domain_state(self.account_id, "prisons")
        if entry is not None and not dom.dirty and isinstance(entry.data, dict):
            pr_list = entry.data.get("prisons") or []
            if any(isinstance(p, dict) and "dayRuns" in p for p in pr_list):
                return entry.data

        if not self.prison_api:
            return entry.data if (entry and isinstance(entry.data, dict)) else None
        try:
            enriched = await fetch_enriched_prisons_list(self.prison_api)
            if enriched:
                cur_data = dict(entry.data) if (entry and isinstance(entry.data, dict)) else {"success": True}
                cur_data["prisons"] = enriched
                state_hub.set_domain_data(self.account_id, "prisons", cur_data)
                state_hub.update_slice(self.account_id, "prisons", cur_data)
                return cur_data
            return await self.prison_api.get_all_prisons()
        except Exception as e:
            logger.debug(f"Не удалось загрузить prisons_data для оценки боссов: {e}")
            return entry.data if (entry and isinstance(entry.data, dict)) else None

    async def _fetch_evaluated_bosses(
        self,
        bootstrap: Dict[str, Any],
        prisons_data: Optional[Any],
    ) -> Dict[int, Dict[str, Any]]:
        """
        Собирает актуальный список боссов (API + каталог), оценивает доступность и сохраняет
        серверные флаги isLocked / unlockReason, если API явно пометил босса заблокированным.
        """
        base_catalog = _load_bosses_catalog() or FALLBACK_BOSSES
        by_id: Dict[int, Dict[str, Any]] = {int(b["id"]): dict(b) for b in base_catalog}

        try:
            api_bosses = await self.api.get_all_bosses()
            if isinstance(api_bosses, list) and api_bosses:
                for ab in api_bosses:
                    if not isinstance(ab, dict) or ab.get("id") is None:
                        continue
                    bid = int(ab["id"])
                    merged = dict(by_id.get(bid, {}))
                    merged.update(ab)
                    # Сохраняем явную блокировку из ответа API/мока, чтобы evaluate не затёр её
                    if ab.get("isLocked") is True:
                        merged["_explicitLocked"] = True
                        merged["_explicitUnlockReason"] = ab.get("unlockReason")
                    by_id[bid] = merged
        except Exception as e:
            logger.debug(f"Fallback на локальный каталог боссов (get_all_bosses={e})")

        eval_list = list(by_id.values())
        BossAPI.evaluate_bosses_availability(eval_list, bootstrap=bootstrap, prisons_data=prisons_data)

        for b in eval_list:
            if b.pop("_explicitLocked", False):
                b["isLocked"] = True
                b["canAttack"] = False
                if b.get("_explicitUnlockReason"):
                    b["unlockReason"] = b.pop("_explicitUnlockReason")
                    b["attackBlockReason"] = b["unlockReason"]

        return {int(b["id"]): b for b in eval_list}

    async def record_friends_damage(
        self,
        bootstrap: Dict[str, Any],
        boss_session_id: Optional[str] = None,
        boss_id: Optional[int] = None,
    ) -> int:
        """
        Сбор и дедуплицированная запись реального урона друзей по boss_session_id
        в BossFriendDamageLog и обновление FriendStats.
        """
        if not self.db_engine:
            return 0

        _, session_data = self._extract_battle(bootstrap)
        session_data = session_data or {}
        sess_id = (
            boss_session_id
            or session_data.get("sessionId")
            or session_data.get("id")
            or bootstrap.get("sessionId")
            or bootstrap.get("claimId")
        )
        if not sess_id:
            b_id = boss_id or session_data.get("bossId") or bootstrap.get("bossId") or 0
            t_start = session_data.get("startedAt") or bootstrap.get("generatedAt") or ""
            sess_id = f"{b_id}:{t_start}" if t_start else None

        if not sess_id:
            return 0

        b_id_int = boss_id or session_data.get("bossId") or bootstrap.get("bossId")
        try:
            b_id_int = int(b_id_int) if b_id_int is not None else None
        except (ValueError, TypeError):
            b_id_int = None

        friend_damage_items: List[Dict[str, Any]] = []

        try:
            fd_res = await self.api.get_friend_damage()
            if isinstance(fd_res, dict):
                items = fd_res.get("items") or fd_res.get("damage") or []
                if isinstance(items, list):
                    friend_damage_items.extend(items)
            elif isinstance(fd_res, list):
                friend_damage_items.extend(fd_res)
        except Exception as e:
            logger.debug(f"Не удалось получить friend_damage от API: {e}")

        reward_data = bootstrap.get("reward") or {}
        fd_obj = bootstrap.get("friendDamage") if isinstance(bootstrap.get("friendDamage"), dict) else {}
        top_dmg = (
            fd_obj.get("items")
            or reward_data.get("topDamage")
            or bootstrap.get("topDamage")
            or bootstrap.get("friendDamageItems")
            or []
        )
        if isinstance(top_dmg, list):
            friend_damage_items.extend(top_dmg)

        if not friend_damage_items:
            return 0

        user_damage_map: Dict[int, Dict[str, Any]] = {}
        for item in friend_damage_items:
            if not isinstance(item, dict):
                continue
            uid = item.get("userId") or item.get("id")
            if not uid:
                continue
            try:
                uid_int = int(uid)
            except (ValueError, TypeError):
                continue

            dmg = int(item.get("damage") or item.get("totalDamage") or item.get("recordedDamage") or 0)
            if dmg <= 0:
                continue

            existing = user_damage_map.get(uid_int)
            if existing is None or dmg > existing["damage"]:
                user_damage_map[uid_int] = {
                    "damage": dmg,
                    "nickname": item.get("nickname") or item.get("name"),
                    "photoUrl": item.get("photoUrl") or item.get("avatarUrl"),
                }

        if not user_damage_map:
            return 0

        now = datetime.utcnow()
        updated_friends = 0

        try:
            async with get_session(self.db_engine) as session:
                for uid_int, data in user_damage_map.items():
                    current_dmg = data["damage"]
                    nick = data["nickname"]
                    photo = data["photoUrl"]

                    stmt_log = select(BossFriendDamageLog).where(
                        BossFriendDamageLog.account_id == self.account_id,
                        BossFriendDamageLog.boss_session_id == str(sess_id),
                        BossFriendDamageLog.user_id == uid_int,
                    )
                    log_entry = (await session.execute(stmt_log)).scalar_one_or_none()

                    delta = 0
                    is_new_hit = False

                    if not log_entry:
                        is_new_hit = True
                        delta = current_dmg
                        log_entry = BossFriendDamageLog(
                            account_id=self.account_id,
                            boss_session_id=str(sess_id),
                            boss_id=b_id_int,
                            user_id=uid_int,
                            recorded_damage=current_dmg,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(log_entry)
                    else:
                        delta = max(0, current_dmg - int(log_entry.recorded_damage or 0))
                        if delta > 0:
                            log_entry.recorded_damage = current_dmg
                            log_entry.updated_at = now

                    stmt_fs = select(FriendStats).where(
                        FriendStats.account_id == self.account_id,
                        FriendStats.user_id == uid_int,
                    )
                    f_stat = (await session.execute(stmt_fs)).scalar_one_or_none()

                    if not f_stat:
                        f_stat = FriendStats(
                            account_id=self.account_id,
                            user_id=uid_int,
                            nickname=nick or f"Игрок {uid_int}",
                            photo_url=photo,
                            total_damage_to_my_bosses=delta,
                            boss_hits_count=1 if is_new_hit else 0,
                            last_boss_hit_at=now if delta > 0 or is_new_hit else None,
                            last_active_at=now,
                            is_whitelisted=False,
                            is_current_friend=True,
                            first_seen_at=now,
                            updated_at=now,
                        )
                        session.add(f_stat)
                    else:
                        if nick and (not f_stat.nickname or f_stat.nickname.startswith("Игрок")):
                            f_stat.nickname = nick
                        if photo:
                            f_stat.photo_url = photo
                        if is_new_hit:
                            f_stat.boss_hits_count = int(f_stat.boss_hits_count or 0) + 1
                        if delta > 0:
                            f_stat.total_damage_to_my_bosses = int(f_stat.total_damage_to_my_bosses or 0) + delta
                            f_stat.last_boss_hit_at = now
                            f_stat.last_active_at = now
                        f_stat.updated_at = now

                    updated_friends += 1

                await session.commit()
        except Exception as e:
            logger.warning(f"Ошибка записи урона друзей по боссу: {e}")

        return updated_friends

    @staticmethod
    def _resolve_boss_name(battle: Optional[Dict[str, Any]], bootstrap: Optional[Dict[str, Any]] = None, fallback_id: Any = None) -> str:
        b = battle if isinstance(battle, dict) else {}
        bs = bootstrap if isinstance(bootstrap, dict) else {}
        for k in ("bossName", "title", "name"):
            v = b.get(k) or bs.get(k)
            if v and str(v).strip() and str(v).strip().lower() != "босс":
                return str(v).strip()
        bid = b.get("bossId") or bs.get("bossId") or fallback_id
        if bid is not None:
            for item in (_load_bosses_catalog() or FALLBACK_BOSSES):
                if str(item.get("id")) == str(bid):
                    nm = item.get("name") or item.get("title")
                    if nm:
                        return str(nm)
            return f"Босс #{bid}"
        return "Босс"

    @staticmethod
    def _count_total_steps(items: Any) -> int:
        if not isinstance(items, list):
            return 0
        total = 0
        for it in items:
            if isinstance(it, dict):
                total += max(1, int(it.get("count") or 1))
        return total

    async def _publish_presets_slice(self) -> None:
        """Публикует актуальное состояние BossPreset в LiveStateHub (срез presets)."""
        if not self.state_hub or not self.db_engine:
            return
        try:
            async with get_session(self.db_engine) as db_sess:
                stmt = select(BossPreset).where(BossPreset.account_id == self.account_id).order_by(BossPreset.id.asc())
                rows = (await db_sess.execute(stmt)).scalars().all()
            serialized = []
            active_run = None
            for p in rows:
                t_steps = self._count_total_steps(p.items)
                p_dict = {
                    "id": p.id,
                    "name": p.name,
                    "items": p.items or [],
                    "totalSteps": t_steps,
                    "daily_enabled": bool(p.daily_enabled),
                    "schedule_time_msk": p.schedule_time_msk,
                    "last_run_date_msk": p.last_run_date_msk,
                    "is_running": bool(p.is_running),
                    "current_step_index": p.current_step_index,
                    "last_status": p.last_status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                serialized.append(p_dict)
                if p.is_running and active_run is None:
                    active_run = p
            if active_run is not None:
                self.state_hub.set_preset_state(
                    self.account_id,
                    active_run.id,
                    current_step=active_run.current_step_index,
                    total_steps=self._count_total_steps(active_run.items),
                    status="running",
                    presets_list=serialized,
                )
            else:
                self.state_hub.set_preset_state(
                    self.account_id,
                    None,
                    status="idle",
                    presets_list=serialized,
                )
        except Exception as e:
            logger.debug(f"Could not publish presets slice: {e}")

    async def on_boss_fight_finished(
        self,
        fight_result: Dict[str, Any],
        active_preset: Optional[BossPreset] = None,
        preset_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[BossPreset]:
        """
        Обработчик завершения боя с боссом (victory | defeat):
        - На поражении логирует уведомление с остатком HP и останавливает активный пресет.
        - На победе продвигает шаг пресета или завершает его с is_running=False.
        """
        outcome = str((fight_result or {}).get("outcome") or "victory").lower()
        boss_name = str((fight_result or {}).get("bossName") or "Босс")
        mode = (fight_result or {}).get("mode")

        if outcome == "defeat":
            snap = await self._load_live_battle_snapshot()
            resolved_hp = resolve_defeat_boss_hp(
                server_payload=fight_result,
                battle=fight_result,
                snapshot=snap,
                boss_id=(fight_result or {}).get("bossId") or self._last_active_boss_id,
                boss_name=boss_name,
                mode=mode,
            )
            rem_hp = resolved_hp["remaining_hp"]
            max_hp = resolved_hp["max_hp"]
            session_id = (fight_result or {}).get("sessionId") or (snap or {}).get("session_id") or f"{boss_name}:{rem_hp or 'unknown'}"
            if self.db_engine:
                parsed = DropParser.parse_boss_defeat(
                    boss_name=boss_name,
                    mode=mode,
                    remaining_hp=rem_hp,
                    max_hp=max_hp,
                    hp_percent=resolved_hp["hp_percent"],
                    hp_known=resolved_hp["hp_known"],
                    personal_damage=resolved_hp.get("personal_damage"),
                )
                parsed["event_key"] = f"boss_defeat_{session_id}"
                await DropParser.save_notification(self.account_id, parsed, self.db_engine)
            await self._clear_live_battle_snapshot()

            if active_preset and self.db_engine:
                total = len(preset_steps or []) or self._count_total_steps(active_preset.items)
                step_num = min(total or 1, int(active_preset.current_step_index or 0) + 1)
                async with get_session(self.db_engine) as db_sess:
                    p_obj = await db_sess.get(BossPreset, active_preset.id)
                    if p_obj and p_obj.is_running:
                        p_obj.is_running = False
                        p_obj.last_status = f"Остановлен (поражение: {boss_name}, шаг {step_num}/{total})"
                        db_sess.add(p_obj)
                        await db_sess.commit()
                await self._log_action(
                    "boss_preset_stopped_defeat",
                    "/api/v1/boss/presets",
                    200,
                    False,
                    {"preset_id": active_preset.id, "boss_name": boss_name, "remaining_hp": rem_hp},
                )
                await self._publish_presets_slice()
            return None

        # Victory outcome when called explicitly
        if active_preset and preset_steps is not None:
            return await self._advance_preset_step(active_preset.id, preset_steps)
        return active_preset

    async def trigger_auto_melee(
        self,
        bootstrap: Optional[Dict[str, Any]] = None,
        config: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Выполняет все готовые (не на перезарядке) бесплатные рукопашные удары в активном бою
        и синхронизирует состояние кулдаунов в LiveStateHub.
        """
        results: Dict[str, Any] = {
            "hits_performed": [],
            "rewards_claimed": 0,
            "killed": False,
            "boss_hp_remaining": None,
            "next_melee_ready_at": None,
            "next_melee_wait_sec": None,
            "errors": [],
        }
        try:
            if bootstrap is None:
                bootstrap = await self._fetch_bootstrap_ready()
            state, battle = self._extract_battle(bootstrap)
            current_hp = battle.get("currentHp") if battle else None
            if state not in ("active", "in_progress") or battle is None or current_hp is None or int(current_hp) <= 0:
                return results
            results["boss_hp_remaining"] = current_hp

            weapons_data = await self.api.get_weapons()
        except Exception as e:
            logger.warning(f"trigger_auto_melee: ошибка чтения состояния боя/оружия: {e}")
            results["errors"].append(str(e))
            return results

        equipped_slots = weapons_data.get("equippedSlots") or []
        equipped_types = {
            (slot_item.get("type") if isinstance(slot_item, dict) else str(slot_item))
            for slot_item in equipped_slots
            if slot_item
        }
        weapon_stats_effective = bootstrap.get("weaponStatsEffective") or {}
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()

        available_melee = [w for w in MELEE_CONFIG if w in equipped_types] if equipped_types else list(MELEE_CONFIG.keys())
        ready_hits: List[str] = []
        earliest_ready_dt: Optional[datetime] = None
        for w in available_melee:
            cfg = MELEE_CONFIG[w]
            last_raw = weapons_data.get(cfg["last_time_key"])
            last_dt = parse_iso_utc(last_raw)
            cooldown_sec = float(weapon_stats_effective.get(cfg["cooldown_key"], cfg["default_cooldown"]))
            if last_dt is None or now_utc >= (last_dt + timedelta(seconds=cooldown_sec)):
                self.melee_ready_at[w] = 0.0
                ready_hits.append(w)
                logger.info(f"Авто-рукопашка: удар {w} ГОТОВ (last={last_raw}, cd={cooldown_sec}s)")
            else:
                ready_dt = last_dt + timedelta(seconds=cooldown_sec)
                self.melee_ready_at[w] = ready_dt.timestamp()
                rem_sec = max(0.0, (ready_dt - now_utc).total_seconds())
                logger.info(f"Авто-рукопашка: удар {w} на КД (осталось {rem_sec:.1f}s)")
                if earliest_ready_dt is None or ready_dt < earliest_ready_dt:
                    earliest_ready_dt = ready_dt

        if not ready_hits:
            if earliest_ready_dt is not None:
                wait_sec = max(1.0, (earliest_ready_dt - now_utc).total_seconds() + 0.5)
                results["next_melee_ready_at"] = earliest_ready_dt.isoformat()
                results["next_melee_wait_sec"] = wait_sec
                if self.on_melee_reschedule is not None and not getattr(config, "is_paused", False):
                    if config is None or getattr(config, "boss_auto_melee", False) or getattr(config, "auto_boss_enabled", False):
                        try:
                            self.on_melee_reschedule(wait_sec)
                        except Exception:
                            pass
            return results

        now_iso = datetime.now(timezone.utc).isoformat()
        for weapon_name in ready_hits:
            try:
                logger.info(f"Нанесение авто-рукопашного удара {weapon_name} по боссу...")
                hit_res = await self.api.hit_boss(weapon_name, count=1)
                new_hp = hit_res.get("currentHp")
                if new_hp is not None:
                    results["boss_hp_remaining"] = new_hp
                    if int(new_hp) > 0:
                        await self._save_live_battle_snapshot(battle, override_hp=int(new_hp))
                results["hits_performed"].append({"weapon": weapon_name, "response": hit_res})
                await self._log_action(
                    "boss_melee_hit",
                    "/api/boss/use-weapon",
                    200,
                    True,
                    {"weapon": weapon_name, "response": hit_res},
                )
                # Обновим локальную метку времени последнего удара для state_hub и melee_ready_at
                last_key = MELEE_CONFIG[weapon_name]["last_time_key"]
                weapons_data[last_key] = now_iso
                cd_sec = float(weapon_stats_effective.get(MELEE_CONFIG[weapon_name]["cooldown_key"], MELEE_CONFIG[weapon_name]["default_cooldown"]))
                self.melee_ready_at[weapon_name] = datetime.now(timezone.utc).timestamp() + cd_sec

                hit_state = str(hit_res.get("state") or "").lower()
                if (new_hp is not None and int(new_hp) <= 0) or hit_res.get("bossDefeated") or hit_state in ("reward", "reward_processing"):
                    results["killed"] = True
                    if hit_res.get("claimId"):
                        try:
                            before_prof = await self._fetch_profile_snapshot_safe()
                            claim_res = await self._claim_reward_with_retry(str(hit_res["claimId"]))
                            if not self._is_claim_not_ready(claim_res):
                                after_prof = await self._fetch_profile_snapshot_safe() if before_prof else None
                                results["rewards_claimed"] += 1
                                results["claim_id"] = str(hit_res["claimId"])
                                results["claim_response"] = claim_res
                                results["claim_before_profile"] = before_prof
                                results["claim_after_profile"] = after_prof
                        except Exception:
                            pass
                    break
                await self._jitter()
            except httpx.HTTPStatusError as err:
                err_text = err.response.text
                status_code = err.response.status_code
                logger.warning(f"Сервер отклонил авто-удар {weapon_name} (HTTP {status_code}): {err_text}")
                results["errors"].append(f"hit_{weapon_name} (HTTP {status_code}): {err_text}")
                await self._log_action(
                    "boss_melee_hit",
                    "/api/boss/use-weapon",
                    status_code,
                    False,
                    {"weapon": weapon_name, "error": err_text},
                )
            except Exception as e:
                logger.error(f"Ошибка при авто-ударе {weapon_name}: {e}")
                results["errors"].append(f"hit_{weapon_name}: {str(e)}")
                await self._log_action(
                    "boss_melee_hit",
                    "/api/boss/use-weapon",
                    500,
                    False,
                    {"weapon": weapon_name, "error": str(e)},
                )

        if self.state_hub and results["hits_performed"]:
            boss_entry = self.state_hub.get_slice(self.account_id, "boss")
            if boss_entry and isinstance(boss_entry.data, dict):
                patched = dict(boss_entry.data)
                ts_map = dict(patched.get("meleeTimestamps") or {})
                for hit in results["hits_performed"]:
                    ts_map[MELEE_CONFIG[hit["weapon"]]["last_time_key"]] = now_iso
                patched["meleeTimestamps"] = ts_map
                if results["boss_hp_remaining"] is not None and isinstance(patched.get("session"), dict):
                    sess_copy = dict(patched["session"])
                    sess_copy["currentHp"] = results["boss_hp_remaining"]
                    patched["session"] = sess_copy
                self.state_hub.update_slice(self.account_id, "boss", patched)

        if (
            not results["killed"]
            and results["boss_hp_remaining"] is not None
            and int(results["boss_hp_remaining"]) > 0
            and available_melee
        ):
            after_utc = datetime.now(timezone.utc)
            next_dt: Optional[datetime] = None
            for w in available_melee:
                cfg = MELEE_CONFIG[w]
                last_dt = parse_iso_utc(weapons_data.get(cfg["last_time_key"]))
                cooldown_sec = float(weapon_stats_effective.get(cfg["cooldown_key"], cfg["default_cooldown"]))
                if last_dt is not None:
                    cand = last_dt + timedelta(seconds=cooldown_sec)
                    if next_dt is None or cand < next_dt:
                        next_dt = cand
            if next_dt is not None:
                wait_sec = max(1.0, (next_dt - after_utc).total_seconds() + 0.5)
                results["next_melee_ready_at"] = next_dt.isoformat()
                results["next_melee_wait_sec"] = wait_sec
                if self.on_melee_reschedule is not None and not getattr(config, "is_paused", False):
                    if config is None or getattr(config, "boss_auto_melee", False) or getattr(config, "auto_boss_enabled", False):
                        try:
                            self.on_melee_reschedule(wait_sec)
                        except Exception:
                            pass

        return results

    execute_ready_melee_hits = trigger_auto_melee

    async def _load_active_preset(self) -> Tuple[Optional[BossPreset], List[Dict[str, Any]]]:
        """Загружает запущенный BossPreset и разворачивает его шаги."""
        if not self.db_engine:
            return None, []

        active_preset: Optional[BossPreset] = None
        preset_steps: List[Dict[str, Any]] = []
        try:
            async with get_session(self.db_engine) as db_sess:
                stmt_act = select(BossPreset).where(
                    BossPreset.account_id == self.account_id,
                    BossPreset.is_running == True,
                )
                active_preset = (await db_sess.execute(stmt_act)).scalar_one_or_none()
                if active_preset and active_preset.items:
                    b_cat = _load_bosses_catalog() or FALLBACK_BOSSES
                    names_map = {b["id"]: b.get("name") for b in b_cat}
                    for itm in active_preset.items:
                        if not isinstance(itm, dict):
                            continue
                        cnt = max(1, int(itm.get("count") or 1))
                        b_id = itm.get("bossId") if itm.get("bossId") is not None else itm.get("boss_id")
                        if not b_id:
                            continue
                        b_id_int = int(b_id)
                        b_name = itm.get("bossName") or itm.get("name") or names_map.get(b_id_int) or f"Босс #{b_id}"
                        b_mode = itm.get("mode") or "pacansky"
                        for _ in range(cnt):
                            preset_steps.append({"bossId": b_id_int, "bossName": b_name, "mode": b_mode})
        except Exception as e:
            logger.warning(f"Ошибка чтения активного пресета: {e}")
            return None, []

        if active_preset and (not preset_steps or active_preset.current_step_index >= len(preset_steps)):
            async with get_session(self.db_engine) as db_sess:
                p_obj = await db_sess.get(BossPreset, active_preset.id)
                if p_obj:
                    p_obj.is_running = False
                    p_obj.last_status = f"Выполнен ({len(preset_steps)}/{len(preset_steps)})"
                    db_sess.add(p_obj)
                    await db_sess.commit()
            logger.info(f"Пресет '{active_preset.name}' успешно выполнен!")
            await self._log_action(
                "boss_preset_completed",
                "/api/v1/boss/presets",
                200,
                True,
                {"preset_id": active_preset.id, "name": active_preset.name, "total_steps": len(preset_steps)},
            )
            await self._publish_presets_slice()
            return None, []

        return active_preset, preset_steps

    async def _advance_preset_step(
        self,
        preset_id: int,
        preset_steps: List[Dict[str, Any]],
        status_note: Optional[str] = None,
    ) -> Optional[BossPreset]:
        if not self.db_engine:
            return None
        async with get_session(self.db_engine) as db_sess:
            p_obj = await db_sess.get(BossPreset, preset_id)
            if not p_obj:
                return None
            p_obj.current_step_index += 1
            if p_obj.current_step_index >= len(preset_steps):
                p_obj.is_running = False
                p_obj.last_status = status_note or f"Выполнен ({len(preset_steps)}/{len(preset_steps)})"
            elif status_note:
                p_obj.last_status = status_note
            else:
                nxt = preset_steps[p_obj.current_step_index]
                p_obj.last_status = f"Выполняется: шаг {p_obj.current_step_index + 1}/{len(preset_steps)} ({nxt['bossName']})"
            db_sess.add(p_obj)
            await db_sess.commit()
            await db_sess.refresh(p_obj)
            res = p_obj if p_obj.is_running else None
        await self._publish_presets_slice()
        return res

    async def check_scheduled_presets(self, now_utc: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Проверка и запуск сохраненных пресетов боссов по расписанию МСК (UTC+3).
        """
        if self.is_paused or server_health_monitor.is_maintenance:
            return None

        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config) or is_night_mode_active(config):
            return None

        now_utc_dt = now_utc or datetime.now(timezone.utc)
        now_msk = now_utc_dt + timedelta(hours=3)
        today_msk = now_msk.strftime("%Y-%m-%d")
        hhmm_msk = now_msk.strftime("%H:%M")

        if not self.db_engine:
            return None

        async with get_session(self.db_engine) as session:
            stmt_running = select(BossPreset).where(
                BossPreset.account_id == self.account_id,
                BossPreset.is_running == True,
            )
            if (await session.execute(stmt_running)).scalar_one_or_none() is not None:
                return None

            stmt = (
                select(BossPreset)
                .where(
                    BossPreset.account_id == self.account_id,
                    BossPreset.daily_enabled == True,
                )
                .order_by(BossPreset.schedule_time_msk.asc())
            )
            presets = (await session.execute(stmt)).scalars().all()

            target_preset: Optional[BossPreset] = None
            for p in presets:
                if not p.items or len(p.items) == 0:
                    continue
                if p.last_run_date_msk == today_msk:
                    continue
                if p.schedule_time_msk <= hhmm_msk:
                    target_preset = p
                    break

            if not target_preset:
                return None

            target_preset.is_running = True
            target_preset.current_step_index = 0
            target_preset.last_run_date_msk = today_msk
            target_preset.last_status = f"Запущен по расписанию ({hhmm_msk} МСК)"
            session.add(target_preset)
            await session.commit()
            preset_id = target_preset.id
            preset_name = target_preset.name

        logger.info(f"Пресет '{preset_name}' (ID={preset_id}) запущен по расписанию МСК ({hhmm_msk}).")
        await self._log_action(
            "boss_preset_schedule_start",
            "/api/v1/boss/presets",
            200,
            True,
            {"preset_id": preset_id, "name": preset_name, "time_msk": hhmm_msk, "date_msk": today_msk},
        )
        res_cycle = await self.run_cycle()
        if isinstance(res_cycle, dict):
            res_cycle["preset_id"] = preset_id
        return res_cycle

    async def _claim_pending_rewards(
        self,
        bootstrap: Dict[str, Any],
        results: Dict[str, Any],
        active_preset: Optional[BossPreset],
        preset_steps: List[Dict[str, Any]],
        claimed_keys_in_cycle: Set[str],
    ) -> Tuple[int, Optional[BossPreset]]:
        """Проверяет и забирает все доступные награды за боссов, возвращая количество собранных наград."""
        state, battle = self._extract_battle(bootstrap)
        battle = battle or {}
        has_reward = bool(
            bootstrap.get("hasReward")
            or battle.get("hasReward")
            or battle.get("rewardAvailable")
            or state == "reward"
            or (battle.get("currentHp") is not None and int(battle.get("currentHp", 1)) <= 0 and battle.get("claimId"))
        )
        unclaimed = bootstrap.get("unclaimedRewards") or []
        claim_ids: List[Optional[str]] = []

        if isinstance(unclaimed, list) and len(unclaimed) > 0:
            for item in unclaimed:
                if isinstance(item, dict):
                    raw_cid = item.get("claimId") or item.get("id")
                    if raw_cid is not None and str(raw_cid).strip():
                        claim_ids.append(str(raw_cid))
                elif item is not None and str(item).strip():
                    claim_ids.append(str(item))
        elif has_reward:
            cid = bootstrap.get("claimId") or battle.get("claimId") or (bootstrap.get("reward") or {}).get("claimId")
            claim_ids.append(str(cid) if cid else None)

        claimed_here = 0
        for cid in claim_ids:
            dedup_key = f"cid:{cid}" if cid else "__latest__"
            if dedup_key in claimed_keys_in_cycle:
                continue
            try:
                await self.record_friends_damage(bootstrap, boss_session_id=cid)
                before_prof = await self._fetch_profile_snapshot_safe()
                logger.info(f"Сбор награды за босса (claimId={cid})...")
                claim_res = await self._claim_reward_with_retry(cid)
                logger.info(f"Сырой ответ claim_reward (cid={cid}): {str(claim_res)[:500]}")
                if self._is_claim_not_ready(claim_res):
                    logger.info(f"Награда за босса (claimId={cid}) еще финализируется сервером (not_ready), повторим на следующем тике.")
                    continue
                claimed_keys_in_cycle.add(dedup_key)

                resolved_boss_name = self._resolve_boss_name(
                    battle,
                    bootstrap,
                    fallback_id=self._last_active_boss_id,
                )
                if resolved_boss_name == "Босс" and self._last_active_boss_name:
                    resolved_boss_name = self._last_active_boss_name
                resolved_mode = (battle.get("mode") if isinstance(battle, dict) else None) or self._last_active_boss_mode
                last_hp = battle.get("currentHp") if isinstance(battle, dict) else None
                b_sess_id = (battle.get("sessionId") if isinstance(battle, dict) else None) or cid or "latest"

                parsed = DropParser.parse_boss_claim(
                    claim_res if isinstance(claim_res, dict) else {},
                    boss_name=resolved_boss_name,
                    mode=resolved_mode,
                )
                outcome = self.classify_boss_outcome(
                    claim_res,
                    last_hp=last_hp,
                    battle=battle,
                    parsed=parsed,
                )
                if outcome == "victory" and before_prof is not None:
                    after_prof = await self._fetch_profile_snapshot_safe()
                    self._merge_profile_delta_rewards(parsed, before_prof, after_prof)
                    if not (parsed.get("rewards") or parsed.get("drops")):
                        await asyncio.sleep(1.5 if self.enable_jitter else 0.02)
                        after_prof_retry = await self._fetch_profile_snapshot_safe()
                        self._merge_profile_delta_rewards(parsed, before_prof, after_prof_retry)

                if outcome == "victory" and not (parsed.get("rewards") or parsed.get("drops")):
                    logger.warning(
                        f"Победа над {resolved_boss_name}, но награды пустые после парсинга и дельты! claim_res={str(claim_res)[:600]}"
                    )
                    self._apply_catalog_fallback_rewards(
                        parsed,
                        boss_id=(battle.get("bossId") if isinstance(battle, dict) else None) or self._last_active_boss_id,
                        boss_name=resolved_boss_name,
                        mode=resolved_mode,
                    )

                logger.info(
                    f"Итог боя с боссом '{resolved_boss_name}': outcome={outcome}, "
                    f"rewards={parsed.get('rewards')}, drops={parsed.get('drops')}"
                )
                await self._log_action("claim_boss_reward", "/api/boss/claim", 200, outcome == "victory", {
                    "outcome": outcome,
                    "claim_res": claim_res,
                })

                if outcome == "defeat":
                    snap = await self._load_live_battle_snapshot()
                    b_id = (battle.get("bossId") if isinstance(battle, dict) else None) or self._last_active_boss_id
                    claim_rw_dict = claim_res.get("rewards") if isinstance(claim_res, dict) and isinstance(claim_res.get("rewards"), dict) else None
                    resolved_hp = resolve_defeat_boss_hp(
                        server_payload=claim_rw_dict or (claim_res if isinstance(claim_res, dict) else None),
                        battle=battle if isinstance(battle, dict) else None,
                        snapshot=snap,
                        boss_id=b_id,
                        boss_name=resolved_boss_name,
                        mode=resolved_mode,
                    )
                    rem_hp = resolved_hp["remaining_hp"]
                    max_hp = resolved_hp["max_hp"]
                    defeat_reason = (
                        (claim_res.get("message") if isinstance(claim_res, dict) else None)
                        or "Время боя вышло, босс не повержен"
                    )
                    defeat_key = f"boss_defeat_{b_sess_id}"
                    defeat_parsed = DropParser.parse_boss_defeat(
                        boss_name=resolved_boss_name,
                        mode=resolved_mode,
                        remaining_hp=rem_hp,
                        max_hp=max_hp,
                        reason=defeat_reason,
                        hp_percent=resolved_hp["hp_percent"],
                        hp_known=resolved_hp["hp_known"],
                        personal_damage=resolved_hp.get("personal_damage"),
                    )
                    defeat_parsed["event_key"] = defeat_key
                    await DropParser.save_notification(self.account_id, defeat_parsed, self.db_engine)
                    if defeat_key not in self._notified_victory_keys:
                        self._notified_victory_keys.add(defeat_key)
                        results.setdefault("defeats", []).append({
                            "boss_name": resolved_boss_name,
                            "mode": resolved_mode,
                            "remaining_hp": rem_hp,
                            "max_hp": max_hp,
                            "hp_percent": resolved_hp["hp_percent"],
                            "hp_known": resolved_hp["hp_known"],
                            "personal_damage": resolved_hp.get("personal_damage"),
                            "reason": defeat_reason,
                            "event_key": defeat_key,
                        })
                    if active_preset:
                        active_preset = await self.on_boss_fight_finished(
                            {
                                "outcome": "defeat",
                                "bossId": b_id,
                                "bossName": resolved_boss_name,
                                "mode": resolved_mode,
                                "remainingHp": rem_hp,
                                "maxHp": max_hp,
                                "personalDamage": resolved_hp.get("personal_damage"),
                                "sessionId": b_sess_id,
                            },
                            active_preset=active_preset,
                            preset_steps=preset_steps,
                        )
                    await self._clear_live_battle_snapshot()
                else:
                    claimed_here += 1
                    results["rewards_claimed"] += 1
                    dur_sec, dur_fmt = self._resolve_battle_duration(battle, b_sess_id)
                    meta_j = parsed.setdefault("meta_json", {})
                    meta_j["duration_sec"] = dur_sec
                    meta_j["duration_formatted"] = dur_fmt
                    event_key = f"boss_claim_{b_sess_id}"
                    parsed["event_key"] = event_key
                    await DropParser.save_notification(self.account_id, parsed, self.db_engine)
                    await self._clear_live_battle_snapshot()
                    if event_key not in self._notified_victory_keys:
                        self._notified_victory_keys.add(event_key)
                        results.setdefault("victories", []).append({
                            "boss_name": meta_j.get("boss_name") or parsed.get("meta", {}).get("boss_name") or resolved_boss_name,
                            "mode": resolved_mode,
                            "rewards": parsed.get("rewards") or [],
                            "drops": parsed.get("drops") or [],
                            "duration_sec": dur_sec,
                            "duration_formatted": dur_fmt,
                            "event_key": event_key,
                        })

                    if active_preset:
                        active_preset = await self._advance_preset_step(active_preset.id, preset_steps)

                try:
                    from core.state_hub import state_hub
                    ev_type = "boss_finished" if outcome == "victory" else "boss_claimed"
                    state_hub.notify_mutation(
                        self.account_id,
                        ev_type,
                        payload={"boss": {"outcome": outcome}},
                        reason=f"boss_{outcome}",
                        extra_domains=["profile", "talents", "notifications"],
                    )
                except Exception:
                    pass

                await self._jitter()
            except Exception as e:
                err_low = str(e).lower()
                if any(m in err_low for m in ("не побежден", "время вышло", "пораж", "defeat", "not defeated")):
                    resolved_boss_name = self._resolve_boss_name(battle, bootstrap, fallback_id=self._last_active_boss_id)
                    if resolved_boss_name == "Босс" and self._last_active_boss_name:
                        resolved_boss_name = self._last_active_boss_name
                    resolved_mode = (battle.get("mode") if isinstance(battle, dict) else None) or self._last_active_boss_mode
                    b_id = (battle.get("bossId") if isinstance(battle, dict) else None) or self._last_active_boss_id
                    b_sess_id = (battle.get("sessionId") if isinstance(battle, dict) else None) or cid or "latest"
                    snap = await self._load_live_battle_snapshot()
                    resolved_hp = resolve_defeat_boss_hp(
                        battle=battle if isinstance(battle, dict) else None,
                        snapshot=snap,
                        boss_id=b_id,
                        boss_name=resolved_boss_name,
                        mode=resolved_mode,
                    )
                    rem_hp = resolved_hp["remaining_hp"]
                    max_hp = resolved_hp["max_hp"]
                    defeat_key = f"boss_defeat_{b_sess_id}"
                    defeat_parsed = DropParser.parse_boss_defeat(
                        boss_name=resolved_boss_name,
                        mode=resolved_mode,
                        remaining_hp=rem_hp,
                        max_hp=max_hp,
                        reason="Время боя вышло, босс не повержен",
                        hp_percent=resolved_hp["hp_percent"],
                        hp_known=resolved_hp["hp_known"],
                        personal_damage=resolved_hp.get("personal_damage"),
                    )
                    defeat_parsed["event_key"] = defeat_key
                    await DropParser.save_notification(self.account_id, defeat_parsed, self.db_engine)
                    if defeat_key not in self._notified_victory_keys:
                        self._notified_victory_keys.add(defeat_key)
                        results.setdefault("defeats", []).append({
                            "boss_name": resolved_boss_name,
                            "mode": resolved_mode,
                            "remaining_hp": rem_hp,
                            "max_hp": max_hp,
                            "hp_percent": resolved_hp["hp_percent"],
                            "hp_known": resolved_hp["hp_known"],
                            "personal_damage": resolved_hp.get("personal_damage"),
                            "reason": "Время боя вышло, босс не повержен",
                            "event_key": defeat_key,
                        })
                    await self._clear_live_battle_snapshot()
                else:
                    logger.error(f"Ошибка сбора награды за босса: {e}")
                    results["errors"].append(f"claim_reward: {str(e)}")
                    await self._log_action("claim_boss_reward", "/api/boss/claim", 500, False, {"error": str(e)})

        return claimed_here, active_preset

    @staticmethod
    def _is_claim_not_ready(claim_res: Any) -> bool:
        """Возвращает True, если сервер еще финализирует награду за босса (not_ready / Reward is being finalized)."""
        if not isinstance(claim_res, dict):
            return False
        if claim_res.get("success") is True:
            return False
        status = str(claim_res.get("status") or "").lower().strip()
        msg = str(claim_res.get("message") or "").lower()
        if status in ("not_ready", "pending", "processing", "finalizing", "reward_processing"):
            return True
        if "being finalized" in msg or "not ready" in msg or "not_ready" in msg:
            return True
        if claim_res.get("retryAfterMs") is not None and not claim_res.get("rewards") and not claim_res.get("drops"):
            return True
        return False

    async def _claim_reward_with_retry(self, cid: Optional[str], max_retries: int = 6) -> Any:
        """Вызывает claim_reward с коротким ретраем при статусе not_ready / Reward is being finalized."""
        claim_res = await self.api.claim_reward(cid)
        attempt = 0
        while self._is_claim_not_ready(claim_res) and attempt < max_retries:
            attempt += 1
            retry_ms = claim_res.get("retryAfterMs") if isinstance(claim_res, dict) else 1500
            try:
                raw_sec = float(retry_ms or 1500) / 1000.0
            except (TypeError, ValueError):
                raw_sec = 1.5
            delay = max(1.0, min(5.0, raw_sec)) if self.enable_jitter else min(0.05, raw_sec)
            logger.info(
                f"Награда (claimId={cid}) финализируется (попытка {attempt}/{max_retries}), ждем {delay:.2f}с..."
            )
            await asyncio.sleep(delay)
            claim_res = await self.api.claim_reward(cid)
        return claim_res

    async def _fetch_profile_snapshot_safe(self) -> Optional[Dict[str, Any]]:
        """Безопасно запрашивает профиль игрока для вычисления дельты наград до/после claim."""
        try:
            if self.player_api is not None and hasattr(self.player_api, "init_player"):
                return await self.player_api.init_player()
            http = getattr(self.api, "http", None)
            if http is not None and hasattr(http, "post"):
                resp = await http.post("/api/player/init", json={})
                if getattr(resp, "status_code", 0) == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Не удалось получить снимок профиля для дельты наград: {e}")
        return None

    @staticmethod
    def _extract_profile_resources(profile_data: Optional[Dict[str, Any]]) -> Dict[str, int]:
        if not isinstance(profile_data, dict):
            return {}
        p = profile_data.get("player") if isinstance(profile_data.get("player"), dict) else profile_data
        cur_sub = p.get("currencies") if isinstance(p.get("currencies"), dict) else {}
        res_sub = p.get("resources") if isinstance(p.get("resources"), dict) else {}
        out: Dict[str, int] = {}
        for key in ("cigarettes", "sugar", "rubles", "paper", "soap", "authority", "keys", "respect", "energy", "signets", "chips"):
            val = cur_sub.get(key)
            if val is None:
                val = res_sub.get(key)
            if val is None:
                val = p.get(key)
            if val is not None:
                try:
                    out[key] = int(val)
                except (TypeError, ValueError):
                    pass
        return out

    @classmethod
    def _merge_profile_delta_rewards(
        cls,
        parsed: Dict[str, Any],
        before_prof: Optional[Dict[str, Any]],
        after_prof: Optional[Dict[str, Any]],
    ) -> None:
        """Дополняет parsed['rewards'] и meta_json['rewards'] ресурсами из дельты профиля без дублирования."""
        from core.drop_parser import CURRENCY_LABELS
        before_res = cls._extract_profile_resources(before_prof)
        after_res = cls._extract_profile_resources(after_prof)
        if not before_res or not after_res:
            return
        rewards = parsed.setdefault("rewards", [])
        existing_currencies = {str(r.get("currency")) for r in rewards if isinstance(r, dict)}
        added = False
        for c_key, after_val in after_res.items():
            before_val = before_res.get(c_key)
            if before_val is None:
                continue
            delta = after_val - before_val
            if delta > 0 and c_key not in existing_currencies:
                label = CURRENCY_LABELS.get(c_key, c_key)
                rewards.append({"currency": c_key, "label": label, "amount": delta})
                existing_currencies.add(c_key)
                added = True
        if added:
            meta_j = parsed.setdefault("meta_json", {})
            meta_j["reward_lines"] = DropParser.format_boss_rewards_lines(parsed)
            meta_j["rewards"] = [
                {
                    "type": "currency",
                    "key": rw["currency"],
                    "name": rw["label"],
                    "amount": rw["amount"],
                    "icon": f"assets/icons/{rw['currency']}.webp",
                }
                for rw in rewards
            ] + [
                {
                    "type": dr.get("kind") or dr.get("type") or "item",
                    "key": str(dr.get("itemId") or dr.get("setId") or dr.get("title") or "item"),
                    "name": dr.get("title") or dr.get("name") or "Предмет",
                    "amount": 1,
                    "icon": dr.get("imageUrl") or "",
                }
                for dr in (parsed.get("drops") or [])
            ]
            if meta_j["reward_lines"]:
                parsed["subtitle"] = "Босс повержен"

    def _record_battle_start(self, battle: Optional[Dict[str, Any]]) -> None:
        if not isinstance(battle, dict):
            return
        sess_id = str(battle.get("sessionId") or "")
        start_ts: Optional[float] = None
        for key in ("startedAt", "createdAt", "startTime"):
            if battle.get(key):
                dt = parse_iso_utc(battle.get(key))
                if dt is not None:
                    start_ts = dt.timestamp()
                    break
        if start_ts is None and battle.get("endsAt") and (battle.get("durationSec") or battle.get("battleDurationSec")):
            ends_dt = parse_iso_utc(battle.get("endsAt"))
            if ends_dt is not None:
                try:
                    dur = float(battle.get("durationSec") or battle.get("battleDurationSec"))
                    start_ts = ends_dt.timestamp() - dur
                except (TypeError, ValueError):
                    pass
        if start_ts is None:
            if sess_id and sess_id in self._battle_started_at_by_session:
                start_ts = self._battle_started_at_by_session[sess_id]
            else:
                start_ts = datetime.now(timezone.utc).timestamp()
        if sess_id:
            self._battle_started_at_by_session.setdefault(sess_id, start_ts)
        self._last_battle_started_at = start_ts

    def _resolve_battle_duration(self, battle: Optional[Dict[str, Any]], session_id: Optional[Any] = None) -> Tuple[int, str]:
        start_ts: Optional[float] = None
        if isinstance(battle, dict):
            for key in ("startedAt", "createdAt", "startTime"):
                if battle.get(key):
                    dt = parse_iso_utc(battle.get(key))
                    if dt is not None:
                        start_ts = dt.timestamp()
                        break
        sess_key = str(session_id or (battle.get("sessionId") if isinstance(battle, dict) else "") or "")
        if start_ts is None and sess_key and sess_key in self._battle_started_at_by_session:
            start_ts = self._battle_started_at_by_session.pop(sess_key)
        elif sess_key:
            self._battle_started_at_by_session.pop(sess_key, None)
        if start_ts is None:
            start_ts = self._last_battle_started_at
        self._last_battle_started_at = None
        if start_ts is None:
            dur_sec = 0
        else:
            dur_sec = max(0, int(datetime.now(timezone.utc).timestamp() - start_ts))
        h = dur_sec // 3600
        m = (dur_sec % 3600) // 60
        s = dur_sec % 60
        return dur_sec, f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _apply_catalog_fallback_rewards(
        parsed: Dict[str, Any],
        *,
        boss_id: Optional[Any] = None,
        boss_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> None:
        """Fallback на гарантированные награды из bosses_catalog.json только при 100% подтверждённой победе."""
        from core.drop_parser import CURRENCY_LABELS
        items = _load_bosses_catalog() or FALLBACK_BOSSES
        if not items:
            return
        norm_mode = _normalize_boss_mode(mode) or "pacansky"
        norm_name = str(boss_name or "").strip().lower()
        target = None
        for b in items:
            if not isinstance(b, dict):
                continue
            if boss_id is not None and b.get("id") is not None and str(b.get("id")) == str(boss_id):
                target = b
                break
            if norm_name and str(b.get("name") or b.get("title") or "").strip().lower() == norm_name:
                target = b
                break
        if not target:
            return
        modes = target.get("modes") if isinstance(target.get("modes"), dict) else {}
        m_obj = modes.get(norm_mode) if isinstance(modes.get(norm_mode), dict) else {}
        gr = m_obj.get("globalReward") or target.get("globalReward")
        if not isinstance(gr, dict):
            return
        rewards = parsed.setdefault("rewards", [])
        if gr.get("authority") and int(gr["authority"]) > 0:
            rewards.append({"currency": "authority", "label": CURRENCY_LABELS.get("authority", "Авторитет"), "amount": int(gr["authority"])})
        if gr.get("keys") and int(gr["keys"]) > 0:
            rewards.append({"currency": "keys", "label": CURRENCY_LABELS.get("keys", "Ключи"), "amount": int(gr["keys"])})
        for cur in (gr.get("currencies") or []):
            if isinstance(cur, dict):
                ck = DropParser._normalize_currency(str(cur.get("type") or cur.get("currency") or ""))
                amt = int(cur.get("amount") or 0)
                if ck and amt > 0 and not any(r["currency"] == ck for r in rewards):
                    rewards.append({"currency": ck, "label": CURRENCY_LABELS.get(ck, ck), "amount": amt})
        if rewards:
            meta_j = parsed.setdefault("meta_json", {})
            meta_j["reward_lines"] = DropParser.format_boss_rewards_lines(parsed)
            meta_j["rewards"] = [
                {
                    "type": "currency",
                    "key": rw["currency"],
                    "name": rw["label"],
                    "amount": rw["amount"],
                    "icon": f"assets/icons/{rw['currency']}.webp",
                }
                for rw in rewards
            ]
            parsed["subtitle"] = "Босс повержен (по каталогу)"

    @staticmethod
    def classify_boss_outcome(
        claim_res: Optional[Dict[str, Any]],
        *,
        last_hp: Optional[Any] = None,
        battle: Optional[Dict[str, Any]] = None,
        parsed: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Строгая классификация исхода боя с боссом: victory | defeat.
        Уровень 1: Явный вердикт сервера (в т.ч. внутри claim_res['rewards']['result']).
        Уровень 2: Наличие реальных непустых наград / истечение таймера.
        Уровень 3: Быстрые победы с hp <= 0 (без ложных побед на голом status='claimed').
        """
        res = claim_res if isinstance(claim_res, dict) else {}
        sub_dicts = [res]
        for sub_k in ("rewards", "data", "result"):
            sub_v = res.get(sub_k)
            if isinstance(sub_v, dict):
                sub_dicts.append(sub_v)

        defeat_words = ("defeat", "lose", "loss", "lost", "timeout", "expired", "failed", "escaped")
        victory_words = ("win", "victory", "won", "killed", "defeated_boss")

        # Уровень 1: Явный вердикт сервера (в т.ч. вложенный rewards.result)
        for d in sub_dicts:
            for k in ("result", "outcome", "status"):
                raw_val = d.get(k)
                if isinstance(raw_val, str):
                    val_low = raw_val.lower().strip()
                    if val_low in defeat_words:
                        return "defeat"
                    if val_low in victory_words:
                        return "victory"
            if (
                d.get("isWin") is False
                or d.get("win") is False
                or d.get("isVictory") is False
                or d.get("victory") is False
                or d.get("won") is False
                or d.get("isDefeat") is True
            ):
                return "defeat"
            if (
                d.get("isWin") is True
                or d.get("win") is True
                or d.get("isVictory") is True
                or d.get("victory") is True
                or d.get("won") is True
                or d.get("bossDefeated") is True
            ):
                return "victory"
            msg_low = f"{d.get('message') or ''} {d.get('error') or ''}".lower()
            if any(m in msg_low for m in ("time expired", "boss escaped", "you lost", "battle failed", "время вышло", "не побежден")):
                return "defeat"

        # Уровень 2: Реальные непустые награды
        has_loot = bool(parsed and ((parsed.get("rewards") or []) or (parsed.get("drops") or [])))
        if has_loot:
            return "victory"

        # Проверка истечения таймера боя
        if isinstance(battle, dict) and battle.get("endsAt"):
            ends_dt = parse_iso_utc(battle.get("endsAt"))
            if ends_dt is not None and datetime.now(timezone.utc) >= ends_dt:
                if last_hp is None or int(last_hp) > 0:
                    return "defeat"

        if last_hp is not None and int(last_hp) > 0:
            return "defeat"

        return "victory" if (last_hp is not None and int(last_hp) <= 0) else "defeat"

    async def _try_summon_next_boss(
        self,
        bootstrap: Dict[str, Any],
        config: Any,
        prisons_data: Optional[Any],
        active_preset: Optional[BossPreset],
        preset_steps: List[Dict[str, Any]],
        results: Dict[str, Any],
        is_conveyor_transition: bool = False,
    ) -> Tuple[bool, Dict[str, Any], Optional[BossPreset]]:
        """
        Пытается призвать следующего босса (сначала из active_preset, затем из config.boss_targets).
        Возвращает (summoned_ok, refreshed_bootstrap, updated_active_preset).
        """
        eval_by_id = await self._fetch_evaluated_bosses(bootstrap, prisons_data)

        # Приоритет A: Активный пресет боссов
        if active_preset:
            while active_preset and active_preset.current_step_index < len(preset_steps):
                step = preset_steps[active_preset.current_step_index]
                b_id_int = step["bossId"]
                b_meta = eval_by_id.get(b_id_int, {})
                b_mode = step["mode"]

                mode_access = (b_meta.get("modesAccess") or {}).get(b_mode, {})
                is_locked = b_meta.get("isLocked", False)
                can_attack_boss = b_meta.get("canAttack", True)
                can_attack_mode = mode_access.get("canAttack", can_attack_boss)

                block_reason = None
                if is_locked:
                    block_reason = b_meta.get("unlockReason") or "Босс заблокирован"
                elif not can_attack_mode or not can_attack_boss:
                    block_reason = mode_access.get("reason") or b_meta.get("attackBlockReason") or "Невозможно атаковать"

                if block_reason:
                    logger.info(
                        f"Пресет '{active_preset.name}': пропуск шага {active_preset.current_step_index + 1}/{len(preset_steps)} "
                        f"(Босс ID={b_id_int} {step['bossName']}, режим {b_mode}): {block_reason}"
                    )
                    await self._log_action(
                        "boss_preset_step_skip",
                        "/api/boss/start-attack",
                        200,
                        False,
                        {
                            "preset_id": active_preset.id,
                            "step_index": active_preset.current_step_index,
                            "boss_id": b_id_int,
                            "boss": step["bossName"],
                            "boss_name": step["bossName"],
                            "mode": b_mode,
                            "reason": block_reason,
                        },
                    )
                    active_preset = await self._advance_preset_step(
                        active_preset.id,
                        preset_steps,
                        status_note=f"Шаг {active_preset.current_step_index + 1} пропущен ({block_reason})",
                    )
                    continue

                if is_conveyor_transition:
                    await self._transition_pause()

                try:
                    logger.info(f"Пресет '{active_preset.name}': призыв босса ID={b_id_int} {step['bossName']} (режим {b_mode})...")
                    summon_res = await self.api.start_battle(boss_id=b_id_int, mode=b_mode)
                    if summon_res.get("success") is not False:
                        results["summoned_bosses"].append({"bossId": b_id_int, "mode": b_mode, "source": "preset"})
                        await self._log_action(
                            "boss_preset_step_summon",
                            "/api/boss/start-attack",
                            200,
                            True,
                            {
                                "preset_id": active_preset.id,
                                "step_index": active_preset.current_step_index,
                                "boss_id": b_id_int,
                                "boss_name": step["bossName"],
                                "mode": b_mode,
                            },
                        )
                        if self.db_engine:
                            async with get_session(self.db_engine) as db_sess:
                                p_obj = await db_sess.get(BossPreset, active_preset.id)
                                if p_obj:
                                    p_obj.last_status = f"Выполняется: шаг {p_obj.current_step_index + 1}/{len(preset_steps)} ({step['bossName']})"
                                    db_sess.add(p_obj)
                                    await db_sess.commit()
                        await self._publish_presets_slice()
                        refreshed = await self._fetch_bootstrap_ready()
                        return True, refreshed, active_preset
                except Exception as err:
                    logger.warning(f"Ошибка призыва босса в пресете (ID={b_id_int}): {err}")
                    await self._log_action(
                        "boss_preset_step_skip",
                        "/api/boss/start-attack",
                        400,
                        False,
                        {
                            "preset_id": active_preset.id,
                            "step_index": active_preset.current_step_index,
                            "boss_id": b_id_int,
                            "boss": step["bossName"],
                            "boss_name": step["bossName"],
                            "mode": b_mode,
                            "reason": str(err),
                        },
                    )
                    active_preset = await self._advance_preset_step(
                        active_preset.id,
                        preset_steps,
                        status_note=f"Ошибка шага {active_preset.current_step_index + 1}: {err}",
                    )
                    continue

            return False, bootstrap, active_preset

        # Приоритет B: Очередь config.boss_targets при включенном авто-призыве
        is_summon_enabled = bool(getattr(config, "auto_boss_enabled", False) or getattr(config, "auto_boss_summon", False))
        raw_targets = getattr(config, "boss_targets", None) or []
        if is_summon_enabled and raw_targets:
            for raw_item in raw_targets:
                target = self._normalize_boss_target(raw_item)
                if not target:
                    continue
                b_id_int = target["bossId"]
                b_mode = target["mode"]
                b_meta = eval_by_id.get(b_id_int, {})

                if b_meta.get("isLocked"):
                    logger.info(
                        f"Пропуск заблокированного босса ID={b_id_int} ({b_meta.get('title') or b_meta.get('name', 'Босс')}): "
                        f"{b_meta.get('unlockReason', 'Босс заблокирован')}."
                    )
                    continue

                mode_access = (b_meta.get("modesAccess") or {}).get(b_mode, {})
                if not b_meta.get("canAttack", True) or (mode_access and not mode_access.get("canAttack", True)):
                    reason = mode_access.get("reason") or b_meta.get("attackBlockReason") or "Недоступен для атаки"
                    logger.info(f"Пропуск босса ID={b_id_int} ({b_meta.get('title') or b_meta.get('name', 'Босс')}): {reason}.")
                    continue

                if is_conveyor_transition:
                    await self._transition_pause()

                try:
                    logger.info(f"Авто-призыв босса ID={b_id_int} (режим {b_mode})...")
                    summon_res = await self.api.start_battle(boss_id=b_id_int, mode=b_mode)
                    if summon_res.get("success") is not False:
                        results["summoned_bosses"].append({"bossId": b_id_int, "mode": b_mode, "source": "auto_queue"})
                        await self._log_action(
                            "boss_auto_summon",
                            "/api/boss/start-attack",
                            200,
                            True,
                            {"boss_id": b_id_int, "mode": b_mode},
                        )
                        refreshed = await self._fetch_bootstrap_ready()
                        return True, refreshed, active_preset
                except Exception as err:
                    logger.warning(f"Не удалось призвать босса {b_id_int}, пробуем следующего: {err}")
                    continue

        return False, bootstrap, active_preset

    async def run_cycle(self, force_manual: bool = False) -> Dict[str, Any]:
        """
        Выполняет конвейерный цикл проверки, сбора наград, призыва и атаки боссов.
        При убийстве босса или сборе награды сразу призывает следующего в том же цикле.
        """
        async with self._cycle_lock:
            if not force_manual and server_health_monitor.is_maintenance:
                if server_health_monitor.should_log_worker_skip():
                    logger.debug("Игровые сервера на техработах — BossWorker поставлен на паузу.")
                return {"status": "skipped", "reason": "maintenance"}

            logger.info(f"=== [Аккаунт {self.account_id}] Запуск цикла проверки боссов (force_manual={force_manual}) ===")

            config = await get_or_create_config(self.account_id, self.db_engine)
            if not force_manual and not is_worker_active(config):
                logger.info("Планировщик на паузе. Пропуск боссов.")
                return {"status": "skipped", "reason": "paused"}
            night_paused = (not force_manual) and is_night_mode_active(config)

            results: Dict[str, Any] = {
                "status": "success",
                "account_id": self.account_id,
                "rewards_claimed": 0,
                "hits_performed": [],
                "summoned_bosses": [],
                "boss_active": False,
                "boss_hp_remaining": None,
                "victories": [],
                "errors": [],
            }

            active_preset, preset_steps = await self._load_active_preset()
            prisons_data = await self._fetch_prisons_safe()
            claimed_keys_in_cycle: Set[str] = set()

            max_chain = 10
            chain_idx = 0
            boss_active = False

            while chain_idx < max_chain:
                # 1. Получение состояния боя
                try:
                    bootstrap = await self._fetch_bootstrap_ready()
                except GameMaintenanceError:
                    logger.debug("BossWorker: выход из цикла из-за режима техработ (состояние боя сохранено).")
                    break
                except Exception as e:
                    logger.error(f"Ошибка при получении bootstrap босса: {e}")
                    results["errors"].append(f"get_bootstrap: {str(e)}")
                    await self._log_action("get_bootstrap", "/api/boss/bootstrap", 500, False, {"error": str(e)})
                    break

                # 2. Сбор всех несобранных наград
                claimed_now, active_preset = await self._claim_pending_rewards(
                    bootstrap=bootstrap,
                    results=results,
                    active_preset=active_preset,
                    preset_steps=preset_steps,
                    claimed_keys_in_cycle=claimed_keys_in_cycle,
                )
                if claimed_now > 0:
                    try:
                        bootstrap = await self._fetch_bootstrap_ready()
                    except Exception as e:
                        results["errors"].append(f"get_bootstrap_after_claim: {str(e)}")
                        break

                state, battle = self._extract_battle(bootstrap)
                current_hp = battle.get("currentHp") if battle else None

                # Если статический мок в тестах продолжает отдавать уже заклейменную награду — считаем слот свободным
                if claimed_keys_in_cycle and state == "reward" and claimed_now == 0:
                    state = "idle"
                    battle = None
                    current_hp = None

                # Обработка поражения от босса (истечение таймера / state defeat / lost / failed)
                is_defeat = False
                if state in ("defeat", "lost", "timeout", "failed") or bool(battle and battle.get("isDefeat")):
                    is_defeat = True
                elif battle and current_hp is not None and int(current_hp) > 0 and battle.get("endsAt"):
                    ends_dt = parse_iso_utc(battle.get("endsAt"))
                    if ends_dt is not None and datetime.now(timezone.utc) > ends_dt:
                        is_defeat = True

                if is_defeat and battle is not None:
                    d_name = self._resolve_boss_name(battle, bootstrap, fallback_id=self._last_active_boss_id)
                    d_mode = battle.get("mode") or self._last_active_boss_mode
                    d_bid = battle.get("bossId") or self._last_active_boss_id
                    snap = await self._load_live_battle_snapshot()
                    resolved_hp = resolve_defeat_boss_hp(
                        battle=battle,
                        snapshot=snap,
                        boss_id=d_bid,
                        boss_name=d_name,
                        mode=d_mode,
                    )
                    d_sess_id = battle.get("sessionId") or (snap or {}).get("session_id") or "latest"
                    d_key = f"boss_defeat_{d_sess_id}"
                    if d_key not in self._notified_victory_keys:
                        self._notified_victory_keys.add(d_key)
                        results.setdefault("defeats", []).append({
                            "boss_name": d_name,
                            "mode": d_mode,
                            "remaining_hp": resolved_hp["remaining_hp"],
                            "max_hp": resolved_hp["max_hp"],
                            "hp_percent": resolved_hp["hp_percent"],
                            "hp_known": resolved_hp["hp_known"],
                            "personal_damage": resolved_hp.get("personal_damage"),
                            "reason": "Время боя вышло, босс не повержен",
                            "event_key": d_key,
                        })
                    active_preset = await self.on_boss_fight_finished(
                        {
                            "outcome": "defeat",
                            "bossId": d_bid,
                            "bossName": d_name,
                            "mode": d_mode,
                            "remainingHp": resolved_hp["remaining_hp"],
                            "maxHp": resolved_hp["max_hp"],
                            "personalDamage": resolved_hp.get("personal_damage"),
                            "sessionId": d_sess_id,
                        },
                        active_preset=active_preset,
                        preset_steps=preset_steps,
                    )
                    state = "idle"
                    battle = None
                    current_hp = None

                # 3. Призыв следующего босса при отсутствии активного боя
                is_battle_alive = (
                    state in ("active", "in_progress")
                    and battle is not None
                    and current_hp is not None
                    and int(current_hp) > 0
                )
                if not is_battle_alive:
                    if night_paused:
                        logger.info("Ночной режим (МСК): автопризыв боссов на паузе.")
                        results["night_mode_paused"] = True
                        boss_active = False
                        break
                    summoned, bootstrap, active_preset = await self._try_summon_next_boss(
                        bootstrap=bootstrap,
                        config=config,
                        prisons_data=prisons_data,
                        active_preset=active_preset,
                        preset_steps=preset_steps,
                        results=results,
                        is_conveyor_transition=(chain_idx > 0 or claimed_now > 0),
                    )
                    if not summoned:
                        boss_active = False
                        break
                    state, battle = self._extract_battle(bootstrap)
                    current_hp = battle.get("currentHp") if battle else None
                    is_battle_alive = (
                        state in ("active", "in_progress")
                        and battle is not None
                        and current_hp is not None
                        and int(current_hp) > 0
                    )
                    if not is_battle_alive:
                        boss_active = False
                        break

                boss_active = True
                results["boss_active"] = True
                results["boss_hp_remaining"] = current_hp
                if isinstance(battle, dict):
                    self._last_active_boss_id = battle.get("bossId") or self._last_active_boss_id
                    self._last_active_boss_mode = battle.get("mode") or self._last_active_boss_mode
                    nm = self._resolve_boss_name(battle, bootstrap, fallback_id=self._last_active_boss_id)
                    if nm and nm != "Босс":
                        self._last_active_boss_name = nm
                    self._record_battle_start(battle)
                    await self._save_live_battle_snapshot(battle, boss_name=nm)
                logger.info(f"Активен бой с боссом! Оставшееся HP: {current_hp}")

                await self.record_friends_damage(bootstrap)

                if night_paused:
                    logger.info("Ночной режим (МСК): автоатака боссов на паузе (бой активен, отслеживаем завершение).")
                    results["night_mode_paused"] = True
                    break

                is_hits_enabled = bool(
                    getattr(config, "boss_auto_melee", False)
                    or getattr(config, "auto_boss_enabled", False)
                    or getattr(config, "auto_boss_hits", True)
                )
                if not is_hits_enabled:
                    logger.info("Авто-удары по боссу отключены в конфигурации.")
                    break

                # 4-5. Нанесение готовых бесплатных рукопашных ударов через общий хелпер
                melee_res = await self.trigger_auto_melee(bootstrap=bootstrap, config=config)
                results["hits_performed"].extend(melee_res.get("hits_performed") or [])
                results["errors"].extend(melee_res.get("errors") or [])
                if melee_res.get("boss_hp_remaining") is not None:
                    results["boss_hp_remaining"] = melee_res["boss_hp_remaining"]
                if melee_res.get("rewards_claimed"):
                    results["rewards_claimed"] += int(melee_res["rewards_claimed"])
                    if melee_res.get("claim_id"):
                        claimed_keys_in_cycle.add(f"cid:{melee_res['claim_id']}")
                    if melee_res.get("claim_response"):
                        r_name = self._resolve_boss_name(battle, bootstrap, fallback_id=self._last_active_boss_id)
                        if r_name == "Босс" and self._last_active_boss_name:
                            r_name = self._last_active_boss_name
                        r_mode = (battle.get("mode") if isinstance(battle, dict) else None) or self._last_active_boss_mode
                        parsed_win = DropParser.parse_boss_claim(
                            melee_res["claim_response"],
                            boss_name=r_name,
                            mode=r_mode,
                        )
                        if melee_res.get("claim_before_profile") is not None:
                            self._merge_profile_delta_rewards(
                                parsed_win,
                                melee_res.get("claim_before_profile"),
                                melee_res.get("claim_after_profile"),
                            )
                        b_sid = battle.get("sessionId") or melee_res["claim_id"] if isinstance(battle, dict) else melee_res["claim_id"]
                        dur_sec, dur_fmt = self._resolve_battle_duration(battle if isinstance(battle, dict) else None, b_sid)
                        meta_win = parsed_win.setdefault("meta_json", {})
                        meta_win["duration_sec"] = dur_sec
                        meta_win["duration_formatted"] = dur_fmt
                        ev_key = f"boss_claim_{b_sid}"
                        parsed_win["event_key"] = ev_key
                        if self.db_engine:
                            await DropParser.save_notification(self.account_id, parsed_win, self.db_engine)
                        if ev_key not in self._notified_victory_keys:
                            self._notified_victory_keys.add(ev_key)
                            results["victories"].append({
                                "boss_name": meta_win.get("boss_name") or r_name,
                                "mode": r_mode,
                                "rewards": parsed_win.get("rewards") or [],
                                "drops": parsed_win.get("drops") or [],
                                "duration_sec": dur_sec,
                                "duration_formatted": dur_fmt,
                                "event_key": ev_key,
                            })
                    if active_preset:
                        active_preset = await self._advance_preset_step(active_preset.id, preset_steps)

                if melee_res.get("killed"):
                    chain_idx += 1
                    continue
                break

            # Уведомление об активности для адаптивного планировщика (12с vs 60с)
            if self.on_activity_change is not None:
                try:
                    self.on_activity_change(bool(boss_active or active_preset is not None))
                except Exception as e:
                    logger.debug(f"Ошибка callback on_activity_change: {e}")

            # Telegram уведомление отправляем ТОЛЬКО по итогам побед и поражений
            if self.notifier is not None:
                victories = results.get("victories") or []
                defeats = results.get("defeats") or []
                if victories or defeats:
                    lines: List[str] = []
                    for vic in victories:
                        m_str = DropParser.format_boss_mode(vic.get("mode"))
                        title_str = f"{vic['boss_name']} ({m_str})" if m_str else str(vic["boss_name"])
                        lines.append(f"👊 <b>Победа над боссом: {title_str}</b>")
                        reward_summary = DropParser.format_boss_rewards_inline(vic)
                        lines.append(f"🔥 Награды: {reward_summary or 'нет данных от сервера'}")
                        dur_fmt = vic.get("duration_formatted") or "00:00:00"
                        lines.append(f"⏱️ Бой продлился: {dur_fmt}")
                    for df in defeats:
                        m_str = DropParser.format_boss_mode(df.get("mode"))
                        title_str = f"{df['boss_name']} ({m_str})" if m_str else str(df["boss_name"])
                        lines.append(f"💀 <b>Поражение от босса: {title_str}</b>")
                        lines.append(f"⏱ {df.get('reason') or 'Время боя вышло, босс не повержен'}")
                        d_rem = df.get("remaining_hp")
                        d_max = df.get("max_hp")
                        if df.get("hp_known") and d_rem and d_max and int(d_rem) > 0 and int(d_max) > 1:
                            pct_str = DropParser.format_hp_percent(int(d_rem), int(d_max))
                            lines.append(
                                f"❤️ Осталось HP: <b>{DropParser.format_space_num(int(d_rem))} / "
                                f"{DropParser.format_space_num(int(d_max))} ({pct_str})</b>"
                            )
                        elif d_max and int(d_max) > 1:
                            lines.append(f"❤️ Осталось HP: <b>нет данных</b> (из {DropParser.format_space_num(int(d_max))})")
                        else:
                            lines.append("❤️ Осталось HP: <b>нет данных</b>")
                        if df.get("personal_damage") and int(df["personal_damage"]) > 0:
                            lines.append(f"⚔️ Личный урон: <b>{DropParser.format_space_num(int(df['personal_damage']))}</b>")
                        hits_cnt = df.get("melee_hits") if df.get("melee_hits") is not None else len(results["hits_performed"])
                        lines.append(f"⚔️ Нанесено рукопашных ударов: <b>{hits_cnt}</b>")
                    await self.notifier.notify("\n".join(lines))

            logger.info(f"=== [Аккаунт {self.account_id}] Цикл проверки боссов завершен ===")
            return results
