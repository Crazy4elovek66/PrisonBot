import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from core.config import settings
from core.database import get_engine, init_db, get_session
from core.models import Account, PlayerSnapshot, ActionLog
from bot.filters import AdminOnlyFilter
from bot.notifier import TelegramNotifier
from bot.handlers import BotContext, build_status_text, build_logs_text, get_main_keyboard


@pytest.mark.asyncio
async def test_admin_only_filter(monkeypatch):
    """AdminOnlyFilter пропускает только события от пользователя с ID == ADMIN_TG_ID."""
    monkeypatch.setattr(settings, "ADMIN_TG_ID", 437225657)
    admin_filter = AdminOnlyFilter()

    # Событие от администратора
    event_admin = SimpleNamespace(from_user=SimpleNamespace(id=437225657))
    assert await admin_filter(event_admin) is True

    # Событие от постороннего пользователя
    event_stranger = SimpleNamespace(from_user=SimpleNamespace(id=999999999))
    assert await admin_filter(event_stranger) is False

    # Событие без from_user
    event_no_user = SimpleNamespace(from_user=None)
    assert await admin_filter(event_no_user) is False


@pytest.mark.asyncio
async def test_telegram_notifier_no_op_and_error_handling():
    """TelegramNotifier безопасно обрабатывает отсутствие бота и сетевые ошибки."""
    # 1. No-op режим (bot=None, admin_id=0)
    notifier_noop = TelegramNotifier(bot=None, admin_id=0)
    await notifier_noop.notify("Любое тестовое сообщение")  # Не должно вызывать исключений

    # 2. Ошибка при отправке
    mock_bot_err = MagicMock()
    mock_bot_err.send_message = AsyncMock(side_effect=Exception("Connection reset by peer"))
    notifier_err = TelegramNotifier(bot=mock_bot_err, admin_id=123456)
    await notifier_err.notify("Сообщение с сетевой ошибкой")  # Не должно падать

    # 3. Успешная отправка
    mock_bot_ok = MagicMock()
    mock_bot_ok.send_message = AsyncMock()
    notifier_ok = TelegramNotifier(bot=mock_bot_ok, admin_id=123456)
    await notifier_ok.notify("<b>Успех</b>")
    mock_bot_ok.send_message.assert_awaited_once_with(
        chat_id=123456,
        text="<b>Успех</b>",
        parse_mode="HTML",
    )


@pytest_asyncio.fixture
async def bot_test_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)

    async with get_session(engine) as session:
        acc = Account(phone="+79991112233", nickname="BossHero")
        session.add(acc)
        await session.flush()

        snapshot = PlayerSnapshot(
            account_id=acc.id,
            level=25,
            authority=88800,
            biceps=120,
            energy=65,
            max_energy=100,
            cigarettes=5500,
            sugar=420,
            rubles=777,
            paper=14,
            soap=3,
        )
        session.add(snapshot)

        action = ActionLog(
            account_id=acc.id,
            action_type="prison_work",
            endpoint="/api/player/prison/1/work",
            status_code=200,
            success=True,
            details={"worksDone": 2},
        )
        session.add(action)

    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_status_formatting_and_pause_resume(bot_test_setup):
    """Проверка форматирования текста /status и переключения режимов паузы планировщика."""
    engine = bot_test_setup

    mock_scheduler = MagicMock()
    mock_scheduler.pause = MagicMock()
    mock_scheduler.resume = MagicMock()
    mock_scheduler.state = 1  # STATE_RUNNING

    ctx = BotContext(db_engine=engine, scheduler=mock_scheduler)

    # 1. Проверка активного статуса
    assert ctx.is_paused() is False
    status_text = await build_status_text(ctx)
    assert "25" in status_text  # Уровень
    assert "88800" in status_text  # Авторитет
    assert "65/100" in status_text  # Энергия
    assert "5500" in status_text  # Папиросы
    assert "777" in status_text  # Рубли
    assert "Активен" in status_text
    assert "prison_work" in status_text

    # 2. Проверка паузы
    ctx.pause()
    mock_scheduler.pause.assert_called_once()
    assert ctx.is_paused() is True
    status_text_paused = await build_status_text(ctx)
    assert "На паузе" in status_text_paused

    # 3. Проверка возобновления
    ctx.resume()
    mock_scheduler.resume.assert_called_once()
    assert ctx.is_paused() is False

    # 4. Проверка клавиатуры
    kb_active = get_main_keyboard(is_paused=False)
    assert any(b.text == "⏸ Пауза" for row in kb_active.inline_keyboard for b in row)

    kb_paused = get_main_keyboard(is_paused=True)
    assert any(b.text == "▶️ Возобновить" for row in kb_paused.inline_keyboard for b in row)

    # 5. Проверка форматирования логов
    logs_text = await build_logs_text(ctx)
    assert "prison_work" in logs_text
    assert "200" in logs_text
