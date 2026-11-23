import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, delete

from telegram.session_manager import get_telegram_client
from core.database import get_session
from core.models import CachedRaidPost

logger = logging.getLogger(__name__)


def clean_channel_username(channel_str: str) -> str:
    """Очищает строку канала вида 'https://t.me/pro_prison' или '@pro_prison' в чистый юзернейм."""
    if not channel_str:
        return ""
    s = channel_str.strip()
    s = re.sub(r"^https?://t\.me/", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^@", "", s)
    s = s.split("/")[0].split("?")[0].strip()
    return s


class RaidChannelScanner:
    """
    Безопасный Read-Only сканер публичных Telegram-каналов с рейдами:
    - Использует существующую сессию Telethon в строго Read-Only режиме.
    - Читает последние до 15 постов каждого канала.
    - Перехватывает telethon.errors.FloodWaitError и активирует cooldown e.seconds + 60.
    - Парсит сообщения через RaidsAPI.parse_raid_text и сохраняет в CachedRaidPost.
    - Очищает кэшированные посты старше 72 часов.
    """

    DEFAULT_RECOMMENDED_CHANNELS = [
        "pro_prison",
        "pro_prison_chat",
    ]

    async def scan_channels(
        self,
        channels: List[str],
        db_engine: Any,
        raids_api: Any,
        account_id: int = 1,
        force: bool = False,
        limit_per_channel: int = 15,
        delay_between_channels: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Сканирует список публичных каналов.
        """
        rate_guard = getattr(raids_api, "rate_guard", None)
        if rate_guard:
            can_run, rem_cd = rate_guard.can_scan_tg(force=force)
            if not can_run:
                return {
                    "success": False,
                    "status": "cooldown",
                    "cooldownSeconds": rem_cd,
                    "message": f"Кулдаун проверки TG-каналов: подождите {rem_cd} сек перед повторным запуском",
                }

        cleaned_channels = []
        for ch in channels:
            c = clean_channel_username(ch)
            if c and c not in cleaned_channels:
                cleaned_channels.append(c)

        if not cleaned_channels:
            return {
                "success": True,
                "status": "no_channels",
                "message": "Список Telegram-каналов пуст. Добавьте публичные каналы в настройках.",
                "foundPosts": 0,
            }

        # Ограничиваем не более 10 каналов за проход
        cleaned_channels = cleaned_channels[:10]

        client = get_telegram_client()
        try:
            await client.connect()
            if not await client.is_user_authorized():
                return {
                    "success": False,
                    "status": "tg_not_configured",
                    "message": "Telegram сессия не авторизована. Требуется вход через python main.py --init-session",
                    "foundPosts": 0,
                }
        except Exception as e:
            logger.warning(f"Ошибка подключения Telethon: {e}")
            return {
                "success": False,
                "status": "tg_error",
                "message": f"Ошибка подключения к Telegram: {e}",
                "foundPosts": 0,
            }

        found_count = 0
        now = datetime.utcnow()

        try:
            import telethon.errors
        except ImportError:
            telethon = None

        try:
            for idx, ch_name in enumerate(cleaned_channels):
                if idx > 0 and delay_between_channels > 0:
                    await asyncio.sleep(delay_between_channels)

                try:
                    entity = await client.get_entity(ch_name)
                    async for msg in client.iter_messages(entity, limit=limit_per_channel):
                        text = getattr(msg, "text", "") or getattr(msg, "message", "") or ""
                        if not text or len(text.strip()) < 10:
                            continue

                        # Проверяем, похож ли текст на рейд (наличие 64-битного ID или ключевых слов рейда)
                        has_id = bool(re.search(r"\b(9\d{15}|\d{7,10})\b", text))
                        has_raid_word = any(w in text.lower() for w in ["рейд", "бригад", "босс", "дамаг", "урон", "хирург", "бурят"])

                        if not (has_id and (has_raid_word or text.count("\n") >= 2)):
                            continue

                        # Парсим через RaidsAPI.parse_raid_text
                        parsed_res = await raids_api.parse_raid_text(
                            raw_text=text,
                            player_api=getattr(raids_api, "player_api", None),
                        )
                        participants = parsed_res.get("participants", [])
                        if not participants:
                            continue

                        msg_id = getattr(msg, "id", int(datetime.utcnow().timestamp()))
                        msg_date = getattr(msg, "date", now)
                        if hasattr(msg_date, "replace"):
                            msg_date = msg_date.replace(tzinfo=None)

                        # Сохраняем в CachedRaidPost
                        async with get_session(db_engine) as session:
                            stmt = select(CachedRaidPost).where(
                                CachedRaidPost.account_id == account_id,
                                CachedRaidPost.channel_username == ch_name,
                                CachedRaidPost.message_id == msg_id,
                            )
                            existing = (await session.execute(stmt)).scalar_one_or_none()

                            if not existing:
                                post_rec = CachedRaidPost(
                                    account_id=account_id,
                                    channel_username=ch_name,
                                    message_id=msg_id,
                                    title=parsed_res.get("title") or f"Рейд из @{ch_name}",
                                    post_date=msg_date,
                                    raw_preview=text[:300],
                                    participants=participants,
                                    created_at=now,
                                )
                                session.add(post_rec)
                            else:
                                existing.participants = participants
                                existing.raw_preview = text[:300]

                        found_count += 1

                except Exception as e:
                    # Проверяем FloodWaitError
                    is_flood = False
                    flood_seconds = 60
                    if telethon and isinstance(e, telethon.errors.FloodWaitError):
                        is_flood = True
                        flood_seconds = getattr(e, "seconds", 60) + 60
                    elif "floodwait" in type(e).__name__.lower() or "flood" in str(e).lower():
                        is_flood = True
                        m = re.search(r"(\d+)", str(e))
                        if m:
                            flood_seconds = int(m.group(1)) + 60

                    if is_flood:
                        logger.warning(f"Telegram FloodWait: {flood_seconds} секунд")
                        if rate_guard:
                            rate_guard.trip_circuit_breaker(f"Telegram FloodWait ({flood_seconds}s)", flood_seconds)
                        return {
                            "success": False,
                            "status": "flood_wait",
                            "floodWaitSeconds": flood_seconds,
                            "message": f"Telegram FloodWaitError: сканер на паузе на {flood_seconds} сек.",
                            "foundPosts": found_count,
                        }

                    logger.warning(f"Не удалось прочитать канал @{ch_name}: {e}")
                    continue

            # Очистка постов старше 72 часов
            async with get_session(db_engine) as session:
                cutoff = now - timedelta(hours=72)
                await session.execute(
                    delete(CachedRaidPost).where(
                        CachedRaidPost.account_id == account_id,
                        CachedRaidPost.created_at < cutoff,
                    )
                )

            if rate_guard:
                rate_guard.record_tg_scan()

            return {
                "success": True,
                "status": "ok",
                "scannedChannels": len(cleaned_channels),
                "foundPosts": found_count,
                "message": f"Проверено {len(cleaned_channels)} каналов, найдено постов с рейдами: {found_count}",
            }

        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
