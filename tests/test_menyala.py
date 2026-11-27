import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from client.api.menyala import (
    MenyalaAPI,
    check_and_notify_menyala_arrival,
    parse_menyala_state,
)
from sqlalchemy.ext.asyncio import create_async_engine
from core.database import get_or_create_config, get_session, init_db
from core.models import Account, Notification
from sqlalchemy import select


def test_parse_menyala_state_waiting_and_active():
    now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    waiting = parse_menyala_state({"active": False, "nextStartAtUtc": None}, now_utc=now)
    assert waiting["is_active"] is False
    assert waiting["next_arrival_ts"] > int(now.timestamp())
    assert waiting["promos"] == []
    assert waiting["exchanges"] == []

    raw_active = {
        "active": True,
        "nextStartAtUtc": None,
        "event": {
            "eventId": "smg-20261127",
            "startedAtUtc": "2026-11-26T21:00:00Z",
            "endsAtUtc": "2026-11-29T21:00:00Z",
            "variant": "Sugar",
            "rates": {
                "cigsPerRuble": 10000,
                "cigsPerPaper": 2000,
                "sugarPerRuble": 7600,
                "sugarPerPaper": 1500,
            },
            "offersLoot": {
                "F": {"rubles": 5, "sugar": 1377, "poisonCount": 3},
                "P": {"rubles": 14, "sugar": 3398, "gunshotCount": 6},
                "B": {"rubles": 12, "sugar": 3155, "knifeCount": 3},
                "A": {"rubles": 21, "sugar": 6566, "chips": 2, "stew": 2},
            },
        },
        "offers": [True, False, False, False],
        "user": {"balances": {"rubles": 214, "sugar": 39732, "cigarettes": 6292}},
        "prices": {"F": 0, "P": 70, "B": 250, "A": 350},
    }
    active = parse_menyala_state(raw_active, now_utc=now)
    assert active["is_active"] is True
    assert active["cycle_id"] == "smg-20261127"
    assert len(active["promos"]) == 4
    assert active["promos"][0]["id"] == "free"
    assert active["promos"][0]["is_free"] is True
    assert active["promos"][0]["claimed"] is True
    assert active["promos"][1]["id"] == "pacan"
    assert active["promos"][1]["price_rubles"] == 70
    assert active["promos"][1]["claimed"] is False
    assert len(active["exchanges"]) == 2
    assert active["exchanges"][0]["id"] == "sugar_to_rubles"
    assert active["exchanges"][0]["rate_from"] == 7600
    assert active["exchanges"][0]["available"] is True


@pytest.mark.asyncio
async def test_menyala_arrival_notifies_once_per_cycle(tmp_path):
    db_path = tmp_path / "menyala_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="+79990001199", nickname="MenyalaTester"))
        await session.commit()

    class FakeMenyalaAPI:
        async def get_state(self):
            return {
                "active": True,
                "event": {
                    "eventId": "smg-20261127",
                    "startedAtUtc": "2026-11-26T21:00:00Z",
                    "endsAtUtc": "2026-11-29T21:00:00Z",
                    "variant": "Sugar",
                    "rates": {"sugarPerRuble": 7600, "sugarPerPaper": 1500},
                    "offersLoot": {"F": {"rubles": 5}, "P": {"rubles": 14}, "B": {"rubles": 12}, "A": {"rubles": 21}},
                },
                "offers": [False, False, False, False],
                "prices": {"F": 0, "P": 70, "B": 250, "A": 350},
                "user": {"balances": {"rubles": 200, "sugar": 10000}},
            }

    notifier = AsyncMock()
    api = FakeMenyalaAPI()

    r1 = await check_and_notify_menyala_arrival(1, api, db_engine=engine, notifier=notifier)
    assert r1["notified"] is True
    assert notifier.notify.await_count == 1

    # Повторный тик в том же цикле не шлёт дубль
    r2 = await check_and_notify_menyala_arrival(1, api, db_engine=engine, notifier=notifier)
    assert r2["notified"] is False
    assert notifier.notify.await_count == 1

    cfg = await get_or_create_config(1, engine)
    assert cfg.last_notified_menyala_cycle == "smg-20261127"
    await engine.dispose()


