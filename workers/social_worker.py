import random
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set

from sqlalchemy import select, or_, and_

from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active
from core.models import (
    ActionLog,
    SentFriendRequest,
    TrackedCandidate,
    FriendStats,
    BossFriendDamageLog,
    FriendsCountSnapshot,
    BotConfig,
)
from client.api.social import SocialAPI
from bot.notifier import TelegramNotifier
from core.drop_parser import DropParser

logger = logging.getLogger(__name__)


class SocialWorker:
    """
    Воркер социальных действий и игровых событий:
    1. Синхронизация текущих друзей, счетчик FriendsCountSnapshot и FriendStats.
    2. Сверка статуса отправленных заявок SentFriendRequest (accepted / ignored).
    3. Автоматический сбор входящих посылок/подарков (auto_gifts) — СТРОГО БЕЗ отправки подарков.
    4. Автоматическое принятие входящих заявок в друзья (auto_friends) с поддержкой filter_mode ("and" / "or").
    5. Сбор доступных наград ежемесячного календаря и событий (auto_events).
    6. Фоновый срез кандидатов (weekly-top, achievements, news, guilds) и приоритетный авто-набор (auto_friend_outreach).
    7. Безопасная очистка неактивных друзей (cleanup_inactive_friends).
    """

    def __init__(
        self,
        account_id: int,
        social_api: SocialAPI,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
    ):
        self.account_id = account_id
        self.api = social_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.raids_api: Optional[Any] = None
        self._last_bg_guild_scan: float = 0.0
        self._friend_req_lock: asyncio.Lock = asyncio.Lock()

    async def _jitter(self, min_sec: Optional[float] = None, max_sec: Optional[float] = None) -> None:
        if self.enable_jitter:
            low = min_sec if min_sec is not None else settings.JITTER_MIN_SEC
            high = max_sec if max_sec is not None else settings.JITTER_MAX_SEC
            delay = random.uniform(low, high)
            await asyncio.sleep(delay)

    async def _log_action(
        self,
        action_type: str,
        endpoint: str,
        status_code: int = 200,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.db_engine:
            return
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
                await session.commit()
        except Exception as e:
            logger.error("Ошибка сохранения ActionLog для социалки: %s", e)

    async def cleanup_inactive_friends(
        self,
        config: Optional[Any] = None,
        max_removals: Optional[int] = None,
    ) -> int:
        """
        Безопасная чистка неактивных друзей:
        - Кандидаты: is_current_friend == True, is_whitelisted == False,
          total_damage_to_my_bosses <= 0, damage_7d == 0,
          (now - last_active_at).days >= inactive_days,
          (now - first_seen_at).days >= inactive_days (не удалять новичков!).
        - Сортировка: total_damage_to_my_bosses ASC, (poison + gunshot + knife) ASC, last_active_at ASC.
        - Суточный лимит: min(config.friend_cleanup_daily_limit, 15) за последние 24ч по ActionLog("friend_remove").
        - Пауза jitter 2.0-4.0с, логирование в ActionLog.
        """
        if not self.db_engine:
            return 0

        if config is None:
            config = await get_or_create_config(self.account_id, self.db_engine)

        inactive_days = getattr(config, "friend_cleanup_inactive_days", 14) or 14
        daily_limit = min(getattr(config, "friend_cleanup_daily_limit", 5) or 5, 15)

        now = datetime.utcnow()
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)

        async with get_session(self.db_engine) as session:
            # Подсчет удаленных за последние 24ч
            action_stmt = select(ActionLog).where(
                ActionLog.account_id == self.account_id,
                ActionLog.action_type == "friend_remove",
                ActionLog.created_at >= day_ago,
                ActionLog.success == True,
            )
            removed_24h = len((await session.execute(action_stmt)).scalars().all())
            budget = max(0, daily_limit - removed_24h)
            if max_removals is not None:
                budget = min(budget, max_removals)

            if budget <= 0:
                logger.info("Суточный лимит удаления неактивных друзей исчерпан (%d/%d)", removed_24h, daily_limit)
                return 0

            # Выборка кандидатов из FriendStats
            stmt = select(FriendStats).where(
                FriendStats.account_id == self.account_id,
                FriendStats.is_current_friend == True,
                FriendStats.is_whitelisted == False,
                FriendStats.total_damage_to_my_bosses <= 0,
            )
            all_candidates = (await session.execute(stmt)).scalars().all()

            eligible_candidates = []
            for cand in all_candidates:
                # Проверка возраста добавления (не удалять новичков)
                if cand.first_seen_at and (now - cand.first_seen_at).days < inactive_days:
                    continue
                # Проверка давности последней активности
                if cand.last_active_at and (now - cand.last_active_at).days < inactive_days:
                    continue

                # Проверка урона за последние 7 дней в BossFriendDamageLog
                dmg_stmt = select(BossFriendDamageLog).where(
                    BossFriendDamageLog.account_id == self.account_id,
                    BossFriendDamageLog.user_id == cand.user_id,
                    BossFriendDamageLog.updated_at >= week_ago,
                    BossFriendDamageLog.recorded_damage > 0,
                )
                recent_logs = (await session.execute(dmg_stmt)).scalars().all()
                if recent_logs:
                    continue

                eligible_candidates.append(cand)

            # Сортировка по приоритету на кик
            eligible_candidates.sort(
                key=lambda c: (
                    c.total_damage_to_my_bosses or 0,
                    (c.poison_damage or 0) + (c.gunshot_damage or 0) + (c.knife_damage or 0),
                    c.last_active_at or datetime.min,
                )
            )

            candidates_to_remove = eligible_candidates[:budget]

        if not candidates_to_remove:
            return 0

        removed_count = 0
        for cand in candidates_to_remove:
            uid = int(cand.user_id)
            nick = cand.nickname or f"Кореш {uid}"

            if self.enable_jitter:
                await asyncio.sleep(random.uniform(2.0, 4.0))

            try:
                res = await self.api.remove_friend(uid)
                is_ok = bool(res.get("success", True)) if isinstance(res, dict) else True
                if is_ok:
                    removed_count += 1
                    async with get_session(self.db_engine) as session:
                        upd_stmt = select(FriendStats).where(
                            FriendStats.account_id == self.account_id,
                            FriendStats.user_id == uid,
                        )
                        fs_obj = (await session.execute(upd_stmt)).scalar_one_or_none()
                        if fs_obj:
                            fs_obj.is_current_friend = False
                            fs_obj.updated_at = datetime.utcnow()
                        await session.commit()

                    await self._log_action(
                        "friend_remove",
                        f"/api/friendship/remove-friend?friendUserId={uid}",
                        200,
                        True,
                        {"userId": uid, "nickname": nick, "reason": "inactive_cleanup"},
                    )
                    logger.info("Удален неактивный друг %s (%s)", uid, nick)
            except Exception as e:
                logger.warning("Ошибка при удалении друга %s: %s", uid, e)
                await self._log_action(
                    "friend_remove",
                    f"/api/friendship/remove-friend?friendUserId={uid}",
                    500,
                    False,
                    {"userId": uid, "nickname": nick, "error": str(e)},
                )

        return removed_count

    async def check_incoming_friend_requests(self, config: Optional[Any] = None) -> Dict[str, Any]:
        """
        Быстрая проверка и обработка входящих заявок в друзья (с защитой asyncio.Lock).
        После принятия/отклонения немедленно обновляет StateHub и пушит social_updated/domain_sync в UI.
        """
        async with self._friend_req_lock:
            if config is None:
                config = await get_or_create_config(self.account_id, self.db_engine)
            if not is_worker_active(config):
                return {"status": "skipped", "reason": "paused_or_sleep", "accepted": 0, "declined": 0}
            if not getattr(config, "auto_friends", False):
                return {"status": "skipped", "reason": "auto_friends_disabled", "accepted": 0, "declined": 0}

            accepted_ids: List[int] = []
            rejected_ids: List[int] = []
            try:
                raw_enriched = None
                if hasattr(self.api, "get_enriched_friend_requests"):
                    res_enr = await self.api.get_enriched_friend_requests()
                    if isinstance(res_enr, list):
                        raw_enriched = res_enr

                if raw_enriched is not None:
                    req_list = raw_enriched
                else:
                    reqs = await self.api.get_friend_requests()
                    req_list = reqs if isinstance(reqs, list) else reqs.get("requests", []) if isinstance(reqs, dict) else []

                accept_all = getattr(config, "friend_accept_all", False)
                filter_mode = getattr(config, "friend_filter_mode", "and")
                min_lvl = getattr(config, "friend_min_level", 0)
                min_auth = getattr(config, "friend_min_authority", 0)
                min_bic = getattr(config, "friend_min_biceps", 0)
                min_tal = getattr(config, "friend_min_talents", 0)
                min_poi = getattr(config, "friend_min_poison_damage", 0)
                min_tot = getattr(config, "friend_min_total_damage", 0)
                auto_decline = getattr(config, "friend_auto_decline_below", False)

                for r in req_list:
                    if not isinstance(r, dict):
                        continue
                    f_id = r.get("userId") or r.get("fromUserId")
                    if not f_id:
                        continue
                    f_uid = int(f_id)

                    lvl = int(r.get("level") or r.get("lvl") or 0)
                    auth = int(r.get("authority", 0) or 0)
                    bic_raw = r.get("biceps")
                    bic = int(bic_raw) if bic_raw is not None else None
                    biceps_pass = (bic >= min_bic) if bic is not None else (min_bic == 0)
                    tal = int(r.get("talents") or r.get("talentsCount") or r.get("TalentsCount") or 0)

                    wep_dmg = r.get("weaponDamage") or r.get("WeaponDamage") or {}
                    poi_dmg = int(r.get("poisonDamage") or wep_dmg.get("poison") or wep_dmg.get("Poison", 0) or 0)
                    gun_dmg = int(wep_dmg.get("gunshot") or wep_dmg.get("Gunshot", 0) or 0)
                    kni_dmg = int(wep_dmg.get("knife") or wep_dmg.get("Knife", 0) or 0)
                    tot_dmg = int(r.get("totalDamage") or (poi_dmg + gun_dmg + kni_dmg) or 0)

                    if accept_all:
                        passes = True
                    elif filter_mode == "or":
                        has_any_threshold = (
                            min_lvl > 0 or min_auth > 0 or min_bic > 0 or
                            min_tal > 0 or min_poi > 0 or min_tot > 0
                        )
                        if not has_any_threshold:
                            passes = True
                        else:
                            passes = (
                                (min_lvl > 0 and lvl >= min_lvl) or
                                (min_auth > 0 and auth >= min_auth) or
                                (min_bic > 0 and bic is not None and bic >= min_bic) or
                                (min_tal > 0 and tal >= min_tal) or
                                (min_poi > 0 and poi_dmg >= min_poi) or
                                (min_tot > 0 and tot_dmg >= min_tot)
                            )
                    else:
                        passes = (
                            lvl >= min_lvl and
                            auth >= min_auth and
                            biceps_pass and
                            tal >= min_tal and
                            poi_dmg >= min_poi and
                            tot_dmg >= min_tot
                        )

                    if passes:
                        try:
                            await self.api.accept_friend(f_uid)
                            accepted_ids.append(f_uid)
                            await self._log_action("accept_friend", "/api/friendship/accept-request", 200, True, {
                                "fromUserId": f_uid, "nickname": r.get("nickname"), "talents": tal, "poisonDamage": poi_dmg
                            })
                            await self._jitter()
                        except Exception as fe:
                            logger.warning("Ошибка принятия друга %s: %s", f_uid, fe)
                    elif auto_decline:
                        try:
                            await self.api.decline_friend(f_uid)
                            rejected_ids.append(f_uid)
                            await self._log_action("decline_friend", "/api/friendship/decline-request", 200, True, {
                                "fromUserId": f_uid, "nickname": r.get("nickname"), "talents": tal
                            })
                            await self._jitter()
                        except Exception as de:
                            logger.warning("Ошибка отклонения друга %s: %s", f_uid, de)

                processed = set(accepted_ids) | set(rejected_ids)
                remaining = [
                    r for r in req_list
                    if isinstance(r, dict) and int(r.get("userId") or r.get("fromUserId") or 0) not in processed
                ]

                try:
                    from core.state_hub import state_hub
                    state_hub.update_slice(
                        self.account_id,
                        "friend_requests",
                        {"success": True, "requests": remaining, "total": len(remaining)},
                    )
                    if accepted_ids:
                        state_hub.invalidate_slice(self.account_id, "friends")
                    if processed:
                        state_hub.emit_change(
                            self.account_id,
                            ["social"],
                            patch={
                                "social": {
                                    "incoming_requests": remaining,
                                    "incoming_count": len(remaining),
                                    "accepted_ids": accepted_ids,
                                    "rejected_ids": rejected_ids,
                                }
                            },
                            reason="auto_friend_requests",
                        )
                except Exception as hub_err:
                    logger.debug("check_incoming_friend_requests hub sync error: %s", hub_err)

                return {
                    "status": "ok",
                    "accepted": len(accepted_ids),
                    "declined": len(rejected_ids),
                    "remaining": len(remaining),
                }
            except Exception as e:
                logger.error("Ошибка получения заявок в друзья: %s", e)
                return {"status": "error", "error": str(e), "accepted": len(accepted_ids), "declined": len(rejected_ids)}

    async def run_cycle(self) -> Dict[str, Any]:
        """Один цикл выполнения социальных активностей."""
        logger.info(f"=== [Аккаунт {self.account_id}] Запуск цикла социальных активностей ===")

        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            logger.info("Планировщик на паузе или активен режим сна. Пропуск социалки.")
            return {"status": "skipped", "reason": "paused_or_sleep"}

        results: Dict[str, Any] = {
            "account_id": self.account_id,
            "gifts_claimed": 0,
            "friends_accepted": 0,
            "monthly_claimed": False,
            "outreach_sent": 0,
            "errors": [],
        }

        # 1. Синхронизация текущих друзей, замер FriendsCountSnapshot и сверка SentFriendRequest
        current_friend_ids: Set[int] = set()
        profiles_by_id: Dict[int, Dict[str, Any]] = {}

        try:
            if hasattr(self.api, "get_all_friend_profiles"):
                raw_profiles = await self.api.get_all_friend_profiles()
                if isinstance(raw_profiles, list):
                    for p in raw_profiles:
                        if isinstance(p, dict):
                            uid = p.get("userId") or p.get("id")
                            if uid:
                                try:
                                    uid_int = int(uid)
                                    current_friend_ids.add(uid_int)
                                    profiles_by_id[uid_int] = p
                                except (ValueError, TypeError):
                                    pass
        except Exception as e:
            logger.debug("get_all_friend_profiles error: %s", e)

        if not current_friend_ids and hasattr(self.api, "get_all_friend_ids"):
            try:
                ids_res = await self.api.get_all_friend_ids()
                if isinstance(ids_res, (set, list)):
                    for uid in ids_res:
                        try:
                            current_friend_ids.add(int(uid))
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                logger.debug("get_all_friend_ids error: %s", e)

        if not current_friend_ids and hasattr(self.api, "get_friends_list"):
            try:
                f_list = await self.api.get_friends_list()
                raw_f = f_list if isinstance(f_list, list) else f_list.get("friends", []) if isinstance(f_list, dict) else []
                for f in raw_f:
                    if isinstance(f, dict):
                        fid = f.get("userId") or f.get("id")
                        if fid:
                            try:
                                current_friend_ids.add(int(fid))
                            except (ValueError, TypeError):
                                pass
                    elif isinstance(f, (int, str)):
                        try:
                            current_friend_ids.add(int(f))
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                logger.debug("get_friends_list error: %s", e)

        if self.db_engine:
            now = datetime.utcnow()
            total_friends = len(current_friend_ids)

            try:
                async with get_session(self.db_engine) as session:
                    # 1.1 Замер FriendsCountSnapshot (раз в 60 мин или при изменении счетчика)
                    last_snap_stmt = select(FriendsCountSnapshot).where(
                        FriendsCountSnapshot.account_id == self.account_id
                    ).order_by(FriendsCountSnapshot.created_at.desc()).limit(1)
                    last_snap = (await session.execute(last_snap_stmt)).scalar_one_or_none()

                    should_record_snapshot = False
                    if last_snap is None:
                        should_record_snapshot = True
                    elif (now - last_snap.created_at).total_seconds() >= 3600 or last_snap.friends_count != total_friends:
                        should_record_snapshot = True

                    if should_record_snapshot and total_friends > 0:
                        snap = FriendsCountSnapshot(
                            account_id=self.account_id,
                            friends_count=total_friends,
                            created_at=now,
                        )
                        session.add(snap)

                    # 1.2 Синхронизация FriendStats
                    existing_stats_stmt = select(FriendStats).where(FriendStats.account_id == self.account_id)
                    existing_stats = (await session.execute(existing_stats_stmt)).scalars().all()
                    stats_map = {s.user_id: s for s in existing_stats}

                    for uid in current_friend_ids:
                        p = profiles_by_id.get(uid, {})
                        nick = p.get("nickname") or p.get("name")
                        photo = p.get("photoUrl") or p.get("avatarUrl") or p.get("photo")
                        lvl = int(p.get("level") or p.get("lvl") or 0)
                        auth = int(p.get("authority") or 0)
                        bic_raw = p.get("biceps")
                        bic = int(bic_raw) if bic_raw is not None else 0
                        tal = int(p.get("talents") or p.get("talentsCount") or p.get("TalentsCount") or 0)
                        wep = p.get("weaponDamage") or p.get("WeaponDamage") or {}
                        poi = int(wep.get("poison") or wep.get("Poison") or p.get("poisonDamage") or 0)
                        gun = int(wep.get("gunshot") or wep.get("Gunshot") or p.get("gunshotDamage") or 0)
                        kni = int(wep.get("knife") or wep.get("Knife") or p.get("knifeDamage") or 0)

                        if uid in stats_map:
                            fs = stats_map[uid]
                            fs.is_current_friend = True
                            if nick:
                                fs.nickname = nick
                            if photo:
                                fs.photo_url = photo
                            if lvl > 0:
                                fs.level = lvl
                            if bic > 0:
                                fs.biceps = bic
                            if tal > 0:
                                fs.talents = tal
                            if poi > 0:
                                fs.poison_damage = poi
                            if gun > 0:
                                fs.gunshot_damage = gun
                            if kni > 0:
                                fs.knife_damage = kni
                            if auth > fs.authority:
                                fs.last_active_at = now
                                fs.prev_authority = fs.authority
                                fs.authority = auth
                            elif auth > 0 and fs.authority == 0:
                                fs.authority = auth
                                fs.prev_authority = auth
                            fs.updated_at = now
                        else:
                            fs = FriendStats(
                                account_id=self.account_id,
                                user_id=uid,
                                nickname=nick,
                                photo_url=photo,
                                level=lvl,
                                authority=auth,
                                prev_authority=auth,
                                biceps=bic,
                                talents=tal,
                                poison_damage=poi,
                                gunshot_damage=gun,
                                knife_damage=kni,
                                total_damage_to_my_bosses=0,
                                boss_hits_count=0,
                                last_active_at=now,
                                is_whitelisted=False,
                                is_current_friend=True,
                                first_seen_at=now,
                                updated_at=now,
                            )
                            session.add(fs)

                    # Помечаем отсутствующих друзей
                    for uid, fs in stats_map.items():
                        if uid not in current_friend_ids and fs.is_current_friend:
                            fs.is_current_friend = False
                            fs.updated_at = now

                    # 1.3 Сверка SentFriendRequest(status="sent")
                    pending_reqs_stmt = select(SentFriendRequest).where(
                        SentFriendRequest.account_id == self.account_id,
                        SentFriendRequest.status == "sent",
                    )
                    pending_reqs = (await session.execute(pending_reqs_stmt)).scalars().all()
                    for req in pending_reqs:
                        if req.target_user_id in current_friend_ids:
                            req.status = "accepted"
                            req.resolved_at = now
                        elif (now - req.created_at).total_seconds() > 72 * 3600:
                            req.status = "ignored"
                            req.resolved_at = now

                    await session.commit()
            except Exception as se:
                logger.error("Ошибка синхронизации FriendStats/Snapshots: %s", se)

        # 2. Сбор входящих посылок / подарков (СТРОГО БЕЗ ОТПРАВКИ ПОДАРКОВ)
        if getattr(config, "auto_gifts", False):
            try:
                inbox = await self.api.get_gifts_inbox()
                gifts_list = inbox.get("gifts", []) if isinstance(inbox, dict) else (inbox if isinstance(inbox, list) else [])
                for g in gifts_list:
                    if not isinstance(g, dict):
                        continue
                    g_id = g.get("id")
                    if g_id:
                        try:
                            claim_res = await self.api.claim_gift(g_id)
                            results["gifts_claimed"] += 1
                            await self._log_action("claim_gift", "/api/gifts/claim", 200, True, {"giftId": g_id})
                            await DropParser.save_notification(
                                self.account_id,
                                DropParser.parse_other(
                                    "Посылка от кореша",
                                    f"Получен подарок от игрока {g.get('fromUserId', 'друга')}",
                                ),
                                self.db_engine,
                            )
                            await self._jitter()
                        except Exception as ge:
                            logger.warning("Ошибка сбора подарка %s: %s", g_id, ge)
            except Exception as e:
                logger.error("Ошибка получения входящих подарков: %s", e)
                results["errors"].append(f"gifts: {e}")

        # 3. Обработка входящих заявок в друзья
        fr_res = await self.check_incoming_friend_requests(config=config)
        results["friends_accepted"] += fr_res.get("accepted", 0)
        if fr_res.get("declined", 0) > 0:
            results["friends_declined"] = results.get("friends_declined", 0) + fr_res["declined"]
        if fr_res.get("error"):
            results["errors"].append(f"friends: {fr_res['error']}")

        # 4. Месячные делюги
        if getattr(config, "auto_events", False):
            try:
                monthly = await self.api.get_monthly_state()
                claimable_tiers = (
                    monthly.get("user", {}).get("claimableTiers", [])
                    if isinstance(monthly.get("user"), dict)
                    else monthly.get("claimableTiers", [])
                )
                if not claimable_tiers:
                    ready_tier = monthly.get("readyTier") or monthly.get("canClaimTier")
                    if ready_tier is not None:
                        claimable_tiers = [ready_tier]

                for tier in claimable_tiers:
                    try:
                        m_res = await self.api.claim_monthly_reward(int(tier))
                        results["monthly_claimed"] = True
                        await self._log_action("claim_monthly", "/api/monthly/claim", 200, True, m_res)
                        await DropParser.save_notification(
                            self.account_id,
                            DropParser.parse_monthly_claim(m_res, tier),
                            self.db_engine,
                        )
                        await self._jitter()
                    except Exception as me:
                        logger.warning("Ошибка сбора награды месячных делюг: %s", me)
            except Exception as e:
                logger.error("Ошибка проверки месячных делюг: %s", e)
                results["errors"].append(f"monthly: {e}")

        # 5. Фоновый срез кандидатов и авто-набор друзей (auto_friend_outreach)
        if getattr(config, "auto_friend_outreach", False):
            if not self.raids_api:
                from client.api.raids import RaidsAPI
                self.raids_api = RaidsAPI()

            # 5.1 Синхронизация weekly-top и ачивок
            try:
                await self.raids_api.sync_weekly_top_and_achievements(
                    social_api=self.api,
                    db_engine=self.db_engine,
                    account_id=self.account_id,
                )
            except Exception as te:
                logger.warning("Ошибка синхронизации еженедельного топа и ачивок: %s", te)

            # 5.2 Автопарсинг новостей
            if getattr(config, "auto_parse_news_raids", False):
                try:
                    await self.raids_api.scan_news_for_candidates(
                        game_http_client=self.api.http,
                        db_engine=self.db_engine,
                        account_id=self.account_id,
                    )
                except Exception as ne:
                    logger.warning("Ошибка парсинга новостей: %s", ne)

            # 5.3 Фоновый срез бригад (раз в 6 часов)
            now_ts = time.time()
            if now_ts - self._last_bg_guild_scan >= 6 * 3600:
                try:
                    await self.raids_api.scan_active_guilds(
                        social_api=self.api,
                        db_engine=self.db_engine,
                        account_id=self.account_id,
                        max_guilds=6,
                        delay_range=(1.5, 3.0) if self.enable_jitter else (0.0, 0.0),
                        force=False,
                        tier=getattr(config, "friends_parser_tier", "accessible") or "accessible",
                        min_authority=int(getattr(config, "friends_parser_min_authority", 0) or 0),
                        max_authority=int(getattr(config, "friends_parser_max_authority", 0) or 0),
                    )
                    self._last_bg_guild_scan = now_ts
                except Exception as ge:
                    logger.warning("Ошибка фонового сканирования бригад: %s", ge)

            # 5.4 Приоритетный авто-набор
            can_send_outreach, remaining_daily, reason = await self.raids_api.rate_guard.can_send(
                self.account_id,
                getattr(config, "friend_outreach_daily_limit", 25),
                self.db_engine,
            )
            if not can_send_outreach:
                logger.info("Фоновый авто-набор пропущен: %s", reason)
            else:
                max_to_send = min(3, remaining_daily)
                if max_to_send > 0 and self.db_engine:
                    min_dmg = getattr(config, "friend_outreach_min_damage", 0)
                    max_dmg = getattr(config, "friend_outreach_max_damage", 0)
                    only_active = getattr(config, "friend_outreach_only_active", True)

                    # Проверяем отправленные ранее
                    sent_ids = set()
                    async with get_session(self.db_engine) as session:
                        s_res = await session.execute(
                            select(SentFriendRequest.target_user_id).where(SentFriendRequest.account_id == self.account_id)
                        )
                        for r in s_res.scalars().all():
                            sent_ids.add(int(r))

                    # Получаем кандидатов через радар (уже отсортированы по score DESC)
                    source_filter = "active" if only_active else "all"
                    cands = await self.raids_api.get_active_players_radar(
                        social_api=self.api,
                        player_api=self.api,
                        db_engine=self.db_engine,
                        account_id=self.account_id,
                        friend_ids=current_friend_ids,
                        sent_user_ids=sent_ids,
                        source=source_filter,
                        min_damage=min_dmg,
                        max_damage=max_dmg,
                        limit=15,
                        exclude_friends=True,
                        tier=getattr(config, "friends_parser_tier", None),
                        min_authority=int(getattr(config, "friends_parser_min_authority", 0) or 0),
                        max_authority=int(getattr(config, "friends_parser_max_authority", 0) or 0),
                    )

                    # Точечное обогащение топ-кандидатов перед отправкой
                    if cands:
                        try:
                            await self.raids_api.enrich_candidates_batch(
                                player_api=self.api,
                                db_engine=self.db_engine,
                                candidates=cands[:10],
                                account_id=self.account_id,
                                max_enrich=10,
                                min_damage=min_dmg,
                                max_damage=max_dmg,
                            )
                        except Exception as ee:
                            logger.debug("Ошибка обогащения кандидатов: %s", ee)

                    candidates_to_invite = []
                    for c in cands:
                        uid_int = int(c["userId"]) if isinstance(c, dict) else int(getattr(c, "user_id", 0))
                        if not uid_int or uid_int in current_friend_ids or uid_int in sent_ids:
                            continue
                        candidates_to_invite.append(c)
                        if len(candidates_to_invite) >= max_to_send:
                            break

                    outreach_sent = 0
                    for c in candidates_to_invite:
                        uid_int = int(c["userId"]) if isinstance(c, dict) else int(getattr(c, "user_id", 0))
                        nick = c.get("nickname") if isinstance(c, dict) else getattr(c, "nickname", f"User {uid_int}")

                        if self.enable_jitter:
                            await asyncio.sleep(random.uniform(1.5, 3.5))

                        try:
                            res = await self.api.send_friend_request(uid_int)
                            is_ok = bool(res.get("success", True)) if isinstance(res, dict) else True
                            msg = res.get("message", "") if isinstance(res, dict) else ""

                            if "лимит" in msg.lower() or "limit" in msg.lower():
                                if getattr(config, "auto_friend_cleanup", False):
                                    cleaned = await self.cleanup_inactive_friends(config=config, max_removals=1)
                                    if cleaned == 0:
                                        self.raids_api.rate_guard.record_friends_limit_reached()
                                        break
                                else:
                                    self.raids_api.rate_guard.record_friends_limit_reached()
                                    break

                            async with get_session(self.db_engine) as session:
                                s_rec = SentFriendRequest(
                                    account_id=self.account_id,
                                    target_user_id=uid_int,
                                    target_nickname=nick,
                                    source="auto_outreach",
                                    status="sent" if is_ok else "failed",
                                )
                                session.add(s_rec)
                                await session.commit()

                            sent_ids.add(uid_int)
                            if is_ok:
                                outreach_sent += 1
                                self.raids_api.rate_guard.record_success()
                                await self._log_action(
                                    "auto_outreach",
                                    f"/api/friendship/send-request?toUserId={uid_int}",
                                    200,
                                    True,
                                    {"userId": uid_int, "nickname": nick},
                                )
                        except Exception as oe:
                            logger.warning(f"Ошибка отправки авто-заявки игроку {uid_int}: %s", oe)
                            err_str = str(oe)
                            if "429" in err_str:
                                self.raids_api.rate_guard.record_error(429)
                                break
                            elif "limit" in err_str.lower() or "лимит" in err_str.lower():
                                if getattr(config, "auto_friend_cleanup", False):
                                    cleaned = await self.cleanup_inactive_friends(config=config, max_removals=1)
                                    if cleaned == 0:
                                        self.raids_api.rate_guard.record_friends_limit_reached()
                                        break
                                else:
                                    self.raids_api.rate_guard.record_friends_limit_reached()
                                    break
                            else:
                                self.raids_api.rate_guard.record_error(500)

                    results["outreach_sent"] = outreach_sent

        if (results["gifts_claimed"] > 0 or results["friends_accepted"] > 0 or results.get("outreach_sent", 0) > 0) and self.notifier is not None:
            lines = ["🤝 <b>Социальные активности:</b>"]
            if results["gifts_claimed"] > 0:
                lines.append(f"🎁 Собрано посылок: <b>{results['gifts_claimed']}</b>")
            if results["friends_accepted"] > 0:
                lines.append(f"👥 Принято в друзья: <b>{results['friends_accepted']}</b>")
            if results.get("outreach_sent", 0) > 0:
                lines.append(f"🚀 Отправлено авто-заявок: <b>{results['outreach_sent']}</b>")
            await self.notifier.notify("\n".join(lines))

        logger.info(
            "Цикл социалки завершен: подарков=%s, друзей=%s, календарь=%s, авто-заявок=%s",
            results["gifts_claimed"],
            results["friends_accepted"],
            results["monthly_claimed"],
            results.get("outreach_sent", 0),
        )
        return results
