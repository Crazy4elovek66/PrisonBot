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



def test_parse_live_zaruby_payload_8_tasks_and_js_render():
    import json
    import subprocess
    from pathlib import Path
    from client.api.zaruby import parse_zaruby_state

    raw = {
        "active": {
            "mode": 1,
            "startUnix": 1795807066,
            "endUnix": 1795893466,
            "tasks": [
                {"taskId": "t1", "type": 4, "requiredAmount": 70, "currentAmount": 35, "status": 0, "title": "Набери 70 уважения зеков 'КРЕСТЫ'"},
                {"taskId": "t2", "type": 4, "requiredAmount": 90, "currentAmount": 60, "status": 0, "title": "Набери 90 уважения зеков 'БУТЫРКА'"},
                {"taskId": "t3", "type": 11, "requiredAmount": 30, "currentAmount": 0, "status": 0, "title": "Получи 30 очков знаний у мастеров"},
                {"taskId": "t4", "type": 6, "bossId": 12, "requiredAmount": 1000, "currentAmount": 0, "status": 0, "title": "Нанеси 1000 урона боссу: Бес"},
                {"taskId": "t5", "type": 6, "bossId": 5, "requiredAmount": 1100, "currentAmount": 0, "status": 0, "title": "Нанеси 1100 урона боссу: Шайба"},
                {"taskId": "t6", "type": 10, "requiredAmount": 1300, "currentAmount": 533, "status": 0, "title": "Заработай 1300 папирос"},
                {"taskId": "t7", "type": 3, "requiredAmount": 2, "currentAmount": 2, "status": 1, "title": "Используй подогрев 2 раза"},
                {"taskId": "t8", "type": 12, "requiredAmount": 1, "currentAmount": 0, "status": 0, "title": "Разведи каталу 1 раз"},
            ],
            "participants": [
                {"userId": 9001, "nickname": "Кодер", "authority": 42594},
                {"userId": 9002, "nickname": "zabavachelovek", "authority": 37196},
                {"userId": 9003, "nickname": "Nadimul", "authority": 0},
                {"userId": 9004, "nickname": "fatherDemon2", "authority": 0},
                {"userId": 9005, "nickname": "Hoang", "authority": 0},
            ],
            "completedCount": 1,
        },
        "progress": {"level": 4, "xp": 50, "need": 80},
        "balances": {"ore_signet": 16, "signet": 8},
        "skipSoapCost": 4,
        "modes": [{"mode": 1, "unlocked": True, "rewardSignet": 10}],
    }
    parsed = parse_zaruby_state(raw, now_unix=1795820000, current_user_id=9001)
    assert parsed["active"] is True
    assert parsed["level"] == 4
    assert parsed["signets"] == 8
    assert parsed["ore_signet"] == 16
    assert parsed["reward_signet"] == 10
    assert parsed["tier_title"] == "Пацанская"
    assert len(parsed["tasks"]) == 8
    assert parsed["completed_count"] == 1
    assert len(parsed["leaderboard"]) == 5
    assert any(p["is_self"] and p["progress_pct"] == parsed["overall_pct_exact"] for p in parsed["leaderboard"])

    app_txt = Path("web/static/app.js").read_text(encoding="utf-8")
    block = app_txt[app_txt.index("let _zarubySelectedTaskId = null;"):app_txt.index("async function loadZarubyState()")]
    script = f"""
const elements = {{}};
const makeEl = (id) => {{
  const el = {{
    id, textContent: '', innerHTML: '', disabled: false, style: {{}},
    classList: {{ add(){{}}, remove(){{}}, contains(){{ return false; }} }},
    querySelectorAll(){{ return []; }},
  }};
  elements[id] = el;
  return el;
}};
['zaruby-level','zaruby-signets','zaruby-ore','zaruby-reward-signets','zaruby-active-banner','btn-zaruby-claim','btn-zaruby-start','zaruby-tasks-progress','zaruby-selected-detail','zaruby-tasks-list','zaruby-leaderboard-list','zaruby-timer'].forEach(makeEl);
global.document = {{ getElementById: (id) => elements[id] || null }};
function setTextIfChanged(el, t) {{ if (el) el.textContent = String(t ?? ''); }}
function escapeHtml(s) {{ return String(s ?? ''); }}
function resolveAppAssetUrl(u) {{ return u; }}
function formatNum(n) {{ return String(n ?? 0); }}
function renderRoutineGameBadges() {{}}
global.setInterval = () => 1;
{block}
renderZarubyState({{ success: true, state: {json.dumps(parsed)} }});
if (elements['zaruby-level'].textContent !== '4') throw new Error('level mismatch');
if (!elements['zaruby-selected-detail'].innerHTML.includes('КРЕСТЫ')) throw new Error('detail missing');
if (!elements['zaruby-leaderboard-list'].innerHTML.includes('%')) throw new Error('leaderboard pct missing');
console.log('ZARUBY_JS_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True, check=True)
    assert "ZARUBY_JS_OK" in res.stdout
