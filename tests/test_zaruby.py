import pytest
from types import SimpleNamespace
from client.api.zaruby import ZARUBA_TIERS, classify_zarub_task, parse_zaruby_state


def test_classify_zarub_task_respects_safety_and_energy_conflicts():
    assert classify_zarub_task({"type": 6, "title": "Нанести урон"}, SimpleNamespace())[0] == "skip_damage"
    assert classify_zarub_task({"type": 4, "title": "Сделать ходки"}, SimpleNamespace(auto_prison=True))[0] == "skip_energy_conflict"
    assert classify_zarub_task({"type": 13, "title": "Потратить рубли"}, SimpleNamespace())[0] == "skip_paid"
    assert classify_zarub_task({"type": 9, "title": "Напряги терпилу"}, SimpleNamespace())[0] == "safe_auto"


def test_parse_zaruby_state_extracts_tasks_and_leaderboard():
    assert ZARUBA_TIERS["pacan"]["mode"] == 1
    assert ZARUBA_TIERS["vor"]["mode"] == 4
    raw = {
        "active": {
            "mode": 2,
            "startUnix": 1000,
            "endUnix": 2000,
            "completedCount": 1,
            "tasks": [{"taskId": 1, "type": 9, "title": "Терпила", "currentAmount": 1, "requiredAmount": 1, "status": 1}],
            "participants": [{"userId": 1, "nickname": "A", "authority": 100}, {"userId": 2, "nickname": "B", "authority": 90}],
        },
        "progress": {"level": 4, "xp": 20, "need": 80},
        "balances": {"ore_signet": 10, "signet": 12},
    }
    parsed = parse_zaruby_state(raw, config=SimpleNamespace())
    assert parsed["completed_count"] == 1
    assert parsed["total_count"] == 1
    assert parsed["tasks"][0]["classification"] == "safe_auto"
    assert len(parsed["leaderboard"]) == 2


def test_parse_zaruby_state_normalizes_ms_end_unix():
    raw = {
        "active": {
            "mode": 1,
            "startUnix": 1700000000000,
            "endUnix": 1700003600000,
            "tasks": [],
            "participants": [],
        }
    }
    parsed = parse_zaruby_state(raw, config=SimpleNamespace())
    assert parsed["end_unix"] == 1700003600


@pytest.mark.asyncio
async def test_zaruby_worker_run_cycle_publishes_state_and_records_health(monkeypatch):
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock
    from workers.zaruby_worker import ZarubyWorker
    from core.database import get_engine, init_db, get_session
    from core.models import Account, BotConfig

    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79990001122", nickname="ZarubTester")
        session.add(acc)
        await session.flush()
        session.add(BotConfig(account_id=acc.id, auto_zaruby_enabled=True))
        acc_id = acc.id

    past_unix = int(datetime.now(timezone.utc).timestamp()) - 120
    zaruby_api = MagicMock()
    zaruby_api.get_state = AsyncMock(
        return_value={
            "active": {
                "mode": 1,
                "startUnix": past_unix - 3600,
                "endUnix": past_unix,
                "tasks": [],
                "participants": [],
            }
        }
    )

    hub_calls = []
    health_calls = []
    wakeup_calls = []
    monkeypatch.setattr("core.state_hub.state_hub.set_domain_data", lambda aid, dom, data: hub_calls.append((aid, dom, data)))
    monkeypatch.setattr("workers.zaruby_worker.server_health_monitor.record_success", lambda: health_calls.append(True))

    worker = ZarubyWorker(
        account_id=acc_id,
        zaruby_api=zaruby_api,
        db_engine=engine,
        on_wakeup_schedule=lambda aid, dt: wakeup_calls.append((aid, dt)),
    )
    res = await worker.run_cycle()
    assert res["status"] == "ok"
    assert len(health_calls) == 1
    assert len(hub_calls) == 1 and hub_calls[0][1] == "zaruby"
    assert wakeup_calls == []  # past endUnix must not be scheduled

    await engine.dispose()

