from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from core.config import settings


class AdminOnlyFilter(BaseFilter):
    """
    Фильтр белого списка: пропускает только апдейты от пользователя с ID == settings.ADMIN_TG_ID.
    Любые действия от посторонних пользователей строго блокируются.
    """

    async def __call__(self, event: TelegramObject) -> bool:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return False
        return bool(settings.ADMIN_TG_ID > 0 and from_user.id == settings.ADMIN_TG_ID)
