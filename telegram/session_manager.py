import os
import logging
from pathlib import Path
from typing import Optional, Callable
from telethon import TelegramClient
from core.config import settings

logger = logging.getLogger(__name__)


class TelegramSessionNotAuthorizedError(Exception):
    """Выбрасывается, когда сессия Telethon не авторизована."""
    pass


def get_telegram_client(session_path: Optional[str] = None) -> TelegramClient:
    """Создает и настраивает экземпляр TelegramClient."""
    path = session_path or settings.TG_SESSION_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(
        path,
        api_id=settings.TG_API_ID,
        api_hash=settings.TG_API_HASH,
        device_model="Desktop",
        system_version="Windows 11",
        app_version="5.0.1",
        lang_code=settings.CLIENT_LANGUAGE,
        system_lang_code=settings.CLIENT_LANGUAGE,
    )
    return client


async def interactive_login(
    session_path: Optional[str] = None,
    phone: Optional[str] = None,
    code_callback: Optional[Callable[[], str]] = None,
    password_callback: Optional[Callable[[], str]] = None,
) -> None:
    """Интерактивная авторизация в Telegram для создания .session файла."""
    client = get_telegram_client(session_path)
    await client.connect()

    try:
        target_phone = phone or settings.TG_PHONE
        if not target_phone:
            target_phone = input("Введите номер телефона (с кодом страны, например +79991234567): ").strip()

        if not await client.is_user_authorized():
            logger.info(f"Запрос кода авторизации для {target_phone}...")
            await client.send_code_request(target_phone)

            if code_callback:
                code = code_callback()
            else:
                code = input("Введите полученный код подтверждения: ").strip()

            try:
                await client.sign_in(target_phone, code)
            except Exception as e:
                # Если включена 2FA (облачный пароль)
                if "Two-steps verification" in str(e) or "SessionPasswordNeededError" in type(e).__name__:
                    if password_callback:
                        pwd = password_callback()
                    else:
                        pwd = input("Введите 2FA облачный пароль: ").strip()
                    await client.sign_in(password=pwd)
                else:
                    raise e

        me = await client.get_me()
        logger.info(f"Успешная авторизация в Telegram! Пользователь: {me.first_name} (@{me.username}) [ID: {me.id}]")
    finally:
        await client.disconnect()