def test_js_runtime_menyala_both_states():
    app_txt = Path("web/static/app.js").read_text(encoding="utf-8")
    block = app_txt[app_txt.index("let _menyalaLastState = null;"):app_txt.index("if (typeof module !== \"undefined\"")]
    script = f"""
const elements = {{}};
const makeEl = (id) => {{
  const el = {{
    id,
    textContent: '',
    innerHTML: '',
    value: '1',
    disabled: false,
    style: {{}},
    className: '',
    classList: {{ add(){{}}, remove(){{}}, contains(){{ return false; }} }},
    selectedOptions: [],
    addEventListener(){{}},
    querySelector(){{ return null; }},
    querySelectorAll(){{ return []; }},
  }};
  elements[id] = el;
  return el;
}};
['menyala-timer','menyala-waiting-box','menyala-active-box','menyala-subtitle','menyala-promos-grid','menyala-exchange-box'].forEach(makeEl);
global.document = {{ getElementById: (id) => elements[id] || null }};
function setTextIfChanged(el, t) {{ if (el) el.textContent = String(t ?? ''); }}
function escapeHtml(s) {{ return String(s ?? ''); }}
function resolveAppAssetUrl(u) {{ return u; }}
function formatNum(n) {{ return String(n ?? 0); }}
function apiFetch() {{ return Promise.resolve({{}}); }}
function showToast() {{}}
function refreshState() {{}}
global.setInterval = () => 1;
global.clearInterval = () => {{}};

{block}

renderMenyalaState({{
  is_active: false,
  next_arrival_ts: Math.floor(Date.now() / 1000) + 90000,
  promos: [],
  exchanges: []
}});
if (elements['menyala-waiting-box'].style.display !== 'block') throw new Error('waiting box not shown');
if (elements['menyala-active-box'].style.display !== 'none') throw new Error('active box should be hidden');

renderMenyalaState({{
  is_active: true,
  cycle_id: 'smg-20261127',
  variant: 'Sugar',
  departure_ts: Math.floor(Date.now() / 1000) + 3600,
  promos: [
    {{ id: 'free', title: 'Бесплатный', price_rubles: 0, is_free: true, claimed: false, items: [{{ key: 'rubles', label: 'Рубли', amount: 5, icon: 'assets/icons/rubles.webp' }}] }},
    {{ id: 'pacan', title: 'Пацанский', price_rubles: 70, is_free: false, claimed: false, items: [{{ key: 'sugar', label: 'Сахар', amount: 3398, icon: 'assets/icons/sugar.webp' }}] }},
    {{ id: 'blat', title: 'Блатной', price_rubles: 250, is_free: false, claimed: true, items: [] }},
    {{ id: 'avtoritet', title: 'Авторитетный', price_rubles: 350, is_free: false, claimed: false, items: [] }}
  ],
  exchanges: [{{ id: 'sugar_to_rubles', from_resource: 'sugar', to_resource: 'rubles', rate_from: 7600, rate_to: 1, available: true }}]
}});
if (elements['menyala-active-box'].style.display !== 'block') throw new Error('active box not shown');
if (!elements['menyala-promos-grid'].innerHTML.includes('Пацанский') || !elements['menyala-promos-grid'].innerHTML.includes('Получено')) {{
  throw new Error('promos grid missing expected cards');
}}
if (!elements['menyala-exchange-box'].innerHTML.includes('Обменять')) {{
  throw new Error('exchange box missing');
}}
console.log('MENYALA_JS_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True, check=True)
    assert "MENYALA_JS_OK" in res.stdout


def test_parse_iso_ts_formats_and_server_clock_offset():
    import email.utils
    from datetime import datetime, timezone
    from client.api.menyala import _parse_iso_ts
    from client.http_client import get_game_now_ts, update_game_server_clock

    expected = int(datetime(2026, 11, 29, 21, 0, 0, tzinfo=timezone.utc).timestamp())
    assert _parse_iso_ts("2026-11-29T21:00:00Z") == expected
    assert _parse_iso_ts("2026-11-29T21:00:00.500Z") == expected
    assert _parse_iso_ts("2026-11-29T21:00:00.4285579Z") == expected
    assert _parse_iso_ts("2026-11-30T00:00:00+03:00") == expected
    assert _parse_iso_ts(expected) == expected
    assert _parse_iso_ts(expected * 1000) == expected

    fake_local = 1764000000.0
    srv_dt = datetime.fromtimestamp(fake_local + 12.0, tz=timezone.utc)
    date_hdr = email.utils.format_datetime(srv_dt, usegmt=True)
    off = update_game_server_clock(date_hdr, local_now_ts=fake_local)
    assert off is not None and abs(off - 12.0) < 1.0
    assert get_game_now_ts() > 0
    # Reset global offset so other tests stay unaffected
    update_game_server_clock(email.utils.format_datetime(datetime.now(timezone.utc), usegmt=True))
