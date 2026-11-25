import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.state_hub import state_hub as global_state_hub
from workers.routine_worker import RoutineWorker
from workers.boss_worker import BossWorker
from workers.prison_worker import PrisonWorker
from workers.social_worker import SocialWorker

logger = logging.getLogger(__name__)


class SchedulerController:
    """
    Адаптивный контроллер фонового планировщика:
    - Переводит BossWorker на быстрый тик (12с) при активном бое/пресете и 60с в простое.
    - Переназначает PrisonWorker точно на момент накопления энергии для 1 следующего этапа.
    - Обеспечивает мгновенное пробуждение воркеров при изменении настроек и ручном запуске.
    - Поддерживает многоуровневый 24/7 фоновый прогрев LiveStateHub.
    """

    BOSS_FAST_INTERVAL_SEC = 12
    BOSS_IDLE_INTERVAL_SEC = 60
    TIER1_FAST_SEC = 20
    TIER1_IDLE_SEC = 40
    TIER2_INTERVAL_SEC = 105
    TIER3_INTERVAL_SEC = 360

    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        routine_worker: RoutineWorker,
        boss_worker: Optional[BossWorker] = None,
        prison_worker: Optional[PrisonWorker] = None,
        social_worker: Optional[SocialWorker] = None,
        state_hub: Optional[Any] = None,
    ) -> None:
        self.scheduler = scheduler
        self.routine_worker = routine_worker
        self.boss_worker = boss_worker
        self.prison_worker = prison_worker
        self.social_worker = social_worker
        self.state_hub = state_hub or global_state_hub
        self.account_id = getattr(routine_worker, "account_id", 1)
        self._boss_fast_mode = False
        self._immediate_boss_task: Optional[asyncio.Task] = None
        self._immediate_prison_task: Optional[asyncio.Task] = None
        self._immediate_routine_task: Optional[asyncio.Task] = None
        self._melee_timer_task: Optional[asyncio.Task] = None
        self._business_timer_task: Optional[asyncio.Task] = None
        self._katala_timer_task: Optional[asyncio.Task] = None

    def set_boss_fast_mode(self, active: bool) -> None:
        """Переключает интервал проверки боссов (12с в бою / 60с в простое)."""
        target_fast = bool(active)
        if target_fast == self._boss_fast_mode:
            return
        self._boss_fast_mode = target_fast
        interval_sec = self.BOSS_FAST_INTERVAL_SEC if target_fast else self.BOSS_IDLE_INTERVAL_SEC
        job_id = f"boss_worker_{self.account_id}"
        try:
            job = self.scheduler.get_job(job_id)
            if job is not None:
                self.scheduler.reschedule_job(job_id, trigger=IntervalTrigger(seconds=interval_sec))
                logger.info("BossWorker переключен в %s режим (%sс).", "быстрый" if target_fast else "фоновый", interval_sec)
        except Exception as e:
            logger.debug("Не удалось изменить интервал BossWorker: %s", e)

    def reschedule_prison_in(self, wait_seconds: float) -> None:
        """Планирует следующее пробуждение PrisonWorker точно к моменту накопления энергии на 1 этап."""
        clamped = max(15.0, min(float(wait_seconds), 300.0))
        job_id = f"prison_worker_{self.account_id}"
        try:
            job = self.scheduler.get_job(job_id)
            if job is not None:
                next_dt = datetime.now(timezone.utc) + timedelta(seconds=clamped)
                self.scheduler.modify_job(job_id, next_run_time=next_dt)
                logger.info("Следующий цикл PrisonWorker назначен через %.0fс (%s).", clamped, next_dt.strftime("%H:%M:%S UTC"))
        except Exception as e:
            logger.debug("Не удалось переназначить next_run_time для PrisonWorker: %s", e)

    async def _run_boss_and_refresh(self, force_manual: bool = False) -> Any:
        if not self.boss_worker:
            return None
        try:
            res = await self.boss_worker.run_cycle(force_manual=force_manual)
            await self.refresh_tier1()
            return res
        except Exception as e:
            logger.warning("Ошибка немедленного цикла BossWorker: %s", e)
            return None

    async def _run_prison_and_refresh(self) -> Any:
        if not self.prison_worker:
            return None
        try:
            res = await self.prison_worker.run_cycle()
            await asyncio.gather(self.refresh_slice("profile"), self.refresh_slice("prisons"), return_exceptions=True)
            return res
        except Exception as e:
            logger.warning("Ошибка немедленного цикла PrisonWorker: %s", e)
            return None

    def trigger_boss_now(self, force_manual: bool = False) -> Optional[asyncio.Task]:
        """Немедленно запускает цикл BossWorker в фоне без ожидания следующего тика планировщика."""
        if not self.boss_worker:
            return None
        if self._immediate_boss_task is not None and not self._immediate_boss_task.done():
            return self._immediate_boss_task
        self._immediate_boss_task = asyncio.create_task(self._run_boss_and_refresh(force_manual=force_manual))
        return self._immediate_boss_task

    def trigger_prison_now(self) -> Optional[asyncio.Task]:
        """Немедленно запускает цикл PrisonWorker в фоне при изменении настроек."""
        if not self.prison_worker:
            return None
        if self._immediate_prison_task is not None and not self._immediate_prison_task.done():
            return self._immediate_prison_task
        self._immediate_prison_task = asyncio.create_task(self._run_prison_and_refresh())
        return self._immediate_prison_task

    async def _delayed_melee_hit(self, delay_sec: float) -> None:
        try:
            await asyncio.sleep(delay_sec)
            if not self.boss_worker:
                return
            if self.boss_worker.db_engine:
                from core.database import get_or_create_config, is_worker_active
                cfg = await get_or_create_config(self.account_id, self.boss_worker.db_engine)
                if not is_worker_active(cfg) or not (
                    getattr(cfg, "boss_auto_melee", False) or getattr(cfg, "auto_boss_enabled", False)
                ):
                    return
                res = await self.boss_worker.trigger_auto_melee(config=cfg)
            else:
                res = await self.boss_worker.trigger_auto_melee()
            if res and (res.get("hits_performed") or res.get("killed")):
                await self.refresh_slice("boss", force=True)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug("Ошибка отложенного авто-удара босса: %s", e)

    def reschedule_boss_melee_in(self, wait_seconds: float) -> None:
        """Планирует точный одноразовый таймер следующего рукопашного удара по КД."""
        if not self.boss_worker:
            return
        clamped = max(1.0, min(float(wait_seconds), 3600.0))
        if self._melee_timer_task is not None and not self._melee_timer_task.done():
            self._melee_timer_task.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._melee_timer_task = loop.create_task(self._delayed_melee_hit(clamped))
        except RuntimeError:
            pass

    async def _delayed_business_collect(self, delay_sec: float) -> None:
        try:
            await asyncio.sleep(delay_sec)
            if not self.routine_worker:
                return
            await self.routine_worker.run_cycle()
            await asyncio.gather(
                self.refresh_slice("profile", force=True),
                self.refresh_slice("state", force=True),
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug("Ошибка отложенного сбора прибыли бизнесов: %s", e)

    def reschedule_business_in(self, wait_seconds: float) -> None:
        """Планирует точное пробуждение RoutineWorker к моменту готовности сбора бизнесов."""
        if not self.routine_worker:
            return
        clamped = max(1.0, min(float(wait_seconds), 9 * 3600.0))
        if self._business_timer_task is not None and not self._business_timer_task.done():
            self._business_timer_task.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._business_timer_task = loop.create_task(self._delayed_business_collect(clamped))
        except RuntimeError:
            pass

    async def _delayed_katala_run(self, delay_sec: float) -> None:
        try:
            await asyncio.sleep(delay_sec)
            if not self.routine_worker:
                return
            await self.routine_worker.play_katala_if_ready()
            await self.refresh_slice("profile", force=True)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug("Ошибка отложенного запуска Каталы: %s", e)

    def reschedule_katala_in(self, wait_seconds: float) -> None:
        """Планирует точный одноразовый запуск Каталы секунда в секунду к моменту отката."""
        if not self.routine_worker:
            return
        clamped = max(2.0, min(float(wait_seconds), 86500.0))
        if self._katala_timer_task is not None and not self._katala_timer_task.done():
            self._katala_timer_task.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._katala_timer_task = loop.create_task(self._delayed_katala_run(clamped))
        except RuntimeError:
            pass

    async def _run_routine_and_refresh(self) -> Any:
        if not self.routine_worker:
            return None
        try:
            res = await self.routine_worker.run_cycle()
            await asyncio.gather(
                self.refresh_slice("profile", force=True),
                self.refresh_slice("monthly", force=True),
                self.refresh_slice("state", force=True),
                return_exceptions=True,
            )
            return res
        except Exception as e:
            logger.warning("Ошибка немедленного цикла RoutineWorker: %s", e)
            return None

    def trigger_routine_now(self) -> Optional[asyncio.Task]:
        """Немедленно запускает цикл RoutineWorker в фоне при изменении настроек."""
        if not self.routine_worker:
            return None
        if self._immediate_routine_task is not None and not self._immediate_routine_task.done():
            return self._immediate_routine_task
        self._immediate_routine_task = asyncio.create_task(self._run_routine_and_refresh())
        return self._immediate_routine_task

    async def refresh_slice(self, slice_name: str, force: bool = True) -> None:
        try:
            from web.routes import refresh_hub_slice
            await refresh_hub_slice(account_id=self.account_id, slice_name=slice_name, force=force)
        except Exception as e:
            logger.debug("Фоновое обновление среза '%s' завершилось с ошибкой: %s", slice_name, e)

    async def refresh_tier1(self) -> None:
        """Tier 1 (20-40с): профиль, состояние, активный босс и награды."""
        await asyncio.gather(
            self.refresh_slice("profile", force=True),
            self.refresh_slice("boss", force=True),
            self.refresh_slice("state", force=True),
            return_exceptions=True,
        )

    async def refresh_tier2(self) -> None:
        """Tier 2 (90-120с): тюрьмы, друзья, входящие заявки и боевая статистика друзей."""
        await asyncio.gather(
            self.refresh_slice("prisons", force=True),
            self.refresh_slice("friends", force=True),
            self.refresh_slice("friend_requests", force=True),
            self.refresh_slice("friends_stats", force=True),
            return_exceptions=True,
        )

    async def refresh_tier3(self) -> None:
        """Tier 3 (5-6м): радар активных дамагеров, рутина (месячные + баулы), коллекции."""
        await asyncio.gather(
            self.refresh_slice("radar", force=True),
            self.refresh_slice("routine", force=True),
            self.refresh_slice("collections", force=True),
            return_exceptions=True,
        )

    async def warmup_all(self) -> None:
        """Первичный прогрев всех срезов LiveStateHub при старте сервиса."""
        logger.info("Запуск фонового прогрева LiveStateHub (Tier 1 -> Tier 2 -> Tier 3)...")
        await self.refresh_tier1()
        await self.refresh_tier2()
        await self.refresh_tier3()
        logger.info("Первичный прогрев LiveStateHub завершен.")


def create_scheduler(
    routine_worker: RoutineWorker,
    boss_worker: Optional[BossWorker] = None,
    prison_worker: Optional[PrisonWorker] = None,
    social_worker: Optional[SocialWorker] = None,
    routine_interval_minutes: Optional[int] = None,
    boss_interval_minutes: Optional[int] = None,
    prison_interval_minutes: Optional[int] = None,
    social_interval_minutes: Optional[int] = None,
) -> AsyncIOScheduler:
    """Создает и настраивает AsyncIOScheduler + SchedulerController для воркеров и фонового LiveStateHub."""
    scheduler = AsyncIOScheduler()
    acc_id = routine_worker.account_id
    controller = SchedulerController(
        scheduler=scheduler,
        routine_worker=routine_worker,
        boss_worker=boss_worker,
        prison_worker=prison_worker,
        social_worker=social_worker,
    )
    setattr(scheduler, "controller", controller)

    r_interval = routine_interval_minutes or settings.ROUTINE_INTERVAL_MINUTES
    routine_worker.on_business_reschedule = controller.reschedule_business_in
    scheduler.add_job(
        routine_worker.run_cycle,
        trigger="interval",
        minutes=r_interval,
        id=f"routine_worker_{acc_id}",
        name=f"Routine Worker for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"RoutineWorker зарегистрирован с интервалом {r_interval} минут.")

    msk_tz = timezone(timedelta(hours=3))
    scheduler.add_job(
        routine_worker.claim_daily_toilet_paper_if_ready,
        trigger=CronTrigger(hour=0, minute=1, timezone=msk_tz),
        id=f"daily_toilet_paper_msk_{acc_id}",
        name=f"Daily Toilet Paper 00:01 MSK for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Cron-триггер ежедневной туалетной бумаги (00:01 МСК) зарегистрирован.")

    scheduler.add_job(
        routine_worker.send_podogrev_if_ready,
        trigger=CronTrigger(hour=0, minute=0, second=5, timezone=msk_tz),
        id=f"daily_podogrev_send_msk_{acc_id}",
        name=f"Daily Podogrev Send 00:00:05 MSK for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Cron-триггер ежедневной раздачи подогревов (00:00:05 МСК) зарегистрирован.")
    routine_worker.on_katala_reschedule = controller.reschedule_katala_in

    if boss_worker:
        boss_worker.on_activity_change = controller.set_boss_fast_mode
        boss_worker.on_melee_reschedule = controller.reschedule_boss_melee_in
        boss_sec = SchedulerController.BOSS_IDLE_INTERVAL_SEC
        scheduler.add_job(
            boss_worker.run_cycle,
            trigger="interval",
            seconds=boss_sec,
            id=f"boss_worker_{acc_id}",
            name=f"Boss Worker for account {acc_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"BossWorker зарегистрирован с адаптивным интервалом ({SchedulerController.BOSS_FAST_INTERVAL_SEC}с/{boss_sec}с).")

        scheduler.add_job(
            boss_worker.check_scheduled_presets,
            trigger="interval",
            minutes=1,
            id=f"boss_preset_scheduler_{acc_id}",
            name=f"Boss Preset Scheduler for account {acc_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("BossPreset scheduler зарегистрирован с интервалом 1 минута.")

    if prison_worker:
        prison_worker.on_reschedule = controller.reschedule_prison_in
        p_interval = prison_interval_minutes or settings.PRISON_INTERVAL_MINUTES
        scheduler.add_job(
            prison_worker.run_cycle,
            trigger="interval",
            minutes=p_interval,
            id=f"prison_worker_{acc_id}",
            name=f"Prison Worker for account {acc_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"PrisonWorker зарегистрирован с точным перерасчетом регена (резерв {p_interval} мин).")

    if social_worker:
        s_interval = social_interval_minutes or settings.SOCIAL_INTERVAL_MINUTES
        scheduler.add_job(
            social_worker.run_cycle,
            trigger="interval",
            minutes=s_interval,
            id=f"social_worker_{acc_id}",
            name=f"Social Worker for account {acc_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"SocialWorker зарегистрирован с интервалом {s_interval} минут.")

    # Многоуровневые фоновые обновления LiveStateHub (для бесшовного SSE UI)
    scheduler.add_job(
        controller.refresh_tier1,
        trigger="interval",
        seconds=SchedulerController.TIER1_IDLE_SEC,
        id=f"hub_tier1_{acc_id}",
        name=f"LiveStateHub Tier 1 for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        controller.refresh_tier2,
        trigger="interval",
        seconds=SchedulerController.TIER2_INTERVAL_SEC,
        id=f"hub_tier2_{acc_id}",
        name=f"LiveStateHub Tier 2 for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        controller.refresh_tier3,
        trigger="interval",
        seconds=SchedulerController.TIER3_INTERVAL_SEC,
        id=f"hub_tier3_{acc_id}",
        name=f"LiveStateHub Tier 3 for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )

    if getattr(routine_worker, "db_engine", None) is not None:
        from core.database import prune_old_notifications
        async def _prune_notifs_job() -> None:
            try:
                await prune_old_notifications(routine_worker.db_engine, days=settings.NOTIFICATIONS_RETENTION_DAYS)
            except Exception as pe:
                logger.debug("Ошибка плановой очистки уведомлений: %s", pe)

        scheduler.add_job(
            _prune_notifs_job,
            trigger="interval",
            hours=1,
            id=f"prune_notifications_{acc_id}",
            name=f"Prune Notifications > {settings.NOTIFICATIONS_RETENTION_DAYS}d for account {acc_id}",
            replace_existing=True,
            max_instances=1,
        )

    return scheduler


def create_routine_scheduler(worker: RoutineWorker, interval_minutes: int = 15) -> AsyncIOScheduler:
    """Обратная совместимость: создание планировщика только для RoutineWorker."""
    return create_scheduler(routine_worker=worker, routine_interval_minutes=interval_minutes)
