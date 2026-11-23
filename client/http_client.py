import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from core.config import settings
from client.auth_provider import AuthProvider

logger = logging.getLogger(__name__)


class GameHttpClient:
    """
    Асинхронный HTTP-клиент для взаимодействия с API Old Prison.
    - Автоматическая подстановка актуального JWT Bearer токена.
    - Обработка 401 Unauthorized с вызовом refresh/relogin и повтором запроса.
    - Экспоненциальный retry при сетевых сбоях (TransportError) и 5xx ошибках.
    """

    def __init__(
        self,
        auth_provider: AuthProvider,
        base_url: Optional[str] = None,
        custom_client: Optional[httpx.AsyncClient] = None,
    ):
        self.auth_provider = auth_provider
        self.base_url = base_url or settings.API_BASE_URL
        self._custom_client = custom_client
        self._client: Optional[httpx.AsyncClient] = custom_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=settings.default_headers,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=60.0,
                ),
                timeout=httpx.Timeout(10.0, connect=3.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed and self._client != self._custom_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        **kwargs,
    ) -> httpx.Response:
        """
        Выполняет HTTP-запрос с автоматической авторизацией, ретраями и авто-обновлением токена.
        """
        client = await self._get_client()

        # 1. Получаем действующий access_token
        token = await self.auth_provider.get_valid_token()
        req_headers = dict(headers or {})
        req_headers["Authorization"] = f"Bearer {token}"

        # Объединяем с базовыми заголовками
        for k, v in settings.default_headers.items():
            if k not in req_headers:
                req_headers[k] = v

        attempt = 0
        backoff = 1.0

        while True:
            try:
                attempt += 1
                response = await client.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    **kwargs,
                )

                # Обработка 401 Unauthorized (истек токен во время запроса)
                if response.status_code == 401:
                    logger.warning(f"Получен 401 Unauthorized для {url}. Принудительное обновление токена...")
                    new_token = await self.auth_provider.refresh_or_relogin(force=True)
                    req_headers["Authorization"] = f"Bearer {new_token}"
                    # Повторяем запрос с новым токеном
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=req_headers,
                        **kwargs,
                    )
                    if 400 <= response.status_code < 500 and response.status_code != 401:
                        logger.warning(f"API {response.status_code} на {url}: {response.text}")
                    return response

                # Логирование 4xx ошибок клиента
                if 400 <= response.status_code < 500:
                    logger.warning(f"API {response.status_code} на {url}: {response.text}")

                # Ретраи при серверных ошибках 5xx
                if response.status_code >= 500 and attempt <= max_retries:
                    logger.warning(
                        f"Сервер вернул HTTP {response.status_code} для {url}. "
                        f"Попытка {attempt}/{max_retries} через {backoff}с..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue

                return response

            except httpx.TransportError as e:
                if attempt <= max_retries:
                    logger.warning(
                        f"Сетевой сбой при обращении к {url} ({e}). "
                        f"Попытка {attempt}/{max_retries} через {backoff}с..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.error(f"Превышено максимальное число попыток ({max_retries}) для {url}.")
                    raise

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)
