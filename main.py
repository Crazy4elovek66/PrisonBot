import sys
import signal
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Optional
from sqlalchemy import select
import uvicorn

from core.config import settings
from core.database import init_db, get_session, get_engine
from core.models import Account, SessionData
from core.scheduler import create_scheduler
from core.state_hub import state_hub
from telegram.session_manager import interactive_login
from client.auth_provider import AuthProvider
from client.http_client import GameHttpClient
from client.api.player import PlayerAPI
from client.api.boss import BossAPI
from client.api.prison import PrisonAPI
from client.api.social import SocialAPI
from workers.routine_worker import RoutineWorker
from workers.boss_worker import BossWorker
from workers.prison_worker import PrisonWorker
from workers.social_worker import SocialWorker
from bot.notifier import TelegramNotifier
from bot.handlers import router as bot_router, bot_context
from web.app import app as web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("PrisonBot")


async def ensure_default_account() -> Account:
    """Гарантирует существование базового аккаунта в локальной БД."""
    async with get_session() as session:
        phone = settings.TG_PHONE or "+70000000000"
        stmt = select(Account).where(Account.phone == phone)
        res = await session.execute(stmt)
        acc = res.scalar_one_or_none()
        if not acc:
            acc = Account(phone=phone, is_active=True)
            session.add(acc)
            await session.flush()
            sess = SessionData(account_id=acc.id)
            session.add(sess)
            logger.info(f"Создан новый аккаунт с ID={acc.id} для телефона {phone}.")
        return acc


