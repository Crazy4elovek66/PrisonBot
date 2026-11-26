import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import httpx

from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active
from core.server_health import server_health_monitor, GameMaintenanceError
from core.models import ActionLog
from client.api.prison import PrisonAPI
from client.api.player import PlayerAPI
from bot.notifier import TelegramNotifier
from core.drop_parser import DropParser
from workers.routine_worker import parse_iso_utc

logger = logging.getLogger(__name__)


def compute_next_stage_wait_seconds(
    current_energy: int,
    stage_cost: int,
    regen_interval_sec: int = 300,
    last_restore_time: Optional[Any] = None,
    now_utc: Optional[datetime] = None,
    jitter_sec: float = 0.0,
) -> float:
    """
    Точный расчёт времени ожидания (в секундах) до накопления энергии на 1 следующий этап тюрьмы.
    Учитывает lastEnergyRestoreTime и интервал регенерации (по умолчанию 300с на +1 энергию).
    """
    cost = int(stage_cost or 0)
    energy = max(0, int(current_energy or 0))
    if cost <= 0 or energy >= cost:
        return round(max(0.0, float(jitter_sec or 0.0)), 2)

    missing = cost - energy
    interval = max(1, int(regen_interval_sec or 300))

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    elapsed_in_tick = 0.0
    last_dt = None
    if isinstance(last_restore_time, datetime):
        last_dt = last_restore_time if last_restore_time.tzinfo else last_restore_time.replace(tzinfo=timezone.utc)
    elif isinstance(last_restore_time, (int, float)):
        try:
            last_dt = datetime.fromtimestamp(float(last_restore_time), tz=timezone.utc)
        except Exception:
            last_dt = None
    elif isinstance(last_restore_time, str) and last_restore_time.strip():
        last_dt = parse_iso_utc(last_restore_time)

    if last_dt is not None and now >= last_dt:
        elapsed_in_tick = (now - last_dt).total_seconds() % interval

    raw_wait = max(1.0, missing * interval - elapsed_in_tick) + max(0.0, float(jitter_sec or 0.0))
    return round(raw_wait, 2)


