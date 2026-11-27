import asyncio
import email.utils
import logging
import time
from typing import Optional, Dict, Any
import httpx
from core.config import settings
from core.server_health import ServerHealthMonitor, GameMaintenanceError, classify_server_failure, server_health_monitor
from client.auth_provider import AuthProvider

logger = logging.getLogger(__name__)

_game_server_offset_sec: float = 0.0
_has_game_server_clock: bool = False


def update_game_server_clock(date_header: Optional[str], local_now_ts: Optional[float] = None) -> Optional[float]:
    """Вычисляет и сглаженно обновляет смещение часов игрового сервера по HTTP-заголовку Date."""
    global _game_server_offset_sec, _has_game_server_clock
    if not date_header or not isinstance(date_header, str):
        return None
    try:
        dt = email.utils.parsedate_to_datetime(date_header.strip())
        if dt is None:
            return None
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        server_ts = dt.timestamp()
    except Exception:
        return None

    ref_local = float(local_now_ts) if local_now_ts is not None else time.time()
    delta = server_ts - ref_local
    if abs(delta) >= 86400.0:
        return None

    if not _has_game_server_clock or abs(delta - _game_server_offset_sec) > 2.0:
        _game_server_offset_sec = delta
        _has_game_server_clock = True
    else:
        _game_server_offset_sec = _game_server_offset_sec * 0.7 + delta * 0.3
    return _game_server_offset_sec


def get_game_server_offset_sec() -> float:
    return _game_server_offset_sec


def get_game_now_ts() -> float:
    """Возвращает текущее UTC epoch время в секундах с учетом смещения игрового сервера."""
    return time.time() + _game_server_offset_sec


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
        health_monitor: Optional[ServerHealthMonitor] = None,
    ):
        self.auth_provider = auth_provider
        self.base_url = base_url or settings.API_BASE_URL
        self._custom_client = custom_client
        self._client: Optional[httpx.AsyncClient] = custom_client
        self.health_monitor: Optional[ServerHealthMonitor] = (
            health_monitor if health_monitor is not None else server_health_monitor
        )

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
        bypass_maintenance_gate: bool = False,
        **kwargs,
    ) -> httpx.Response:
        """
        Выполняет HTTP-запрос с автоматической авторизацией, ретраями и авто-обновлением токена.
        При активном режиме техработ мгновенно бросает GameMaintenanceError без выхода в сеть.
        """
        if (
            self.health_monitor is not None
            and self.health_monitor.is_maintenance
            and not bypass_maintenance_gate
        ):
            raise GameMaintenanceError("Игровые сервера на технических работах")

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
                update_game_server_clock(response.headers.get("Date"))

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

                # Проверка ответа на технические работы / 5xx / HTML-заглушку
                if self.health_monitor is not None:
                    ctype = response.headers.get("content-type", "")
                    body_snippet = ""
                    if response.status_code >= 500 or "html" in ctype.lower() or "maintenance" in ctype.lower():
                        body_snippet = response.text[:1200]
                    is_outage, _, _ = classify_server_failure(
                        status_code=response.status_code,
                        content_type=ctype,
                        body_text=body_snippet,
                    )
                    if is_outage:
                        in_maint = await self.health_monitor.record_failure(
                            status_code=response.status_code,
                            content_type=ctype,
                            body_text=body_snippet,
                        )
                        if in_maint and not bypass_maintenance_gate:
                            raise GameMaintenanceError(self.health_monitor.to_dict().get("reason") or "Технические работы")
                    elif response.status_code < 500:
                        await self.health_monitor.record_success()

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

            except GameMaintenanceError:
                raise
            except httpx.TransportError as e:
                if self.health_monitor is not None:
                    in_maint = await self.health_monitor.record_failure(exc=e)
                    if in_maint and not bypass_maintenance_gate:
                        raise GameMaintenanceError(self.health_monitor.to_dict().get("reason") or str(e)) from e
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
