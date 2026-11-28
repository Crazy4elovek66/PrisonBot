import asyncio
import logging
import math
import random
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set

import httpx
from sqlalchemy import select, func, or_

from client.api.social import (
    SocialAPI,
    _has_explicit_obshak_field,
    calculate_level_from_authority,
    extract_player_combat_stats,
    parse_obshak_info,
)
from core.database import get_session
from core.models import SentFriendRequest, TrackedCandidate, BotConfig

logger = logging.getLogger(__name__)


def parse_damage_string(val_str: str) -> int:
    """Парсит строковый урон вида '600кк', '1.5ккк', '750т', '100m' в число."""
    if not val_str:
        return 0
    clean = str(val_str).lower().replace(" ", "").replace(",", ".")

    # 1. Сначала ищем число с явным суффиксом урона (ккк, млрд, b, кк, млн, m, к, тыс, t)
    m = re.search(r"([\d\.]+)\s*(ккк|млрд|b|кк|млн|m|к|тыс|t)", clean)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit in ("ккк", "млрд", "b"):
            return int(num * 1_000_000_000)
        elif unit in ("кк", "млн", "m"):
            return int(num * 1_000_000)
        elif unit in ("к", "тыс", "t"):
            return int(num * 1_000)
        return int(num)

    # 2. Фолбэк: если суффикса нет, отрезаем начальную нумерацию списка вида "1.", "2)"
    clean_no_index = re.sub(r"^\d+[\.\)]", "", clean).strip()
    m2 = re.search(r"(\d+)", clean_no_index)
    if m2:
        return int(m2.group(1))
    return 0


# Реалистичные тиры авторитета для парсера кандидатов и бригад
PARSER_TIER_PRESETS: Dict[str, tuple[int, int]] = {
    "accessible": (0, 2_000_000),
    "mid": (200_000, 15_000_000),
    "top": (15_000_000, 0),
    "custom": (0, 0),
}


def resolve_authority_bounds(
    tier: Optional[str] = None,
    min_authority: int = 0,
    max_authority: int = 0,
) -> tuple[int, int]:
    """Разрешает границы авторитета из тира парсера и ручных порогов."""
    t_norm = str(tier or "accessible").lower().strip()
    if t_norm != "custom" and t_norm in PARSER_TIER_PRESETS and int(min_authority or 0) == 0 and int(max_authority or 0) == 0:
        return PARSER_TIER_PRESETS[t_norm]
    return max(0, int(min_authority or 0)), max(0, int(max_authority or 0))


