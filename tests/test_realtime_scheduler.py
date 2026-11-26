import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.scheduler import SchedulerController
from core.server_health import ServerHealthMonitor
from workers.poker_worker import PokerWorker
from workers.fartovy_worker import FartovyWorker
from workers.zaruby_worker import ZarubyWorker


@pytest.mark.asyncio
async def test_scheduler_schedule_wakeup_triggers_worker_once():
    controller = SchedulerController(
        scheduler=MagicMock(),
        routine_worker=MagicMock(account_id=1),
    )
    called = asyncio.Event()

    async def fake_run_cycle():
        called.set()

    controller.poker_worker = MagicMock(run_cycle=fake_run_cycle)
    run_at = datetime.now(timezone.utc) + timedelta(milliseconds=50)
    controller.schedule_wakeup("poker", run_at)
    await asyncio.wait_for(called.wait(), timeout=3.5)
    status = controller.worker_status
    assert "poker" in status
    assert status["poker"]["last_result"] == "ok"


@pytest.mark.asyncio
async def test_poker_worker_respects_maintenance_and_lock(monkeypatch):
    monkeypatch.setattr(ServerHealthMonitor, "is_maintenance", property(lambda self: True))
    poker_api = AsyncMock()
    worker = PokerWorker(account_id=1, poker_api=poker_api, player_api=AsyncMock(), notifier=AsyncMock(), enable_jitter=False)
    await worker.run_cycle()
    poker_api.get_state.assert_not_called()


@pytest.mark.asyncio
async def test_fartovy_worker_schedules_wakeup_from_next_green_match_at(monkeypatch):
    monkeypatch.setattr(ServerHealthMonitor, "is_maintenance", property(lambda self: False))
    fartovy_api = AsyncMock()
    fartovy_api.get_state.return_value = {
        "success": True,
        "data": {
            "state": {
                "slotsGrass": 0,
                "energyRegenCap": 15,
                "energyTsUtc": datetime.now(timezone.utc).isoformat(),
                "freeSpins": 0,
            }
        },
    }
    player_api = AsyncMock()
    player_api.init_player.return_value = {"success": True, "currencies": {"rubles": 100}}
    scheduled = []

    worker = FartovyWorker(
        account_id=1,
        fartovy_api=fartovy_api,
        player_api=player_api,
        notifier=AsyncMock(),
        on_wakeup_schedule=lambda name, dt: scheduled.append((name, dt)),
        enable_jitter=False,
    )
    import workers.fartovy_worker as fw_mod
    monkeypatch.setattr(fw_mod, "is_worker_active", AsyncMock(return_value=(True, MagicMock(auto_fartovy_enabled=True, sleep_mode_enabled=False))))
    monkeypatch.setattr(fw_mod, "get_game_guard_state", AsyncMock(return_value={"guard_tripped": False}))
    await worker.run_cycle()

    assert len(scheduled) == 1
    assert scheduled[0][0] == "fartovy"


@pytest.mark.asyncio
async def test_zaruby_worker_respects_maintenance(monkeypatch):
    monkeypatch.setattr(ServerHealthMonitor, "is_maintenance", property(lambda self: True))
    zaruby_api = AsyncMock()
    worker = ZarubyWorker(account_id=1, zaruby_api=zaruby_api, player_api=AsyncMock(), notifier=AsyncMock())
    await worker.run_cycle()
    zaruby_api.get_state.assert_not_called()
