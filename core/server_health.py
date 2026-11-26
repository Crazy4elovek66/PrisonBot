"""
Централизованный детектор технических работ игры (ServerHealthMonitor),
классификатор сетевых/серверных сбоев и активный дежурный Watchdog.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class GameMaintenanceError(RuntimeError):
    """Исключение, выбрасываемое HTTP-клиентом при активном режиме техработ без выхода в сеть."""


_MAINTENANCE_HTML_MARKERS = (
    "<!doctype html",
    "<html",
    "error: server error",
    "service unavailable",
    "bad gateway",
    "gateway time-out",
    "gateway timeout",
    "under maintenance",
    "технические работы",
    "техработы",
)

_OUTAGE_STATUS_CODES = {500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526}
_IGNORED_BUSINESS_CODES = {400, 401, 403, 404, 409, 422, 429}


def classify_server_failure(
    exc: Optional[BaseException] = None,
    status_code: Optional[int] = None,
    content_type: Optional[str] = None,
    body_text: Optional[str] = None,
) -> Tuple[bool, bool, str]:
    """
    Классифицирует сбой игрового API:
    Возвращает (is_server_outage, is_immediate_maintenance, reason).
    """
    if isinstance(exc, asyncio.CancelledError):
        return False, False, ""

    if status_code is not None and status_code in _IGNORED_BUSINESS_CODES:
        return False, False, ""

    ctype = (content_type or "").lower()
    body = (body_text or "")
    body_low = body.lower()

    # Явный 503 Service Unavailable -> мгновенный вход в MAINTENANCE
    if status_code == 503:
        return True, True, "HTTP 503 Service Unavailable"

    # Проверка JSON на явные флаги техработ
    if body and ("application/json" in ctype or body.lstrip().startswith("{")):
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                if (
                    parsed.get("maintenance") is True
                    or parsed.get("isMaintenance") is True
                    or str(parsed.get("status", "")).lower() == "maintenance"
                ):
                    msg = str(parsed.get("message") or "Технические работы в игре")
                    return True, True, msg
                msg_low = str(parsed.get("message") or "").lower()
                if "технические работы" in msg_low or "maintenance" in msg_low:
                    return True, True, str(parsed.get("message"))
        except Exception:
            pass

    # Проверка HTML-заглушки / текстовых маркеров техработ при 5xx или даже 200 HTML
    has_html_or_marker = (
        "text/html" in ctype
        or any(marker in body_low for marker in _MAINTENANCE_HTML_MARKERS)
    )
    if status_code is not None and status_code in _OUTAGE_STATUS_CODES:
        if has_html_or_marker:
            return True, True, f"HTTP {status_code} / Server Error (HTML)"
        return True, False, f"HTTP {status_code}"

    if status_code == 200 and has_html_or_marker:
        return True, True, "HTML-заглушка вместо JSON"

    # Сетевые сбои и таймауты httpx
    if exc is not None:
        if isinstance(
            exc,
            (
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
                TimeoutError,
            ),
        ):
            return True, False, "Таймаут соединения с игровым сервером"
        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.RemoteProtocolError,
                httpx.NetworkError,
                httpx.TransportError,
                OSError,
            ),
        ):
            return True, False, f"Сетевой сбой ({type(exc).__name__})"

    return False, False, ""


def format_outage_duration(seconds: Optional[int]) -> str:
    """Форматирует длительность техработ в ЧЧ:ММ:СС для Telegram-уведомлений."""
    total = max(0, int(seconds or 0))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class HealthSnapshot:
    status: str = "online"  # "online" | "maintenance"
    is_maintenance: bool = False
    started_at: Optional[datetime] = None
    last_check_at: Optional[datetime] = None
    next_check_in_sec: int = 0
    check_attempts: int = 0
    consecutive_failures: int = 0
    last_error: str = ""
    last_recovered_at: Optional[datetime] = None
    last_outage_duration_sec: Optional[int] = None


class ServerHealthMonitor:
    """
    Единый монитор доступности серверов игры с гистерезисом,
    частым дежурным Watchdog (10-15с) и однократными уведомлениями.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        failure_window_sec: float = 30.0,
        fast_interval_sec: float = 10.0,
        slow_interval_sec: float = 15.0,
        slow_after_sec: float = 600.0,
        jitter_sec: float = 1.0,
        confirm_delay_sec: float = 1.5,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.failure_window_sec = float(failure_window_sec)
        self.fast_interval_sec = float(fast_interval_sec)
        self.slow_interval_sec = float(slow_interval_sec)
        self.slow_after_sec = float(slow_after_sec)
        self.jitter_sec = float(jitter_sec)
        self.confirm_delay_sec = float(confirm_delay_sec)

        self._lock = asyncio.Lock()
        self._state = HealthSnapshot()
        self._failure_timestamps: List[float] = []
        self._watchdog_task: Optional[asyncio.Task] = None
        self._wake_event = asyncio.Event()
        self._last_probe_mono: float = 0.0
        self._last_skip_log_mono: float = 0.0

        self.probe_fn: Optional[Callable[[], Awaitable[Tuple[bool, Optional[int], str]]]] = None
        self.refresh_token_fn: Optional[Callable[[], Awaitable[Any]]] = None
        self.on_maintenance_start: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None
        self.on_maintenance_end: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None

    @property
    def is_maintenance(self) -> bool:
        return self._state.is_maintenance

    @property
    def status(self) -> str:
        return self._state.status

    def should_log_worker_skip(self, min_interval_sec: float = 300.0) -> bool:
        now_m = time.monotonic()
        if now_m - self._last_skip_log_mono >= min_interval_sec:
            self._last_skip_log_mono = now_m
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        s = self._state
        now_utc = datetime.now(timezone.utc)
        duration_sec = 0
        if s.is_maintenance and s.started_at is not None:
            duration_sec = max(0, int((now_utc - s.started_at).total_seconds()))
        return {
            "status": s.status,
            "active": s.is_maintenance,
            "is_maintenance": s.is_maintenance,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "duration_sec": duration_sec,
            "last_check_at": s.last_check_at.isoformat() if s.last_check_at else None,
            "next_check_in_sec": int(s.next_check_in_sec) if s.is_maintenance else 0,
            "check_attempts": int(s.check_attempts),
            "consecutive_failures": int(s.consecutive_failures),
            "reason": s.last_error or "",
            "last_recovered_at": s.last_recovered_at.isoformat() if s.last_recovered_at else None,
            "last_outage_duration_sec": s.last_outage_duration_sec,
        }

    async def _enter_maintenance_locked(self, reason: str) -> bool:
        """Переводит монитор в MAINTENANCE под lock. Возвращает True только при первом входе."""
        if self._state.is_maintenance:
            if reason:
                self._state.last_error = reason
            return False

        now_utc = datetime.now(timezone.utc)
        self._state.status = "maintenance"
        self._state.is_maintenance = True
        self._state.started_at = now_utc
        self._state.last_check_at = now_utc
        self._state.check_attempts = 0
        self._state.next_check_in_sec = int(self.fast_interval_sec)
        if reason:
            self._state.last_error = reason
        logger.warning("ServerHealthMonitor: переход ONLINE -> MAINTENANCE (причина: %s)", self._state.last_error)
        self._ensure_watchdog_running()
        return True

    async def _exit_maintenance_locked(self) -> Tuple[bool, Dict[str, Any]]:
        """Переводит монитор в ONLINE под lock. Возвращает (changed, snapshot_dict)."""
        if not self._state.is_maintenance:
            self._state.consecutive_failures = 0
            self._failure_timestamps.clear()
            return False, self.to_dict()

        now_utc = datetime.now(timezone.utc)
        dur_sec = 0
        if self._state.started_at is not None:
            dur_sec = max(0, int((now_utc - self._state.started_at).total_seconds()))

        self._state.status = "online"
        self._state.is_maintenance = False
        self._state.consecutive_failures = 0
        self._failure_timestamps.clear()
        self._state.last_recovered_at = now_utc
        self._state.last_outage_duration_sec = dur_sec
        self._state.next_check_in_sec = 0
        snap = self.to_dict()
        logger.info("ServerHealthMonitor: переход MAINTENANCE -> ONLINE (длительность простоя: %ss)", dur_sec)
        return True, snap

    def _ensure_watchdog_running(self) -> None:
        if self.probe_fn is None:
            return
        if self._watchdog_task is not None and not self._watchdog_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._watchdog_task = loop.create_task(self._watchdog_loop())
        except RuntimeError:
            pass

    async def stop_watchdog(self) -> None:
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except (asyncio.CancelledError, Exception):
                pass
        self._watchdog_task = None

    async def record_failure(
        self,
        exc: Optional[BaseException] = None,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None,
        body_text: Optional[str] = None,
    ) -> bool:
        """
        Регистрирует сбой игрового API. Возвращает True, если монитор находится в MAINTENANCE.
        """
        is_outage, immediate, reason = classify_server_failure(
            exc=exc,
            status_code=status_code,
            content_type=content_type,
            body_text=body_text,
        )
        if not is_outage:
            return self._state.is_maintenance

        entered_now = False
        snap: Optional[Dict[str, Any]] = None
        async with self._lock:
            now_mono = time.monotonic()
            self._failure_timestamps = [
                ts for ts in self._failure_timestamps
                if (now_mono - ts) <= self.failure_window_sec
            ]
            self._failure_timestamps.append(now_mono)
            self._state.consecutive_failures += 1
            if reason:
                self._state.last_error = reason

            if immediate or len(self._failure_timestamps) >= self.failure_threshold:
                entered_now = await self._enter_maintenance_locked(reason)
                if entered_now:
                    snap = self.to_dict()

        if entered_now and snap is not None and self.on_maintenance_start is not None:
            try:
                await self.on_maintenance_start(snap)
            except Exception as cb_err:
                logger.warning("Ошибка callback on_maintenance_start: %s", cb_err)

        return self._state.is_maintenance

    async def record_success(self) -> bool:
        """Регистрирует успешный ответ игрового сервера. Возвращает True при выходе из MAINTENANCE."""
        exited_now = False
        snap: Dict[str, Any] = {}
        async with self._lock:
            self._state.last_check_at = datetime.now(timezone.utc)
            if self._state.is_maintenance:
                exited_now, snap = await self._exit_maintenance_locked()
            else:
                self._state.consecutive_failures = 0
                self._failure_timestamps.clear()

        if exited_now and self.on_maintenance_end is not None:
            try:
                await self.on_maintenance_end(snap)
            except Exception as cb_err:
                logger.warning("Ошибка callback on_maintenance_end: %s", cb_err)
        return exited_now

    async def _run_single_probe(self) -> Tuple[bool, str]:
        """Выполняет безопасную read-only пробу через probe_fn (с авто-refresh при 401)."""
        if self.probe_fn is None:
            return False, "probe_fn не настроен"

        try:
            ok, code, reason = await self.probe_fn()
            if code == 401 and self.refresh_token_fn is not None:
                logger.info("Watchdog: получен 401 при проверке сервера, обновляем токен...")
                await self.refresh_token_fn()
                ok, code, reason = await self.probe_fn()
            return bool(ok), str(reason or "")
        except Exception as exc:
            _, _, rsn = classify_server_failure(exc=exc)
            return False, rsn or str(exc)

    async def probe_now(self, bypass_debounce: bool = False) -> Dict[str, Any]:
        """
        Немедленная проверка доступности игрового сервера (по кнопке 'Проверить снова' или из Watchdog).
        """
        now_m = time.monotonic()
        if not bypass_debounce and (now_m - self._last_probe_mono) < 2.0 and self._state.is_maintenance:
            res = self.to_dict()
            res["recovered"] = False
            res["debounced"] = True
            return res

        self._last_probe_mono = now_m
        self._state.last_check_at = datetime.now(timezone.utc)
        self._state.check_attempts += 1

        ok, reason = await self._run_single_probe()
        recovered = False
        if ok:
            if self._state.is_maintenance and self.confirm_delay_sec > 0:
                await asyncio.sleep(self.confirm_delay_sec)
                ok2, reason2 = await self._run_single_probe()
                if not ok2:
                    if reason2:
                        self._state.last_error = reason2
                    res = self.to_dict()
                    res["recovered"] = False
                    return res
            recovered = await self.record_success()
            if not self._state.is_maintenance:
                recovered = True
        else:
            if reason:
                self._state.last_error = reason
            if not self._state.is_maintenance:
                # Если ручная проверка обнаружила сбой при ONLINE — прогоняем через классификатор
                pass

        res = self.to_dict()
        res["recovered"] = recovered
        return res

    async def _watchdog_loop(self) -> None:
        """Дежурный цикл частой проверки оживления сервера во время техработ."""
        try:
            while self._state.is_maintenance:
                elapsed = 0.0
                if self._state.started_at is not None:
                    elapsed = max(0.0, (datetime.now(timezone.utc) - self._state.started_at).total_seconds())
                base_interval = self.fast_interval_sec if elapsed < self.slow_after_sec else self.slow_interval_sec
                jitter = random.uniform(-self.jitter_sec, self.jitter_sec) if self.jitter_sec > 0 else 0.0
                wait_sec = max(1.0, base_interval + jitter)
                self._state.next_check_in_sec = int(round(wait_sec))

                self._wake_event.clear()
                try:
                    await asyncio.wait_for(self._wake_event.wait(), timeout=wait_sec)
                except asyncio.TimeoutError:
                    pass

                if not self._state.is_maintenance:
                    break

                probe_res = await self.probe_now(bypass_debounce=True)
                if probe_res.get("recovered") or not self._state.is_maintenance:
                    break
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("Watchdog loop error: %s", exc)


server_health_monitor = ServerHealthMonitor()