class PrisonWorker:
    """
    Воркер непрерывного расходования энергии в тюрьмах:
    - Единый метод drain_all_energy(...) под asyncio.Lock сливает ВСЮ доступную энергию
      до 0 / ниже стоимости этапа (не останавливаясь на runCompleted).
    - После каждого завершенного чекпоинта или круга актуализирует energyCost следующего этапа.
    - После слива рассчитывает точное время до следующего этапа и переназначает триггер APScheduler.
    - Не спамит Telegram при одиночных реген-ходках.
    """

    DEFAULT_MAX_RUNS = 200

    def __init__(
        self,
        account_id: int,
        prison_api: PrisonAPI,
        player_api: Optional[PlayerAPI] = None,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
        max_iterations: int = DEFAULT_MAX_RUNS,
        state_hub: Optional[Any] = None,
        on_reschedule: Optional[Callable[[float], Any]] = None,
    ):
        self.account_id = account_id
        self.prison_api = prison_api
        self.player_api = player_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.max_iterations = max_iterations
        self.state_hub = state_hub
        self.on_reschedule = on_reschedule
        self._drain_lock = asyncio.Lock()

    async def _fast_pause(self) -> None:
        if self.enable_jitter:
            await asyncio.sleep(random.uniform(0.35, 0.6))

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
                    details=details,
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            logger.error("Ошибка сохранения ActionLog для тюрьмы: %s", e)

    def select_target_prison(
        self,
        prisons: List[Dict[str, Any]],
        target_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Выбор целевой тюрьмы:
        - Если задан target_id > 0 и эта тюрьма разблокирована — выбираем её.
        - Иначе выбираем тюрьму с максимальным id среди разблокированных.
        """
        if not prisons:
            return None

        tid = settings.PRISON_TARGET_ID if target_id is None else target_id
        if tid and tid > 0:
            for p in prisons:
                if p.get("id") == tid and p.get("isUnlocked", True):
                    return p

        unlocked = [p for p in prisons if p.get("isUnlocked") is True or p.get("id") == 1]
        if unlocked:
            return max(unlocked, key=lambda p: p.get("id", 0))

        return prisons[0]

    @staticmethod
    def _extract_energy_info(init_data: Any) -> Dict[str, Any]:
        if not isinstance(init_data, dict):
            return {"energy": 0, "max_energy": 100, "last_restore": None, "interval": 300}
        player_info = init_data.get("player") if isinstance(init_data.get("player"), dict) else {}
        energy = init_data.get("energy", player_info.get("energy", 0)) or 0
        max_energy = init_data.get("maxEnergy", player_info.get("maxEnergy", 100)) or 100
        last_restore = init_data.get("lastEnergyRestoreTime") or player_info.get("lastEnergyRestoreTime")
        interval = init_data.get("energyRestoreIntervalSeconds") or player_info.get("energyRestoreIntervalSeconds") or 300
        return {
            "energy": int(energy),
            "max_energy": int(max_energy),
            "last_restore": last_restore,
            "interval": int(interval),
        }

    async def _fetch_stage_cost(self, prison_id: int, is_day: bool) -> Dict[str, Any]:
        prison_data: Dict[str, Any] = {}
        checkpoints: List[Dict[str, Any]] = []
        has_unclaimed_cp = False

        try:
            state_resp = await self.prison_api.get_prison_state(prison_id)
            prison_data = state_resp.get("data", state_resp) if isinstance(state_resp, dict) else {}
            if isinstance(prison_data, dict) and (prison_data.get("hasUnclaimedCheckpoint") or prison_data.get("unclaimedCheckpoint")):
                has_unclaimed_cp = True
        except Exception as e:
            logger.debug("Ошибка получения состояния тюрьмы %s: %s", prison_id, e)

        try:
            cp_resp = await self.prison_api.get_checkpoints(prison_id, is_day=is_day)
            raw_cp = cp_resp.get("data", cp_resp) if isinstance(cp_resp, dict) else cp_resp
            if isinstance(raw_cp, list):
                checkpoints = raw_cp
        except Exception as e:
            logger.debug("Ошибка получения чекпоинтов тюрьмы %s: %s", prison_id, e)

        current_cp_idx = int(
            (prison_data.get("dayCurrentCheckpoint", 0) if is_day else prison_data.get("nightCurrentCheckpoint", 0)) or 0
        )
        cost = 10
        if checkpoints and 0 <= current_cp_idx < len(checkpoints):
            cost = int(checkpoints[current_cp_idx].get("energyCost", 10) or 10)
        elif checkpoints:
            cost = int(checkpoints[0].get("energyCost", 10) or 10)
        if cost <= 0:
            cost = 10

        return {
            "stage_cost": cost,
            "prison_data": prison_data if isinstance(prison_data, dict) else {},
            "has_unclaimed_cp": has_unclaimed_cp,
        }

    async def drain_all_energy(
        self,
        prison_id: Optional[int] = None,
        mode: Optional[str] = None,
        collect_podogrev: bool = False,
        source: str = "auto",
        max_runs: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Непрерывно тратит всю доступную энергию игрока на ходки, пока remaining_energy >= stage_cost.
        Не прерывается при runCompleted / checkpointCompleted: обновляет stage_cost следующего этапа и продолжает цикл.
        """
        run_limit = int(max_runs or self.max_iterations or self.DEFAULT_MAX_RUNS)

        async with self._drain_lock:
            config = await get_or_create_config(self.account_id, self.db_engine)
            target_prison_id = prison_id if prison_id is not None else getattr(config, "prison_target_id", settings.PRISON_TARGET_ID)
            prefer_night = getattr(config, "prison_prefer_night", settings.PRISON_PREFER_NIGHT)

            current_energy = 0
            max_energy = 100
            last_restore_time = None
            regen_interval_sec = 300

            if self.player_api is not None:
                try:
                    init_data = await self.player_api.init_player()
                    e_info = self._extract_energy_info(init_data)
                    current_energy = e_info["energy"]
                    max_energy = e_info["max_energy"]
                    last_restore_time = e_info["last_restore"]
                    regen_interval_sec = e_info["interval"]
                except Exception as e:
                    logger.warning("Не удалось получить профиль игрока для проверки энергии: %s", e)

            try:
                prisons_resp = await self.prison_api.get_all_prisons()
                prisons_list = prisons_resp.get("prisons", []) if isinstance(prisons_resp, dict) else prisons_resp
                if not isinstance(prisons_list, list):
                    prisons_list = []
            except Exception as e:
                logger.error("Ошибка загрузки списка тюрем: %s", e)
                return {"status": "error", "error": str(e), "runsCompleted": 0, "works_done": 0}

            if prison_id is not None:
                target_prison = next((p for p in prisons_list if int(p.get("id", 0)) == int(prison_id)), None)
                if not target_prison:
                    target_prison = {"id": int(prison_id), "name": f"Тюрьма #{prison_id}", "isUnlocked": True}
            else:
                target_prison = self.select_target_prison(prisons_list, target_id=target_prison_id)

            if not target_prison:
                logger.warning("Не найдено доступных тюрем для ходок.")
                return {"status": "no_prisons", "runsCompleted": 0, "works_done": 0}

            pid = int(target_prison.get("id", 1))
            pname = target_prison.get("name", f"Тюрьма #{pid}")

            if mode == "night":
                is_day = False
            elif mode == "day":
                is_day = True
            else:
                is_day = not prefer_night

            stage_info = await self._fetch_stage_cost(pid, is_day)
            job_energy_cost = stage_info["stage_cost"]
            checkpoint_completed = stage_info["has_unclaimed_cp"]

            works_done = 0
            checkpoints_claimed = 0
            circles_completed = 0
            rewards_agg: Dict[str, int] = {"cigarettes": 0, "authority": 0, "rubles": 0, "experience": 0}
            drops: List[Dict[str, Any]] = []
            last_work_resp: Dict[str, Any] = {}
            podogrev_checked = False

            # Если энергия уже на 0/ниже порога, но разрешен автосбор подогревов — проверим входящие подогревы сразу
            if current_energy < job_energy_cost and collect_podogrev and self.player_api is not None and current_energy < max_energy:
                podogrev_checked = True
                try:
                    pod_res = await self.player_api.collect_all_podogrev()
                    claimed_cnt = int((pod_res.get("claimed", 0) or 0)) if isinstance(pod_res, dict) else 0
                    applied_en = int((pod_res.get("appliedEnergy", 0) or 0)) if isinstance(pod_res, dict) else 0
                    if claimed_cnt > 0 or applied_en > 0:
                        init_data = await self.player_api.init_player()
                        e_info = self._extract_energy_info(init_data)
                        current_energy = e_info["energy"]
                        max_energy = e_info["max_energy"]
                        last_restore_time = e_info["last_restore"]
                        regen_interval_sec = e_info["interval"]
                except Exception as e:
                    logger.warning("Ошибка предварительного сбора подогревов: %s", e)

            if current_energy <= 0 or current_energy < job_energy_cost:
                wait_buf = random.uniform(3.0, 6.0) if self.enable_jitter else 4.0
                next_wait_sec = compute_next_stage_wait_seconds(
                    current_energy=current_energy,
                    stage_cost=job_energy_cost,
                    regen_interval_sec=regen_interval_sec,
                    last_restore_time=last_restore_time,
                    jitter_sec=wait_buf,
                )
                if self.on_reschedule is not None:
                    try:
                        self.on_reschedule(max(15.0, min(next_wait_sec, 300.0)))
                    except Exception:
                        pass
                return {
                    "status": "skipped_low_energy" if source == "auto" else "low_energy",
                    "energy": current_energy,
                    "remaining_energy": current_energy,
                    "remainingEnergy": current_energy,
                    "job_energy_cost": job_energy_cost,
                    "stageCost": job_energy_cost,
                    "works_done": 0,
                    "runsCompleted": 0,
                    "rewards": rewards_agg,
                    "drops": drops,
                    "next_wait_seconds": next_wait_sec,
                    "prisonId": pid,
                    "prisonName": pname,
                }

            # Основной цикл слива энергии (может сделать второй проход после сбора подогревов)
            while True:
                while current_energy >= job_energy_cost and works_done < run_limit:
                    try:
                        work_resp = await self.prison_api.do_prison_work(pid, is_day=is_day)
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 400:
                            logger.info("Сервер вернул 400 при выполнении ходки (недостаточно энергии).")
                            break
                        logger.error("HTTP ошибка при выполнении ходки: %s", e)
                        break
                    except Exception as e:
                        logger.error("Непредвиденная ошибка при выполнении ходки: %s", e)
                        break

                    if not isinstance(work_resp, dict) or work_resp.get("success") is False:
                        err_msg = work_resp.get("error", "Unknown error") if isinstance(work_resp, dict) else "Invalid response"
                        logger.info("Ответ сервера с ошибкой ходки: %s", err_msg)
                        break

                    last_work_resp = work_resp
                    works_done += 1

                    # Обновляем энергию и время регена из ответа
                    if "energy" in work_resp and work_resp["energy"] is not None:
                        current_energy = int(work_resp["energy"])
                    elif "newEnergy" in work_resp and work_resp["newEnergy"] is not None:
                        current_energy = int(work_resp["newEnergy"])
                    elif isinstance(work_resp.get("player"), dict) and work_resp["player"].get("energy") is not None:
                        current_energy = int(work_resp["player"]["energy"])
                    else:
                        current_energy = max(0, current_energy - job_energy_cost)

                    if work_resp.get("lastEnergyRestoreTime"):
                        last_restore_time = work_resp["lastEnergyRestoreTime"]

                    # Агрегируем награды и дроп
                    rewards_agg["cigarettes"] += int(work_resp.get("rewardCigarettes") or 0)
                    rewards_agg["authority"] += int(work_resp.get("rewardAuthority") or 0)
                    rewards_agg["rubles"] += int(work_resp.get("rewardRubles") or 0)
                    rewards_agg["experience"] += int(work_resp.get("rewardExperience") or 0)
                    for d_key in ("droppedItems", "drops", "items", "loot"):
                        raw_d = work_resp.get(d_key)
                        if isinstance(raw_d, list):
                            for it in raw_d:
                                drops.append(it if isinstance(it, dict) else {"name": str(it)})

                    if self.state_hub is not None:
                        self.state_hub.patch_profile_resources(
                            self.account_id,
                            energy=current_energy,
                            maxEnergy=max_energy,
                            lastEnergyRestoreTime=last_restore_time,
                        )

                    day_param = "true" if is_day else "false"
                    await self._log_action(
                        action_type="prison_work",
                        endpoint=f"/api/player/prison/{pid}/work?isDay={day_param}",
                        status_code=200,
                        success=True,
                        details={
                            "prisonId": pid,
                            "prisonName": pname,
                            "worksDone": works_done,
                            "remainingEnergy": current_energy,
                            "source": source,
                        },
                    )

                    cp_done = bool(work_resp.get("checkpointCompleted") or work_resp.get("canClaimCheckpoint"))
                    run_done = bool(work_resp.get("runCompleted"))

                    if cp_done:
                        checkpoint_completed = True
                        try:
                            await self.prison_api.claim_checkpoints(pid, is_day=is_day)
                            checkpoints_claimed += 1
                            checkpoint_completed = False
                            await self._log_action(
                                action_type="prison_checkpoint_claim",
                                endpoint=f"/api/player/prison/{pid}/checkpoints?isDay={day_param}",
                                status_code=200,
                                success=True,
                                details={"prisonId": pid, "checkpointsClaimed": True},
                            )
                        except Exception as e:
                            logger.warning("Ошибка сбора чекпоинта: %s", e)

                    if run_done:
                        circles_completed += 1
                        logger.info("Полный круг тюрьмы #%s успешно завершен! Продолжаем слив оставшейся энергии (%s).", pid, current_energy)

                    # При завершении чекпоинта или круга актуализируем stage_cost и НЕ прерываем цикл!
                    if cp_done or run_done:
                        new_stage = await self._fetch_stage_cost(pid, is_day)
                        job_energy_cost = new_stage["stage_cost"]

                    if current_energy >= job_energy_cost and works_done < run_limit:
                        await self._fast_pause()

                # Проверяем подогревы, если энергия опустилась ниже стоимости этапа
                if (
                    collect_podogrev
                    and not podogrev_checked
                    and self.player_api is not None
                    and current_energy < max_energy
                    and works_done < run_limit
                ):
                    podogrev_checked = True
                    try:
                        pod_res = await self.player_api.collect_all_podogrev()
                        claimed_cnt = int((pod_res.get("claimed", 0) or 0)) if isinstance(pod_res, dict) else 0
                        applied_en = int((pod_res.get("appliedEnergy", 0) or 0)) if isinstance(pod_res, dict) else 0
                        if claimed_cnt > 0 or applied_en > 0:
                            init_data = await self.player_api.init_player()
                            e_info = self._extract_energy_info(init_data)
                            current_energy = e_info["energy"]
                            max_energy = e_info["max_energy"]
                            last_restore_time = e_info["last_restore"]
                            regen_interval_sec = e_info["interval"]
                            if current_energy >= job_energy_cost:
                                continue
                    except Exception as e:
                        logger.warning("Ошибка умного сбора подогревов в PrisonWorker: %s", e)
                break

            # Если к началу цикла уже был несобранный чекпоинт, заберем его
            if checkpoint_completed:
                try:
                    await self.prison_api.claim_checkpoints(pid, is_day=is_day)
                    day_param = "true" if is_day else "false"
                    await self._log_action(
                        action_type="prison_checkpoint_claim",
                        endpoint=f"/api/player/prison/{pid}/checkpoints?isDay={day_param}",
                        status_code=200,
                        success=True,
                        details={"prisonId": pid, "checkpointsClaimed": True},
                    )
                except Exception as e:
                    logger.warning("Ошибка сбора чекпоинта: %s", e)

            # Тренировка у мастера (если включена и осталась энергия)
            if source == "auto" and getattr(config, "auto_masters", False) and current_energy >= 10:
                master_id = getattr(config, "master_target_id", 1)
                try:
                    await self.prison_api.do_master_work(master_id=master_id)
                except Exception as e:
                    logger.warning("Ошибка тренировки у мастера %s: %s", master_id, e)

            # Расчет точного времени ожидания следующего этапа и переназначение APScheduler
            wait_buf = random.uniform(3.0, 6.0) if self.enable_jitter else 4.0
            next_wait_sec = compute_next_stage_wait_seconds(
                current_energy=current_energy,
                stage_cost=job_energy_cost,
                regen_interval_sec=regen_interval_sec,
                last_restore_time=last_restore_time,
                jitter_sec=wait_buf,
            )
            if self.on_reschedule is not None:
                try:
                    self.on_reschedule(max(15.0, min(next_wait_sec, 300.0)))
                except Exception as e:
                    logger.debug("Ошибка переназначения расписания PrisonWorker: %s", e)

            if works_done > 0:
                p_data = stage_info.get("prison_data") if isinstance(stage_info, dict) else {}
                cp_idx = int((p_data.get("dayCurrentCheckpoint" if is_day else "nightCurrentCheckpoint")) or 0) if isinstance(p_data, dict) else 0
                cur_stage = cp_idx + 1 if cp_idx >= 0 else None
                merged_payload = dict(last_work_resp) if isinstance(last_work_resp, dict) else {}
                for rk, rv in rewards_agg.items():
                    if rv > 0 and rk not in merged_payload and f"reward{rk.capitalize()}" not in merged_payload:
                        merged_payload[rk] = rv
                parsed_work = DropParser.parse_prison_work(
                    merged_payload,
                    prison_name=pname,
                    works_count=works_done,
                    is_day=is_day,
                    stage_num=cur_stage,
                    prison_id=pid,
                )
                await DropParser.save_notification(self.account_id, parsed_work, self.db_engine)

                # Не спамим в Telegram при одиночной реген-ходке без дропа
                if source != "manual" and self.notifier is not None and (works_done >= 2 or len(drops) > 0 or circles_completed > 0):
                    text = (
                        f"⛓️ <b>Тюремные ходки</b>\n"
                        f"🏛 Тюрьма: <b>{pname}</b>\n"
                        f"⚒ Выполнено ходок: <b>{works_done}</b>\n"
                        f"⚡️ Оставшаяся энергия: <b>{current_energy}</b>"
                    )
                    await self.notifier.notify(text)

            logger.info(
                "Слив энергии завершен (source=%s). Выполнено: %s, остаток энергии: %s, следующий тик через %.1fс",
                source,
                works_done,
                current_energy,
                next_wait_sec,
            )
            return {
                "status": "success" if works_done > 0 else ("skipped_low_energy" if source == "auto" else "low_energy"),
                "prison_id": pid,
                "prisonId": pid,
                "prison_name": pname,
                "prisonName": pname,
                "mode": "day" if is_day else "night",
                "works_done": works_done,
                "runsCompleted": works_done,
                "checkpoints_claimed": checkpoints_claimed,
                "circles_completed": circles_completed,
                "energy": current_energy,
                "remaining_energy": current_energy,
                "remainingEnergy": current_energy,
                "stageCost": job_energy_cost,
                "rewards": rewards_agg,
                "drops": drops,
                "next_wait_seconds": next_wait_sec,
            }

    async def run_cycle(self) -> Dict[str, Any]:
        """Основной автоматический цикл: проверяет активность, автосбор подогревов и сливает всю энергию."""
        if server_health_monitor.is_maintenance:
            if server_health_monitor.should_log_worker_skip():
                logger.debug("Игровые сервера на техработах — PrisonWorker на паузе.")
            return {"status": "skipped", "reason": "maintenance"}

        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            logger.info("Планировщик на паузе или активен режим сна. Пропуск ходок.")
            return {"status": "skipped", "reason": "paused_or_sleep"}

        if not getattr(config, "auto_prison", True):
            logger.info("Авто-ходки в тюрьмах отключены в конфигурации.")
            return {"status": "skipped", "reason": "auto_prison_disabled"}

        try:
            return await self.drain_all_energy(
                collect_podogrev=bool(getattr(config, "auto_podogrev", True)),
                source="auto",
            )
        except GameMaintenanceError:
            return {"status": "skipped", "reason": "maintenance"}
