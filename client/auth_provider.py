import time
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from sqlalchemy import select
from core.config import settings
from core.database import get_session
from core.models import Account, SessionData
from telegram.webview import WebViewExtractor

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Общая ошибка аутентификации."""
    pass


class AuthProvider:
    """
    Двухуровневый провайдер авторизации:
    1. Кэшированный accessToken (с проверкой времени жизни).
    2. Обновление через refreshToken (POST /api/auth/refresh).
    3. Fallback: on-demand получение initData через Telethon и вход (POST /api/auth/login).
    """

    def __init__(
        self,
        account_id: int,
        http_client: Optional[httpx.AsyncClient] = None,
        webview_extractor: Optional[WebViewExtractor] = None,
        db_engine: Optional[Any] = None,
    ):
        self.account_id = account_id
        self._custom_http = http_client
        self.webview_extractor = webview_extractor or WebViewExtractor()
        self.db_engine = db_engine
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._custom_http:
            return self._custom_http
        return httpx.AsyncClient(
            base_url=settings.API_BASE_URL,
            headers=settings.default_headers,
            timeout=30.0,
        )

    async def get_valid_token(self) -> str:
        """Возвращает действующий access_token, обновляя его при необходимости."""
        async with self._lock:
            # 1. Читаем текущее состояние сессии из БД
            async with get_session(self.db_engine) as session:
                stmt = select(SessionData).where(SessionData.account_id == self.account_id)
                res = await session.execute(stmt)
                sess = res.scalar_one_or_none()

                now = time.time()
                # Если токен есть и до истечения более 300 секунд (5 минут)
                if sess and sess.access_token and (sess.access_exp - now) > 300:
                    return sess.access_token

            # 2. Если токен истек или отсутствует, вызываем обновление
            return await self._refresh_or_relogin_locked(force=False)

    async def refresh_or_relogin(self, force: bool = False) -> str:
        """Публичный метод принудительного обновления или релогина под блокировкой."""
        async with self._lock:
            return await self._refresh_or_relogin_locked(force=force)

    async def _refresh_or_relogin_locked(self, force: bool = False) -> str:
        """Внутренний метод обновления/входа, вызываемый строго под self._lock."""
        client = await self._get_client()
        should_close_client = (client != self._custom_http)

        try:
            # Читаем данные сессии
            refresh_token: Optional[str] = None
            init_data: Optional[str] = None
            access_token: Optional[str] = None
            access_exp: int = 0

            async with get_session(self.db_engine) as session:
                stmt = select(SessionData).where(SessionData.account_id == self.account_id)
                res = await session.execute(stmt)
                sess = res.scalar_one_or_none()
                if sess:
                    refresh_token = sess.refresh_token
                    init_data = sess.init_data
                    access_token = sess.access_token
                    access_exp = sess.access_exp

            now = time.time()
            # Проверяем, не обновил ли токен другой поток, пока мы ждали lock
            if not force and access_token and (access_exp - now) > 300:
                return access_token

            # Шаг 1: Пробуем продлить через refresh_token
            if refresh_token:
                logger.info(f"Попытка обновления токена через refresh для аккаунта {self.account_id}...")
                try:
                    resp = await client.post(
                        "/api/auth/refresh",
                        json={"refresh": refresh_token},
                        headers=settings.default_headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        new_access = data.get("accessToken") or data.get("access")
                        new_refresh = data.get("refreshToken") or data.get("refresh") or refresh_token
                        new_exp = int(data.get("accessExp", now + 86400))

                        if new_access:
                            await self._save_session(
                                access_token=new_access,
                                refresh_token=new_refresh,
                                access_exp=new_exp,
                            )
                            logger.info(f"Токен успешно обновлен через refresh для аккаунта {self.account_id}.")
                            return new_access
                    else:
                        logger.warning(
                            f"Обновление через refresh отклонено сервером (HTTP {resp.status_code}): {resp.text}"
                        )
                except Exception as e:
                    logger.warning(f"Ошибка сетевого запроса refresh: {e}")

            # Шаг 2: Fallback — вход через initData
            logger.info(f"Запуск резервного входа (fallback login) для аккаунта {self.account_id}...")
            fresh_init_data = await self.webview_extractor.fetch_fresh_init_data()

            resp = await client.post(
                "/api/auth/login",
                json={"initData": fresh_init_data},
                headers=settings.default_headers,
            )
            if resp.status_code != 200:
                raise AuthError(f"Ошибка входа /api/auth/login (HTTP {resp.status_code}): {resp.text}")

            data = resp.json()
            new_access = data.get("accessToken") or data.get("access")
            new_refresh = data.get("refreshToken") or data.get("refresh")
            new_exp = int(data.get("accessExp", now + 86400))
            user_id = data.get("userId")
            nickname = data.get("nickname")

            if not new_access:
                raise AuthError(f"Сервер не вернул accessToken при логине: {data}")

            await self._save_session(
                access_token=new_access,
                refresh_token=new_refresh,
                access_exp=new_exp,
                init_data=fresh_init_data,
                game_user_id=user_id,
                nickname=nickname,
            )
            logger.info(f"Успешный вход через initData для аккаунта {self.account_id} (userId: {user_id}).")
            return new_access

        finally:
            if should_close_client:
                await client.aclose()

    async def _save_session(
        self,
        access_token: str,
        refresh_token: Optional[str],
        access_exp: int,
        init_data: Optional[str] = None,
        game_user_id: Optional[int] = None,
        nickname: Optional[str] = None,
    ) -> None:
        """Сохраняет обновленные данные сессии и аккаунта в SQLite."""
        async with get_session(self.db_engine) as session:
            # 1. Обновляем сессию
            stmt = select(SessionData).where(SessionData.account_id == self.account_id)
            res = await session.execute(stmt)
            sess = res.scalar_one_or_none()
            if not sess:
                sess = SessionData(account_id=self.account_id)
                session.add(sess)

            sess.access_token = access_token
            if refresh_token:
                sess.refresh_token = refresh_token
            sess.access_exp = access_exp
            if init_data:
                sess.init_data = init_data

            # 2. Обновляем аккаунт при наличии данных
            if game_user_id or nickname:
                acc_stmt = select(Account).where(Account.id == self.account_id)
                acc_res = await session.execute(acc_stmt)
                acc = acc_res.scalar_one_or_none()
                if acc:
                    if game_user_id:
                        acc.game_user_id = game_user_id
                    if nickname:
                        acc.nickname = nickname
