import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Any, List, Optional
import httpx
from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active
from core.server_health import server_health_monitor, GameMaintenanceError
from core.models import PlayerSnapshot, ActionLog
from client.api.player import PlayerAPI
from bot.notifier import TelegramNotifier
from core.drop_parser import DropParser

logger = logging.getLogger(__name__)


MSK_TZ = timezone(timedelta(hours=3))

NEGATIVE_QUEST_ACTIONS: Dict[str, Dict[str, Any]] = {
    "StressVictim": {
        "interaction_type": "Fight",
        "cigs_cost": 100,
        "title": "Наехать",
    },
    "SpitSoup": {
        "interaction_type": "Harknut",
        "cigs_cost": 0,
        "title": "Харкнуть в баланду",
    },
    "AddYeast": {
        "interaction_type": "TossDroj",
        "cigs_cost": 0,
        "title": "Подкинуть дрожжей",
    },
}


def get_toilet_paper_reset_info(
    can_claim: bool,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Рассчитывает точный таймер сброса ежедневной бесплатной туалетной бумаги.
    Согласно серверной логике («Ещё рано! Приходи завтра.»), сброс происходит в 00:00 МСК (UTC+3).
    """
    ref_utc = now_utc or datetime.now(timezone.utc)
    if ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=timezone.utc)
    now_msk = ref_utc.astimezone(MSK_TZ)
    next_midnight_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    seconds_until = 0 if can_claim else max(1, int((next_midnight_msk - now_msk).total_seconds()))
    return {
        "canClaim": bool(can_claim),
        "resetMode": "midnight_msk",
        "secondsUntilReset": seconds_until,
        "nextResetAt": next_midnight_msk.isoformat(),
    }


def parse_iso_utc(ts_str: Optional[str]) -> Optional[datetime]:
    """Безопасный парсинг временной метки ISO в UTC datetime."""
    if not ts_str:
        return None
    try:
        clean_ts = str(ts_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class RoutineWorker:
    """
    Воркер ежедневных и регулярных игровых активностей:
    1. Синхронизация профиля и фиксация снапшота в БД (POST /api/player/init).
    2. Сбор ежедневной туалетной бумаги (POST /api/daily/toilet-paper).
    3. Сбор прибыли с бизнесов (POST /api/player/business/collect).
    4. Проверка и бритье бороды (POST /api/beard/update).
    5. Сбор подогревов от друзей (POST /api/podogrev/collect/all).
    """

    def __init__(
        self,
        account_id: int,
        player_api: PlayerAPI,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
        prison_worker: Optional[Any] = None,
        social_api: Optional[Any] = None,
        on_business_reschedule: Optional[Callable[[float], Any]] = None,
        on_katala_reschedule: Optional[Callable[[float], Any]] = None,
    ):
        self.account_id = account_id
        self.api = player_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.prison_worker = prison_worker
        self.social_api = social_api
        self.on_business_reschedule = on_business_reschedule
        self.on_katala_reschedule = on_katala_reschedule
        self._daily_interaction_done: Dict[str, Dict[str, set]] = {}
        self._daily_interaction_limit_hit: Dict[str, set] = {}
        self._interaction_pool_cache: tuple = (0.0, [])
        self._last_menyala_check_ts: float = 0.0

    async def _jitter(self) -> None:
        if self.enable_jitter:
            delay = random.uniform(settings.JITTER_MIN_SEC, settings.JITTER_MAX_SEC)
            await asyncio.sleep(delay)

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

    async def send_podogrev_if_ready(self, config: Optional[Any] = None) -> Dict[str, Any]:
        """Отправляет бесплатные подогревы всем доступным друзьям, если включен тумблер auto_podogrev_send."""
        if server_health_monitor.is_maintenance:
            return {"success": False, "sent": 0, "skipped": True, "reason": "maintenance"}
        if config is None and self.db_engine:
            config = await get_or_create_config(self.account_id, self.db_engine)
        if config is not None and (not is_worker_active(config) or not getattr(config, "auto_podogrev_send", False)):
            return {"success": False, "sent": 0, "skipped": True}
        try:
            friends_res = await self.api.get_podogrev_friends(page=1, page_size=50)
            friends_list = (
                (friends_res.get("friends") or friends_res.get("items") or friends_res.get("list") or [])
                if isinstance(friends_res, dict)
                else []
            )
            uids_to_send = [
                int(f.get("userId") or f.get("id"))
                for f in friends_list
                if isinstance(f, dict) and (f.get("userId") or f.get("id"))
            ]
            if not uids_to_send:
                return {"success": True, "sent": 0}
            send_res = await self.api.send_podogrev(uids_to_send, send_to_all=True, gift_type=1)
            await self._log_action("send_podogrev", "/api/podogrev/send", 200, True, send_res)
            logger.info(f"Отправлены бесплатные подогревы друзьям ({len(uids_to_send)} чел.)")
            return {"success": True, "sent": len(uids_to_send), "result": send_res}
        except Exception as e:
            logger.error(f"Ошибка при отправке подогревов друзьям: {e}")
            await self._log_action("send_podogrev", "/api/podogrev/send", 500, False, {"error": str(e)})
            return {"success": False, "sent": 0, "error": str(e)}

    async def play_katala_if_ready(self, config: Optional[Any] = None) -> Dict[str, Any]:
        """Запускает бесплатную партию у Каталы и перепланирует точный таймер следующего запуска."""
        if server_health_monitor.is_maintenance:
            return {"success": False, "status": "skipped", "reason": "maintenance"}
        if config is None and self.db_engine:
            config = await get_or_create_config(self.account_id, self.db_engine)
        if config is not None and (not is_worker_active(config) or not getattr(config, "auto_katala", False)):
            return {"success": False, "status": "skipped"}
        try:
            from client.api.katala import KatalaAPI, play_free_daily_game
            katala_api = KatalaAPI(self.api.http)
            katala_res = await play_free_daily_game(
                katala_api,
                player_api=self.api,
                account_id=self.account_id,
                allow_paid=False,
                db_engine=self.db_engine,
            )
            if katala_res.get("success"):
                await self._log_action("katala_game", "/api/card/finish", 200, True, katala_res)
                logger.info(f"Успешно сыграна бесплатная суточная партия у Каталы: комбо={katala_res.get('combo')}")
                next_cd = katala_res.get("next_cooldown_sec") or 86400
                if self.on_katala_reschedule is not None:
                    try:
                        self.on_katala_reschedule(float(next_cd) + 2.0)
                    except Exception:
                        pass
            else:
                sec_left = katala_res.get("seconds_left")
                logger.info(
                    f"Катала пропущена: status={katala_res.get('status')}, "
                    f"seconds_left={sec_left}, msg={katala_res.get('message') or katala_res.get('error')}"
                )
                if sec_left is not None and float(sec_left) > 0 and self.on_katala_reschedule is not None:
                    try:
                        self.on_katala_reschedule(float(sec_left) + 2.0)
                    except Exception:
                        pass
            return katala_res
        except Exception as e:
            logger.warning(f"Ошибка при автоигре у Каталы: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def collect_interaction_targets(
        self,
        from_user_id: int,
        min_count: int = 80,
        force_refresh: bool = False,
    ) -> List[int]:
        """
        Собирает широкий дедуплицированный пул целей для фарма достижений (исключая свой userId):
        1) Друзья
        2) Кандидаты и отправленные заявки из БД (радар / рейды)
        3) Топы игроков (weekly-top, achievements, friend/top100)
        4) Участники бригад (recruitment + guild members)
        """
        now_ts = datetime.now(timezone.utc).timestamp()
        cached_ts, cached_list = self._interaction_pool_cache
        if not force_refresh and cached_list and (now_ts - cached_ts) < 600.0 and len(cached_list) >= min_count:
            return list(cached_list)

        targets: List[int] = []
        seen: set = {int(from_user_id)} if from_user_id else set()

        def _add_uid(raw: Any) -> None:
            try:
                uid = int(raw)
                if uid > 0 and uid not in seen:
                    seen.add(uid)
                    targets.append(uid)
            except (TypeError, ValueError):
                pass

        def _extract_from_items(items: Any) -> None:
            if not isinstance(items, list):
                return
            for item in items:
                if isinstance(item, dict):
                    _add_uid(item.get("userId") or item.get("playerId") or item.get("id"))
                elif isinstance(item, (int, str)):
                    _add_uid(item)

        if self.social_api is not None:
            if hasattr(self.social_api, "get_all_friend_profiles"):
                try:
                    _extract_from_items(await self.social_api.get_all_friend_profiles())
                except Exception as e:
                    logger.debug(f"collect_interaction_targets friends error: {e}")

        if self.db_engine is not None:
            try:
                from sqlalchemy import select
                from core.models import TrackedCandidate, SentFriendRequest
                async with get_session(self.db_engine) as session:
                    c_rows = (await session.execute(
                        select(TrackedCandidate.user_id)
                        .where(TrackedCandidate.account_id == self.account_id)
                        .limit(200)
                    )).scalars().all()
                    for uid in c_rows:
                        _add_uid(uid)
                    s_rows = (await session.execute(
                        select(SentFriendRequest.target_user_id)
                        .where(SentFriendRequest.account_id == self.account_id)
                        .limit(200)
                    )).scalars().all()
                    for uid in s_rows:
                        _add_uid(uid)
            except Exception as e:
                logger.debug(f"collect_interaction_targets db error: {e}")

        if self.social_api is not None and len(targets) < min_count:
            for fetcher_name in ("get_weekly_top", "get_weekly_achievements", "get_friend_top100"):
                fetcher = getattr(self.social_api, fetcher_name, None)
                if callable(fetcher):
                    try:
                        res = await fetcher(100) if fetcher_name != "get_friend_top100" else await fetcher()
                        if isinstance(res, dict):
                            _extract_from_items(res.get("top") or res.get("players") or res.get("users") or res.get("items") or res.get("data"))
                        elif isinstance(res, list):
                            _extract_from_items(res)
                    except Exception as e:
                        logger.debug(f"collect_interaction_targets {fetcher_name} error: {e}")

        if self.social_api is not None and len(targets) < min_count and hasattr(self.social_api, "get_recruitment_list") and hasattr(self.social_api, "get_guild_members"):
            try:
                rec = await self.social_api.get_recruitment_list(50)
                guilds = rec.get("guilds") or rec.get("items") or rec.get("list") or [] if isinstance(rec, dict) else (rec if isinstance(rec, list) else [])
                guild_ids: List[int] = []
                for g in guilds:
                    if isinstance(g, dict):
                        gid = g.get("guildId") or g.get("id")
                        if gid and int(gid) not in guild_ids:
                            guild_ids.append(int(gid))
                for gid in guild_ids[:5]:
                    if len(targets) >= min_count:
                        break
                    try:
                        m_res = await self.social_api.get_guild_members(gid)
                        members = m_res.get("members") or m_res.get("users") or [] if isinstance(m_res, dict) else (m_res if isinstance(m_res, list) else [])
                        _extract_from_items(members)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"collect_interaction_targets guilds error: {e}")

        if targets:
            self._interaction_pool_cache = (now_ts, list(targets))
        return targets

    async def _load_daily_interaction_groups(self, msk_today: str) -> Dict[str, set]:
        """Загружает из SQLite отработанные за сегодня цели по группам ('biceps', 'negative') и чистит старые дни."""
        groups: Dict[str, set] = {"biceps": set(), "negative": set()}
        if self.db_engine is None:
            return groups
        try:
            from sqlalchemy import select, delete
            from core.models import DailyInteractionTarget
            cutoff_day = (datetime.now(MSK_TZ) - timedelta(days=2)).strftime("%Y-%m-%d")
            async with get_session(self.db_engine) as session:
                await session.execute(
                    delete(DailyInteractionTarget).where(
                        DailyInteractionTarget.account_id == self.account_id,
                        DailyInteractionTarget.day_msk < cutoff_day,
                    )
                )
                rows = (await session.execute(
                    select(DailyInteractionTarget.action_group, DailyInteractionTarget.target_id).where(
                        DailyInteractionTarget.account_id == self.account_id,
                        DailyInteractionTarget.day_msk == msk_today,
                    )
                )).all()
                for grp, tid in rows:
                    groups.setdefault(grp, set()).add(int(tid))
                await session.commit()
        except Exception as e:
            logger.debug(f"_load_daily_interaction_groups error: {e}")
        return groups

    async def _record_daily_interaction_target(
        self,
        msk_today: str,
        action_group: str,
        target_id: int,
        action_type: str,
    ) -> None:
        if self.db_engine is None:
            return
        try:
            from sqlalchemy import select
            from core.models import DailyInteractionTarget
            async with get_session(self.db_engine) as session:
                existing = (await session.execute(
                    select(DailyInteractionTarget.id).where(
                        DailyInteractionTarget.account_id == self.account_id,
                        DailyInteractionTarget.day_msk == msk_today,
                        DailyInteractionTarget.action_group == action_group,
                        DailyInteractionTarget.target_id == int(target_id),
                    )
                )).scalar_one_or_none()
                if existing is None:
                    session.add(
                        DailyInteractionTarget(
                            account_id=self.account_id,
                            day_msk=msk_today,
                            action_group=action_group,
                            target_id=int(target_id),
                            action_type=action_type,
                        )
                    )
                    await session.commit()
        except Exception as e:
            logger.debug(f"_record_daily_interaction_target error: {e}")

    async def process_auto_interactions(
        self,
        config: Optional[Any] = None,
        player_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Выполняет включенные ежедневные авто-взаимодействия (Качать бицуху, Плевать в баланду, Кидать дрожжи)
        по расширенному пулу целей до достижения суточного лимита сервера (с учетом MSK даты и правила 1 негативного действия на игрока).
        """
        if config is None and self.db_engine is not None:
            config = await get_or_create_config(self.account_id, self.db_engine)
        if config is not None and not is_worker_active(config):
            return {"status": "skipped", "reason": "paused_or_sleep"}
        if self.social_api is None:
            return {"status": "skipped", "reason": "no_social_api"}

        actions_cfg = [
            ("auto_biceps", "UpgradeBiceps", "Качать бицуху", "biceps"),
            ("auto_spit_balanda", "Harknut", "Плевать в баланду", "negative"),
            ("auto_throw_yeast", "TossDroj", "Кидать дрожжи", "negative"),
        ]
        enabled = [(attr, act, title, grp) for attr, act, title, grp in actions_cfg if getattr(config, attr, False)]
        if not enabled:
            return {"status": "skipped", "reason": "none_enabled"}

        msk_today = datetime.now(MSK_TZ).strftime("%Y-%m-%d")
        done_today = self._daily_interaction_done.setdefault(msk_today, {})
        limit_hit_today = self._daily_interaction_limit_hit.setdefault(msk_today, set())

        for old_day in [k for k in list(self._daily_interaction_done.keys()) if k != msk_today]:
            self._daily_interaction_done.pop(old_day, None)
        for old_day in [k for k in list(self._daily_interaction_limit_hit.keys()) if k != msk_today]:
            self._daily_interaction_limit_hit.pop(old_day, None)

        if all(act in limit_hit_today for _, act, _, _ in enabled):
            return {"status": "limit_reached", "day": msk_today}

        db_groups = await self._load_daily_interaction_groups(msk_today)
        for grp in ("biceps", "negative"):
            done_today.setdefault(grp, set()).update(db_groups.get(grp, set()))

        from_user_id = 0
        if isinstance(player_data, dict):
            from_user_id = int(player_data.get("userId") or (player_data.get("player") or {}).get("userId") or 0)
        if not from_user_id:
            try:
                p_init = await self.api.init_player()
                from_user_id = int(p_init.get("userId") or (p_init.get("player") or {}).get("userId") or 0)
            except Exception as e:
                logger.warning(f"auto_interactions: не удалось получить userId игрока: {e}")
                return {"status": "error", "error": str(e)}

        targets = await self.collect_interaction_targets(from_user_id, min_count=80)
        summary: Dict[str, Any] = {"day": msk_today, "targets_pool": len(targets), "actions": {}}

        limit_markers = ("лимит", "limit", "исчерпан", "больше нельзя", "максимум")
        already_markers = ("уже", "already", "использовано", "недоступ", "негатив", "этому игроку")

        async def _execute_for_targets(action_type: str, title: str, action_group: str, target_list: List[int]) -> tuple:
            if action_type in limit_hit_today:
                return 0, True
            acted_set = done_today.setdefault(action_group, set())
            done_cnt = 0
            hit_limit = False

            for uid in target_list:
                if uid in acted_set:
                    continue
                try:
                    res = await self.social_api.perform_interaction(from_user_id, uid, action_type)
                    ok = bool(res.get("success", True)) if isinstance(res, dict) else True
                    msg = str((res.get("message") or res.get("error") or "") if isinstance(res, dict) else "").lower()
                    if ok:
                        done_cnt += 1
                        acted_set.add(uid)
                        await self._record_daily_interaction_target(msk_today, action_group, uid, action_type)
                        if isinstance(res, dict) and res.get("remaining") == 0:
                            hit_limit = True
                            limit_hit_today.add(action_type)
                            break
                    elif any(m in msg for m in already_markers):
                        acted_set.add(uid)
                        await self._record_daily_interaction_target(msk_today, action_group, uid, action_type)
                    elif any(m in msg for m in limit_markers):
                        hit_limit = True
                        limit_hit_today.add(action_type)
                        break
                except httpx.HTTPStatusError as err:
                    err_txt = (err.response.text or "").lower()
                    if any(m in err_txt for m in already_markers):
                        acted_set.add(uid)
                        await self._record_daily_interaction_target(msk_today, action_group, uid, action_type)
                    elif any(m in err_txt for m in limit_markers):
                        hit_limit = True
                        limit_hit_today.add(action_type)
                        break
                except Exception as e:
                    logger.debug(f"auto_interactions ({action_type} -> {uid}): {e}")

                if self.enable_jitter:
                    await asyncio.sleep(random.uniform(0.3, 0.55))

            return done_cnt, hit_limit

        # 1. Бицуха (независимая группа)
        for _, act, title, grp in enabled:
            if grp == "biceps":
                done_cnt, hit_limit = await _execute_for_targets(act, title, grp, targets)
                summary["actions"][act] = {"done": done_cnt, "limit_reached": hit_limit}
                if done_cnt > 0 or hit_limit:
                    await self._log_action(f"auto_{act.lower()}", "/api/interaction/perform", 200, True, {"title": title, "done": done_cnt, "limit_reached": hit_limit, "day": msk_today})
                    logger.info(f"Авто-действие '{title}': выполнено={done_cnt}, лимит={hit_limit}")

        # 2. Негативные действия (Harknut / TossDroj) — общее суточное исключение по игрокам + честное разделение пула
        neg_enabled = [(act, title) for _, act, title, grp in enabled if grp == "negative" and act not in limit_hit_today]
        for _, act, title, grp in enabled:
            if grp == "negative" and act in limit_hit_today:
                summary["actions"][act] = {"done": 0, "limit_reached": True}

        if neg_enabled:
            neg_acted = done_today.setdefault("negative", set())
            eligible_neg = [uid for uid in targets if uid not in neg_acted]
            if len(neg_enabled) == 2:
                (act1, title1), (act2, title2) = neg_enabled[0], neg_enabled[1]
                slice1 = eligible_neg[0::2]
                slice2 = eligible_neg[1::2]
                d1, l1 = await _execute_for_targets(act1, title1, "negative", slice1)
                d2, l2 = await _execute_for_targets(act2, title2, "negative", slice2)
                # Если одно из действий не достигло лимита, добираем оставшиеся нетронутые цели
                if not l1:
                    rem = [uid for uid in eligible_neg if uid not in neg_acted]
                    if rem:
                        extra_d1, l1 = await _execute_for_targets(act1, title1, "negative", rem)
                        d1 += extra_d1
                if not l2:
                    rem = [uid for uid in eligible_neg if uid not in neg_acted]
                    if rem:
                        extra_d2, l2 = await _execute_for_targets(act2, title2, "negative", rem)
                        d2 += extra_d2
                for act, title, done_cnt, hit_limit in ((act1, title1, d1, l1), (act2, title2, d2, l2)):
                    summary["actions"][act] = {"done": done_cnt, "limit_reached": hit_limit}
                    if done_cnt > 0 or hit_limit:
                        await self._log_action(f"auto_{act.lower()}", "/api/interaction/perform", 200, True, {"title": title, "done": done_cnt, "limit_reached": hit_limit, "day": msk_today})
                        logger.info(f"Авто-действие '{title}': выполнено={done_cnt}, лимит={hit_limit}")
            else:
                act, title = neg_enabled[0]
                done_cnt, hit_limit = await _execute_for_targets(act, title, "negative", eligible_neg)
                summary["actions"][act] = {"done": done_cnt, "limit_reached": hit_limit}
                if done_cnt > 0 or hit_limit:
                    await self._log_action(f"auto_{act.lower()}", "/api/interaction/perform", 200, True, {"title": title, "done": done_cnt, "limit_reached": hit_limit, "day": msk_today})
                    logger.info(f"Авто-действие '{title}': выполнено={done_cnt}, лимит={hit_limit}")

        try:
            from core.state_hub import state_hub
            state_hub.emit_change(
                self.account_id,
                ["routine", "profile"],
                patch={"routine": {"auto_interactions": summary}},
                reason="auto_interactions",
            )
        except Exception:
            pass

        return summary

    async def run_cycle(self) -> Dict[str, Any]:
        """Выполняет один полный цикл рутинных задач."""
        if server_health_monitor.is_maintenance:
            if server_health_monitor.should_log_worker_skip():
                logger.debug("Игровые сервера на техработах — RoutineWorker на паузе.")
            return {"status": "skipped", "reason": "maintenance"}

        logger.info(f"=== [Аккаунт {self.account_id}] Запуск цикла рутинных задач ===")

        # Проверка живого BotConfig
        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            logger.info("Планировщик на паузе или активен режим сна. Пропуск рутины.")
            return {"status": "skipped", "reason": "paused_or_sleep"}

        results: Dict[str, Any] = {
            "account_id": self.account_id,
            "snapshot_saved": False,
            "toilet_paper_claimed": False,
            "business_collected": False,
            "beard_updated": False,
            "podogrev_collected": False,
            "podogrev_sent": False,
            "katala_played": False,
            "monthly_tiers_claimed": 0,
            "monthly_actions_done": 0,
            "kolsik_rolled": False,
            "errors": [],
        }

        # 1. Синхронизация профиля (POST /api/player/init)
        try:
            player_data = await self.api.init_player()
            currencies = player_data.get("currencies", {})
            can_claim_paper = bool(player_data.get("canClaimToiletPaper", False))

            async with get_session(self.db_engine) as session:
                snapshot = PlayerSnapshot(
                    account_id=self.account_id,
                    level=int(player_data.get("level", 0)),
                    authority=int(player_data.get("authority", 0)),
                    biceps=int(player_data.get("biceps", 0)),
                    energy=int(player_data.get("energy", 0)),
                    max_energy=int(player_data.get("maxEnergy", 0)),
                    cigarettes=int(currencies.get("cigarettes", 0)),
                    sugar=int(currencies.get("sugar", 0)),
                    rubles=int(currencies.get("rubles", 0)),
                    paper=int(currencies.get("paper", 0)),
                    soap=int(currencies.get("soap", 0)),
                    can_claim_toilet_paper=can_claim_paper,
                    last_business_collect_time=str(player_data.get("lastBusinessCollectTime", "")),
                    raw_payload=player_data,
                )
                session.add(snapshot)

            results["snapshot_saved"] = True
            await self._log_action("init_player", "/api/player/init", 200, True, {
                "level": player_data.get("level"),
                "authority": player_data.get("authority"),
                "can_claim_paper": can_claim_paper,
            })
            logger.info(
                f"Профиль синхронизирован: Уровень {player_data.get('level')}, "
                f"Авторитет: {player_data.get('authority')}, Энергия: {player_data.get('energy')}/{player_data.get('maxEnergy')}"
            )
        except Exception as e:
            logger.error(f"Ошибка при синхронизации профиля: {e}")
            results["errors"].append(f"init_player: {str(e)}")
            await self._log_action("init_player", "/api/player/init", 500, False, {"error": str(e)})
            can_claim_paper = False

        await self._jitter()

        # 2. Сбор ежедневной туалетной бумаги
        if can_claim_paper and getattr(config, "auto_toilet_paper", False):
            try:
                paper_res = await self.api.claim_toilet_paper()
                results["toilet_paper_claimed"] = True
                await self._log_action("claim_toilet_paper", "/api/daily/toilet-paper", 200, True, paper_res)
                logger.info(f"Туалетная бумага успешно собрана! Новый баланс: {paper_res.get('balance')}")
                # Сохранение уведомления
                await DropParser.save_notification(
                    self.account_id,
                    DropParser.parse_other(
                        "Ежедневная бумага",
                        "Сбор рулона",
                        rewards=[{"currency": "paper", "label": "Бумага", "amount": 1}],
                    ),
                    self.db_engine,
                )
            except Exception as e:
                logger.error(f"Ошибка при сборе туалетной бумаги: {e}")
                results["errors"].append(f"claim_toilet_paper: {str(e)}")
                await self._log_action("claim_toilet_paper", "/api/daily/toilet-paper", 500, False, {"error": str(e)})

        await self._jitter()

        # 3. Проверка и сбор прибыли с бизнесов
        if getattr(config, "auto_business", False):
            try:
                biz_data = await self.api.get_businesses()
                player_biz = biz_data.get("playerBusinesses", [])
                has_active_biz = any(isinstance(b, dict) and b.get("level", 0) > 0 for b in player_biz)

                last_collect_str = biz_data.get("lastCollectTime")
                last_collect_dt = parse_iso_utc(last_collect_str)
                can_collect_by_timer = True

                if last_collect_dt:
                    now_utc = datetime.now(timezone.utc)
                    elapsed_sec = (now_utc - last_collect_dt).total_seconds()
                    elapsed_minutes = elapsed_sec / 60.0
                    if elapsed_minutes < settings.BUSINESS_COLLECT_MIN_MINUTES:
                        can_collect_by_timer = False
                        wait_sec = max(1.0, settings.BUSINESS_COLLECT_MIN_MINUTES * 60.0 - elapsed_sec + 1.0)
                        if self.on_business_reschedule is not None:
                            try:
                                self.on_business_reschedule(wait_sec)
                            except Exception:
                                pass
                        logger.info(
                            f"Бизнесы еще не накопили прибыль (прошло {elapsed_minutes:.1f} мин из {settings.BUSINESS_COLLECT_MIN_MINUTES} мин). Пропуск сбора (следующий через {wait_sec:.0f}с)."
                        )

                if not has_active_biz:
                    logger.info("Нет активных бизнесов (level > 0). Пропуск сбора прибыли.")
                elif not can_collect_by_timer:
                    pass
                else:
                    try:
                        biz_res = await self.api.collect_business_rewards()
                        results["business_collected"] = True
                        if self.on_business_reschedule is not None:
                            try:
                                self.on_business_reschedule(settings.BUSINESS_COLLECT_MIN_MINUTES * 60.0 + 1.0)
                            except Exception:
                                pass
                        await self._log_action("collect_business", "/api/player/business/collect", 200, True, biz_res)
                        logger.info(f"Прибыль с бизнесов собрана: {biz_res.get('rewards')}")
                        # Сохранение уведомления о сборе с бизнесов
                        await DropParser.save_notification(
                            self.account_id,
                            DropParser.parse_business_collect(biz_res),
                            self.db_engine,
                        )
                    except httpx.HTTPStatusError as err:
                        err_text = err.response.text
                        status_code = err.response.status_code
                        logger.warning(f"Сервер отклонил сбор прибыли с бизнесов (HTTP {status_code}): {err_text}")
                        results["errors"].append(f"collect_business (HTTP {status_code}): {err_text}")
                        await self._log_action(
                            "collect_business",
                            "/api/player/business/collect",
                            status_code,
                            False,
                            {"error": err_text},
                        )
            except Exception as e:
                logger.error(f"Ошибка при проверке бизнесов: {e}")
                results["errors"].append(f"get_businesses: {str(e)}")
                await self._log_action("get_businesses", "/api/player/business/all", 500, False, {"error": str(e)})

        await self._jitter()

        # 4. Проверка и бритье бороды
        if getattr(config, "auto_beard", False):
            try:
                beard_res = await self.api.update_beard()
                results["beard_updated"] = True
                await self._log_action("update_beard", "/api/beard/update", 200, True, beard_res)
                logger.info(f"Борода обновлена: фаза {beard_res.get('beardPhase')}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении бороды: {e}")
                results["errors"].append(f"update_beard: {str(e)}")
                await self._log_action("update_beard", "/api/beard/update", 500, False, {"error": str(e)})

        await self._jitter()

        # 5. Сбор подогревов от друзей (с защитой от сгорания при полной энергии)
        if getattr(config, "auto_podogrev", False):
            cur_e = player_data.get("player", {}).get("energy", player_data.get("energy", 0)) if "player_data" in locals() and isinstance(player_data, dict) else 0
            max_e = player_data.get("player", {}).get("maxEnergy", player_data.get("maxEnergy", 100)) if "player_data" in locals() and isinstance(player_data, dict) else 100
            should_collect_podogrev = True
            if (getattr(config, "auto_prison", False) or getattr(config, "auto_masters", False)) and cur_e >= max_e:
                should_collect_podogrev = False
                logger.info(f"Энергия полна ({cur_e}/{max_e}) и включены ходки/мастера: сбор подогревов отложен до слива энергии.")

            if should_collect_podogrev:
                try:
                    podogrev_res = await self.api.collect_all_podogrev()
                    results["podogrev_collected"] = True
                    await self._log_action("collect_podogrev", "/api/podogrev/collect/all", 200, True, podogrev_res)
                    applied_energy = podogrev_res.get("appliedEnergy", 0)
                    logger.info(f"Подогревы собраны: добавлено энергии {applied_energy}")
                    if applied_energy > 0:
                        await DropParser.save_notification(
                            self.account_id,
                            DropParser.parse_other(
                                "Подогревы от друзей",
                                f"+{applied_energy} энергии",
                                rewards=[{"currency": "energy", "label": "Энергия", "amount": applied_energy}],
                            ),
                            self.db_engine,
                        )
                except Exception as e:
                    logger.error(f"Ошибка при сборе подогревов: {e}")
                    results["errors"].append(f"collect_podogrev: {str(e)}")
                    await self._log_action("collect_podogrev", "/api/podogrev/collect/all", 500, False, {"error": str(e)})

        # 5.1. Отправка бесплатных подогревов друзьям
        if getattr(config, "auto_podogrev_send", False):
            pod_sent_res = await self.send_podogrev_if_ready(config=config)
            if pod_sent_res.get("sent", 0) > 0:
                results["podogrev_sent"] = True
            if pod_sent_res.get("error"):
                results["errors"].append(f"send_podogrev: {pod_sent_res['error']}")

        # 5.2. Бесплатная суточная партия у Каталы (1-в-1 по правилам игры с шульмовками)
        if getattr(config, "auto_katala", False):
            katala_res = await self.play_katala_if_ready(config=config)
            if katala_res.get("success"):
                results["katala_played"] = True
            elif katala_res.get("error"):
                results["errors"].append(f"katala_game: {katala_res['error']}")

        # 5.3. Авто-взаимодействия (Качать бицуху, Плевать в баланду, Кидать дрожжи до лимита)
        if (
            getattr(config, "auto_biceps", False)
            or getattr(config, "auto_spit_balanda", False)
            or getattr(config, "auto_throw_yeast", False)
        ):
            inter_res = await self.process_auto_interactions(
                config=config,
                player_data=player_data if "player_data" in locals() and isinstance(player_data, dict) else None,
            )
            results["auto_interactions"] = inter_res

        # 5.4. Месячные делюги — выполнение дневного негативного квеста и автосбор тиров
        if getattr(config, "auto_monthly_tasks", False) or getattr(config, "auto_events", False):
            mq_res = await self.process_monthly_quests(
                config=config,
                player_data=player_data if "player_data" in locals() and isinstance(player_data, dict) else None,
            )
            results["monthly_actions_done"] += int(mq_res.get("actions_performed", 0))
            results["monthly_tiers_claimed"] += int(mq_res.get("tiers_claimed", 0))
            results["errors"].extend(mq_res.get("errors") or [])

        # 5.5. Проверка приезда Менялы (не чаще раза в 5 минут, уведомление Web+TG 1 раз за цикл)
        now_mono = asyncio.get_event_loop().time()
        if (now_mono - self._last_menyala_check_ts) >= 300.0 and getattr(self.api, "http", None) is not None:
            self._last_menyala_check_ts = now_mono
            try:
                from client.api.menyala import MenyalaAPI, check_and_notify_menyala_arrival
                m_api = MenyalaAPI(self.api.http)
                results["menyala"] = await check_and_notify_menyala_arrival(
                    account_id=self.account_id,
                    menyala_api=m_api,
                    db_engine=self.db_engine,
                    notifier=self.notifier,
                )
            except Exception as me:
                logger.debug("Menyala check skipped: %s", me)

        await self._jitter()

        # 6. Кольщик (автопокупка наколок за туалетную бумагу или рубли)
        if getattr(config, "auto_kolsik", False):
            currency = str(getattr(config, "kolsik_currency", "paper")).lower().strip()
            cur_balance = int(currencies.get(currency, 0)) if "currencies" in locals() and isinstance(currencies, dict) else 0
            cost = 15
            if cur_balance >= cost:
                try:
                    kolsik_res = await self.api.roll_kolsik(currency)
                    results["kolsik_rolled"] = True
                    endpoint = "/api/kolsik/roll" if currency == "rubles" else "/api/kolsik/roll-paper"
                    await self._log_action("kolsik_roll", endpoint, 200, True, kolsik_res)
                    await DropParser.save_notification(
                        self.account_id,
                        DropParser.parse_kolsik_roll(kolsik_res, currency),
                        self.db_engine,
                    )
                    logger.info("Успешно набита наколка у Кольщика за %s: %s", currency, kolsik_res)
                except httpx.HTTPStatusError as err:
                    status_code = err.response.status_code
                    logger.warning("Кольщик отклонил покупку (HTTP %s): %s", status_code, err.response.text)
                    results["errors"].append(f"roll_kolsik (HTTP {status_code})")
                    endpoint = "/api/kolsik/roll" if currency == "rubles" else "/api/kolsik/roll-paper"
                    await self._log_action("kolsik_roll", endpoint, status_code, False, {"error": err.response.text})
                except Exception as ke:
                    logger.warning("Ошибка при автопрокрутке кольщика: %s", ke)
                    results["errors"].append(f"roll_kolsik: {str(ke)}")
            else:
                logger.info(
                    "Недостаточно средств для Кольщика (%s: %s при стоимости %s). Пропуск.",
                    currency, cur_balance, cost
                )

        # 7. Уведомление владельца при наличии сборов
        if self.notifier is not None:
            applied_energy = podogrev_res.get("appliedEnergy", 0) if results["podogrev_collected"] and "podogrev_res" in locals() and isinstance(podogrev_res, dict) else 0
            kolsik_info = results.get("kolsik_rolled", False)
            if results["toilet_paper_claimed"] or results["business_collected"] or applied_energy > 0 or kolsik_info:
                lines = ["📦 <b>Рутинные сборы:</b>"]
                if results["toilet_paper_claimed"]:
                    lines.append("🧻 Собрана ежедневная туалетная бумага")
                if results["business_collected"]:
                    lines.append("💼 Собрана прибыль с бизнесов")
                if applied_energy > 0:
                    lines.append(f"⚡️ Подогревы от друзей: +{applied_energy} энергии")
                if kolsik_info:
                    lines.append("🎨 Набита новая татуировка у Кольщика")
                await self.notifier.notify("\n".join(lines))

        # 8. Если получена энергия из подогревов или рулона - сразу триггерим PrisonWorker для мгновенного слива энергии
        if (results["toilet_paper_claimed"] or (results["podogrev_collected"] and "applied_energy" in locals() and applied_energy > 0)) and self.prison_worker:
            asyncio.create_task(self.prison_worker.run_cycle())

        logger.info(f"=== [Аккаунт {self.account_id}] Цикл рутинных задач завершен ===")
        return results

    async def _get_social_api(self) -> Optional[Any]:
        if self.social_api is not None:
            return self.social_api
        http = getattr(self.api, "http", None)
        if http is not None:
            from client.api.social import SocialAPI
            self.social_api = SocialAPI(http_client=http)
            return self.social_api
        return None

    async def process_monthly_quests(
        self,
        config: Optional[Any] = None,
        player_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Обрабатывает активное ежедневное задание Месячных делюг (в т.ч. негативные действия на друзьях:
        StressVictim -> Fight, SpitSoup -> Harknut, AddYeast -> TossDroj) и собирает доступные тиры наград.
        Друзья выбираются от самого низкого авторитета вверх; выполняется ровно remaining = target - current раз.
        """
        summary: Dict[str, Any] = {
            "actions_performed": 0,
            "tiers_claimed": 0,
            "quest_action": None,
            "errors": [],
        }
        try:
            m_state = await self.api.get_monthly_state(track_open=True)
        except Exception as e:
            logger.warning(f"Ошибка проверки месячных делюг: {e}")
            summary["errors"].append(f"monthly_state: {e}")
            return summary

        if not isinstance(m_state, dict):
            return summary

        user_m = m_state.get("user", {}) or {}
        global_m = m_state.get("global", {}) or {}
        active_day_id = user_m.get("activeDayId")
        days_defs = global_m.get("days") or []
        user_days = user_m.get("days") or {}

        today_quest = next((d for d in days_defs if isinstance(d, dict) and d.get("dayId") == active_day_id), None)
        if today_quest:
            action_key = str(today_quest.get("action") or "")
            summary["quest_action"] = action_key
            day_prog = user_days.get(str(active_day_id)) or user_days.get(active_day_id) or {}
            is_completed = bool(day_prog.get("completed", False))
            current_prog = int(day_prog.get("progress") or 0)
            target_cnt = int(today_quest.get("target") or 0)
            remaining = max(0, target_cnt - current_prog)

            if not is_completed and remaining > 0 and action_key in NEGATIVE_QUEST_ACTIONS:
                spec = NEGATIVE_QUEST_ACTIONS[action_key]
                cigs_cost = int(spec["cigs_cost"])
                inter_type = str(spec["interaction_type"])

                p_data = player_data
                if not isinstance(p_data, dict) or not (p_data.get("userId") or p_data.get("id")):
                    try:
                        p_data = await self.api.init_player()
                    except Exception as pe:
                        logger.warning(f"Не удалось получить профиль для месячного квеста {action_key}: {pe}")
                        p_data = {}

                from_user_id = int(p_data.get("userId") or p_data.get("id") or 0)
                cigs = int((p_data.get("currencies") or {}).get("cigarettes", 0))

                if cigs_cost > 0 and cigs < cigs_cost:
                    summary["skipped_reason"] = f"недостаточно папирос ({cigs} < {cigs_cost})"
                    logger.info(
                        "Пропуск месячного задания %s: недостаточно папирос (%s < %s).",
                        action_key, cigs, cigs_cost,
                    )
                elif from_user_id > 0:
                    s_api = await self._get_social_api()
                    friends: list = []
                    if s_api is not None:
                        try:
                            if hasattr(s_api, "get_all_friend_profiles"):
                                friends = await s_api.get_all_friend_profiles()
                            elif hasattr(s_api, "get_friends_list"):
                                fl = await s_api.get_friends_list()
                                friends = fl.get("friends", []) if isinstance(fl, dict) else (fl if isinstance(fl, list) else [])
                        except Exception as fe:
                            logger.warning(f"Ошибка загрузки списка друзей для месячного квеста: {fe}")

                    # Сортируем от самых слабых (минимальный бицепс, затем авторитет) для гарантированных побед в Fight
                    sorted_friends = sorted(
                        [f for f in friends if isinstance(f, dict) and (f.get("userId") or f.get("id"))],
                        key=lambda f: (int(f.get("biceps") if f.get("biceps") is not None else 999999), int(f.get("authority") or 0)),
                    )

                    for fr in sorted_friends:
                        if remaining <= 0:
                            break
                        if cigs_cost > 0 and cigs < cigs_cost:
                            summary["skipped_reason"] = f"недостаточно папирос ({cigs} < {cigs_cost})"
                            logger.info("Папиросы закончились (%s < %s) во время выполнения %s.", cigs, cigs_cost, action_key)
                            break

                        to_uid = int(fr.get("userId") or fr.get("id"))
                        if to_uid == from_user_id:
                            continue

                        try:
                            act_res = await s_api.perform_interaction(from_user_id, to_uid, inter_type)
                            if isinstance(act_res, dict) and act_res.get("success", True):
                                if cigs_cost > 0:
                                    cigs -= cigs_cost
                                msg_lower = str(act_res.get("message") or "").lower()
                                is_loss = inter_type == "Fight" and ("проиграл" in msg_lower) and ("победил" not in msg_lower)
                                if is_loss:
                                    logger.debug("Бой с %s проигран (%s), пробуем следующего слабого друга.", to_uid, act_res.get("message"))
                                    await self._jitter()
                                    continue
                                summary["actions_performed"] += 1
                                remaining -= 1
                                await self._log_action(
                                    "monthly_quest_action",
                                    "/api/interaction/perform",
                                    200,
                                    True,
                                    {
                                        "quest": action_key,
                                        "type": inter_type,
                                        "toUserId": to_uid,
                                        "remaining": remaining,
                                    },
                                )
                                await self._jitter()
                        except Exception as ie:
                            # На дневном откате / ошибке у конкретного друга просто переходим к следующему слабому другу
                            logger.debug("Не удалось применить %s к %s: %s", inter_type, to_uid, ie)
                            continue

                    if summary["actions_performed"] > 0:
                        if self.db_engine:
                            await DropParser.save_notification(
                                self.account_id,
                                DropParser.parse_other(
                                    f"Месячная делюга: {spec['title']}",
                                    f"Выполнено действий: {summary['actions_performed']} (день {active_day_id})",
                                    rewards=[],
                                ),
                                self.db_engine,
                            )
                        try:
                            m_state = await self.api.get_monthly_state(track_open=True)
                            user_m = m_state.get("user", {}) or {}
                        except Exception:
                            pass

        claimable_tiers = user_m.get("claimableTiers", []) or []
        for tier in claimable_tiers:
            try:
                c_res = await self.api.claim_monthly_tier(tier)
                if c_res.get("success", True):
                    summary["tiers_claimed"] += 1
                    await self._log_action("monthly_claim", "/api/monthly/claim", 200, True, c_res)
                    logger.info(f"Собран тир {tier} месячных делюг: {c_res}")
            except Exception as te:
                logger.warning(f"Ошибка сбора тира {tier} месячных делюг: {te}")
                summary["errors"].append(f"monthly_claim_{tier}: {te}")

        return summary

    async def claim_daily_toilet_paper_if_ready(self) -> Dict[str, Any]:
        """
        Целевой триггер проверки и сбора ежедневной туалетной бумаги (вызывается по расписанию 00:01 МСК).
        """
        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config) or not getattr(config, "auto_toilet_paper", False):
            return {"status": "skipped", "reason": "disabled_or_paused"}

        try:
            player_data = await self.api.init_player()
            can_claim = bool(player_data.get("canClaimToiletPaper", False))
            if not can_claim:
                return {"status": "already_claimed"}

            paper_res = await self.api.claim_toilet_paper()
            if not isinstance(paper_res, dict) or not paper_res.get("success", True):
                return {"status": "rejected", "result": paper_res}

            await self._log_action("claim_toilet_paper", "/api/daily/toilet-paper", 200, True, paper_res)
            await DropParser.save_notification(
                self.account_id,
                DropParser.parse_other(
                    "Ежедневная бумага",
                    "Сбор рулона",
                    rewards=[{"currency": "paper", "label": "Бумага", "amount": 1}],
                ),
                self.db_engine,
            )
            logger.info(f"[00:01 МСК] Туалетная бумага успешно собрана! Баланс: {paper_res.get('balance')}")
            if self.prison_worker:
                asyncio.create_task(self.prison_worker.run_cycle())
            return {"status": "claimed", "result": paper_res}
        except Exception as e:
            logger.warning(f"Ошибка при плановом сборе туалетной бумаги: {e}")
            return {"status": "error", "error": str(e)}
