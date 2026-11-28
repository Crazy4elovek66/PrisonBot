import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import select

from client.http_client import get_game_now_ts
from core.database import (
    OUTREACH_SOURCE_LABELS,
    count_outreach_sent_last_24h,
    get_or_create_config,
    get_outreach_excluded_ids,
    get_session,
    is_worker_active,
    normalize_outreach_criteria,
    normalize_outreach_source,
    record_outreach_history,
)
from core.models import FriendStats, TrackedCandidate

logger = logging.getLogger(__name__)


def evaluate_outreach_candidate(
    cand: Any,
    criteria: Dict[str, Any],
    excluded_ids: Optional[Set[int]] = None,
    friend_ids: Optional[Set[int]] = None,
    sent_status_map: Optional[Dict[int, str]] = None,
    self_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Вычисляет канонический источник, точный `outreach_status` и человекочитаемую причину отсева `filter_reason`.
    """
    excluded = excluded_ids or set()
    friends = friend_ids or set()
    status_map = sent_status_map or {}
    crit = normalize_outreach_criteria(criteria)

    min_dmg = crit["min_damage"]
    max_dmg = crit["max_damage"]
    min_auth = crit["min_authority"]
    max_auth = crit["max_authority"]
    allowed_sources = {normalize_outreach_source(s) for s in (crit.get("sources") or [])}
    keywords = [kw.strip().lower() for kw in str(crit.get("exclude_keywords") or "").split(",") if kw.strip()]

    if isinstance(cand, dict):
        uid = int(cand.get("userId") or cand.get("user_id") or cand.get("id") or 0)
        nick = str(cand.get("nickname") or cand.get("name") or f"Игрок #{uid}")
        dmg = int(cand.get("damage") or max(int(cand.get("poisonDamage") or cand.get("poison_damage") or 0), int(cand.get("totalDamage") or cand.get("total_damage") or 0)))
        auth = int(cand.get("authority") or 0)
        src_raw = cand.get("source") or "weekly_top"
        sources_list = cand.get("sources") if isinstance(cand.get("sources"), list) else [src_raw]
        last_seen = str(cand.get("last_seen_at") or cand.get("lastSeenAt") or "")
        ob_type = str(cand.get("obshak_type") or "unknown").lower()
        has_ob = bool(cand.get("has_obshak"))
    else:
        uid = int(getattr(cand, "user_id", 0) or 0)
        nick = str(getattr(cand, "nickname", None) or f"Игрок #{uid}")
        dmg = int(max(int(getattr(cand, "poison_damage", 0) or 0), int(getattr(cand, "total_damage", 0) or 0)))
        auth = int(getattr(cand, "authority", 0) or 0)
        src_raw = getattr(cand, "source", "weekly_top") or "weekly_top"
        sources_list = [src_raw]
        ls_dt = getattr(cand, "last_seen_at", None)
        last_seen = ls_dt.isoformat() if ls_dt else ""
        ob_type = str(getattr(cand, "obshak_type", "unknown") or "unknown").lower()
        has_ob = bool(getattr(cand, "has_obshak", False))

    canon_sources = []
    for s in sources_list:
        cs = normalize_outreach_source(s)
        if cs and cs not in canon_sources:
            canon_sources.append(cs)
    canon_src = canon_sources[0] if canon_sources else normalize_outreach_source(src_raw)
    src_label = OUTREACH_SOURCE_LABELS.get(canon_src, canon_src)

    outreach_status = "matched"
    filter_reason = ""
    skip_reason_key = None

    if self_id is not None and uid == int(self_id):
        outreach_status = "filtered_out"
        filter_reason = "Собственный аккаунт"
        skip_reason_key = "self_skipped"
    elif uid in friends:
        outreach_status = "already_friend"
        filter_reason = "Уже в друзьях"
        skip_reason_key = "already_friend"
    elif uid in excluded or uid in status_map:
        raw_st = str(status_map.get(uid) or "sent").lower()
        if raw_st == "already_friend":
            outreach_status = "already_friend"
            filter_reason = "Уже в друзьях"
            skip_reason_key = "already_friend"
        elif raw_st == "already_pending":
            outreach_status = "already_pending"
            filter_reason = "Заявка уже отправлена"
            skip_reason_key = "already_sent"
        elif raw_st == "privacy_blocked":
            outreach_status = "privacy_blocked"
            filter_reason = "Закрыты заявки в друзья"
            skip_reason_key = "already_sent"
        elif raw_st == "ignored":
            outreach_status = "ignored"
            filter_reason = "Заявка проигнорирована (ранее отправлялась)"
            skip_reason_key = "already_sent"
        else:
            outreach_status = "sent"
            filter_reason = "Заявка отправлена"
            skip_reason_key = "already_sent"
    elif not (set(canon_sources) & allowed_sources):
        outreach_status = "filtered_out"
        filter_reason = "Источник отключен"
        skip_reason_key = "source_filtered"
    elif dmg < min_dmg:
        outreach_status = "filtered_out"
        filter_reason = "Урон ниже порога"
        skip_reason_key = "damage_out_of_range"
    elif max_dmg > 0 and dmg > max_dmg:
        outreach_status = "filtered_out"
        filter_reason = "Урон выше порога"
        skip_reason_key = "damage_out_of_range"
    elif auth < min_auth or (max_auth > 0 and auth > max_auth):
        outreach_status = "filtered_out"
        filter_reason = "Авторитет вне диапазона"
        skip_reason_key = "authority_out_of_range"
    elif keywords:
        low_nick = nick.lower()
        hit_kw = next((kw for kw in keywords if kw in low_nick), None)
        if hit_kw:
            outreach_status = "filtered_out"
            filter_reason = f"Исключен по слову «{hit_kw}»"
            skip_reason_key = "keyword_excluded"

    ob_filter = str(crit.get("obshak_filter") or "any").lower()
    if outreach_status == "matched" and ob_filter != "any":
        if ob_filter in ("has_any", "has_obshak") and not (has_ob or ob_type in ("pacan", "blat", "vor", "avtoritet")):
            outreach_status = "filtered_out"
            filter_reason = "Нет общака"
            skip_reason_key = "source_filtered"
        elif ob_filter in ("none", "no_obshak") and (has_ob or ob_type != "none"):
            outreach_status = "filtered_out"
            filter_reason = "Есть общак (фильтр: без общака)"
            skip_reason_key = "source_filtered"
        elif ob_filter in ("pacan", "blat", "vor", "avtoritet") and ob_type != ob_filter:
            outreach_status = "filtered_out"
            filter_reason = f"Требуется общак ({ob_filter})"
            skip_reason_key = "source_filtered"

    return {
        "userId": uid,
        "nickname": nick,
        "damage": dmg,
        "authority": auth,
        "source": canon_src,
        "sources": canon_sources,
        "source_label": src_label,
        "last_seen_at": last_seen,
        "outreach_status": outreach_status,
        "filter_reason": filter_reason,
        "matches_criteria": outreach_status == "matched",
        "_skip_key": skip_reason_key,
    }


def filter_outreach_candidates(
    candidates: Iterable[Any],
    criteria: Dict[str, Any],
    excluded_ids: Optional[Set[int]] = None,
    friend_ids: Optional[Set[int]] = None,
    self_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Чистая детерминированная фильтрация и сортировка кандидатов для авто-рассылки.
    Возвращает `(matched_candidates, skip_stats)`.
    """
    crit = normalize_outreach_criteria(criteria)
    sort_by = crit["sort_by"]

    skip_stats = {
        "self_skipped": 0,
        "already_friend": 0,
        "already_sent": 0,
        "damage_out_of_range": 0,
        "authority_out_of_range": 0,
        "source_filtered": 0,
        "keyword_excluded": 0,
    }
    matched: List[Dict[str, Any]] = []
    seen_uids: Set[int] = set()

    for c in candidates:
        ev = evaluate_outreach_candidate(
            c,
            criteria=crit,
            excluded_ids=excluded_ids,
            friend_ids=friend_ids,
            self_id=self_id,
        )
        uid = ev["userId"]
        if uid <= 0 or uid in seen_uids:
            continue
        seen_uids.add(uid)

        sk = ev.pop("_skip_key", None)
        if ev["matches_criteria"]:
            matched.append(ev)
        elif sk and sk in skip_stats:
            skip_stats[sk] += 1

    if sort_by == "damage":
        matched.sort(key=lambda x: (x["damage"], x["authority"]), reverse=True)
    elif sort_by == "authority":
        matched.sort(key=lambda x: (x["authority"], x["damage"]), reverse=True)
    else:
        matched.sort(key=lambda x: (x["last_seen_at"], x["damage"]), reverse=True)

    return matched, skip_stats


class FriendOutreachWorker:
    """
    Самостоятельный воркер авто-рассылки заявок в друзья по активным игрокам.
    """

    def __init__(
        self,
        account_id: int,
        social_api: Any,
        player_api: Any = None,
        raids_api: Any = None,
        db_engine: Any = None,
        state_hub: Any = None,
        enable_jitter: bool = True,
    ):
        self.account_id = account_id
        self.social_api = social_api
        self.player_api = player_api
        self.raids_api = raids_api
        self.db_engine = db_engine
        self.state_hub = state_hub
        self.enable_jitter = enable_jitter
        self._lock = asyncio.Lock()
        self._enrichment_lock = asyncio.Lock()

        self.cooldown_until_ts: float = 0.0
        self.enrichment_cooldown_until_ts: float = 0.0
        self.enrichment_in_progress: bool = False
        self.last_run_ts: float = 0.0
        self.last_error: str = ""
        self.last_sent_player: Optional[Dict[str, Any]] = None
        self.worker_status: str = "Ожидание запуска"
        self.last_skip_stats: Dict[str, int] = {}

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "worker_status": self.worker_status,
            "last_run_ts": self.last_run_ts,
            "last_error": self.last_error,
            "last_sent_player": self.last_sent_player,
            "cooldown_until_ts": self.cooldown_until_ts,
            "enrichment_in_progress": bool(self.enrichment_in_progress or self._enrichment_lock.locked()),
            "enrichment_cooldown_until_ts": self.enrichment_cooldown_until_ts,
            "skip_stats": dict(self.last_skip_stats),
        }

    def wake_enrichment(self, batch_size: int = 25) -> None:
        """Неблокирующе будит фоновое обогащение профилей/общака сразу после скана источников."""
        if not self.player_api or self._enrichment_lock.locked():
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.run_profile_enrichment_pass(batch_size=batch_size))
        except RuntimeError:
            pass

    async def run_profile_enrichment_pass(
        self,
        batch_size: int = 25,
        user_ids: Optional[List[int]] = None,
        delay_sec: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Автоматический фоновый проход обогащения профилей и общака (работает даже при auto_friend_outreach=False).
        За 1 запрос get_player_view обновляет authority, level, total_damage, nickname, brigade_name и obshak_type.
        """
        from core.database import get_obshak_coverage_stats, normalize_outreach_criteria
        from core.models import BotConfig
        from sqlalchemy import select

        if not self.player_api:
            return {"status": "no_player_api", "checked": 0, "updated": 0, "with_obshak": 0}

        eng = self.db_engine or get_engine()
        now_ts = get_game_now_ts()
        if not user_ids and self.enrichment_cooldown_until_ts > now_ts:
            return {
                "status": "cooldown",
                "cooldown_sec": round(self.enrichment_cooldown_until_ts - now_ts, 1),
                "checked": 0,
                "updated": 0,
                "with_obshak": 0,
            }

        async with self._enrichment_lock:
            self.enrichment_in_progress = True
            try:
                prio_sources: Optional[List[str]] = None
                try:
                    async with get_session(eng) as session:
                        cfg = (
                            await session.execute(select(BotConfig).where(BotConfig.account_id == self.account_id))
                        ).scalar_one_or_none()
                        if cfg is not None:
                            crit = normalize_outreach_criteria(getattr(cfg, "outreach_criteria", None), cfg=cfg)
                            prio_sources = crit.get("sources")
                except Exception:
                    prio_sources = None

                r_api = self.raids_api
                if r_api is None:
                    from client.api.raids import RaidsAPI
                    r_api = RaidsAPI()
                    self.raids_api = r_api

                res = await r_api.enrich_candidates_profiles_and_obshak(
                    player_api=self.player_api,
                    db_engine=eng,
                    account_id=self.account_id,
                    user_ids=user_ids,
                    max_profiles=batch_size,
                    delay_sec=delay_sec,
                    ttl_seconds=86400.0,
                    prioritized_sources=prio_sources,
                )
                if res.get("rate_limited"):
                    self.enrichment_cooldown_until_ts = get_game_now_ts() + 120.0

                coverage = await get_obshak_coverage_stats(account_id=self.account_id, engine=eng)
                if res.get("updated", 0) > 0:
                    hub = self.state_hub
                    if hub is None:
                        try:
                            from core.state_hub import state_hub as global_hub
                            hub = global_hub
                        except Exception:
                            hub = None
                    if hub is not None:
                        try:
                            hub.invalidate_slice(self.account_id, "outreach")
                            hub.emit_change(
                                self.account_id,
                                ["outreach", "active_players"],
                                patch={"obshak_coverage": coverage},
                                reason="profile_obshak_enrichment",
                            )
                        except Exception as e:
                            logger.debug("Ошибка публикации obshak_coverage в StateHub: %s", e)

                return {
                    "status": "rate_limited" if res.get("rate_limited") else "success",
                    **res,
                    "obshak_coverage": coverage,
                }
            finally:
                self.enrichment_in_progress = False

    def _publish_state(self, status_payload: Dict[str, Any]) -> None:
        hub = self.state_hub
        if hub is None:
            try:
                from core.state_hub import state_hub as global_hub
                hub = global_hub
            except Exception:
                hub = None
        if hub is None:
            return
        try:
            hub.invalidate_slice(self.account_id, "friends")
            hub.update_slice(self.account_id, "outreach", status_payload, source_tag="outreach_worker")
            hub.emit_change(self.account_id, ["outreach", "active_players", "friends"], patch={"outreach": status_payload}, reason="outreach_cycle")
        except Exception as e:
            logger.debug("Ошибка публикации outreach в StateHub: %s", e)

    async def _load_candidates_and_friends(self) -> Tuple[List[TrackedCandidate], Set[int], Optional[int]]:
        candidates: List[TrackedCandidate] = []
        friend_ids: Set[int] = set()
        self_id: Optional[int] = None

        if self.player_api is not None:
            try:
                me = await self.player_api.get_me()
                if isinstance(me, dict):
                    uid = me.get("id") or me.get("userId")
                    if uid:
                        self_id = int(uid)
            except Exception:
                pass

        if self.social_api is not None:
            try:
                if hasattr(self.social_api, "get_all_friend_ids"):
                    friend_ids = await self.social_api.get_all_friend_ids()
            except Exception:
                pass

        if self.db_engine is not None:
            async with get_session(self.db_engine) as session:
                rows = (
                    await session.execute(
                        select(TrackedCandidate).where(TrackedCandidate.account_id == self.account_id)
                    )
                ).scalars().all()
                candidates = list(rows)
                if not friend_ids:
                    f_rows = (
                        await session.execute(
                            select(FriendStats.user_id).where(
                                FriendStats.account_id == self.account_id,
                                FriendStats.is_current_friend == True,
                            )
                        )
                    ).scalars().all()
                    friend_ids = {int(uid) for uid in f_rows if uid is not None}

        return candidates, friend_ids, self_id

    async def run_cycle(self, manual: bool = False) -> Dict[str, Any]:
        """Запускает один цикл безопасной авто-рассылки заявок в друзья."""
        async with self._lock:
            now_ts = get_game_now_ts()
            self.last_run_ts = now_ts

            config = await get_or_create_config(self.account_id, self.db_engine)
            criteria = normalize_outreach_criteria(getattr(config, "outreach_criteria", None), cfg=config)
            daily_limit = criteria["daily_limit"]

            if not manual:
                if not is_worker_active(config):
                    self.worker_status = "Пауза (бот на паузе или режим сна)"
                    return {"status": "skipped", "reason": "paused_or_sleep", **self.get_telemetry()}
                if not criteria["enabled"]:
                    self.worker_status = "Выключен"
                    return {"status": "skipped", "reason": "outreach_disabled", **self.get_telemetry()}
                if now_ts < self.cooldown_until_ts:
                    rem_cd = int(self.cooldown_until_ts - now_ts)
                    self.worker_status = f"Пауза (ожидание {rem_cd}с: {self.last_error or 'лимит'})"
                    return {"status": "cooldown", "cooldownSeconds": rem_cd, **self.get_telemetry()}

            sent_24h = await count_outreach_sent_last_24h(self.account_id, now_ts=now_ts, engine=self.db_engine)
            remaining = max(0, daily_limit - sent_24h)

            if remaining == 0:
                self.worker_status = f"Достигнут лимит {sent_24h}/{daily_limit} за 24ч"
                payload = {
                    "success": True,
                    "server_now_ts": round(now_ts, 3),
                    "sent_24h": sent_24h,
                    "daily_limit": daily_limit,
                    "matched_count": 0,
                    "criteria": criteria,
                    **self.get_telemetry(),
                }
                self._publish_state(payload)
                return {"status": "limit_reached", "sent_count": 0, **payload}

            if self.raids_api is not None and self.social_api is not None:
                try:
                    await self.raids_api.sync_weekly_top_and_achievements(
                        social_api=self.social_api,
                        db_engine=self.db_engine,
                        account_id=self.account_id,
                    )
                except Exception as te:
                    logger.debug("Ошибка синхронизации weekly_top в FriendOutreachWorker: %s", te)

            if str(criteria.get("obshak_filter") or "any").lower() != "any" and self.player_api is not None:
                try:
                    await self.run_profile_enrichment_pass(batch_size=15)
                except Exception as ee:
                    logger.debug("Ошибка авто-допроверки общака в run_cycle: %s", ee)

            candidates, friend_ids, self_id = await self._load_candidates_and_friends()
            excluded_ids = await get_outreach_excluded_ids(self.account_id, engine=self.db_engine)
            matched, skip_stats = filter_outreach_candidates(
                candidates,
                criteria=criteria,
                excluded_ids=excluded_ids,
                friend_ids=friend_ids,
                self_id=self_id,
            )
            self.last_skip_stats = skip_stats

            if not matched:
                self.worker_status = "Нет подходящих кандидатов по текущим критериям"
                payload = {
                    "success": True,
                    "server_now_ts": round(now_ts, 3),
                    "sent_24h": sent_24h,
                    "daily_limit": daily_limit,
                    "matched_count": 0,
                    "criteria": criteria,
                    **self.get_telemetry(),
                }
                self._publish_state(payload)
                return {"status": "no_candidates", "sent_count": 0, **payload}

            batch_limit = min(remaining, criteria["batch_size"])
            sent_in_cycle = 0
            self.last_error = ""

            for idx, cand in enumerate(matched):
                if sent_in_cycle >= batch_limit:
                    break
                if idx > 0:
                    delay = float(criteria["delay_between_requests_sec"])
                    if self.enable_jitter:
                        delay = max(0.5, delay + random.uniform(-0.5, 0.5))
                    await asyncio.sleep(delay)

                uid = int(cand["userId"])
                nick = cand["nickname"]
                try:
                    res = await self.social_api.send_friend_request(uid)
                    is_ok = bool(res.get("success", True)) if isinstance(res, dict) else True
                    msg = str(res.get("message", "") if isinstance(res, dict) else "")
                    err_code = str(res.get("code", "") if isinstance(res, dict) else "").lower()
                    low_msg = msg.lower()

                    if err_code == "already_friends" or "уже в друзьях" in low_msg or "already friend" in low_msg:
                        await record_outreach_history(
                            self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                            status="already_friend", error_message=msg, sent_at=get_game_now_ts(), engine=self.db_engine,
                        )
                        continue
                    if "уже отправлена" in low_msg or "already pending" in low_msg or "already sent" in low_msg:
                        await record_outreach_history(
                            self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                            status="already_pending", error_message=msg, sent_at=get_game_now_ts(), engine=self.db_engine,
                        )
                        continue
                    if "закры" in low_msg or "privacy" in low_msg:
                        await record_outreach_history(
                            self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                            status="privacy_blocked", error_message=msg, sent_at=get_game_now_ts(), engine=self.db_engine,
                        )
                        continue
                    if err_code in ("friends_limit_reached", "target_friends_limit_reached") or "лимит" in low_msg or "limit" in low_msg:
                        if err_code == "target_friends_limit_reached":
                            await record_outreach_history(
                                self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                                status="privacy_blocked", error_message=msg, sent_at=get_game_now_ts(), engine=self.db_engine,
                            )
                            continue
                        self.last_error = msg or "Достигнут лимит друзей/заявок на сервере"
                        self.cooldown_until_ts = get_game_now_ts() + 1800.0
                        self.worker_status = f"Пауза ({self.last_error})"
                        break

                    if is_ok:
                        cur_ts = get_game_now_ts()
                        await record_outreach_history(
                            self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                            status="sent", sent_at=cur_ts, engine=self.db_engine,
                        )
                        sent_in_cycle += 1
                        sent_24h += 1
                        self.last_sent_player = {"userId": uid, "nickname": nick, "sent_at": cur_ts}
                    else:
                        await record_outreach_history(
                            self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                            status="error", error_message=msg, sent_at=get_game_now_ts(), engine=self.db_engine,
                        )
                except Exception as exc:
                    err_str = str(exc)
                    low_err = err_str.lower()
                    if "429" in err_str or "too many" in low_err:
                        self.last_error = "Сервер ограничил частоту (429)"
                        self.cooldown_until_ts = get_game_now_ts() + 300.0
                        self.worker_status = f"Пауза ({self.last_error})"
                        break
                    if "лимит" in low_err or "limit" in low_err:
                        self.last_error = err_str[:160]
                        self.cooldown_until_ts = get_game_now_ts() + 1800.0
                        self.worker_status = f"Пауза ({self.last_error})"
                        break
                    await record_outreach_history(
                        self.account_id, uid, nick, cand["source"], cand["damage"], cand["authority"],
                        status="error", error_message=err_str[:250], sent_at=get_game_now_ts(), engine=self.db_engine,
                    )

            if not self.last_error:
                self.worker_status = "Активен" if criteria["enabled"] else "Готов (ручной прогон)"

            payload = {
                "success": True,
                "server_now_ts": round(get_game_now_ts(), 3),
                "sent_24h": sent_24h,
                "daily_limit": daily_limit,
                "matched_count": max(0, len(matched) - sent_in_cycle),
                "sent_in_cycle": sent_in_cycle,
                "criteria": criteria,
                **self.get_telemetry(),
            }
            self._publish_state(payload)
            return {"status": "success", "sent_count": sent_in_cycle, **payload}
