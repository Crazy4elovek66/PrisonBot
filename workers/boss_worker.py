import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx
from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active
from core.models import ActionLog, FriendStats, BossFriendDamageLog, BossPreset
from sqlalchemy import select
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


class BossWorker:
    """
    Воркер автоматического мониторинга и ведения боя с боссами:
    1. Проверка наличия и сбор наград за поверженных боссов.
    2. Проверка активного боя с боссом.
    3. Определение доступных и готовых бесплатных рукопашных ударов (punchChest, kickBalls, pokeEyes, kneeEar).
    4. Нанесение серии готовых ударов без расхода платного оружия.
    5. Запись результатов в ActionLog.
    """

    def __init__(
        self,
        account_id: int,
        boss_api: BossAPI,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
    ):
        self.account_id = account_id
        self.api = boss_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.is_paused: bool = False

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

    async def record_friends_damage(
        self,
        bootstrap: Dict[str, Any],
        boss_session_id: Optional[str] = None,
        boss_id: Optional[int] = None,
    ) -> int:
        """
        Сбор и дедуплицированная запись реального урона друзей по boss_session_id
        в BossFriendDamageLog и обновление FriendStats.
        Возвращает количество обработанных друзей.
        """
        if not self.db_engine:
            return 0

        session_data = bootstrap.get("session") or {}
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
        top_dmg = reward_data.get("topDamage") or bootstrap.get("topDamage") or bootstrap.get("friendDamageItems") or []
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
            from sqlalchemy import select

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

    async def check_scheduled_presets(self, now_utc: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Проверка и запуск сохраненных пресетов боссов по расписанию МСК (UTC+3):
        - Минутный тикер;
        - Проверка активности воркера (is_worker_active);
        - Вычисление времени и даты по МСК;
        - Защита от повторного запуска в те же сутки (last_run_date_msk != today_msk);
        - Запуск run_cycle() при срабатывании расписания.
        """
        if self.is_paused:
            return None

        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            return None

        now_utc_dt = now_utc or datetime.now(timezone.utc)
        now_msk = now_utc_dt + timedelta(hours=3)
        today_msk = now_msk.strftime("%Y-%m-%d")
        hhmm_msk = now_msk.strftime("%H:%M")

        if not self.db_engine:
            return None

        async with get_session(self.db_engine) as session:
            # Проверяем, не выполняется ли уже какой-либо пресет для этого аккаунта
            stmt_running = select(BossPreset).where(
                BossPreset.account_id == self.account_id,
                BossPreset.is_running == True,
            )
            res_running = await session.execute(stmt_running)
            if res_running.scalar_one_or_none() is not None:
                return None

            # Ищем пресет, готовый к запуску сегодня
            stmt = select(BossPreset).where(
                BossPreset.account_id == self.account_id,
                BossPreset.daily_enabled == True,
            ).order_by(BossPreset.schedule_time_msk.asc())
            res = await session.execute(stmt)
            presets = res.scalars().all()

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

    async def run_cycle(self) -> Dict[str, Any]:
        """Выполняет один цикл проверки и атаки босса."""
        logger.info(f"=== [Аккаунт {self.account_id}] Запуск цикла проверки боссов ===")

        # Проверка живого BotConfig
        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            logger.info("Планировщик на паузе или активен режим сна. Пропуск боссов.")
            return {"status": "skipped", "reason": "paused_or_sleep"}

        results: Dict[str, Any] = {
            "account_id": self.account_id,
            "rewards_claimed": 0,
            "hits_performed": [],
            "boss_active": False,
            "boss_hp_remaining": None,
            "errors": [],
        }

        # 0. Проверяем наличие активного запущенного пресета
        active_preset: Optional[BossPreset] = None
        preset_steps: List[Dict[str, Any]] = []
        if self.db_engine:
            try:
                async with get_session(self.db_engine) as db_sess:
                    stmt_act = select(BossPreset).where(
                        BossPreset.account_id == self.account_id,
                        BossPreset.is_running == True,
                    )
                    res_act = await db_sess.execute(stmt_act)
                    active_preset = res_act.scalar_one_or_none()
                    if active_preset and active_preset.items:
                        b_cat = _load_bosses_catalog() or FALLBACK_BOSSES
                        names_map = {b["id"]: b.get("name") for b in b_cat}
                        for itm in active_preset.items:
                            if not isinstance(itm, dict):
                                continue
                            cnt = max(1, int(itm.get("count") or 1))
                            b_id = itm.get("bossId") or itm.get("boss_id")
                            if not b_id:
                                continue
                            b_id_int = int(b_id)
                            b_name = itm.get("bossName") or itm.get("name") or names_map.get(b_id_int) or f"Босс #{b_id}"
                            b_mode = itm.get("mode") or "pacansky"
                            for _ in range(cnt):
                                preset_steps.append({"bossId": b_id_int, "bossName": b_name, "mode": b_mode})
            except Exception as e:
                logger.warning(f"Ошибка чтения активного пресета: {e}")

        # Если пресет завершен по шагам
        if active_preset and (not preset_steps or active_preset.current_step_index >= len(preset_steps)):
            if self.db_engine:
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
            active_preset = None

        # 1. Загрузка состояния боя
        try:
            bootstrap = await self.api.get_bootstrap()
        except Exception as e:
            logger.error(f"Ошибка при получении bootstrap босса: {e}")
            results["errors"].append(f"get_bootstrap: {str(e)}")
            await self._log_action("get_bootstrap", "/api/boss/bootstrap", 500, False, {"error": str(e)})
            return results

        # 2. Проверка и сбор наград за поверженных боссов
        has_reward = bool(bootstrap.get("hasReward", False))
        unclaimed = bootstrap.get("unclaimedRewards") or []
        claim_ids: List[Optional[str]] = []

        if isinstance(unclaimed, list) and len(unclaimed) > 0:
            for item in unclaimed:
                if item is not None and str(item).strip():
                    claim_ids.append(str(item))
        elif has_reward:
            claim_id = bootstrap.get("claimId")
            claim_ids.append(str(claim_id) if claim_id else None)

        for cid in claim_ids:
            try:
                # Фиксируем урон друзей перед сбором награды
                await self.record_friends_damage(bootstrap, boss_session_id=cid)

                logger.info(f"Сбор награды за босса (claimId={cid})...")
                claim_res = await self.api.claim_reward(cid)
                results["rewards_claimed"] += 1
                await self._log_action("claim_boss_reward", "/api/boss/claim", 200, True, claim_res)
                logger.info(f"Награда за босса успешно собрана: {claim_res}")

                # Сохранение уведомления в Notification с дедупликацией
                parsed = DropParser.parse_boss_claim(
                    claim_res,
                    boss_name=bootstrap.get("session", {}).get("bossName") or bootstrap.get("title") or "Босс",
                    mode=bootstrap.get("session", {}).get("mode"),
                )
                b_sess_id = bootstrap.get("session", {}).get("sessionId") or cid or "latest"
                parsed["event_key"] = f"boss_claim_{b_sess_id}"
                await DropParser.save_notification(self.account_id, parsed, self.db_engine)

                # Если выполняется пресет, продвигаем шаг после сбора награды
                if active_preset and self.db_engine:
                    async with get_session(self.db_engine) as db_sess:
                        p_obj = await db_sess.get(BossPreset, active_preset.id)
                        if p_obj:
                            p_obj.current_step_index += 1
                            if p_obj.current_step_index >= len(preset_steps):
                                p_obj.is_running = False
                                p_obj.last_status = f"Выполнен ({len(preset_steps)}/{len(preset_steps)})"
                            else:
                                nxt = preset_steps[p_obj.current_step_index]
                                p_obj.last_status = f"Выполняется: шаг {p_obj.current_step_index + 1}/{len(preset_steps)} ({nxt['bossName']})"
                            db_sess.add(p_obj)
                            await db_sess.commit()
                            active_preset = p_obj if p_obj.is_running else None

                await self._jitter()
            except Exception as e:
                logger.error(f"Ошибка сбора награды за босса: {e}")
                results["errors"].append(f"claim_reward: {str(e)}")
                await self._log_action("claim_boss_reward", "/api/boss/claim", 500, False, {"error": str(e)})

        # 3. Проверка активного боя и авто-призыв босса при необходимости
        state = bootstrap.get("state")
        session = bootstrap.get("session") or {}
        current_hp = session.get("currentHp")

        # Приоритет A: Если активен пресет боссов
        if (state != "active" or not session or current_hp is None or current_hp <= 0) and active_preset:
            boss_catalog = {b["id"]: dict(b) for b in (_load_bosses_catalog() or FALLBACK_BOSSES)}
            eval_list = list(boss_catalog.values())
            BossAPI.evaluate_bosses_availability(eval_list, bootstrap=bootstrap)
            eval_by_id = {b["id"]: b for b in eval_list}

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
                        f"Пресет '{active_preset.name}': пропуск заблокированного шага {active_preset.current_step_index + 1}/{len(preset_steps)} "
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
                    if self.db_engine:
                        async with get_session(self.db_engine) as db_sess:
                            p_obj = await db_sess.get(BossPreset, active_preset.id)
                            if p_obj:
                                p_obj.current_step_index += 1
                                if p_obj.current_step_index >= len(preset_steps):
                                    p_obj.is_running = False
                                    p_obj.last_status = "Выполнен (шаги завершены или пропущены)"
                                else:
                                    p_obj.last_status = f"Шаг {p_obj.current_step_index} пропущен ({block_reason})"
                                db_sess.add(p_obj)
                                await db_sess.commit()
                                active_preset = p_obj if p_obj.is_running else None
                    if not active_preset:
                        break
                    continue
                else:
                    # Босс доступен -> призываем!
                    try:
                        logger.info(f"Пресет '{active_preset.name}': призыв босса ID={b_id_int} {step['bossName']} (режим {b_mode})...")
                        summon_res = await self.api.start_battle(boss_id=b_id_int, mode=b_mode)
                        if summon_res.get("success") is not False:
                            logger.info(f"Бой с боссом ID={b_id_int} успешно запущен!")
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
                            bootstrap = await self.api.get_bootstrap()
                            session = bootstrap.get("session") or {}
                            state = bootstrap.get("state")
                            current_hp = session.get("currentHp")
                            break
                    except Exception as err:
                        logger.warning(f"Ошибка призыва босса в пресете: {err}")
                        if self.db_engine:
                            async with get_session(self.db_engine) as db_sess:
                                p_obj = await db_sess.get(BossPreset, active_preset.id)
                                if p_obj:
                                    p_obj.current_step_index += 1
                                    if p_obj.current_step_index >= len(preset_steps):
                                        p_obj.is_running = False
                                        p_obj.last_status = f"Завершен с ошибкой: {err}"
                                    else:
                                        p_obj.last_status = f"Ошибка шага {p_obj.current_step_index}: {err}"
                                    db_sess.add(p_obj)
                                    await db_sess.commit()
                                    active_preset = p_obj if p_obj.is_running else None
                        break

        # Приоритет B: Если пресет не активен, но включена автоатака боссов из очереди config.boss_targets
        is_summon_enabled = getattr(config, "auto_boss_enabled", False) or getattr(config, "auto_boss_summon", False)
        if (state != "active" or not session or current_hp is None or current_hp <= 0) and (not active_preset):
            if is_summon_enabled and config.boss_targets:
                boss_catalog = {b["id"]: dict(b) for b in (_load_bosses_catalog() or FALLBACK_BOSSES)}
                eval_list = list(boss_catalog.values())
                BossAPI.evaluate_bosses_availability(eval_list, bootstrap=bootstrap)
                eval_by_id = {b["id"]: b for b in eval_list}

                for target in config.boss_targets:
                    if not isinstance(target, dict) or not target.get("enabled", True):
                        continue
                    b_id = target.get("bossId")
                    b_mode = target.get("mode", "pacansky")
                    if not b_id:
                        continue
                    b_id_int = int(b_id)
                    b_meta = eval_by_id.get(b_id_int, {})

                    # 1. Проверка доступности/блокировки босса
                    if b_meta.get("isLocked"):
                        logger.info(
                            f"Пропуск заблокированного босса ID={b_id_int} ({b_meta.get('title', 'Босс')}): "
                            f"{b_meta.get('unlockReason', 'Босс заблокирован')}."
                        )
                        continue

                    # 2. Проверка возможности атаковать
                    if not b_meta.get("canAttack", True):
                        logger.info(
                            f"Пропуск босса ID={b_id_int} ({b_meta.get('title', 'Босс')}): "
                            f"{b_meta.get('attackBlockReason', 'Недоступен для атаки')}."
                        )
                        continue

                    try:
                        logger.info(f"Авто-призыв босса ID={b_id_int} (режим {b_mode})...")
                        summon_res = await self.api.start_battle(boss_id=b_id_int, mode=b_mode)
                        if summon_res.get("success") is not False:
                            logger.info(f"Бой с боссом ID={b_id_int} успешно запущен!")
                            bootstrap = await self.api.get_bootstrap()
                            session = bootstrap.get("session") or {}
                            state = bootstrap.get("state")
                            current_hp = session.get("currentHp")
                            break
                    except Exception as err:
                        logger.warning(f"Не удалось запустить бой с боссом {b_id_int}: {err}")

        if state != "active" or not session or current_hp is None or current_hp <= 0:
            logger.info(f"Активный бой с боссом отсутствует (state={state}, HP={current_hp}).")
            return results

        results["boss_active"] = True
        results["boss_hp_remaining"] = current_hp
        logger.info(f"Активен бой с боссом! Оставшееся HP: {current_hp}")

        # Фиксируем актуальный урон друзей по текущему активному боссу
        await self.record_friends_damage(bootstrap)

        is_hits_enabled = getattr(config, "auto_boss_enabled", False) or getattr(config, "auto_boss_hits", True)
        if not is_hits_enabled:
            logger.info("Авто-удары по боссу отключены в конфигурации.")
            return results

        # 4. Расчет доступных и готовых бесплатных ударов
        try:
            weapons_data = await self.api.get_weapons()
        except Exception as e:
            logger.error(f"Ошибка при получении оружия: {e}")
            results["errors"].append(f"get_weapons: {str(e)}")
            await self._log_action("get_weapons", "/api/boss/weapons", 500, False, {"error": str(e)})
            return results

        equipped_slots = weapons_data.get("equippedSlots") or []
        weapon_stats_effective = bootstrap.get("weaponStatsEffective") or {}
        now_utc = datetime.now(timezone.utc)

        # Выбираем только разблокированные рукопашные атаки
        available_melee = [w for w in MELEE_CONFIG if w in equipped_slots]
        ready_hits: List[str] = []

        for w in available_melee:
            cfg = MELEE_CONFIG[w]
            last_raw = weapons_data.get(cfg["last_time_key"])
            last_dt = parse_iso_utc(last_raw)
            cooldown_sec = weapon_stats_effective.get(cfg["cooldown_key"], cfg["default_cooldown"])

            if last_dt is None:
                ready_hits.append(w)
            elif now_utc >= (last_dt + timedelta(seconds=cooldown_sec)):
                ready_hits.append(w)
            else:
                remaining_sec = (last_dt + timedelta(seconds=cooldown_sec) - now_utc).total_seconds()
                logger.debug(f"Удар {w} на кулдауне (осталось {remaining_sec:.0f}с).")

        if not ready_hits:
            logger.info("Нет готовых рукопашных ударов (все на перезарядке).")
            return results

        logger.info(f"Готовые к применению бесплатные удары: {ready_hits}")

        # 5. Выполнение серии ударов
        for weapon_name in ready_hits:
            try:
                logger.info(f"Нанесение удара {weapon_name} по боссу...")
                hit_res = await self.api.hit_boss(weapon_name, count=1)
                new_hp = hit_res.get("currentHp")
                if new_hp is not None:
                    results["boss_hp_remaining"] = new_hp

                results["hits_performed"].append({"weapon": weapon_name, "response": hit_res})
                await self._log_action(
                    "boss_melee_hit",
                    "/api/boss/use-weapon",
                    200,
                    True,
                    {"weapon": weapon_name, "response": hit_res},
                )
                logger.info(f"Удар {weapon_name} успешно нанесен! Новое HP: {new_hp}")

                # Если босс погиб
                if new_hp is not None and new_hp <= 0:
                    logger.info("🎉 Босс повержен в результате серии ударов!")
                    # Пытаемся сразу забрать награду, если сервер вернул claimId
                    if hit_res.get("claimId"):
                        try:
                            await self.api.claim_reward(str(hit_res["claimId"]))
                            results["rewards_claimed"] += 1
                        except Exception:
                            pass
                    if active_preset and self.db_engine:
                        try:
                            async with get_session(self.db_engine) as db_sess:
                                p_obj = await db_sess.get(BossPreset, active_preset.id)
                                if p_obj:
                                    p_obj.current_step_index += 1
                                    if p_obj.current_step_index >= len(preset_steps):
                                        p_obj.is_running = False
                                        p_obj.last_status = f"Выполнен ({len(preset_steps)}/{len(preset_steps)})"
                                    else:
                                        nxt = preset_steps[p_obj.current_step_index]
                                        p_obj.last_status = f"Выполняется: шаг {p_obj.current_step_index + 1}/{len(preset_steps)} ({nxt['bossName']})"
                                    db_sess.add(p_obj)
                                    await db_sess.commit()
                        except Exception as e:
                            logger.warning(f"Ошибка обновления пресета при гибели босса: {e}")
                    break

                await self._jitter()

            except httpx.HTTPStatusError as err:
                err_text = err.response.text
                status_code = err.response.status_code
                logger.warning(f"Сервер отклонил удар {weapon_name} (HTTP {status_code}): {err_text}")
                results["errors"].append(f"hit_{weapon_name} (HTTP {status_code}): {err_text}")
                await self._log_action(
                    "boss_melee_hit",
                    "/api/boss/use-weapon",
                    status_code,
                    False,
                    {"weapon": weapon_name, "error": err_text},
                )
            except Exception as e:
                logger.error(f"Ошибка при нанесении удара {weapon_name}: {e}")
                results["errors"].append(f"hit_{weapon_name}: {str(e)}")
                await self._log_action(
                    "boss_melee_hit",
                    "/api/boss/use-weapon",
                    500,
                    False,
                    {"weapon": weapon_name, "error": str(e)},
                )

        # 6. Уведомление владельца при значимых событиях боя
        if self.notifier is not None:
            if results["rewards_claimed"] > 0 or len(results["hits_performed"]) > 0:
                lines = ["👊 <b>Битва с боссом:</b>"]
                if len(results["hits_performed"]) > 0:
                    lines.append(f"⚔️ Нанесено рукопашных ударов: <b>{len(results['hits_performed'])}</b>")
                    if results["boss_hp_remaining"] is not None:
                        lines.append(f"❤️ Оставшееся HP босса: <b>{results['boss_hp_remaining']}</b>")
                if results["rewards_claimed"] > 0:
                    lines.append(f"🏆 Собрано наград: <b>{results['rewards_claimed']}</b>")
                await self.notifier.notify("\n".join(lines))

        logger.info(f"=== [Аккаунт {self.account_id}] Цикл проверки боссов завершен ===")
        return results
