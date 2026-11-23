import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.config import settings
from workers.routine_worker import RoutineWorker
from workers.boss_worker import BossWorker
from workers.prison_worker import PrisonWorker
from workers.social_worker import SocialWorker

logger = logging.getLogger(__name__)


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
    """Создает и настраивает AsyncIOScheduler для выполнения рутинных, боевых, тюремных и социальных задач."""
    scheduler = AsyncIOScheduler()

    r_interval = routine_interval_minutes or settings.ROUTINE_INTERVAL_MINUTES
    scheduler.add_job(
        routine_worker.run_cycle,
        trigger="interval",
        minutes=r_interval,
        id=f"routine_worker_{routine_worker.account_id}",
        name=f"Routine Worker for account {routine_worker.account_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"RoutineWorker зарегистрирован с интервалом {r_interval} минут.")

    if boss_worker:
        b_interval = boss_interval_minutes or settings.BOSS_INTERVAL_MINUTES
        scheduler.add_job(
            boss_worker.run_cycle,
            trigger="interval",
            minutes=b_interval,
            id=f"boss_worker_{boss_worker.account_id}",
            name=f"Boss Worker for account {boss_worker.account_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"BossWorker зарегистрирован с интервалом {b_interval} минут.")

        scheduler.add_job(
            boss_worker.check_scheduled_presets,
            trigger="interval",
            minutes=1,
            id=f"boss_preset_scheduler_{boss_worker.account_id}",
            name=f"Boss Preset Scheduler for account {boss_worker.account_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"BossPreset scheduler зарегистрирован с интервалом 1 минута.")

    if prison_worker:
        p_interval = prison_interval_minutes or settings.PRISON_INTERVAL_MINUTES
        scheduler.add_job(
            prison_worker.run_cycle,
            trigger="interval",
            minutes=p_interval,
            id=f"prison_worker_{prison_worker.account_id}",
            name=f"Prison Worker for account {prison_worker.account_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"PrisonWorker зарегистрирован с интервалом {p_interval} минут.")

    if social_worker:
        s_interval = social_interval_minutes or settings.SOCIAL_INTERVAL_MINUTES
        scheduler.add_job(
            social_worker.run_cycle,
            trigger="interval",
            minutes=s_interval,
            id=f"social_worker_{social_worker.account_id}",
            name=f"Social Worker for account {social_worker.account_id}",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"SocialWorker зарегистрирован с интервалом {s_interval} минут.")

    return scheduler


def create_routine_scheduler(worker: RoutineWorker, interval_minutes: int = 15) -> AsyncIOScheduler:
    """Обратная совместимость: создание планировщика только для RoutineWorker."""
    return create_scheduler(routine_worker=worker, routine_interval_minutes=interval_minutes)
