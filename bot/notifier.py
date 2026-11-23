import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Сервис проактивных уведомлений владельца бота.
    Если bot is None или admin_id <= 0, работает в безопасном no-op режиме.
    Все ошибки отправки перехватываются, предотвращая сбои игровых воркеров.
    """

    def __init__(self, bot: Optional[Any] = None, admin_id: int = 0):
        self.bot = bot
        self.admin_id = admin_id

    async def notify(self, text: str) -> None:
        """Безопасная отправка сообщения владельцу в HTML-разметке."""
        if self.bot is None or self.admin_id <= 0:
            return

        try:
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Не удалось отправить уведомление в Telegram: %s", e)