def compute_candidate_score(
    cand: TrackedCandidate,
    now: datetime,
    min_damage: int = 0,
    max_damage: int = 0,
) -> int:
    """
    Балльная система ранжирования Candidate Score:
    - Свежие (< 6ч) кандидаты из tg_channel и news_ad получают наивысший приоритет.
    - Высокий вес игрокам с ростом боевого урона (damage_delta > 0) и активностью в лагере.
    - Бонус окну достижимости (Sweet Spot min_damage..max_damage).
    - Легкий логарифмический бонус за абсолютный урон.
    """
    score = 0
    age_hours = max(0.0, (now - (cand.last_seen_at or now)).total_seconds() / 3600.0)

    # 1. Теплые источники (игрок сам ищет друзей прямо сейчас)
    if cand.source == "tg_channel":
        score += 5000 if age_hours <= 6 else (2500 if age_hours <= 24 else 500)
    elif cand.source == "news_ad":
        score += 4500 if age_hours <= 6 else (2000 if age_hours <= 24 else 400)
    elif cand.source == "import":
        score += 3500 if age_hours <= 24 else 500

    # 2. Реальная боевая активность (рост урона по боссам)
    dmg_delta = cand.damage_delta or 0
    if dmg_delta > 0:
        score += 2500 + min(2000, int(dmg_delta // 10_000))
    elif cand.is_active_recently:
        score += 800

    # 3. Активность в бригаде и боевые статы
    if (cand.camp_activity or 0) > 0:
        score += 600
    weapon_sum = (cand.poison_damage or 0) + (cand.gunshot_damage or 0) + (cand.knife_damage or 0)
    if weapon_sum > 0:
        score += min(1500, weapon_sum // 5)

    # 4. Окно достижимости (Sweet Spot)
    tot_dmg = cand.total_damage or 0
    if min_damage > 0 and max_damage > 0 and min_damage <= tot_dmg <= max_damage:
        score += 1500

    # 5. Легкий бонус за абсолютный урон (логарифмический)
    if tot_dmg > 0:
        score += min(1000, int(math.log10(tot_dmg + 1) * 100))

    return score


class OutreachRateGuard:
    """
    Централизованный контроль лимитов и предохранитель (Circuit Breaker)
    для исходящих заявок в друзья и сканирований.
    """

    def __init__(self):
        self._circuit_open: bool = False
        self._circuit_reason: str = ""
        self._circuit_reset_at: float = 0.0
        self._consecutive_errors: int = 0
        self._last_guild_scan: float = 0.0
        self._last_tg_scan: float = 0.0
        self._last_weekly_top_scan: float = 0.0
        self._last_news_scan: float = 0.0

    def trip_circuit_breaker(self, reason: str, cooldown_seconds: int) -> None:
        """Активация предохранителя с заданной паузой."""
        self._circuit_open = True
        self._circuit_reason = reason
        self._circuit_reset_at = time.time() + cooldown_seconds
        logger.warning(f"Предохранитель (Circuit Breaker) АКТИВИРОВАН: {reason}. Пауза: {cooldown_seconds} сек.")

    def is_circuit_open(self) -> bool:
        """Проверка, активен ли предохранитель (с авто-сбросом по истечении времени)."""
        if self._circuit_open:
            if time.time() >= self._circuit_reset_at:
                self._circuit_open = False
                self._circuit_reason = ""
                self._consecutive_errors = 0
                return False
            return True
        return False

    def record_error(self, status_code: int) -> None:
        """Регистрация ошибки API (429 или подряд идущих 4xx/5xx)."""
        if status_code == 429:
            self.trip_circuit_breaker("429 Too Many Requests (cooldown 60 min)", 3600)
        elif status_code in (400, 401, 403, 500, 502, 503, 504):
            self._consecutive_errors += 1
            if self._consecutive_errors >= 3:
                self.trip_circuit_breaker("3 подряд ошибки API (cooldown 10 min)", 600)

    def record_success(self) -> None:
        """Сброс счетчика последовательных ошибок при успехе."""
        self._consecutive_errors = 0

    def record_friends_limit_reached(self) -> None:
        """Активация предохранителя на 24 часа при ответе игры о лимите друзей."""
        self.trip_circuit_breaker("Достигнут лимит друзей игры (cooldown 24ч)", 86400)

    async def get_daily_sent_count(self, account_id: int, db_engine: Any) -> int:
        """Точный подсчет отправленных заявок за последние 24 часа со статусом 'sent'."""
        if not db_engine:
            return 0
        try:
            async with get_session(db_engine) as session:
                cutoff = datetime.utcnow() - timedelta(hours=24)
                stmt = select(func.count(SentFriendRequest.id)).where(
                    SentFriendRequest.account_id == account_id,
                    SentFriendRequest.status == "sent",
                    SentFriendRequest.created_at >= cutoff,
                )
                res = await session.execute(stmt)
                return int(res.scalar() or 0)
        except Exception as e:
            logger.warning(f"Ошибка подсчета суточных заявок: {e}")
            return 0

    async def can_send(
        self,
        account_id: int,
        daily_limit: int,
        db_engine: Any,
    ) -> tuple[bool, int, Optional[str]]:
        """
        Проверка возможности отправки заявки в друзья.
        Возвращает (allowed, remaining, reason).
        """
        if self.is_circuit_open():
            rem_sec = int(max(0, self._circuit_reset_at - time.time()))
            return False, 0, f"Предохранитель активен: {self._circuit_reason}. До сброса: {rem_sec} сек."

        effective_limit = max(1, int(daily_limit or 50))
        sent = await self.get_daily_sent_count(account_id, db_engine)
        if sent >= effective_limit:
            return False, 0, f"Суточный лимит заявок исчерпан ({sent}/{effective_limit})"

        remaining = max(0, effective_limit - sent)
        return True, remaining, None

    def can_scan_guilds(self, force: bool = False) -> tuple[bool, int]:
        """Проверка кулдауна сканирования бригад (300 сек)."""
        if force:
            return True, 0
        now = time.time()
        elapsed = now - self._last_guild_scan
        if elapsed < 300:
            return False, int(300 - elapsed)
        return True, 0

    def record_guild_scan(self) -> None:
        self._last_guild_scan = time.time()

    def can_scan_tg(self, force: bool = False) -> tuple[bool, int]:
        """Проверка кулдауна сканирования TG-каналов (900 сек)."""
        if force:
            return True, 0
        now = time.time()
        elapsed = now - self._last_tg_scan
        if elapsed < 900:
            return False, int(900 - elapsed)
        return True, 0

    def record_tg_scan(self) -> None:
        self._last_tg_scan = time.time()

    def can_scan_weekly_top(self, force: bool = False) -> tuple[bool, int]:
        """Проверка кулдауна сканирования топа (900 сек)."""
        if force:
            return True, 0
        now = time.time()
        elapsed = now - self._last_weekly_top_scan
        if elapsed < 900:
            return False, int(900 - elapsed)
        return True, 0

    def record_weekly_top_scan(self) -> None:
        self._last_weekly_top_scan = time.time()

    def can_scan_news(self, force: bool = False) -> tuple[bool, int]:
        """Проверка кулдауна сканирования новостей (600 сек)."""
        if force:
            return True, 0
        now = time.time()
        elapsed = now - self._last_news_scan
        if elapsed < 600:
            return False, int(600 - elapsed)
        return True, 0

    def record_news_scan(self) -> None:
        self._last_news_scan = time.time()

    async def get_safety_status(
        self,
        account_id: int,
        daily_limit: int,
        db_engine: Any,
    ) -> Dict[str, Any]:
        """Получение сводки статуса безопасности и лимитов."""
        circuit_open = self.is_circuit_open()
        effective_limit = max(1, int(daily_limit or 50))
        sent = await self.get_daily_sent_count(account_id, db_engine)
        remaining = max(0, effective_limit - sent)
        _, g_cd = self.can_scan_guilds()
        _, tg_cd = self.can_scan_tg()
        _, top_cd = self.can_scan_weekly_top()
        _, news_cd = self.can_scan_news()

        reset_iso = None
        if circuit_open and self._circuit_reset_at > 0:
            reset_iso = datetime.utcfromtimestamp(self._circuit_reset_at).isoformat()

        return {
            "sentLast24h": sent,
            "dailyLimit": effective_limit,
            "remaining24h": remaining,
            "circuitOpen": circuit_open,
            "circuitReason": self._circuit_reason if circuit_open else "",
            "circuitResetAt": reset_iso,
            "guildScanCooldownSec": g_cd,
            "tgScanCooldownSec": tg_cd,
            "weeklyTopCooldownSec": top_cd,
            "newsScanCooldownSec": news_cd,
        }


class RaidsAPI:
    """
    Клиент-агрегатор для раздела «Рейды и Новости»:
    1. Игровой радар активных дамагеров из официального API игры (GET /api/weekly-top/top)
       и локальной базы TrackedCandidate с детектором роста за 6-24ч.
    2. Сканер активных бригад (GET /api/guild/recruitment/list, GET /api/guild/{id}/members).
    3. Парсер текстовых постов рейдов из Telegram-каналов и чатов.
    """

    def __init__(self, external_token: Optional[str] = None):
        self.external_token = external_token
        self._news_cache: Optional[Dict[str, Any]] = None
        self._news_cache_time: float = 0
        self._raids_cache: Optional[Dict[str, Any]] = None
        self._raids_cache_time: float = 0
        self.rate_guard = OutreachRateGuard()
        self._guild_cursor: int = 0

    async def get_news(self, limit: int = 20, force_refresh: bool = False) -> Dict[str, Any]:
        """Возвращает пустую ленту (внешний ProPrisonBot удален; новости читаются через news_feed_service)."""
        return {"posts": []}

    async def get_raids(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Возвращает базовый локальный контейнер рейдов (без внешнего ProPrisonBot)."""
        return {
            "sourceStatus": "ok",
            "sourceMessage": "Рейды из Telegram-каналов и радар активных игроков",
            "isPaywalled": False,
            "raids": [],
        }

    async def scan_active_guilds(
        self,
        social_api: SocialAPI,
        db_engine: Any,
        account_id: int = 1,
        max_guilds: int = 8,
        delay_range: tuple[float, float] = (1.5, 3.0),
        force: bool = False,
        tier: str = "accessible",
        min_authority: int = 0,
        max_authority: int = 0,
    ) -> Dict[str, Any]:
        """
        Автономный игровой сканер активных бригад:
        1. Проверяет кулдаун 300с.
        2. Запрашивает список набора /api/guild/recruitment/list (не только топ-1, а все открытые бригады с ротацией).
        3. По тиру (accessible / mid / top / custom) и ротации выбирает до max_guilds бригад.
        4. Запрашивает участников каждой бригады /api/guild/{id}/members.
        5. Сохраняет / обновляет кандидатов в TrackedCandidate с вычислением дельты за 6-24ч.
        """
        can_run, rem_cd = self.rate_guard.can_scan_guilds(force=force)
        if not can_run:
            return {
                "success": False,
                "status": "cooldown",
                "cooldownSeconds": rem_cd,
                "message": f"Кулдаун сканирования бригад: подождите {rem_cd} сек перед повторным запуском.",
            }

        auth_min, auth_max = resolve_authority_bounds(tier, min_authority, max_authority)

        try:
            rec_res = await social_api.get_recruitment_list(limit=100)
            raw_guilds = rec_res.get("items") or rec_res.get("list") or rec_res.get("guilds") or []
            if isinstance(rec_res, list):
                raw_guilds = rec_res
        except Exception as e:
            logger.warning(f"Ошибка получения списка набора бригад: {e}")
            raw_guilds = []

        guild_items = []
        for g in raw_guilds:
            if isinstance(g, dict):
                gid = g.get("guildId") or g.get("id")
                gname = g.get("name") or g.get("guildName") or f"Бригада #{gid}"
                m_count = int(g.get("membersCount") or g.get("memberCount") or g.get("members") or 0)
                g_level = int(g.get("level") or (g.get("emblem") or {}).get("lvl") or 1)
                max_members = int(g.get("maxMembers") or 50)
                if gid:
                    guild_items.append({
                        "guildId": int(gid),
                        "name": str(gname),
                        "membersCount": m_count,
                        "level": g_level,
                        "hasOpenSlots": m_count < max_members,
                    })

        if not guild_items:
            return {
                "success": True,
                "status": "no_guilds",
                "scannedGuilds": 0,
                "message": "Бригады для сканирования не найдены в ответе игры.",
            }

        # Сортируем бригады в зависимости от тира, чтобы не упираться в один и тот же топ-1
        t_norm = str(tier or "accessible").lower().strip()
        if t_norm == "accessible":
            # Предпочитаем доступные/средние открытые бригады (уровень 1..30) с активными слотами
            tiered_guilds = [g for g in guild_items if g["membersCount"] >= 3 and g["level"] <= 35]
            guild_items.sort(key=lambda x: (not x["hasOpenSlots"], x["level"], -x["membersCount"]))
            valid_guilds = tiered_guilds if len(tiered_guilds) >= 3 else [g for g in guild_items if g["membersCount"] >= 3]
        elif t_norm == "mid":
            tiered_guilds = [g for g in guild_items if g["membersCount"] >= 3 and 10 <= g["level"] <= 45]
            guild_items.sort(key=lambda x: (-x["level"], -x["membersCount"]))
            valid_guilds = tiered_guilds if len(tiered_guilds) >= 3 else [g for g in guild_items if g["membersCount"] >= 3]
        else:
            guild_items.sort(key=lambda x: (-x["level"], -x["membersCount"]))
            valid_guilds = [g for g in guild_items if g["membersCount"] >= 3]

        if not valid_guilds:
            valid_guilds = guild_items

        # Читаем курсор ротации из BotConfig (fallback на self._guild_cursor)
        cursor = self._guild_cursor
        if db_engine:
            try:
                async with get_session(db_engine) as session:
                    cfg_stmt = select(BotConfig.guild_scan_cursor).where(BotConfig.account_id == account_id)
                    cursor_val = (await session.execute(cfg_stmt)).scalar_one_or_none()
                    if cursor_val is not None:
                        cursor = int(cursor_val)
            except Exception as e:
                logger.warning(f"Ошибка чтения курсора ротации бригад из БД: {e}")

        total_g = len(valid_guilds)
        count_to_scan = min(max_guilds, total_g)
        selected_guilds = [
            valid_guilds[(cursor + i) % total_g]
            for i in range(count_to_scan)
        ]
        next_cursor = (cursor + count_to_scan) % total_g
        self._guild_cursor = next_cursor

        if db_engine:
            try:
                async with get_session(db_engine) as session:
                    cfg_stmt = select(BotConfig).where(BotConfig.account_id == account_id)
                    cfg = (await session.execute(cfg_stmt)).scalar_one_or_none()
                    if cfg:
                        cfg.guild_scan_cursor = next_cursor
                        await session.commit()
            except Exception as e:
                logger.warning(f"Ошибка сохранения курсора ротации бригад в БД: {e}")

        scanned_count = 0
        now = datetime.utcnow()

        for idx, g_info in enumerate(selected_guilds):
            if idx > 0 and delay_range[1] > 0:
                await asyncio.sleep(random.uniform(delay_range[0], delay_range[1]))

            try:
                m_res = await social_api.get_guild_members(g_info["guildId"])
                members = m_res.get("members") or m_res.get("items") or []
                if isinstance(m_res, list):
                    members = m_res
            except Exception as e:
                logger.warning(f"Не удалось получить участников бригады {g_info['guildId']}: {e}")
                continue

            scanned_count += 1
            if not db_engine:
                continue

            seen_in_tx: Dict[int, TrackedCandidate] = {}
            async with get_session(db_engine) as session:
                for m in members:
                    if not isinstance(m, dict):
                        continue
                    uid = m.get("userId") or m.get("id")
                    if not uid:
                        continue
                    uid_int = int(uid)

                    authority = int(m.get("authority") or m.get("resources", {}).get("authority") or 0)
                    level = int(m.get("level") or m.get("lvl") or 0)
                    if level == 0 and authority > 0:
                        level = calculate_level_from_authority(authority)

                    boss_damage = int(m.get("bossDamage") or m.get("totalDamage") or m.get("activityRating") or 0)
                    camp_activity = int(m.get("campActivity") or m.get("camp_activity") or 0)
                    talents = int(m.get("talents") or m.get("talentsCount") or 0)

                    wep_dmg = m.get("weaponDamage") or {}
                    poi_dmg = int(wep_dmg.get("poison") or m.get("poisonDamage") or 0)
                    gun_dmg = int(wep_dmg.get("gunshot") or m.get("gunshotDamage") or 0)
                    kni_dmg = int(wep_dmg.get("knife") or m.get("knifeDamage") or 0)
                    nick = m.get("nickname") or m.get("name") or f"Игрок {uid_int}"
                    photo = m.get("photoUrl") or m.get("avatarUrl")

                    cand = seen_in_tx.get(uid_int)
                    if not cand:
                        stmt = select(TrackedCandidate).where(
                            TrackedCandidate.account_id == account_id,
                            TrackedCandidate.user_id == uid_int,
                        )
                        cand = (await session.execute(stmt)).scalar_one_or_none()

                    if not cand:
                        cand = TrackedCandidate(
                            account_id=account_id,
                            user_id=uid_int,
                            nickname=nick,
                            photo_url=photo,
                            guild_id=g_info["guildId"],
                            guild_name=g_info["name"],
                            level=level,
                            authority=authority,
                            prev_authority=authority,
                            authority_delta=0,
                            poison_damage=poi_dmg,
                            gunshot_damage=gun_dmg,
                            knife_damage=kni_dmg,
                            total_damage=boss_damage,
                            prev_total_damage=boss_damage,
                            damage_delta=0,
                            camp_activity=camp_activity,
                            talents=talents,
                            score=0,
                            source="guild",
                            is_active_recently=(camp_activity > 0),
                            first_seen_at=now,
                            last_seen_at=now,
                            last_snapshot_at=now,
                        )
                        cand.score = compute_candidate_score(cand, now)
                        session.add(cand)
                        seen_in_tx[uid_int] = cand
                    else:
                        seen_in_tx[uid_int] = cand
                        cand.last_seen_at = now
                        cand.nickname = nick or cand.nickname
                        cand.guild_id = g_info["guildId"]
                        cand.guild_name = g_info["name"]
                        if photo:
                            cand.photo_url = photo
                        if level > 0:
                            cand.level = max(cand.level, level)
                        cand.camp_activity = max(cand.camp_activity, camp_activity)
                        if talents > 0:
                            cand.talents = max(cand.talents, talents)
                        if poi_dmg > 0:
                            cand.poison_damage = max(cand.poison_damage, poi_dmg)
                        if gun_dmg > 0:
                            cand.gunshot_damage = max(cand.gunshot_damage, gun_dmg)
                        if kni_dmg > 0:
                            cand.knife_damage = max(cand.knife_damage, kni_dmg)

                        elapsed_sec = (now - cand.last_snapshot_at).total_seconds()
                        if elapsed_sec >= 6 * 3600:
                            a_delta = max(0, authority - cand.prev_authority) if authority > 0 else 0
                            d_delta = max(0, boss_damage - cand.prev_total_damage)
                            cand.authority_delta = a_delta
                            cand.damage_delta = d_delta
                            cand.is_active_recently = (d_delta > 0 or a_delta > 0 or cand.camp_activity > 0)
                            if elapsed_sec >= 24 * 3600:
                                if authority > 0:
                                    cand.prev_authority = authority
                                cand.prev_total_damage = boss_damage
                                cand.last_snapshot_at = now
                        elif cand.damage_delta > 0 or cand.authority_delta > 0 or cand.camp_activity > 0:
                            cand.is_active_recently = True

                        if boss_damage > 0:
                            cand.total_damage = max(cand.total_damage, boss_damage)
                        if authority > 0:
                            cand.authority = authority
                        cand.score = compute_candidate_score(cand, now)

                await session.commit()

        self.rate_guard.record_guild_scan()

        total_c = 0
        active_c = 0
        if db_engine:
            async with get_session(db_engine) as session:
                t_stmt = select(func.count(TrackedCandidate.id)).where(TrackedCandidate.account_id == account_id)
                a_stmt = select(func.count(TrackedCandidate.id)).where(
                    TrackedCandidate.account_id == account_id,
                    TrackedCandidate.is_active_recently == True,
                )
                total_c = int((await session.execute(t_stmt)).scalar() or 0)
                active_c = int((await session.execute(a_stmt)).scalar() or 0)

        return {
            "success": True,
            "status": "ok",
            "scannedGuilds": scanned_count,
            "totalCandidates": total_c,
            "activeCandidates": active_c,
            "message": f"Просканировано {scanned_count} бригад. В базе: {total_c} кандидатов ({active_c} активных).",
        }

    async def get_active_players_radar(
        self,
        social_api: SocialAPI,
        player_api: Optional[Any] = None,
        db_engine: Optional[Any] = None,
        account_id: int = 1,
        current_user_id: Optional[int] = None,
        friend_ids: Optional[Set[int]] = None,
        sent_user_ids: Optional[Set[int]] = None,
        source: str = "all",
        min_damage: int = 0,
        max_damage: int = 0,
        limit: int = 50,
        exclude_friends: bool = False,
        tier: Optional[str] = None,
        min_authority: int = 0,
        max_authority: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Игровой радар активных дамагеров:
        1. Если доступна локальная база TrackedCandidate, выбирает игроков с учетом детектора активности.
        2. Если база пуста или не задана, запрашивает weekly-top напрямую и кэширует кандидатов.
        3. Применяет фильтры min_damage, max_damage, min_authority, max_authority, tier, source
           и вычисляет актуальный статус дружбы ('friend' | 'sent' | 'none').
        """
        friends = friend_ids or set()
        sent = sent_user_ids or set()
        auth_min, auth_max = (
            resolve_authority_bounds(tier, min_authority, max_authority)
            if (tier is not None or min_authority > 0 or max_authority > 0)
            else (0, 0)
        )

        candidates: List[Dict[str, Any]] = []

        if db_engine:
            try:
                async with get_session(db_engine) as session:
                    stmt = select(TrackedCandidate).where(TrackedCandidate.account_id == account_id)

                    if source == "active":
                        stmt = stmt.where(
                            or_(
                                TrackedCandidate.is_active_recently == True,
                                TrackedCandidate.authority_delta > 0,
                            )
                        )
                    elif source == "guild":
                        stmt = stmt.where(TrackedCandidate.source == "guild")
                    elif source == "weekly_top":
                        stmt = stmt.where(TrackedCandidate.source == "weekly_top")

                    if min_damage > 0:
                        stmt = stmt.where(TrackedCandidate.total_damage >= min_damage)
                    if max_damage > 0:
                        stmt = stmt.where(TrackedCandidate.total_damage <= max_damage)
                    if auth_min > 0:
                        stmt = stmt.where(TrackedCandidate.authority >= auth_min)
                    if auth_max > 0:
                        stmt = stmt.where(TrackedCandidate.authority <= auth_max)

                    stmt = stmt.order_by(
                        TrackedCandidate.score.desc(),
                        TrackedCandidate.damage_delta.desc(),
                        TrackedCandidate.total_damage.desc(),
                        TrackedCandidate.authority_delta.desc(),
                        TrackedCandidate.authority.desc(),
                    )

                    res = await session.execute(stmt)
                    rows = res.scalars().all()

                    for row in rows:
                        uid_int = int(row.user_id)
                        if current_user_id and uid_int == int(current_user_id):
                            continue

                        is_friend = uid_int in friends
                        if exclude_friends and is_friend:
                            continue

                        friend_status = "friend" if is_friend else "sent" if uid_int in sent else "none"

                        lvl = row.level or 0
                        auth = int(row.authority or 0)
                        if (lvl <= 1 or lvl == 0) and auth > 0:
                            lvl = calculate_level_from_authority(auth)

                        candidates.append({
                            "userId": uid_int,
                            "nickname": row.nickname or f"Игрок {uid_int}",
                            "level": lvl,
                            "authority": auth,
                            "prevAuthority": row.prev_authority,
                            "authorityDelta": row.authority_delta,
                            "damageDelta": row.damage_delta,
                            "campActivity": row.camp_activity,
                            "talents": row.talents,
                            "score": row.score,
                            "isActiveRecently": bool(row.is_active_recently or (row.damage_delta > 0) or (row.authority_delta > 0)),
                            "damage": row.total_damage,
                            "rank": None,
                            "photoUrl": row.photo_url,
                            "guildId": row.guild_id,
                            "guildName": row.guild_name,
                            "friendStatus": friend_status,
                            "source": row.source,
                            "poisonDamage": int(row.poison_damage or 0),
                            "gunshotDamage": int(row.gunshot_damage or 0),
                            "knifeDamage": int(row.knife_damage or 0),
                        })

                        if len(candidates) >= limit:
                            break
            except Exception as e:
                logger.warning(f"Ошибка выборки кандидатов из TrackedCandidate: {e}")

        # Если из локальной БД не нашли кандидатов (или БД не подключена) и источник all/weekly_top,
        # запрашиваем официальный еженедельный топ игры
        if not candidates and source in ("all", "weekly_top"):
            try:
                top_res = await social_api.get_weekly_top(limit=100)
                raw_top = top_res.get("top", []) if isinstance(top_res, dict) else []
            except Exception as e:
                logger.warning(f"Не удалось загрузить еженедельный топ игроков: {e}")
                raw_top = []

            now = datetime.utcnow()
            for entry in raw_top:
                if not isinstance(entry, dict):
                    continue
                uid = entry.get("userId") or entry.get("id")
                if not uid or (current_user_id and int(uid) == int(current_user_id)):
                    continue

                uid_int = int(uid)
                dmg = int(entry.get("damage") or entry.get("totalDamage") or 0)
                if min_damage > 0 and dmg < min_damage:
                    continue
                if max_damage > 0 and dmg > max_damage:
                    continue

                is_friend = uid_int in friends
                if exclude_friends and is_friend:
                    continue

                friend_status = "friend" if is_friend else "sent" if uid_int in sent else "none"

                authority = int(entry.get("authority") or 0)
                if auth_min > 0 and authority < auth_min:
                    continue
                if auth_max > 0 and authority > auth_max:
                    continue
                lvl = int(entry.get("level") or entry.get("lvl") or 0)
                if lvl == 0 and authority > 0:
                    lvl = calculate_level_from_authority(authority)

                nick = entry.get("nickname") or entry.get("name") or f"Игрок {uid_int}"
                photo = entry.get("photoUrl") or entry.get("avatarUrl")

                # Кэшируем кандидата в локальную базу TrackedCandidate, если db_engine передан
                score_val = 0
                if db_engine:
                    try:
                        async with get_session(db_engine) as session:
                            c_stmt = select(TrackedCandidate).where(
                                TrackedCandidate.account_id == account_id,
                                TrackedCandidate.user_id == uid_int,
                            )
                            c_exist = (await session.execute(c_stmt)).scalar_one_or_none()
                            if not c_exist:
                                c_exist = TrackedCandidate(
                                    account_id=account_id,
                                    user_id=uid_int,
                                    nickname=nick,
                                    photo_url=photo,
                                    level=lvl,
                                    authority=authority,
                                    prev_authority=authority,
                                    authority_delta=0,
                                    total_damage=dmg,
                                    prev_total_damage=dmg,
                                    damage_delta=0,
                                    poison_damage=0,
                                    gunshot_damage=0,
                                    knife_damage=0,
                                    camp_activity=0,
                                    talents=0,
                                    source="weekly_top",
                                    is_active_recently=(dmg > 0),
                                    first_seen_at=now,
                                    last_seen_at=now,
                                    last_snapshot_at=now,
                                )
                                c_exist.score = compute_candidate_score(c_exist, now, min_damage=min_damage, max_damage=max_damage)
                                session.add(c_exist)
                                await session.commit()
                                score_val = c_exist.score
                            else:
                                score_val = c_exist.score
                    except Exception as e:
                        logger.warning(f"Ошибка сохранения кандидата из топа: {e}")

                candidates.append({
                    "userId": uid_int,
                    "nickname": nick,
                    "level": lvl,
                    "authority": authority,
                    "prevAuthority": authority,
                    "authorityDelta": 0,
                    "damageDelta": 0,
                    "campActivity": 0,
                    "talents": 0,
                    "score": score_val,
                    "isActiveRecently": (dmg > 0),
                    "damage": dmg,
                    "rank": entry.get("rank"),
                    "photoUrl": photo,
                    "guildId": None,
                    "guildName": None,
                    "friendStatus": friend_status,
                    "source": "weekly_top",
                    "poisonDamage": 0,
                    "gunshotDamage": 0,
                    "knifeDamage": 0,
                })

                if len(candidates) >= limit:
                    break

        if player_api and db_engine and candidates:
            try:
                candidates = await self.enrich_candidates_batch(
                    player_api=player_api,
                    db_engine=db_engine,
                    candidates=candidates,
                    account_id=account_id,
                    max_enrich=min(limit, 50),
                    min_damage=min_damage,
                    max_damage=max_damage,
                    social_api=social_api,
                )
            except Exception as e:
                logger.warning(f"Ошибка точечного обогащения кандидатов Радара: {e}")

        return candidates

    async def sync_weekly_top_and_achievements(
        self,
        social_api: SocialAPI,
        db_engine: Any,
        account_id: int = 1,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Синхронизирует TrackedCandidate с официальным еженедельным топом игры:
        GET /api/weekly-top/top?limit=100 и GET /api/weekly-top/achievements?limit=100.
        Считает damage_delta и authority_delta за окно 6-24ч, пересчитывает Candidate Score.
        """
        can_run, rem_cd = self.rate_guard.can_scan_weekly_top(force=force)
        if not can_run:
            return {
                "success": False,
                "status": "cooldown",
                "cooldownSeconds": rem_cd,
                "message": f"Кулдаун сканирования топа: подождите {rem_cd} сек.",
            }

        top_entries = []
        try:
            top_res = await social_api.get_weekly_top(limit=100)
            items = (
                top_res.get("top") or top_res.get("items") or []
                if isinstance(top_res, dict)
                else top_res if isinstance(top_res, list) else []
            )
            for item in items:
                if isinstance(item, dict):
                    top_entries.append((item, "weekly_top"))
        except Exception as e:
            logger.warning(f"Ошибка загрузки weekly_top: {e}")

        try:
            ach_res = await social_api.get_top_achievements(limit=100)
            items = (
                ach_res.get("achievements") or ach_res.get("top") or ach_res.get("items") or []
                if isinstance(ach_res, dict)
                else ach_res if isinstance(ach_res, list) else []
            )
            for item in items:
                if isinstance(item, dict):
                    top_entries.append((item, "achievements"))
        except Exception as e:
            logger.warning(f"Ошибка загрузки top_achievements: {e}")

        if not top_entries or not db_engine:
            self.rate_guard.record_weekly_top_scan()
            return {"success": True, "synced": len(top_entries)}

        now = datetime.utcnow()
        synced_count = 0

        merged_by_uid: Dict[int, Dict[str, Any]] = {}
        for entry, src in top_entries:
            uid = entry.get("userId") or entry.get("id")
            if not uid:
                continue
            uid_int = int(uid)
            dmg = int(entry.get("damage") or entry.get("totalDamage") or 0)
            authority = int(entry.get("authority") or 0)
            lvl = int(entry.get("level") or entry.get("lvl") or 0)
            nick = entry.get("nickname") or entry.get("name") or f"Игрок {uid_int}"
            photo = entry.get("photoUrl") or entry.get("avatarUrl")
            if uid_int not in merged_by_uid:
                merged_by_uid[uid_int] = {
                    "uid_int": uid_int,
                    "damage": dmg,
                    "authority": authority,
                    "level": lvl,
                    "nickname": nick,
                    "photoUrl": photo,
                    "source": src,
                }
            else:
                m = merged_by_uid[uid_int]
                if dmg > m["damage"]:
                    m["damage"] = dmg
                if authority > m["authority"]:
                    m["authority"] = authority
                if lvl > m["level"]:
                    m["level"] = lvl
                if not m["photoUrl"] and photo:
                    m["photoUrl"] = photo

        seen_in_tx: Dict[int, TrackedCandidate] = {}
        async with get_session(db_engine) as session:
            for uid_int, data in merged_by_uid.items():
                dmg = data["damage"]
                authority = data["authority"]
                lvl = data["level"]
                if lvl == 0 and authority > 0:
                    lvl = calculate_level_from_authority(authority)
                nick = data["nickname"]
                photo = data["photoUrl"]
                src = data["source"]

                cand = seen_in_tx.get(uid_int)
                if not cand:
                    stmt = select(TrackedCandidate).where(
                        TrackedCandidate.account_id == account_id,
                        TrackedCandidate.user_id == uid_int,
                    )
                    cand = (await session.execute(stmt)).scalar_one_or_none()

                if not cand:
                    cand = TrackedCandidate(
                        account_id=account_id,
                        user_id=uid_int,
                        nickname=nick,
                        photo_url=photo,
                        level=lvl,
                        authority=authority,
                        prev_authority=authority,
                        authority_delta=0,
                        total_damage=dmg,
                        prev_total_damage=dmg,
                        damage_delta=0,
                        poison_damage=0,
                        gunshot_damage=0,
                        knife_damage=0,
                        source=src,
                        is_active_recently=(dmg > 0),
                        first_seen_at=now,
                        last_seen_at=now,
                        last_snapshot_at=now,
                    )
                    cand.score = compute_candidate_score(cand, now)
                    session.add(cand)
                    seen_in_tx[uid_int] = cand
                else:
                    seen_in_tx[uid_int] = cand
                    cand.last_seen_at = now
                    cand.nickname = nick or cand.nickname
                    if photo:
                        cand.photo_url = photo
                    if lvl > 0:
                        cand.level = max(cand.level, lvl)
                    if cand.poison_damage == 250 and cand.gunshot_damage == 60 and cand.knife_damage == 30:
                        cand.poison_damage = 0
                        cand.gunshot_damage = 0
                        cand.knife_damage = 0
                        cand.enriched_at = None

                    elapsed_sec = (now - cand.last_snapshot_at).total_seconds()
                    if elapsed_sec >= 6 * 3600:
                        a_delta = max(0, authority - cand.prev_authority) if authority > 0 else 0
                        d_delta = max(0, dmg - cand.prev_total_damage)
                        cand.authority_delta = a_delta
                        cand.damage_delta = d_delta
                        cand.is_active_recently = (d_delta > 0 or dmg > 0 or a_delta > 0)
                        if elapsed_sec >= 24 * 3600:
                            if authority > 0:
                                cand.prev_authority = authority
                            cand.prev_total_damage = dmg
                            cand.last_snapshot_at = now
                    elif cand.damage_delta > 0 or dmg > 0 or cand.authority_delta > 0:
                        cand.is_active_recently = True

                    if dmg > 0:
                        cand.total_damage = max(cand.total_damage, dmg)
                    if authority > 0:
                        cand.authority = authority
                    cand.score = compute_candidate_score(cand, now)

                synced_count += 1
            await session.commit()

        self.rate_guard.record_weekly_top_scan()
        return {"success": True, "synced": synced_count}

    async def scan_news_for_candidates(
        self,
        game_http_client: Any,
        db_engine: Any,
        account_id: int = 1,
        player_api: Optional[Any] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Извлекает кандидатов из локально кэшированных TG-постов рейдов без обращений к внешнему ProPrisonBot.
        """
        can_run, rem_cd = self.rate_guard.can_scan_news(force=force)
        if not can_run:
            return {
                "success": False,
                "status": "cooldown",
                "cooldownSeconds": rem_cd,
                "message": f"Кулдаун сканирования: подождите {rem_cd} сек.",
            }

        texts: List[str] = []
        if db_engine:
            try:
                async with get_session(db_engine) as session:
                    rows = (await session.execute(
                        select(CachedRaidPost.raw_preview).where(CachedRaidPost.account_id == account_id).limit(30)
                    )).scalars().all()
                    texts = [str(t) for t in rows if t]
            except Exception as e:
                logger.debug("Ошибка чтения CachedRaidPost для кандидатов: %s", e)

        if not texts or not db_engine:
            self.rate_guard.record_news_scan()
            return {"success": True, "foundCandidates": 0}

        now = datetime.utcnow()
        found_count = 0

        seen_in_tx: Dict[int, TrackedCandidate] = {}
        async with get_session(db_engine) as session:
            for text_block in texts:
                parsed = await self.parse_raid_text(text_block, player_api=player_api)
                participants = parsed.get("participants", [])

                for p in participants:
                    uid_int = int(p.get("userId"))
                    claimed_dmg = int(p.get("claimedDamage") or 0)
                    nick = p.get("nickname") or f"Игрок {uid_int}"
                    level = int(p.get("level") or 0)
                    authority = int(p.get("authority") or 0)
                    photo = p.get("photoUrl")

                    cand = seen_in_tx.get(uid_int)
                    if not cand:
                        stmt = select(TrackedCandidate).where(
                            TrackedCandidate.account_id == account_id,
                            TrackedCandidate.user_id == uid_int,
                        )
                        cand = (await session.execute(stmt)).scalar_one_or_none()

                    if not cand:
                        cand = TrackedCandidate(
                            account_id=account_id,
                            user_id=uid_int,
                            nickname=nick,
                            photo_url=photo,
                            level=level,
                            authority=authority,
                            prev_authority=authority,
                            authority_delta=0,
                            total_damage=claimed_dmg,
                            prev_total_damage=claimed_dmg,
                            damage_delta=0,
                            poison_damage=0,
                            gunshot_damage=0,
                            knife_damage=0,
                            source="news_ad",
                            is_active_recently=True,
                            first_seen_at=now,
                            last_seen_at=now,
                            last_snapshot_at=now,
                        )
                        cand.score = compute_candidate_score(cand, now)
                        session.add(cand)
                        seen_in_tx[uid_int] = cand
                    else:
                        seen_in_tx[uid_int] = cand
                        cand.last_seen_at = now
                        cand.nickname = nick or cand.nickname
                        if photo:
                            cand.photo_url = photo
                        if level > 0:
                            cand.level = max(cand.level, level)
                        if claimed_dmg > 0:
                            cand.total_damage = max(cand.total_damage, claimed_dmg)
                        cand.is_active_recently = True
                        cand.score = compute_candidate_score(cand, now)

                    found_count += 1
            await session.commit()

        self.rate_guard.record_news_scan()
        return {"success": True, "foundCandidates": found_count}

    async def enrich_candidates_batch(
        self,
        player_api: Any,
        db_engine: Any,
        candidates: List[Dict[str, Any]],
        account_id: int = 1,
        max_enrich: int = 15,
        min_damage: int = 0,
        max_damage: int = 0,
        social_api: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Точечное обогащение топ-кандидатов перед отправкой заявки:
        Запрашивает player_api.get_player_view(uid), get_player_summary(uid) и сверяет со входящими заявками
        для получения реальных authority, level, talents и weaponDamage (без подстановки 250/60/30).
        """
        if not player_api or not db_engine or not candidates:
            return candidates

        sem = asyncio.Semaphore(3)
        now = datetime.utcnow()
        to_enrich = []

        # Подтягиваем реальные weaponDamage из входящих заявок (/api/friendship/requests), если игрок есть там
        incoming_req_map: Dict[int, Dict[str, Any]] = {}
        if social_api and hasattr(social_api, "get_friend_requests"):
            try:
                req_res = await social_api.get_friend_requests(page=0, page_size=50)
                req_list = (
                    req_res
                    if isinstance(req_res, list)
                    else req_res.get("requests", [])
                    if isinstance(req_res, dict)
                    else []
                )
                for req_item in req_list:
                    if isinstance(req_item, dict):
                        r_uid = req_item.get("userId") or req_item.get("fromUserId") or req_item.get("id")
                        if r_uid:
                            incoming_req_map[int(r_uid)] = req_item
            except Exception as e:
                logger.debug(f"Не удалось получить входящие заявки при обогащении радара: {e}")

        async with get_session(db_engine) as session:
            cand_map = {int(c["userId"]): c for c in candidates if c.get("userId")}
            for c in candidates[:max_enrich]:
                uid = c.get("userId")
                if not uid:
                    continue
                stmt = select(TrackedCandidate).where(
                    TrackedCandidate.account_id == account_id,
                    TrackedCandidate.user_id == int(uid),
                )
                cand = (await session.execute(stmt)).scalar_one_or_none()
                if cand:
                    has_fake_floor = (cand.poison_damage == 250 and cand.gunshot_damage == 60 and cand.knife_damage == 30)
                    has_zero_weapons = (
                        (cand.poison_damage or 0) == 0
                        and (cand.gunshot_damage or 0) == 0
                        and (cand.knife_damage or 0) == 0
                    )
                    has_incoming_match = int(uid) in incoming_req_map and (cand.poison_damage or 0) == 0
                    needs = (
                        cand.enriched_at is None
                        or (now - cand.enriched_at).total_seconds() >= 24 * 3600
                        or (cand.authority or 0) == 0
                        or has_fake_floor
                        or has_zero_weapons
                        or has_incoming_match
                    )
                    if needs:
                        to_enrich.append(cand)
                    else:
                        # Синхронизируем реальные статы из кэша БД в in-memory структуру
                        target_c = cand_map.get(int(cand.user_id))
                        if target_c:
                            target_c["authority"] = int(cand.authority or 0)
                            c_lvl = cand.level or 0
                            if (c_lvl <= 1 or c_lvl == 0) and cand.authority > 0:
                                c_lvl = calculate_level_from_authority(cand.authority)
                            target_c["level"] = c_lvl
                            target_c["talents"] = int(cand.talents or 0)
                            target_c["poisonDamage"] = int(cand.poison_damage or 0)
                            target_c["gunshotDamage"] = int(cand.gunshot_damage or 0)
                            target_c["knifeDamage"] = int(cand.knife_damage or 0)

            if not to_enrich:
                return candidates

            async def _enrich_one(cand: TrackedCandidate):
                async with sem:
                    try:
                        p_view = await player_api.get_player_view(cand.user_id)
                        p_summary = None
                        if hasattr(player_api, "get_player_summary"):
                            try:
                                p_summary = await player_api.get_player_summary(cand.user_id)
                            except Exception:
                                p_summary = None

                        p_data = p_view.get("data") if isinstance(p_view.get("data"), dict) else p_view
                        inc_data = incoming_req_map.get(int(cand.user_id))

                        # Объединяем данные player/view и входящей заявки (если есть) без затирания реальных полей
                        merged_payload: Dict[str, Any] = {}
                        if isinstance(p_data, dict):
                            merged_payload.update(p_data)
                        if isinstance(inc_data, dict):
                            for k, v in inc_data.items():
                                if k not in merged_payload or not merged_payload[k]:
                                    merged_payload[k] = v

                        ext = extract_player_combat_stats(merged_payload, summary_payload=p_summary)

                        if ext["authority"] > 0:
                            cand.authority = ext["authority"]
                        if ext["level"] > 0:
                            cand.level = ext["level"]
                        elif (cand.level or 0) <= 1 and (cand.authority or 0) > 0:
                            cand.level = calculate_level_from_authority(cand.authority)

                        if isinstance(p_data, dict):
                            cand.nickname = p_data.get("nickname") or p_data.get("name") or cand.nickname
                            cand.photo_url = p_data.get("photoUrl") or p_data.get("avatarUrl") or cand.photo_url
                            g_obj = p_data.get("guild")
                            if isinstance(g_obj, dict) and g_obj.get("name"):
                                cand.brigade_name = str(g_obj["name"])
                            elif p_data.get("guildName") or p_data.get("brigadeName"):
                                cand.brigade_name = str(p_data.get("guildName") or p_data.get("brigadeName"))

                        from client.api.player import extract_obshak_from_payload
                        ob_has, ob_type = extract_obshak_from_payload(merged_payload)
                        if ob_type != "unknown":
                            cand.has_obshak = bool(ob_has)
                            cand.obshak_type = ob_type
                            cand.obshak_checked_at = time.time()

                        if ext["talents"] > 0:
                            cand.talents = ext["talents"]

                        # Сбрасываем фиктивные 250/60/30, оставляем только реально полученные значения (или 0)
                        was_fake = (cand.poison_damage == 250 and cand.gunshot_damage == 60 and cand.knife_damage == 30)
                        cur_p = 0 if was_fake else int(cand.poison_damage or 0)
                        cur_g = 0 if was_fake else int(cand.gunshot_damage or 0)
                        cur_k = 0 if was_fake else int(cand.knife_damage or 0)

                        cand.poison_damage = ext["poisonDamage"] if ext["poisonDamage"] > 0 else cur_p
                        cand.gunshot_damage = ext["gunshotDamage"] if ext["gunshotDamage"] > 0 else cur_g
                        cand.knife_damage = ext["knifeDamage"] if ext["knifeDamage"] > 0 else cur_k

                        cand.enriched_at = now
                        cand.score = compute_candidate_score(cand, now, min_damage=min_damage, max_damage=max_damage)

                        target_c = cand_map.get(int(cand.user_id))
                        if target_c:
                            target_c["authority"] = int(cand.authority or 0)
                            target_c["level"] = int(cand.level or 0)
                            target_c["nickname"] = cand.nickname
                            target_c["photoUrl"] = cand.photo_url
                            target_c["talents"] = int(cand.talents or 0)
                            target_c["poisonDamage"] = int(cand.poison_damage or 0)
                            target_c["gunshotDamage"] = int(cand.gunshot_damage or 0)
                            target_c["knifeDamage"] = int(cand.knife_damage or 0)
                            target_c["score"] = cand.score
                    except Exception as e:
                        logger.debug(f"Ошибка точечного обогащения игрока {cand.user_id}: {e}")
                    await asyncio.sleep(random.uniform(0.1, 0.25))

            tasks = [_enrich_one(cand) for cand in to_enrich]
            await asyncio.gather(*tasks, return_exceptions=True)
            await session.commit()

        return candidates

    async def parse_raid_text(
        self,
        raw_text: str,
        player_api: Optional[Any] = None,
        friend_ids: Optional[Set[int]] = None,
        sent_user_ids: Optional[Set[int]] = None,
        current_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Парсер скопированного текстового сообщения о рейде:
        Извлекает ID игроков, заявленный урон, названия и имена.
        Обогащает профили найденных игроков через player_api.get_player_view.
        """
        if not raw_text:
            return {"title": "Импортированный рейд", "participants": []}

        friends = friend_ids or set()
        sent = sent_user_ids or set()

        # Поиск 64-битных и обычных цифровых ID (например 9000000000141538 или 437225657)
        id_pattern = re.compile(r"\b(9\d{15}|\d{6,12})\b")
        found_ids = set(id_pattern.findall(raw_text))

        # Поиск ссылок вида vk.com/id123456 или t.me/...
        vk_pattern = re.compile(r"vk\.com/id(\d+)")
        for m in vk_pattern.findall(raw_text):
            found_ids.add(m)

        if current_user_id:
            found_ids.discard(str(current_user_id))

        # Попытка извлечь заголовок / бригаду из первой строки
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        first_line = lines[0] if lines else "Импортированный рейд"

        # Извлечение урона для каждого игрока по строкам
        player_damage_map = {}
        for line in lines:
            line_ids = id_pattern.findall(line) + vk_pattern.findall(line)
            if line_ids:
                dmg = parse_damage_string(line)
                for lid in line_ids:
                    player_damage_map[lid] = dmg

        participants = []
        sem = asyncio.Semaphore(5)

        async def _enrich_participant(uid_str: str) -> Dict[str, Any]:
            uid = int(uid_str)
            nick = f"Игрок {uid}"
            level = 0
            authority = 0
            photo = None
            claimed_dmg = player_damage_map.get(uid_str, 0)

            if player_api:
                try:
                    async with sem:
                        p_view = await player_api.get_player_view(uid)
                        p_data = p_view.get("data") if isinstance(p_view.get("data"), dict) else p_view
                        if isinstance(p_data, dict):
                            nick = p_data.get("nickname") or p_data.get("name") or nick
                            authority = int(p_data.get("resources", {}).get("authority") or p_data.get("authority") or 0)
                            level = int(p_data.get("level") or p_data.get("lvl") or 0)
                            photo = p_data.get("photoUrl") or p_data.get("avatarUrl")
                except Exception as e:
                    logger.debug(f"Не удалось загрузить инфо игрока {uid}: {e}")

            if level == 0 and authority > 0:
                level = calculate_level_from_authority(authority)

            friend_status = "friend" if uid in friends else "sent" if uid in sent else "none"

            return {
                "userId": uid,
                "nickname": nick,
                "level": level,
                "authority": authority,
                "claimedDamage": claimed_dmg,
                "photoUrl": photo,
                "friendStatus": friend_status,
            }

        tasks = [_enrich_participant(uid_str) for uid_str in list(found_ids)[:50]]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)

        for p in enriched:
            if isinstance(p, dict) and p.get("userId"):
                participants.append(p)

        # Сортируем по заявленному урону или авторитету
        participants.sort(key=lambda x: (x.get("claimedDamage", 0), x.get("authority", 0)), reverse=True)

        return {
            "title": first_line[:100],
            "totalFound": len(participants),
            "participants": participants,
        }

    async def collect_top_brigades_candidates(
        self,
        social_api: Any,
        db_engine: Any,
        account_id: int = 1,
        top_brigades_limit: int = 15,
        self_id: Optional[int] = None,
        delay_sec: float = 0.35,
    ) -> Dict[str, Any]:
        """
        Живой сбор участников из топа/списка бригад игры (GET /api/guild/recruitment/list + /api/guild/{id}/members).
        Сохраняет кандидатов в tracked_candidates с каноническим source='brigades' и brigade_name.
        """
        if not social_api or not db_engine:
            return {"success": False, "collected": 0, "brigades_scanned": 0}

        try:
            raw_list = await social_api.get_recruitment_list(limit=max(20, int(top_brigades_limit)))
        except Exception as e:
            logger.warning("Ошибка загрузки списка бригад: %s", e)
            return {"success": False, "collected": 0, "brigades_scanned": 0, "error": str(e)}

        guilds = raw_list if isinstance(raw_list, list) else (raw_list.get("guilds") or raw_list.get("items") or [] if isinstance(raw_list, dict) else [])
        guilds = [g for g in guilds if isinstance(g, dict) and (g.get("guildId") or g.get("id"))][:top_brigades_limit]

        now = datetime.utcnow()
        collected = 0
        brigades_scanned = 0
        seen_uids: Set[int] = set()

        for idx, g in enumerate(guilds):
            if idx > 0 and delay_sec > 0:
                await asyncio.sleep(delay_sec)
            gid = int(g.get("guildId") or g.get("id"))
            g_name = str(g.get("name") or f"Бригада #{gid}").strip()

            try:
                m_raw = await social_api.get_guild_members(gid)
            except Exception as ge:
                if "429" in str(ge):
                    logger.warning("429 при опросе бригады %s — остановка пачки", gid)
                    break
                continue

            brigades_scanned += 1
            members = m_raw if isinstance(m_raw, list) else (m_raw.get("members") or m_raw.get("players") or [] if isinstance(m_raw, dict) else [])
            if not members:
                continue

            async with get_session(db_engine) as session:
                for m in members:
                    if not isinstance(m, dict):
                        continue
                    uid_raw = m.get("userId") or m.get("id")
                    if not uid_raw:
                        continue
                    uid = int(uid_raw)
                    if (self_id is not None and uid == int(self_id)) or uid in seen_uids:
                        continue
                    seen_uids.add(uid)

                    nick = str(m.get("nickname") or m.get("name") or f"Игрок {uid}").strip()
                    authority = int(m.get("authority") or 0)
                    level = int(m.get("level") or 0)
                    if level == 0 and authority > 0:
                        level = calculate_level_from_authority(authority)
                    camp_obj = m.get("campActivity") if isinstance(m.get("campActivity"), dict) else {}
                    camp_total = int(camp_obj.get("total") or (m.get("campActivity") if isinstance(m.get("campActivity"), (int, float)) else 0) or 0)
                    act_rating = int(m.get("activityRating") or 0)
                    dmg = int(m.get("bossDamage") or m.get("totalDamage") or camp_obj.get("damage") or act_rating or 0)

                    cand = (
                        await session.execute(
                            select(TrackedCandidate).where(
                                TrackedCandidate.account_id == account_id,
                                TrackedCandidate.user_id == uid,
                            )
                        )
                    ).scalar_one_or_none()

                    from client.api.player import extract_obshak_from_payload
                    ob_has, ob_type = extract_obshak_from_payload(m)

                    if not cand:
                        cand = TrackedCandidate(
                            account_id=account_id,
                            user_id=uid,
                            nickname=nick,
                            photo_url=m.get("photoUrl") or m.get("avatarUrl"),
                            guild_id=gid,
                            guild_name=g_name,
                            brigade_name=g_name,
                            level=level,
                            authority=authority,
                            total_damage=dmg,
                            camp_activity=camp_total,
                            source="brigades",
                            is_active_recently=(act_rating > 0 or camp_total > 0),
                            has_obshak=bool(ob_has) if ob_type != "unknown" else None,
                            obshak_type=ob_type,
                            obshak_checked_at=time.time() if ob_type != "unknown" else None,
                            first_seen_at=now,
                            last_seen_at=now,
                            last_snapshot_at=now,
                        )
                        session.add(cand)
                    else:
                        cand.last_seen_at = now
                        cand.nickname = nick or cand.nickname
                        cand.guild_id = gid
                        cand.guild_name = g_name
                        cand.brigade_name = g_name
                        cand.source = "brigades"
                        if dmg > int(cand.total_damage or 0):
                            cand.total_damage = dmg
                        if authority > int(cand.authority or 0):
                            cand.authority = authority
                        if act_rating > 0 or camp_total > 0:
                            cand.is_active_recently = True
                        if ob_type != "unknown":
                            cand.has_obshak = bool(ob_has)
                            cand.obshak_type = ob_type
                            cand.obshak_checked_at = time.time()
                    collected += 1
                await session.commit()

        return {
            "success": True,
            "collected": collected,
            "players_saved": collected,
            "brigades_scanned": brigades_scanned,
            "guilds_scanned": brigades_scanned,
        }

    async def enrich_candidates_profiles_and_obshak(
        self,
        player_api: Any,
        db_engine: Any,
        account_id: int = 1,
        user_ids: Optional[List[int]] = None,
        max_profiles: int = 25,
        delay_sec: float = 0.3,
        ttl_seconds: float = 86400.0,
        prioritized_sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Единое обогащение профилей кандидатов: за 1 запрос get_player_view(uid) обновляет
        nickname, authority, level, total_damage, brigade_name, has_obshak, obshak_type и obshak_checked_at.
        """
        if not player_api or not db_engine:
            return {"success": False, "checked": 0, "updated": 0, "with_obshak": 0, "rate_limited": False}

        from client.api.player import extract_obshak_from_payload
        from core.database import get_candidates_needing_profile_enrichment

        now_ts = time.time()
        limit_n = max(1, min(50, int(max_profiles or 25)))
        checked = 0
        updated = 0
        with_obshak = 0
        rate_limited = False

        if user_ids:
            clean_ids = [int(u) for u in user_ids if u]
            if not clean_ids:
                return {"success": True, "checked": 0, "updated": 0, "with_obshak": 0, "rate_limited": False}
            async with get_session(db_engine) as session:
                rows = (
                    await session.execute(
                        select(TrackedCandidate).where(
                            TrackedCandidate.account_id == account_id,
                            TrackedCandidate.user_id.in_(clean_ids),
                        )
                    )
                ).scalars().all()
                to_check_ids = [
                    int(r.user_id) for r in rows
                    if (getattr(r, "obshak_type", "unknown") in (None, "", "unknown"))
                    or (getattr(r, "obshak_checked_at", None) is None)
                    or ((now_ts - float(r.obshak_checked_at)) > ttl_seconds)
                ][:limit_n]
        else:
            prio_cands = await get_candidates_needing_profile_enrichment(
                account_id=account_id,
                limit=limit_n,
                ttl_sec=int(ttl_seconds),
                prioritized_sources=prioritized_sources,
                engine=db_engine,
            )
            to_check_ids = [int(c.user_id) for c in prio_cands if getattr(c, "user_id", None) is not None]

        if not to_check_ids:
            return {"success": True, "checked": 0, "updated": 0, "with_obshak": 0, "rate_limited": False}

        async with get_session(db_engine) as session:
            rows_db = (
                await session.execute(
                    select(TrackedCandidate).where(
                        TrackedCandidate.account_id == account_id,
                        TrackedCandidate.user_id.in_(to_check_ids),
                    )
                )
            ).scalars().all()
            by_uid = {int(r.user_id): r for r in rows_db}

            for idx, uid in enumerate(to_check_ids):
                cand = by_uid.get(uid)
                if not cand:
                    continue
                if idx > 0 and delay_sec > 0:
                    await asyncio.sleep(delay_sec)
                try:
                    pv = await player_api.get_player_view(uid)
                    checked += 1
                    p_data = pv.get("data") if isinstance(pv, dict) and isinstance(pv.get("data"), dict) else pv
                    ob_has, ob_type = extract_obshak_from_payload(p_data)
                    if ob_type == "unknown" and isinstance(p_data, dict):
                        # Полный ответ get_player_view без блока общака считаем проверенным (none)
                        ob_has, ob_type = False, "none"
                    cand.has_obshak = bool(ob_has)
                    cand.obshak_type = str(ob_type)
                    cand.obshak_checked_at = time.time()
                    if cand.has_obshak:
                        with_obshak += 1

                    if isinstance(p_data, dict):
                        p_nick = p_data.get("nickname") or p_data.get("name")
                        if p_nick:
                            cand.nickname = str(p_nick)
                        ext = extract_player_combat_stats(p_data)
                        if ext.get("authority", 0) > int(cand.authority or 0):
                            cand.authority = int(ext["authority"])
                        if ext.get("level", 0) > int(cand.level or 0):
                            cand.level = int(ext["level"])
                        elif (cand.level or 0) <= 1 and int(cand.authority or 0) > 0:
                            cand.level = calculate_level_from_authority(int(cand.authority))
                        if ext.get("totalDamage", 0) > int(cand.total_damage or 0):
                            cand.total_damage = int(ext["totalDamage"])
                        g_obj = p_data.get("guild")
                        if isinstance(g_obj, dict) and g_obj.get("name"):
                            cand.brigade_name = str(g_obj["name"])
                        elif p_data.get("guildName") or p_data.get("brigadeName"):
                            cand.brigade_name = str(p_data.get("guildName") or p_data.get("brigadeName"))
                    cand.enriched_at = datetime.utcnow()
                    updated += 1
                except Exception as exc:
                    if "429" in str(exc) or "too many" in str(exc).lower():
                        rate_limited = True
                        break
                    logger.debug("Ошибка обогащения профиля/общака %s: %s", uid, exc)
            await session.commit()

        return {
            "success": True,
            "checked": checked,
            "updated": updated,
            "with_obshak": with_obshak,
            "rate_limited": rate_limited,
        }

    async def enrich_candidates_obshak(
        self,
        player_api: Any,
        db_engine: Any,
        account_id: int = 1,
        user_ids: Optional[List[int]] = None,
        max_profiles: int = 15,
        delay_sec: float = 0.45,
        ttl_seconds: float = 86400.0,
    ) -> Dict[str, Any]:
        """Совместимая обёртка над единым обогащением профилей и общака."""
        return await self.enrich_candidates_profiles_and_obshak(
            player_api=player_api,
            db_engine=db_engine,
            account_id=account_id,
            user_ids=user_ids,
            max_profiles=max_profiles,
            delay_sec=delay_sec,
            ttl_seconds=ttl_seconds,
        )
