import re
import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote
from telethon import functions
from core.config import settings
from telegram.session_manager import get_telegram_client, TelegramSessionNotAuthorizedError

logger = logging.getLogger(__name__)


class WebViewExtractor:
    """Извлечение и парсинг initData из Telegram Mini App через MTProto."""

    @staticmethod
    def parse_tg_web_app_data_from_url(url: str) -> str:
        """
        Извлекает и декодирует строку tgWebAppData из URL (фрагмента или query).
        Корректно обрабатывает как URL-encoded формат, так и составные параметры Telegram.
        """
        if not url:
            raise ValueError("URL cannot be empty")

        # tgWebAppData может находиться как в фрагменте (#), так и в query (?)
        target_part = ""
        if "#" in url:
            target_part = url.split("#", 1)[1]
        elif "?" in url:
            target_part = url.split("?", 1)[1]
        else:
            target_part = url

        # Ищем параметр tgWebAppData
        match = re.search(r"tgWebAppData=([^#?]+)", target_part)
        if not match:
            raise ValueError(f"tgWebAppData not found in URL: {url}")

        raw_val = match.group(1)
        # Отсекаем последующие параметры Telegram Mini App (например &tgWebAppVersion=8.0)
        sub_match = re.search(r"^(.*?)(?:&tgWebApp[a-zA-Z0-9_]*=|$)", raw_val)
        if sub_match:
            raw_val = sub_match.group(1)

        decoded = unquote(raw_val)
        return decoded

    async def fetch_fresh_init_data(self, session_path: Optional[str] = None) -> str:
        """
        Подключается к Telegram через Telethon в режиме on-demand,
        запрашивает свежий initData через RequestWebViewRequest и немедленно закрывает соединение.
        """
        client = get_telegram_client(session_path)
        logger.info("Подключение к Telegram MTProto для запроса свежего initData...")
        await client.connect()

        try:
            if not await client.is_user_authorized():
                raise TelegramSessionNotAuthorizedError(
                    "Сессия Telegram не авторизована! Запустите 'python main.py --init-session' для первичного входа."
                )

            logger.info(f"Запрос RequestWebViewRequest для бота @{settings.BOT_USERNAME}...")
            result = await client(
                functions.messages.RequestWebViewRequest(
                    peer=settings.BOT_USERNAME,
                    bot=settings.BOT_USERNAME,
                    platform=settings.CLIENT_PLATFORM,
                    from_bot_menu=False,
                    url=settings.WEBAPP_URL,
                )
            )

            if not hasattr(result, "url") or not result.url:
                raise ValueError("Telegram сервер не вернул URL веб-приложения в RequestWebViewRequest.")

            init_data = self.parse_tg_web_app_data_from_url(result.url)
            logger.info("Свежий initData успешно получен.")
            return init_data
        finally:
            await client.disconnect()
            logger.info("MTProto-соединение Telethon безопасно закрыто.")
