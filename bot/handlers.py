import logging
import asyncio
from typing import Optional, Any
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from sqlalchemy import select
from core.config import settings

from core.database import get_session
from core.models import PlayerSnapshot, ActionLog
from core.state_hub import state_hub
from bot.filters import AdminOnlyFilter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(AdminOnlyFilter())
router.callback_query.filter(AdminOnlyFilter())


class BotContext:
    """Контекст зависимостей Telegram-бота управления."""

    def __init__(
        self,
        db_engine: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        routine_worker: Optional[Any] = None,
        boss_worker: Optional[Any] = None,
        prison_worker: Optional[Any] = None,
        social_worker: Optional[Any] = None,
    ):
        self.db_engine = db_engine
        self.scheduler = scheduler
        self.routine_worker = routine_worker
        self.boss_worker = boss_worker
        self.prison_worker = prison_worker
        self.social_worker = social_worker
        self._player_api = None
        self._boss_api = None
        self._prison_api = None
        self._social_api = None
        self._is_paused: bool = False
        self._is_running_manual: bool = False
        self.state_hub = state_hub
        self.scheduler_controller = None

    @property
    def player_api(self):
        if self._player_api is not None:
            return self._player_api
        return getattr(self.routine_worker, "api", None)

    @player_api.setter
    def player_api(self, value):
        self._player_api = value

    @property
    def boss_api(self):
        if self._boss_api is not None:
            return self._boss_api
        return getattr(self.boss_worker, "api", None)

    @boss_api.setter
    def boss_api(self, value):
        self._boss_api = value

    @property
    def prison_api(self):
        if self._prison_api is not None:
            return self._prison_api
        return getattr(self.prison_worker, "prison_api", None)

    @prison_api.setter
    def prison_api(self, value):
        self._prison_api = value

    @property
    def social_api(self):
        if self._social_api is not None:
            return self._social_api
        return getattr(self.social_worker, "api", None)

    @social_api.setter
    def social_api(self, value):
        self._social_api = value

    def is_paused(self) -> bool:
        if self.scheduler is not None:
            # 2 = STATE_PAUSED in apscheduler
            state = getattr(self.scheduler, "state", None)
            if state == 2:
                return True
        return self._is_paused

    def pause(self) -> None:
        self._is_paused = True
        if self.scheduler is not None:
            try:
                self.scheduler.pause()
            except Exception as e:
                logger.warning("Ошибка вызова scheduler.pause(): %s", e)

    def resume(self) -> None:
        self._is_paused = False
        if self.scheduler is not None:
            try:
                self.scheduler.resume()
            except Exception as e:
                logger.warning("Ошибка вызова scheduler.resume(): %s", e)


bot_context = BotContext()


def get_main_keyboard(is_paused: bool = False) -> InlineKeyboardMarkup:
    """Формирование клавиатуры управления ботом."""
    builder = InlineKeyboardBuilder()
    pause_text = "▶️ Возобновить" if is_paused else "⏸ Пауза"
    pause_cb = "cb_resume" if is_paused else "cb_pause"

    builder.row(
        InlineKeyboardButton(text="📊 Статус", callback_data="cb_status"),
        InlineKeyboardButton(text="🚀 Запустить сейчас", callback_data="cb_run"),
    )
    builder.row(
        InlineKeyboardButton(text=pause_text, callback_data=pause_cb),
        InlineKeyboardButton(text="📜 Логи", callback_data="cb_logs"),
    )
    if settings.WEBAPP_PUBLIC_URL and settings.WEBAPP_PUBLIC_URL.strip():
        builder.row(
            InlineKeyboardButton(
                text="📱 Открыть WebApp",
                web_app=WebAppInfo(url=settings.WEBAPP_PUBLIC_URL.strip()),
            )
        )
    return builder.as_markup()


async def build_status_text(ctx: BotContext) -> str:
    """Генерация сводки статуса игрока и планировщика."""
    snapshot: Optional[PlayerSnapshot] = None
    last_log: Optional[ActionLog] = None

    try:
        async with get_session(ctx.db_engine) as session:
            stmt_snap = select(PlayerSnapshot).order_by(PlayerSnapshot.id.desc()).limit(1)
            res_snap = await session.execute(stmt_snap)
            snapshot = res_snap.scalar_one_or_none()

            stmt_log = select(ActionLog).order_by(ActionLog.id.desc()).limit(1)
            res_log = await session.execute(stmt_log)
            last_log = res_log.scalar_one_or_none()
    except Exception as e:
        logger.error("Ошибка выборки статуса из БД: %s", e)

    scheduler_status = "⏸ <b>На паузе</b>" if ctx.is_paused() else "🟢 <b>Активен</b>"

    if snapshot:
        text = (
            "📊 <b>Статус персонажа:</b>\n\n"
            f"🎖 Уровень: <b>{snapshot.level}</b> | "
            f"👑 Авторитет: <b>{snapshot.authority}</b> | "
            f"💪 Бицуха: <b>{snapshot.biceps}</b>\n"
            f"⚡️ Энергия: <b>{snapshot.energy}/{snapshot.max_energy}</b>\n\n"
            "💰 <b>Балансы:</b>\n"
            f"  🚬 Папиросы: <b>{snapshot.cigarettes}</b>\n"
            f"  🍬 Сахар: <b>{snapshot.sugar}</b>\n"
            f"  💵 Рубли: <b>{snapshot.rubles}</b>\n"
            f"  🧻 Бумага: <b>{snapshot.paper}</b>\n"
            f"  🧼 Мыло: <b>{snapshot.soap}</b>\n\n"
            f"⏱ Планировщик: {scheduler_status}\n"
        )
    else:
        text = (
            "📊 <b>Статус персонажа:</b>\n\n"
            "<i>Снимков игрока пока нет в базе данных.</i>\n\n"
            f"⏱ Планировщик: {scheduler_status}\n"
        )

    if last_log:
        ts_str = last_log.created_at.strftime("%H:%M:%S UTC") if last_log.created_at else "-"
        status_txt = "✅" if last_log.success else "❌"
        text += f"Последнее действие: {status_txt} <code>{last_log.action_type}</code> ({ts_str})"
    else:
        text += "Последнее действие: <i>нет записей</i>"

    return text


