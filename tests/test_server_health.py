import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from client.http_client import GameHttpClient
from core.server_health import (
    GameMaintenanceError,
    ServerHealthMonitor,
    classify_server_failure,
    server_health_monitor,
)


def test_classify_server_failure_rules():
    # Явные техработы (мгновенный вход)
    assert classify_server_failure(status_code=503) == (True, True, "HTTP 503 Service Unavailable")
    out, imm, _ = classify_server_failure(
        status_code=500,
        content_type="text/html; charset=utf-8",
        body_text="<html><title>502 Server Error</title>Error: Server Error</html>",
    )
    assert (out, imm) == (True, True)
    out_json, imm_json, _ = classify_server_failure(
        status_code=200,
        content_type="application/json",
        body_text='{"maintenance": true, "message": "Техработы"}',
    )
    assert (out_json, imm_json) == (True, True)

    # Одиночные сетевые ошибки -> требуют порога (is_immediate=False)
    assert classify_server_failure(exc=httpx.ConnectTimeout("timeout"))[0:2] == (True, False)
    assert classify_server_failure(status_code=502)[0:2] == (True, False)

    # Бизнес/auth ошибки -> не техработы
    for code in (400, 401, 403, 404, 409, 422, 429):
        assert classify_server_failure(status_code=code) == (False, False, "")
    assert classify_server_failure(exc=asyncio.CancelledError()) == (False, False, "")


@pytest.mark.asyncio
async def test_server_health_hysteresis_and_single_notification():
    mon = ServerHealthMonitor(failure_threshold=3, failure_window_sec=30.0)
    starts = []
    ends = []

    async def on_start(snap):
        starts.append(snap)

    async def on_end(snap):
        ends.append(snap)

    mon.on_maintenance_start = on_start
    mon.on_maintenance_end = on_end

    # 1-2 одиночных таймаута не включают MAINTENANCE и сбрасываются после успеха
    await mon.record_failure(exc=httpx.ReadTimeout("t1"))
    await mon.record_failure(exc=httpx.ReadTimeout("t2"))
    assert mon.is_maintenance is False
    await mon.record_success()
    assert mon.to_dict()["consecutive_failures"] == 0

    # 3 подряд сетевых сбоя -> вход в MAINTENANCE + ровно 1 уведомление
    await mon.record_failure(exc=httpx.ReadTimeout("t1"))
    await mon.record_failure(exc=httpx.ReadTimeout("t2"))
    await mon.record_failure(exc=httpx.ReadTimeout("t3"))
    assert mon.is_maintenance is True
    assert len(starts) == 1

    # Повторный сбой не спамит уведомлением
    await mon.record_failure(status_code=503)
    assert len(starts) == 1

    # Выход -> 1 уведомление восстановления
    await mon.record_success()
    assert mon.is_maintenance is False
    assert len(ends) == 1
    assert ends[0]["last_outage_duration_sec"] >= 0


@pytest.mark.asyncio
async def test_http_client_maintenance_gate_and_watchdog_recovery():
    mon = ServerHealthMonitor(
        failure_threshold=1,
        fast_interval_sec=0.05,
        slow_interval_sec=0.05,
        jitter_sec=0.0,
        confirm_delay_sec=0.0,
    )
    calls = []
    probe_state = {"ok": False, "need_refresh": False}
    refreshed = {"cnt": 0}
    ends = []

    async def mock_probe():
        if probe_state["need_refresh"]:
            probe_state["need_refresh"] = False
            return False, 401, "HTTP 401"
        if probe_state["ok"]:
            return True, 200, "ok"
        return False, 503, "HTTP 503"

    async def mock_refresh():
        refreshed["cnt"] += 1

    mon.probe_fn = mock_probe
    mon.refresh_token_fn = mock_refresh
    mon.on_maintenance_end = lambda snap: asyncio.sleep(0, result=ends.append(snap))

    def handler(req: httpx.Request):
        calls.append(req.url.path)
        if mon.is_maintenance and req.url.path == "/api/probe":
            return httpx.Response(200, json={"userId": 1})
        return httpx.Response(503, headers={"content-type": "text/html"}, text="<html>Server Error</html>")

    auth = SimpleNamespace(get_valid_token=AsyncMock(return_value="tok"), refresh_or_relogin=AsyncMock(return_value="tok2"))
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test")
    http = GameHttpClient(auth_provider=auth, custom_client=async_client, health_monitor=mon)

    # Первый запрос ловит 503 и переводит в MAINTENANCE
    with pytest.raises(GameMaintenanceError):
        await http.get("/api/boss/bootstrap", max_retries=0)
    assert mon.is_maintenance is True
    assert len(calls) == 1

    # Обычный запрос при MAINTENANCE мгновенно бросает GameMaintenanceError без выхода в сеть
    with pytest.raises(GameMaintenanceError):
        await http.get("/api/player/init")
    assert len(calls) == 1

    # Запрос с bypass_maintenance_gate=True проходит мимо gate
    resp = await http.get("/api/probe", bypass_maintenance_gate=True)
    assert resp.status_code == 200
    assert mon.is_maintenance is False  # record_success вывел из техработ

    # Проверка 401 -> refresh_token -> выход из техработ через probe_now
    await mon.record_failure(status_code=503)
    assert mon.is_maintenance is True
    probe_state["need_refresh"] = True
    probe_state["ok"] = True
    res = await mon.probe_now(bypass_debounce=True)
    assert refreshed["cnt"] == 1
    assert res["recovered"] is True
    assert mon.is_maintenance is False

    await mon.stop_watchdog()
    await async_client.aclose()


@pytest.mark.asyncio
async def test_workers_freeze_during_maintenance_without_losing_state(monkeypatch):
    from workers.boss_worker import BossWorker
    from workers.prison_worker import PrisonWorker
    from workers.routine_worker import RoutineWorker
    from workers.social_worker import SocialWorker
    import workers.boss_worker as bw_m
    import workers.prison_worker as pw_m
    import workers.routine_worker as rw_m
    import workers.social_worker as sw_m

    fake_mon = SimpleNamespace(is_maintenance=True, should_log_worker_skip=lambda: False)
    for m in (bw_m, pw_m, rw_m, sw_m):
        monkeypatch.setattr(m, "server_health_monitor", fake_mon)

    api_mock = SimpleNamespace(get_bootstrap=AsyncMock(), init_player=AsyncMock(), get_enriched_friend_requests=AsyncMock())
    bw = BossWorker(account_id=1, boss_api=api_mock, player_api=api_mock, db_engine=None, enable_jitter=False)
    pw = PrisonWorker(account_id=1, prison_api=api_mock, player_api=api_mock, db_engine=None, enable_jitter=False)
    rw = RoutineWorker(account_id=1, player_api=api_mock, db_engine=None, enable_jitter=False)
    sw = SocialWorker(account_id=1, social_api=api_mock, db_engine=None, enable_jitter=False)

    assert (await bw.run_cycle())["reason"] == "maintenance"
    assert (await pw.run_cycle())["reason"] == "maintenance"
    assert (await rw.run_cycle())["reason"] == "maintenance"
    assert (await sw.run_cycle())["reason"] == "maintenance"
    assert api_mock.get_bootstrap.await_count == 0
    assert api_mock.init_player.await_count == 0
    assert api_mock.get_enriched_friend_requests.await_count == 0
