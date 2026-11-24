import random
import asyncio
import logging
from typing import Dict, Any, Optional, List
import httpx

from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active
from core.models import ActionLog
from client.api.prison import PrisonAPI
from client.api.player import PlayerAPI
from bot.notifier import TelegramNotifier
from core.drop_parser import DropParser

logger = logging.getLogger(__name__)


class PrisonWorker:
    """
    Воркер автоматического расходования энергии в тюрьмах:
    1. Проверка текущего запаса энергии игрока (порог PRISON_MIN_ENERGY).
    2. Выбор целевой тюрьмы (по PRISON_TARGET_ID или старшей разблокированной с максимальным id).
    3. Определение стоимости ходки из конфигурации чекпоинтов.
    4. Выполнение серии ходок (до исчерпания свободной энергии, с предохранителем max_iterations).
    5. Проверка и фиксация прохождения чекпоинтов.
    6. Отправка итоговой сводки через TelegramNotifier при выполнении >= 1 ходки.
    """

    def __init__(
        self,
        account_id: int,
        prison_api: PrisonAPI,
        player_api: Optional[PlayerAPI] = None,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
        max_iterations: int = 25,
    ):
        self.account_id = account_id
        self.prison_api = prison_api
        self.player_api = player_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.max_iterations = max_iterations

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
        - Если задан target_id > 0 (или settings.PRISON_TARGET_ID > 0) и эта тюрьма разблокирована - выбираем её.
        - Иначе выбираем тюрьму с максимальным id среди всех с isUnlocked == True (или тюрьму 1 по умолчанию).
        """
        if not prisons:
            return None

        tid = settings.PRISON_TARGET_ID if target_id is None else target_id
        if tid > 0:
            for p in prisons:
                if p.get("id") == tid and p.get("isUnlocked", True):
                    return p

        unlocked = [p for p in prisons if p.get("isUnlocked") is True or p.get("id") == 1]
        if unlocked:
            return max(unlocked, key=lambda p: p.get("id", 0))

        return prisons[0]

    async def run_cycle(self) -> Dict[str, Any]:
        """
        Основной цикл расходования восстанавливаемой энергии на тюремные ходки.
        """
        # Проверка живого BotConfig
        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            logger.info("Планировщик на паузе или активен режим сна. Пропуск ходок.")
            return {"status": "skipped", "reason": "paused_or_sleep"}

        if not getattr(config, "auto_prison", True):
            logger.info("Авто-ходки в тюрьмах отключены в конфигурации.")
            return {"status": "skipped", "reason": "auto_prison_disabled"}

        min_energy = getattr(config, "prison_min_energy", settings.PRISON_MIN_ENERGY)
        target_prison_id = getattr(config, "prison_target_id", settings.PRISON_TARGET_ID)
        prefer_night = getattr(config, "prison_prefer_night", settings.PRISON_PREFER_NIGHT)

        current_energy = 0
        max_energy = 100

        # 1. Получение актуальной энергии игрока
        if self.player_api is not None:
            try:
                init_data = await self.player_api.init_player()
                player_info = init_data.get("player", {}) if isinstance(init_data, dict) else {}
                current_energy = player_info.get("energy", init_data.get("energy", 0))
                max_energy = player_info.get("maxEnergy", init_data.get("maxEnergy", 100))
            except Exception as e:
                logger.warning("Не удалось получить профиль игрока для проверки энергии: %s", e)

        if current_energy <= 0:
            logger.info("Энергия равна 0. Цикл ходок пропущен.")
            return {
                "status": "skipped_low_energy",
                "energy": current_energy,
            }

        # 2. Получение списка тюрем и выбор целевой
        try:
            prisons_resp = await self.prison_api.get_all_prisons()
            prisons_list = (
                prisons_resp.get("prisons", [])
                if isinstance(prisons_resp, dict)
                else prisons_resp
            )
            if not isinstance(prisons_list, list):
                prisons_list = []
        except Exception as e:
            logger.error("Ошибка загрузки списка тюрем: %s", e)
            return {"status": "error", "error": str(e)}

        target_prison = self.select_target_prison(prisons_list, target_id=target_prison_id)
        if not target_prison:
            logger.warning("Не найдено доступных тюрем для ходок.")
            return {"status": "no_prisons"}

        prison_id = target_prison.get("id", 1)
        prison_name = target_prison.get("name", f"Тюрьма #{prison_id}")
        is_day = not prefer_night

        logger.info(
            "Выбрана тюрьма: '%s' (ID: %s, смена: %s). Текущая энергия: %s",
            prison_name,
            prison_id,
            "день" if is_day else "ночь",
            current_energy,
        )

        # 3. Загрузка состояния тюрьмы и чекпоинтов
        checkpoint_completed = False
        try:
            state_resp = await self.prison_api.get_prison_state(prison_id)
            prison_data = (
                state_resp.get("data", state_resp)
                if isinstance(state_resp, dict)
                else {}
            )
            if prison_data.get("hasUnclaimedCheckpoint") or prison_data.get("unclaimedCheckpoint"):
                checkpoint_completed = True
        except Exception as e:
            logger.warning("Ошибка получения состояния тюрьмы %s: %s", prison_id, e)
            prison_data = {}

        try:
            cp_resp = await self.prison_api.get_checkpoints(prison_id, is_day=is_day)
            checkpoints = (
                cp_resp.get("data", cp_resp)
                if isinstance(cp_resp, dict)
                else cp_resp
            )
            if not isinstance(checkpoints, list):
                checkpoints = []
        except Exception as e:
            logger.warning("Ошибка получения чекпоинтов тюрьмы %s: %s", prison_id, e)
            checkpoints = []

        # Определение стоимости ходки
        current_cp_idx = (
            prison_data.get("dayCurrentCheckpoint", 0)
            if is_day
            else prison_data.get("nightCurrentCheckpoint", 0)
        )
        job_energy_cost = 10
        if checkpoints and 0 <= current_cp_idx < len(checkpoints):
            job_energy_cost = checkpoints[current_cp_idx].get("energyCost", 10)
        elif checkpoints:
            job_energy_cost = checkpoints[0].get("energyCost", 10)

        if job_energy_cost <= 0:
            job_energy_cost = 10

        if current_energy < job_energy_cost:
            logger.info(
                "Энергия (%s) ниже стоимости ходки (%s). Цикл ходок пропущен.",
                current_energy,
                job_energy_cost,
            )
            return {
                "status": "skipped_low_energy",
                "energy": current_energy,
                "job_energy_cost": job_energy_cost,
            }

        # 4. Цикл выполнения ходок
        works_done = 0
        iterations = 0

        while current_energy >= job_energy_cost and iterations < self.max_iterations:
            iterations += 1
            try:
                work_resp = await self.prison_api.do_prison_work(prison_id, is_day=is_day)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    logger.info("Сервер вернул 400 при выполнении ходки (недостаточно энергии).")
                    break
                logger.error("HTTP ошибка при выполнении ходки: %s", e)
                break
            except Exception as e:
                logger.error("Непредвиденная ошибка при выполнении ходки: %s", e)
                break

            if isinstance(work_resp, dict) and work_resp.get("success") is False:
                err_msg = work_resp.get("error", "Unknown error")
                logger.info("Ответ сервера с ошибкой ходки: %s", err_msg)
                break

            works_done += 1

            # Обновление энергии
            if isinstance(work_resp, dict) and "energy" in work_resp:
                current_energy = work_resp["energy"]
            else:
                current_energy -= job_energy_cost

            if isinstance(work_resp, dict) and work_resp.get("checkpointCompleted"):
                checkpoint_completed = True

            day_param = "true" if is_day else "false"
            await self._log_action(
                action_type="prison_work",
                endpoint=f"/api/player/prison/{prison_id}/work?isDay={day_param}",
                status_code=200,
                success=True,
                details={
                    "prisonId": prison_id,
                    "prisonName": prison_name,
                    "worksDone": works_done,
                    "remainingEnergy": current_energy,
                },
            )

            if isinstance(work_resp, dict) and work_resp.get("runCompleted"):
                logger.info("Полный круг тюрьмы #%s успешно завершен!", prison_id)
                break

            await self._jitter()

        # 5. Сбор / актуализация чекпоинтов при готовности
        if checkpoint_completed:
            try:
                claim_resp = await self.prison_api.claim_checkpoints(prison_id, is_day=is_day)
                day_param = "true" if is_day else "false"
                await self._log_action(
                    action_type="prison_checkpoint_claim",
                    endpoint=f"/api/player/prison/{prison_id}/checkpoints?isDay={day_param}",
                    status_code=200,
                    success=True,
                    details={
                        "prisonId": prison_id,
                        "checkpointsClaimed": True,
                    },
                )
                logger.info("Чекпоинт в тюрьме #%s успешно собран/актуализирован.", prison_id)
            except Exception as e:
                logger.warning("Ошибка сбора чекпоинта: %s", e)

        # 6. Тренировка у мастера (если включено в BotConfig)
        if getattr(config, "auto_masters", False):
            master_id = getattr(config, "master_target_id", 1)
            if current_energy >= 10:
                try:
                    logger.info(f"Выполнение тренировки у мастера ID={master_id}...")
                    m_res = await self.prison_api.do_master_work(master_id=master_id)
                    logger.info(f"Тренировка у мастера {master_id} успешно выполнена: {m_res}")
                except Exception as e:
                    logger.warning(f"Ошибка тренировки у мастера {master_id}: {e}")

        # 6.1 Умный сбор входящих подогревов и повторный слив энергии в ходки/мастеров
        if getattr(config, "auto_podogrev", True) and self.player_api is not None and current_energy < max_energy:
            try:
                podogrev_res = await self.player_api.collect_all_podogrev()
                claimed_count = podogrev_res.get("claimed", 0) if isinstance(podogrev_res, dict) else 0
                if claimed_count > 0:
                    logger.info("Собрано %s подогревов. Проверяем баланс энергии для повторного слива...", claimed_count)
                    try:
                        init_data = await self.player_api.init_player()
                        player_info = init_data.get("player", {}) if isinstance(init_data, dict) else {}
                        current_energy = player_info.get("energy", current_energy)
                        max_energy = player_info.get("maxEnergy", max_energy)
                    except Exception as e:
                        logger.warning("Не удалось обновить баланс энергии после сбора подогревов: %s", e)

                    # Немедленный повторный слив полученной энергии в ходки
                    if current_energy >= job_energy_cost:
                        extra_works = 0
                        while current_energy >= job_energy_cost and iterations < self.max_iterations:
                            iterations += 1
                            try:
                                work_resp = await self.prison_api.do_prison_work(prison_id, is_day=is_day)
                            except Exception as e:
                                logger.info("Остановка дополнительного цикла ходок: %s", e)
                                break

                            if isinstance(work_resp, dict) and work_resp.get("success") is False:
                                break

                            works_done += 1
                            extra_works += 1

                            if isinstance(work_resp, dict) and "energy" in work_resp:
                                current_energy = work_resp["energy"]
                            else:
                                current_energy -= job_energy_cost

                            if isinstance(work_resp, dict) and work_resp.get("checkpointCompleted"):
                                checkpoint_completed = True

                            day_param = "true" if is_day else "false"
                            await self._log_action(
                                action_type="prison_work",
                                endpoint=f"/api/player/prison/{prison_id}/work?isDay={day_param}",
                                status_code=200,
                                success=True,
                                details={
                                    "prisonId": prison_id,
                                    "prisonName": prison_name,
                                    "worksDone": works_done,
                                    "remainingEnergy": current_energy,
                                    "source": "podogrev_reinvest",
                                },
                            )

                            if isinstance(work_resp, dict) and work_resp.get("runCompleted"):
                                logger.info("Полный круг тюрьмы #%s успешно завершен!", prison_id)
                                break

                            await self._jitter()

                        logger.info("Дополнительно выполнено ходок после подогревов: %s", extra_works)

                        # Если осталась энергия на мастера
                        if getattr(config, "auto_masters", False) and current_energy >= 10:
                            master_id = getattr(config, "master_target_id", 1)
                            try:
                                await self.prison_api.do_master_work(master_id=master_id)
                            except Exception as e:
                                logger.warning(f"Ошибка повторной тренировки у мастера {master_id}: {e}")
            except Exception as e:
                logger.warning("Ошибка умного сбора подогревов в PrisonWorker: %s", e)

        # 7. Сохранение уведомления в Notification
        if works_done > 0:
            parsed_work = DropParser.parse_prison_work(
                last_work_resp if "last_work_resp" in locals() and last_work_resp else (work_resp if "work_resp" in locals() and isinstance(work_resp, dict) else {}),
                prison_name=prison_name,
                works_count=works_done,
            )
            await DropParser.save_notification(self.account_id, parsed_work, self.db_engine)

        # 8. Уведомление через TelegramNotifier
        if works_done > 0 and self.notifier is not None:
            text = (
                f"⛓️ <b>Тюремные ходки</b>\n"
                f"🏛 Тюрьма: <b>{prison_name}</b>\n"
                f"⚒ Выполнено ходок: <b>{works_done}</b>\n"
                f"⚡️ Оставшаяся энергия: <b>{current_energy}</b>"
            )
            await self.notifier.notify(text)

        logger.info(
            "Цикл ходок завершен. Выполнено: %s, остаток энергии: %s",
            works_done,
            current_energy,
        )
        return {
            "status": "success",
            "prison_id": prison_id,
            "prison_name": prison_name,
            "works_done": works_done,
            "remaining_energy": current_energy,
        }