async def build_logs_text(ctx: BotContext) -> str:
    """Генерация списка последних 10 действий."""
    try:
        async with get_session(ctx.db_engine) as session:
            stmt = select(ActionLog).order_by(ActionLog.id.desc()).limit(10)
            res = await session.execute(stmt)
            logs = res.scalars().all()
    except Exception as e:
        logger.error("Ошибка выборки логов из БД: %s", e)
        return f"❌ Ошибка загрузки логов: {e}"

    if not logs:
        return "📜 <b>Логи действий:</b>\n\n<i>Записей пока нет.</i>"

    lines = ["📜 <b>Последние 10 действий:</b>\n"]
    for entry in logs:
        ts = entry.created_at.strftime("%H:%M:%S") if entry.created_at else "--:--:--"
        st = "✅" if entry.success else "❌"
        lines.append(f"• [{ts}] {st} <code>{entry.action_type}</code> (код {entry.status_code})")

    return "\n".join(lines)


async def execute_manual_run(ctx: BotContext, reply_target: Any) -> None:
    """Фоновый запуск всех воркеров с уведомлением о завершении."""
    if ctx._is_running_manual:
        await reply_target.answer("⚠️ Внеочередной прогон уже выполняется!")
        return

    ctx._is_running_manual = True
    await reply_target.answer("🚀 <b>Запущен внеочередной прогон воркеров...</b>", parse_mode="HTML")

    async def _runner():
        try:
            if ctx.routine_worker:
                await ctx.routine_worker.run_cycle()
            if ctx.boss_worker:
                await ctx.boss_worker.run_cycle()
            if ctx.prison_worker:
                await ctx.prison_worker.run_cycle()
            if ctx.social_worker:
                await ctx.social_worker.run_cycle()
            await reply_target.answer("✅ <b>Внеочередной прогон успешно завершен!</b>", parse_mode="HTML")
        except Exception as e:
            logger.error("Ошибка во время ручного прогона: %s", e)
            await reply_target.answer(f"❌ <b>Ошибка при прогоне:</b> {e}", parse_mode="HTML")
        finally:
            ctx._is_running_manual = False

    asyncio.create_task(_runner())


# --- ОБРАБОТЧИКИ КОМАНД ---

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    text = (
        "👋 <b>Добро пожаловать в панель управления PrisonBot!</b>\n\n"
        "Доступные команды:\n"
        "• /status — сводка по персонажу и балансам\n"
        "• /logs — последние 10 логов активности\n"
        "• /run — принудительный запуск всех воркеров\n"
        "• /pause — поставить планировщик на паузу\n"
        "• /resume — возобновить работу планировщика"
    )
    kb = get_main_keyboard(is_paused=bot_context.is_paused())
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    text = await build_status_text(bot_context)
    kb = get_main_keyboard(is_paused=bot_context.is_paused())
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("logs"))
async def cmd_logs(message: Message) -> None:
    text = await build_logs_text(bot_context)
    kb = get_main_keyboard(is_paused=bot_context.is_paused())
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("run"))
async def cmd_run(message: Message) -> None:
    await execute_manual_run(bot_context, message)


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    bot_context.pause()
    kb = get_main_keyboard(is_paused=True)
    await message.answer("⏸ <b>Планировщик поставлен на паузу.</b>", parse_mode="HTML", reply_markup=kb)


@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    bot_context.resume()
    kb = get_main_keyboard(is_paused=False)
    await message.answer("▶️ <b>Планировщик возобновлен.</b>", parse_mode="HTML", reply_markup=kb)


# --- ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ---

@router.callback_query(F.data == "cb_status")
async def cb_status(query: CallbackQuery) -> None:
    text = await build_status_text(bot_context)
    kb = get_main_keyboard(is_paused=bot_context.is_paused())
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await query.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await query.answer()


@router.callback_query(F.data == "cb_logs")
async def cb_logs(query: CallbackQuery) -> None:
    text = await build_logs_text(bot_context)
    kb = get_main_keyboard(is_paused=bot_context.is_paused())
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await query.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await query.answer()


@router.callback_query(F.data == "cb_run")
async def cb_run(query: CallbackQuery) -> None:
    await execute_manual_run(bot_context, query.message)
    await query.answer("Запуск...")


@router.callback_query(F.data == "cb_pause")
async def cb_pause(query: CallbackQuery) -> None:
    bot_context.pause()
    kb = get_main_keyboard(is_paused=True)
    text = await build_status_text(bot_context)
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await query.answer("Планировщик на паузе")


@router.callback_query(F.data == "cb_resume")
async def cb_resume(query: CallbackQuery) -> None:
    bot_context.resume()
    kb = get_main_keyboard(is_paused=False)
    text = await build_status_text(bot_context)
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await query.answer("Планировщик возобновлен")
