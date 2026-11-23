import hmac
import hashlib
import json
import urllib.parse
from typing import Optional
from fastapi import Header, HTTPException, status
from core.config import settings


def validate_telegram_init_data(init_data: str, bot_token: str, admin_id: int) -> bool:
    """
    Валидация подписи initData из Telegram Mini App по официальному алгоритму HMAC-SHA256:
    1. Извлекается hash.
    2. Все остальные параметры сортируются по алфавиту и соединяются через \n.
    3. Вычисляется secret_key = HMAC_SHA256(b"WebAppData", bot_token).
    4. Вычисляется HMAC_SHA256(secret_key, data_check_string) и сравнивается с hash.
    5. Проверяется соответствие user.id == admin_id.
    """
    if not init_data or not bot_token:
        return False

    try:
        parsed = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        params = dict(parsed)
        received_hash = params.pop("hash", None)
        if not received_hash:
            return False

        # Формирование строки проверки
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

        # Вычисление секретного ключа и хеша
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return False

        # Проверка ID пользователя
        user_raw = params.get("user")
        if user_raw:
            user_data = json.loads(user_raw)
            user_id = user_data.get("id")
            if admin_id > 0 and user_id != admin_id:
                return False

        return True
    except Exception:
        return False


async def verify_admin(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> bool:
    """
    FastAPI зависимость авторизации:
    - Проверяет заголовок X-Admin-Token (для прямого открытия в браузере или DevTools)
    - ИЛИ проверяет заголовок X-Telegram-Init-Data (для Telegram Mini App)
    """
    # 1. Проверка токена браузера (если совпадает с WEB_ADMIN_TOKEN)
    if x_admin_token and settings.WEB_ADMIN_TOKEN and x_admin_token == settings.WEB_ADMIN_TOKEN:
        return True

    # 2. Проверка Telegram WebApp initData
    if x_telegram_init_data:
        if validate_telegram_init_data(x_telegram_init_data, settings.TG_BOT_TOKEN, settings.ADMIN_TG_ID):
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid Telegram WebApp signature or unauthorized user",
        )

    if x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid admin token",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Authentication required (X-Telegram-Init-Data or X-Admin-Token)",
    )
