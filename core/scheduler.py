import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.state_hub import state_hub as global_state_hub
from core.server_health import server_health_monitor, GameMaintenanceError
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
    FRIEND_REQUESTS_FAST_SEC = 30
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
        self.health_monitor = server_health_monitor
        self.account_id = getattr(routine_worker, "account_id", 1)
        self._boss_fast_mode = False
        self._battle_watcher_task: Optional[asyncio.Task] = None
        self._immediate_boss_task: Optional[asyncio.Task] = None
        self._immediate_prison_task: Optional[asyncio.Task] = None
        self._immediate_routine_task: Optional[asyncio.Task] = None
        self._immediate_social_req_task: Optional[asyncio.Task] = None
        self._melee_timer_task: Optional[asyncio.Task] = None
        self._business_timer_task: Optional[asyncio.Task] = None
        self._katala_timer_task: Optional[asyncio.Task] = None
        self._wakeup_tasks: Dict[str, asyncio.Task] = {}
        self.worker_status: Dict[str, Dict[str, Any]] = {}
        self.poker_worker: Optional[Any] = None
        self.fartovy_worker: Optional[Any] = None
        self.zaruby_worker: Optional[Any] = None

    def schedule_wakeup(self, worker_name: str, run_at_utc: datetime) -> None:
        """
        Универсальный real-time wake-up триггер для любого независимого воркера.
        Пробуждает воркер точно по откату серверного таймера (без блокировки соседних воркеров).
        """
        now_utc = datetime.now(timezone.utc)
        target = run_at_utc if run_at_utc.tzinfo else run_at_utc.replace(tzinfo=timezone.utc)
        delay = max(1.0, min((target - now_utc).total_seconds(), 86500.0))

        old_task = self._wakeup_tasks.get(worker_name)
        if old_task is not None and not old_task.done():
            old_task.cancel()

        st = self.worker_status.setdefault(worker_name, {})
        st["next_wakeup_at"] = target.isoformat()

        async def _runner() -> None:
            try:
                await asyncio.sleep(delay)
                if self.health_monitor and self.health_monitor.is_maintenance:
                    return
                worker_map = {
                    "poker": self.poker_worker,
                    "fartovy": self.fartovy_worker,
                    "zaruby": self.zaruby_worker,
                    "boss": self.boss_worker,
                    "prison": self.prison_worker,
                    "routine": self.routine_worker,
                    "social": self.social_worker,
                }
                w = worker_map.get(worker_name)
                if w is not None and hasattr(w, "run_cycle"):
                    st["status"] = "running"
                    st["last_run_at"] = datetime.now(timezone.utc).isoformat()
                    res = await w.run_cycle()
                    st["status"] = "idle"
                    st["last_result"] = res.get("status") if isinstance(res, dict) else "ok"
            except asyncio.CancelledError:
                return
            except Exception as exc:
                st["status"] = "error"
                st["last_result"] = str(exc)
                logger.debug("Wakeup error for %s: %s", worker_name, exc)

        try:
            loop = asyncio.get_running_loop()
            self._wakeup_tasks[worker_name] = loop.create_task(_runner())
        except RuntimeError:
            pass

    def set_boss_fast_mode(self, active: bool) -> None:
        """Переключает интервал проверки боссов (адаптивный BattleWatcher в бою / 60с в простое)."""
        target_fast = bool(active)
        if target_fast == self._boss_fast_mode:
            if target_fast and (self._battle_watcher_task is None or self._battle_watcher_task.done()):
                self._start_battle_watcher()
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

        if target_fast:
            self._start_battle_watcher()
        else:
            self._stop_battle_watcher()

    def _start_battle_watcher(self) -> None:
        if not self.boss_worker:
            return
        if self._battle_watcher_task is not None and not self._battle_watcher_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._battle_watcher_task = loop.create_task(self._battle_watcher_loop())
        except RuntimeError:
            pass

    def _stop_battle_watcher(self) -> None:
        if self._battle_watcher_task is not None and not self._battle_watcher_task.done():
            self._battle_watcher_task.cancel()
        self._battle_watcher_task = None

    async def _battle_watcher_loop(self) -> None:
        from workers.boss_worker import compute_adaptive_battle_poll_interval

        last_logged_interval: Optional[float] = None
        try:
            while self._boss_fast_mode and self.boss_worker:
                cur_hp = None
                max_hp = None
                boss_entry = self.state_hub.get_slice(self.account_id, "boss")
                if boss_entry and isinstance(boss_entry.data, dict):
                    sess = boss_entry.data.get("session") or {}
                    if isinstance(sess, dict):
                        cur_hp = sess.get("currentHp")
                        max_hp = sess.get("maxHp")

                degraded = bool(
                    self.health_monitor.is_maintenance
                    or getattr(self.health_monitor, "consecutive_failures", 0) > 0
                )
                interval = compute_adaptive_battle_poll_interval(cur_hp, max_hp, server_degraded=degraded)
                if last_logged_interval != interval:
                    logger.info(
                        "BattleWatcher: адаптивный интервал %.1fс (hp=%s/%s, degraded=%s).",
                        interval,
                        cur_hp,
                        max_hp,
                        degraded,
                    )
                    last_logged_interval = interval

                await asyncio.sleep(interval)
                if not self._boss_fast_mode or not self.boss_worker:
                    break

                tick = await self.boss_worker.watch_active_battle_tick()
                if tick.get("needs_action"):
                    await self.boss_worker.run_cycle()
                    await self.refresh_tier1()
                elif not tick.get("active"):
                    self.set_boss_fast_mode(False)
                    break
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug("BattleWatcher завершился с ошибкой: %s", e)

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
                from core.database import get_or_create_config, is_worker_active, is_night_mode_active
                cfg = await get_or_create_config(self.account_id, self.boss_worker.db_engine)
                if not is_worker_active(cfg) or is_night_mode_active(cfg) or not (
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

    async def _run_social_requests_and_refresh(self) -> Any:
        if not self.social_worker:
            return None
        try:
            res = await self.social_worker.check_incoming_friend_requests()
            if isinstance(res, dict) and (res.get("accepted", 0) > 0 or res.get("declined", 0) > 0):
                await asyncio.gather(
                    self.refresh_slice("friends", force=True),
                    self.refresh_slice("friend_requests", force=True),
                    return_exceptions=True,
                )
            return res
        except Exception as e:
            logger.warning("Ошибка немедленной проверки заявок в друзья: %s", e)
            return None

    def trigger_social_requests_now(self) -> Optional[asyncio.Task]:
        """Немедленно проверяет входящие заявки в друзья (при смене фильтров в UI)."""
        if not self.social_worker:
            return None
        if self._immediate_social_req_task is not None and not self._immediate_social_req_task.done():
            return self._immediate_social_req_task
        self._immediate_social_req_task = asyncio.create_task(self._run_social_requests_and_refresh())
        return self._immediate_social_req_task

    async def refresh_slice(self, slice_name: str, force: bool = True) -> None:
        if self.health_monitor and self.health_monitor.is_maintenance:
            return
        try:
            from web.routes import refresh_hub_slice
            await refresh_hub_slice(account_id=self.account_id, slice_name=slice_name, force=force)
        except GameMaintenanceError:
            return
        except Exception as e:
            logger.debug("Фоновое обновление среза '%s' завершилось с ошибкой: %s", slice_name, e)

    async def refresh_tier1(self) -> None:
        """Tier 1 (20-40с): профиль, состояние, активный босс и награды."""
        if self.health_monitor and self.health_monitor.is_maintenance:
            return
        await asyncio.gather(
            self.refresh_slice("profile", force=True),
            self.refresh_slice("boss", force=True),
            self.refresh_slice("talents", force=True),
            self.refresh_slice("state", force=True),
            return_exceptions=True,
        )

    async def refresh_tier2(self) -> None:
        """Tier 2 (90-120с): тюрьмы, друзья, входящие заявки и боевая статистика друзей."""
        if self.health_monitor and self.health_monitor.is_maintenance:
            return
        await asyncio.gather(
            self.refresh_slice("prisons", force=True),
            self.refresh_slice("friends", force=True),
            self.refresh_slice("friend_requests", force=True),
            self.refresh_slice("friends_stats", force=True),
            return_exceptions=True,
        )

    async def refresh_tier3(self) -> None:
        """Tier 3 (5-6м): радар активных дамагеров, рутина (месячные + баулы), коллекции."""
        if self.health_monitor and self.health_monitor.is_maintenance:
            return
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
    poker_worker: Optional[Any] = None,
    fartovy_worker: Optional[Any] = None,
    zaruby_worker: Optional[Any] = None,
    friend_outreach_worker: Optional[Any] = None,
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
    controller.poker_worker = poker_worker
    controller.fartovy_worker = fartovy_worker
    controller.zaruby_worker = zaruby_worker
    controller.friend_outreach_worker = friend_outreach_worker
    try:
        from core.state_hub import state_hub
        state_hub.register_wakeup_callback(controller.schedule_wakeup)
    except Exception:
        pass

    if poker_worker is not None:
        poker_worker.on_wakeup_schedule = controller.schedule_wakeup
        scheduler.add_job(
            poker_worker.run_cycle,
            trigger="interval",
            minutes=4,
            id=f"poker_worker_{acc_id}",
            replace_existing=True,
            max_instances=1,
        )
    if fartovy_worker is not None:
        fartovy_worker.on_wakeup_schedule = controller.schedule_wakeup
        scheduler.add_job(
            fartovy_worker.run_cycle,
            trigger="interval",
            minutes=4,
            id=f"fartovy_worker_{acc_id}",
            replace_existing=True,
            max_instances=1,
        )
    if zaruby_worker is not None:
        zaruby_worker.on_wakeup_schedule = controller.schedule_wakeup
        scheduler.add_job(
            zaruby_worker.run_cycle,
            trigger="interval",
            minutes=4,
            id=f"zaruby_worker_{acc_id}",
            replace_existing=True,
            max_instances=1,
        )

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

    scheduler.add_job(
        routine_worker.process_auto_interactions,
        trigger=CronTrigger(hour=0, minute=0, second=10, timezone=msk_tz),
        id=f"daily_auto_interactions_msk_{acc_id}",
        name=f"Daily Auto Interactions 00:00:10 MSK for account {acc_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Cron-триггер ежедневных авто-взаимодействий (00:00:10 МСК) зарегистрирован.")
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

        scheduler.add_job(
            social_worker.check_incoming_friend_requests,
            trigger="interval",
            seconds=SchedulerController.FRIEND_REQUESTS_FAST_SEC,
            id=f"friend_requests_fast_{acc_id}",
            name=f"Fast Friend Requests Check for account {acc_id}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            f"Быстрая проверка входящих заявок в друзья зарегистрирована с интервалом {SchedulerController.FRIEND_REQUESTS_FAST_SEC}с."
        )

    if friend_outreach_worker is not None:
        scheduler.add_job(
            friend_outreach_worker.run_cycle,
            trigger="interval",
            seconds=300,
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
            id=f"friend_outreach_worker_{acc_id}",
            name=f"Friend Outreach Worker for account {acc_id}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("FriendOutreachWorker зарегистрирован с независимым интервалом 300с (старт через 10с).")

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