async def run_bot(once_mode: bool = False) -> None:
    """Основной жизненный цикл фонового сервиса."""
    logger.info("Инициализация базы данных...")
    Path("storage").mkdir(parents=True, exist_ok=True)
    await init_db()

    account = await ensure_default_account()
    auth_provider = AuthProvider(account_id=account.id)
    http_client = GameHttpClient(auth_provider=auth_provider)
    player_api = PlayerAPI(http_client=http_client)
    boss_api = BossAPI(http_client=http_client)
    prison_api = PrisonAPI(http_client=http_client)
    social_api = SocialAPI(http_client=http_client)

    # Инициализация Telegram-бота и нотификатора
    bot = None
    dp = None
    if settings.TG_BOT_TOKEN and settings.TG_BOT_TOKEN.strip():
        try:
            from aiogram import Bot, Dispatcher
            bot = Bot(token=settings.TG_BOT_TOKEN)
            dp = Dispatcher()
            dp.include_router(bot_router)
            logger.info("Telegram-бот управления успешно настроен.")
        except Exception as e:
            logger.warning(f"Не удалось инициализировать aiogram Bot: {e}")
            bot = None
            dp = None
    else:
        logger.info("TG_BOT_TOKEN не задан. Бот управления отключен (режим no-op).")

    notifier = TelegramNotifier(bot=bot, admin_id=settings.ADMIN_TG_ID)

    routine_worker = RoutineWorker(
        account_id=account.id,
        player_api=player_api,
        notifier=notifier,
        social_api=social_api,
    )
    boss_worker = BossWorker(
        account_id=account.id,
        boss_api=boss_api,
        notifier=notifier,
        prison_api=prison_api,
        player_api=player_api,
        state_hub=state_hub,
    )
    prison_worker = PrisonWorker(
        account_id=account.id,
        prison_api=prison_api,
        player_api=player_api,
        notifier=notifier,
        state_hub=state_hub,
    )
    social_worker = SocialWorker(
        account_id=account.id,
        social_api=social_api,
        notifier=notifier,
    )
    routine_worker.prison_worker = prison_worker

    if once_mode:
        logger.info("Запуск в режиме одиночного прогона (--once)...")
        await routine_worker.run_cycle()
        await boss_worker.run_cycle()
        await prison_worker.run_cycle()
        await social_worker.run_cycle()
        await http_client.aclose()
        if bot:
            await bot.session.close()
        logger.info("Одиночный прогон завершен.")
        return

    # Запуск планировщика
    scheduler = create_scheduler(
        routine_worker=routine_worker,
        boss_worker=boss_worker,
        prison_worker=prison_worker,
        social_worker=social_worker,
        routine_interval_minutes=settings.ROUTINE_INTERVAL_MINUTES,
        boss_interval_minutes=settings.BOSS_INTERVAL_MINUTES,
        prison_interval_minutes=settings.PRISON_INTERVAL_MINUTES,
        social_interval_minutes=settings.SOCIAL_INTERVAL_MINUTES,
    )

    # Обновление глобального контекста для Telegram-бота и WebApp
    bot_context.db_engine = get_engine()
    bot_context.scheduler = scheduler
    bot_context.scheduler_controller = getattr(scheduler, "controller", None)
    bot_context.state_hub = state_hub
    bot_context.player_api = player_api
    bot_context.boss_api = boss_api
    bot_context.prison_api = prison_api
    bot_context.social_api = social_api
    bot_context.routine_worker = routine_worker
    bot_context.boss_worker = boss_worker
    bot_context.prison_worker = prison_worker
    bot_context.social_worker = social_worker

    # Запуск WebApp Dashboard (FastAPI / uvicorn) немедленно, не блокируя порт стартовыми циклами воркеров
    web_config = uvicorn.Config(
        app=web_app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="warning",
        loop="asyncio",
    )
    web_server = uvicorn.Server(web_config)
    web_server_task = asyncio.create_task(web_server.serve())
    logger.info(f"Web Dashboard запущен на http://{settings.WEB_HOST}:{settings.WEB_PORT}")

    scheduler.start()
    logger.info(
        f"Воркеры успешно запущены (Рутина: {settings.ROUTINE_INTERVAL_MINUTES} мин, "
        f"Боссы: {settings.BOSS_INTERVAL_MINUTES} мин, Тюрьмы: {settings.PRISON_INTERVAL_MINUTES} мин, "
        f"Социалка: {settings.SOCIAL_INTERVAL_MINUTES} мин)."
    )

    async def _run_startup_workers() -> None:
        await asyncio.sleep(0.5)
        logger.info("Выполнение стартовых циклов рутины, боссов, тюрем и социалки в фоне...")
        for name, coro in (
            ("routine_worker", routine_worker.run_cycle()),
            ("boss_worker", boss_worker.run_cycle()),
            ("prison_worker", prison_worker.run_cycle()),
            ("social_worker", social_worker.run_cycle()),
        ):
            try:
                await coro
            except Exception as w_err:
                logger.warning(f"Ошибка стартового цикла {name}: {w_err}")
        if bot_context.scheduler_controller is not None:
            try:
                await bot_context.scheduler_controller.warmup_all()
            except Exception as wu_err:
                logger.warning(f"Ошибка прогрева LiveStateHub: {wu_err}")

    startup_workers_task = asyncio.create_task(_run_startup_workers())

    polling_task = None
    if bot and dp:
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
        logger.info("Telegram polling запущен.")

    stop_event = asyncio.Event()

    def handle_stop():
        logger.info("Получен сигнал завершения работы...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_stop)
        except (NotImplementedError, AttributeError):
            pass

    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("Остановка планировщика, веб-сервера и закрытие соединений...")
        if polling_task:
            polling_task.cancel()
            try:
                await polling_task
            except (asyncio.CancelledError, Exception):
                pass
        web_server.should_exit = True
        try:
            await web_server_task
        except Exception:
            pass
        scheduler.shutdown(wait=False)
        await http_client.aclose()
        if bot:
            await bot.session.close()
        logger.info("PrisonBot штатно остановлен.")


def main():
    parser = argparse.ArgumentParser(description="Автономный клиент игры Old Prison (Тюряга V3)")
    parser.add_argument(
        "--init-session",
        action="store_true",
        help="Интерактивный вход в Telegram MTProto для генерации .session файла",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Выполнить один цикл рутины, боссов, тюрем и социалки и завершить работу",
    )

    args = parser.parse_args()

    if args.init_session:
        logger.info("Запуск интерактивной авторизации в Telegram...")
        asyncio.run(interactive_login())
    else:
        try:
            asyncio.run(run_bot(once_mode=args.once))
        except KeyboardInterrupt:
            logger.info("Выход по прерыванию пользователя.")


if __name__ == "__main__":
    main()
