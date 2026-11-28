import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from core.config import settings
from core.database import get_engine, init_db
from web.app import app
from web.routes import bot_context

AUTH_HEADERS = {"X-Admin-Token": "test_admin_token"}


@pytest.fixture(autouse=True)
def setup_test_auth(monkeypatch):
    monkeypatch.setattr(settings, "WEB_ADMIN_TOKEN", "test_admin_token")
    from web.routes import _flight_cache
    _flight_cache._cache.clear()
    yield
    _flight_cache._cache.clear()


@pytest.mark.asyncio
async def test_live_boss_endpoint_weapon_damages():
    mock_boss_api = AsyncMock()
    mock_boss_api.get_bootstrap = AsyncMock(return_value={
        "state": "active",
        "hasReward": False,
        "weaponStatsEffective": {"poison": 350, "gunshot": 80, "knife": 45},
    })
    mock_boss_api.get_weapons = AsyncMock(return_value={})
    mock_boss_api.get_all_bosses = AsyncMock(return_value=[])

    bot_context.boss_api = mock_boss_api

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/live/boss", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "weaponDamages" in data
        assert data["weaponDamages"]["poison"] == 350
        assert data["weaponDamages"]["gunshot"] == 80
        assert data["weaponDamages"]["knife"] == 45


@pytest.mark.asyncio
async def test_collections_ranking_ready_first():
    mock_player_api = AsyncMock()
    mock_player_api.get_collections = AsyncMock(return_value={
        "collections": [
            {
                "prisonid": 1,
                "collections": [
                    {
                        "id": 10,
                        "name": "Несобранная",
                        "items": [{"id": 1}, {"id": 2}],
                    },
                    {
                        "id": 20,
                        "name": "Собранная",
                        "items": [{"id": 3}, {"id": 4}],
                    }
                ]
            }
        ],
        "playerProgress": {
            "data": {
                "1": {
                    "10": {"items": {"1": 1, "2": 0}}, # собрано 1/2 -> canExchange = False
                    "20": {"items": {"3": 2, "4": 1}}, # собрано 2/2 -> canExchange = True
                }
            }
        }
    })
    mock_player_api.init_player = AsyncMock(return_value={"stashes": []})
    mock_player_api.get_stashgear_all = AsyncMock(return_value={})

    bot_context.player_api = mock_player_api

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/live/collections", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        cols = data["collections"]
        assert len(cols) == 2
        # Готовая коллекция (canExchange == True) ДОЛЖНА быть первой!
        assert cols[0]["collectionId"] == 20
        assert cols[0]["canExchange"] is True
        assert cols[1]["collectionId"] == 10
        assert cols[1]["canExchange"] is False


@pytest.mark.asyncio
async def test_wardrobe_room_render_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Комната 54 («Торт Люськи» — оригинальный Flash room.bundle без фейковых обрезков)
        r54 = await ac.get("/api/v1/wardrobe/room-render/54", headers=AUTH_HEADERS)
        assert r54.status_code == 200
        d54 = r54.json()
        assert d54["renderMode"] == "bundle"
        assert d54["hasForeground"] is True
        assert d54["foregroundSource"] == "room.bundle:gameBirthday_back_front"
        assert "room.bundle" in d54["bundleUrl"]
        assert d54["isAnimated"] is True

        # Комната 27 (Анимированная Spine 4.2)
        r27 = await ac.get("/api/v1/wardrobe/room-render/27", headers=AUTH_HEADERS)
        assert r27.status_code == 200
        d27 = r27.json()
        assert d27["renderMode"] == "spine"
        assert d27["isAnimated"] is True
        assert d27["spine"] is not None
        assert "skeleton.json" in d27["spine"]["skeletonUrl"]
        assert "skeleton.atlas" in d27["spine"]["atlasUrl"]
        assert d27["spine"]["altRootOffset"] is False


@pytest.mark.asyncio
async def test_brand_logo_and_favicon_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r_index = await ac.get("/")
        assert r_index.status_code == 200
        html = r_index.text
        assert "favicon-32x32.png" in html
        assert "favicon.ico" in html
        assert "apple-touch-icon.png" in html
        assert "bot_logo_128.webp" in html
        assert '<div class="drawer-logo">⛓️</div>' not in html

        checks = [
            ("/favicon.ico", ("image/x-icon", "image/vnd.microsoft.icon")),
            ("/assets/icons/favicon-32x32.png", ("image/png",)),
            ("/assets/icons/favicon-16x16.png", ("image/png",)),
            ("/assets/icons/bot_logo_128.webp", ("image/webp",)),
            ("/assets/icons/apple-touch-icon.png", ("image/png",)),
        ]
        for url, allowed_mimes in checks:
            resp = await ac.get(url)
            assert resp.status_code == 200, f"{url} returned {resp.status_code}"
            assert len(resp.content) > 0
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            assert ctype in allowed_mimes, f"{url} unexpected content-type: {ctype}"

        for extra_url in ("/assets/icons/complect.webp", "/assets/icons/room_reward.webp"):
            r_ex = await ac.get(extra_url)
            assert r_ex.status_code == 200
            assert r_ex.headers.get("content-type", "").split(";")[0].strip().lower() == "image/webp"

        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
        css = (root / "web" / "static" / "styles.css").read_text(encoding="utf-8")
        assert "function renderCollectionsData(" in js
        assert "function getDropIconHtml(" in js
        assert "complect.webp" in js
        assert "stash.webp" in js
        assert "white-space: pre-line" in css


def test_collection_icons_relative_resolution_and_nonblocking_startup():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    main_py = (root / "main.py").read_text(encoding="utf-8")

    assert "function resolveAssetUrl(" in js
    col_fn_start = js.index("function renderCollectionsData(")
    col_fn_end = js.index("async function loadCollections()", col_fn_start)
    col_fn = js[col_fn_start:col_fn_end]
    assert "resolveAppAssetUrl(" in col_fn
    assert "this.style.display='none'" not in col_fn
    assert "stash.webp" not in col_fn

    # uvicorn должен запускаться ДО фоновых циклов воркеров
    assert main_py.index("web_server.serve()") < main_py.rindex("routine_worker.run_cycle()")


def test_resolve_app_asset_url_idempotency_and_sw_v7():
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    sw = (root / "web" / "static" / "sw.js").read_text(encoding="utf-8")

    # Проверка sw.js
    assert "prisonbot-assets-v37" in sw
    assert "skipWaiting" in sw
    assert "clients.claim" in sw
    assert "isCacheableAssetResponse" in sw
    assert "resp.ok" in sw

    # Синхронность версий в index.html, app.js и sw.js
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'const ASSET_VERSION = "20261127_16";' in js
    assert "Ночной режим (только боссы)" in index_html
    assert "katala-free-status-badge" in index_html
    for icon_name in ("cigarettes.webp", "rubles.webp", "sugar.webp", "soap.webp"):
        assert f"/static/assets/icons/{icon_name}?v=20261127_16" in index_html

    # Проверка меню навигации и блока активного боя в index.html
    for expected_snippet in (
        'src="assets/icons/boss.webp?v=20261127_16"',
        'src="assets/icons/room_reward.webp?v=20261127_16"',
        'src="assets/icons/complect.webp?v=20261127_16"',
        'src="assets/icons/podogrev.webp?v=20261127_16"',
        'src="assets/icons/authority.webp?v=20261127_16"',
        'id="boss-title"><img class="boss-battle-icon" src="assets/icons/boss.webp?v=20261127_16"',
    ):
        assert expected_snippet in index_html
    assert "⚔️ Поиск активного рейда" not in index_html

    # Извлекаем getAppBasePrefix + resolveAppAssetUrl и прогоняем в Node.js
    fn_start = js.index("function getAppBasePrefix()")
    fn_end = js.index("function gameIcon(", fn_start)
    fn_code = js[fn_start:fn_end]

    proxy_inputs = [
        "api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp",
        "/api/v1/assets/proxy?path=assets/PrisonV3/collections/30/1/1.webp",
        "prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp",
        "/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp",
        "/prison/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp",
    ]
    icon_inputs = [
        "/static/assets/icons/cigarettes.webp",
        "/static/assets/icons/rubles.webp?v=old",
        "static/assets/icons/sugar.webp?v=20261125_17",
        "/prison/static/assets/icons/soap.webp",
        "assets/icons/podogrev.webp",
        "assets/icons/boss.webp",
        "assets/icons/stash.webp",
        "assets/icons/room_reward.webp",
        "assets/icons/complect.webp",
        "assets/icons/authority.webp",
    ]

    node_script = (
        fn_code
        + "\nconst proxyInputs = "
        + json.dumps(proxy_inputs)
        + ";\nconst iconInputs = "
        + json.dumps(icon_inputs)
        + ";\nfor (const p of ['/prison/', '/prison', '/']) {\n"
        + "  globalThis.window = { location: { pathname: p, origin: 'https://zvezdoed.space' } };\n"
        + "  for (const inp of proxyInputs) {\n"
        + "    const r1 = resolveAppAssetUrl(inp);\n"
        + "    const r2 = resolveAppAssetUrl(r1);\n"
        + "    if (r1 !== r2) throw new Error('Not idempotent: ' + r1 + ' vs ' + r2);\n"
        + "    if (r1.includes('v=20261126_03')) throw new Error('Proxy url polluted with v=: ' + r1);\n"
        + "    if (p.startsWith('/prison')) {\n"
        + "      if (!r1.startsWith('/prison/api/v1/assets/proxy?path=')) throw new Error('Bad prison url: ' + r1);\n"
        + "      if (r1.includes('/prison/prison')) throw new Error('Double prefix: ' + r1);\n"
        + "    } else {\n"
        + "      if (!r1.startsWith('/api/v1/assets/proxy?path=')) throw new Error('Bad root url: ' + r1);\n"
        + "    }\n"
        + "  }\n"
        + "  for (const inp of iconInputs) {\n"
        + "    const r1 = resolveAppAssetUrl(inp);\n"
        + "    const r2 = resolveAppAssetUrl(r1);\n"
        + "    if (r1 !== r2) throw new Error('Icon not idempotent: ' + r1 + ' vs ' + r2);\n"
        + "    if (!r1.includes('v=20261126_03')) throw new Error('Missing icon version: ' + r1);\n"
        + "    if ((r1.match(/\\?v=/g) || []).length !== 1) throw new Error('Duplicate ?v=: ' + r1);\n"
        + "    if (p.startsWith('/prison')) {\n"
        + "      if (!r1.startsWith('/prison/')) throw new Error('Bad prison icon: ' + r1);\n"
        + "      if (r1.includes('/prison/prison')) throw new Error('Double prefix on icon: ' + r1);\n"
        + "    } else {\n"
        + "      if (r1.startsWith('/prison/')) throw new Error('Bad root icon: ' + r1);\n"
        + "    }\n"
        + "  }\n"
        + "}\nconsole.log('OK_NODE_IDEMPOTENT');\n"
    )
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node failed: {proc.stderr or proc.stdout}"
    assert "OK_NODE_IDEMPOTENT" in proc.stdout


def test_resource_icons_http_serving():
    from pathlib import Path
    from fastapi.testclient import TestClient
    from web.app import create_app

    root = Path(__file__).resolve().parent.parent
    client = TestClient(create_app())
    for name in (
        "cigarettes.webp",
        "rubles.webp",
        "sugar.webp",
        "soap.webp",
        "boss.webp",
        "stash.webp",
        "room_reward.webp",
        "complect.webp",
        "podogrev.webp",
        "authority.webp",
    ):
        expected = (root / "web" / "static" / "assets" / "icons" / name).read_bytes()
        for url in (f"/assets/icons/{name}", f"/static/assets/icons/{name}?v=20261125_17"):
            resp = client.get(url)
            assert resp.status_code == 200, f"Failed {url}: {resp.status_code}"
            assert "image/webp" in resp.headers.get("content-type", "").lower()
            assert resp.content == expected


def test_render_boss_data_runtime_node():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    def extract_fn(name: str) -> str:
        start = js.index(f"function {name}(")
        # Find matching brace
        depth = 0
        in_fn = False
        for idx in range(start, len(js)):
            ch = js[idx]
            if ch == "{":
                depth += 1
                in_fn = True
            elif ch == "}":
                depth -= 1
                if in_fn and depth == 0:
                    return js[start : idx + 1]
        raise AssertionError(f"Could not extract {name}")

    helpers = "\n".join([
        'const ASSET_VERSION = "20261125_17";',
        extract_fn("getAppBasePrefix"),
        extract_fn("resolveAppAssetUrl"),
        extract_fn("setTextIfChanged"),
        extract_fn("setWidthIfChanged"),
        extract_fn("formatNum"),
        extract_fn("renderBossData"),
    ])

    node_script = helpers + """
function makeEl(id, initialText = "", initialHtml = "") {
  return {
    id,
    textContent: initialText,
    innerHTML: initialHtml,
    style: {},
    parentElement: null,
    _children: {},
    querySelector(sel) {
      if (sel.includes("boss-title-text")) return this._children.titleText || null;
      return null;
    },
    appendChild(child) { child.parentElement = this; }
  };
}

const titleTextEl = makeEl("boss-title-text", "Поиск активного рейда...");
const titleEl = makeEl("boss-title", "", '<img class="boss-battle-icon" src="assets/icons/boss.webp?v=20261125_17" alt="Босс"> <span id="boss-title-text">Поиск активного рейда...</span>');
titleEl._children.titleText = titleTextEl;

const elems = {
  "boss-active-card": makeEl("boss-active-card"),
  "boss-talents-idle-card": makeEl("boss-talents-idle-card"),
  "boss-manual-attack-card": makeEl("boss-manual-attack-card"),
  "boss-title": titleEl,
  "boss-title-text": titleTextEl,
  "boss-mode-badge": makeEl("boss-mode-badge", "Режим: -"),
  "boss-hp-numbers": makeEl("boss-hp-numbers", "- / -"),
  "boss-hp-percent": makeEl("boss-hp-percent", "0%"),
  "boss-hp-fill": makeEl("boss-hp-fill"),
  "boss-personal-damage": makeEl("boss-personal-damage", "0"),
  "btn-boss-claim": makeEl("btn-boss-claim"),
  "boss-poison-damage": makeEl("boss-poison-damage", "250"),
  "boss-gunshot-damage": makeEl("boss-gunshot-damage", "60"),
  "boss-knife-damage": makeEl("boss-knife-damage", "30"),
};

globalThis.window = { location: { pathname: "/prison/", origin: "https://zvezdoed.space" } };
globalThis.document = { getElementById: (id) => elems[id] || null };
let liveSlices = { data: {} };
let bossData = null;
let bossCatalog = [];
let bossCatalogMap = new Map();
let botConfig = null;
function updateMeleeTimers() {}
function updateBossQueueUI() {}
function renderBossTalentsWidget() {}
function loadBossPresets() {}

// 1. Active boss battle
renderBossData({
  success: true,
  hasReward: true,
  weaponDamages: { poison: 300, gunshot: 80, knife: 40 },
  session: { bossId: 5, title: "Кирпич", mode: "blotnoy", currentHp: 12000, maxHp: 20000, personalDamage: 3450 }
});

if (elems["boss-active-card"].style.display !== "block") throw new Error("activeCard not shown");
if (titleTextEl.textContent !== "Кирпич") throw new Error("Bad title: " + titleTextEl.textContent);
if (!titleEl.innerHTML.includes("assets/icons/boss.webp?v=20261125_17")) throw new Error("Missing boss icon in title");
if (elems["boss-mode-badge"].textContent !== "Режим: Блатной") throw new Error("Bad mode: " + elems["boss-mode-badge"].textContent);
if (elems["boss-hp-numbers"].textContent !== `${formatNum(12000)} / ${formatNum(20000)}`) throw new Error("Bad hp numbers: " + elems["boss-hp-numbers"].textContent);
if (elems["boss-hp-percent"].textContent !== "60%") throw new Error("Bad hp pct: " + elems["boss-hp-percent"].textContent);
if (elems["boss-hp-fill"].style.width !== "60%") throw new Error("Bad hp width: " + elems["boss-hp-fill"].style.width);
if (elems["boss-personal-damage"].textContent !== formatNum(3450)) throw new Error("Bad dmg: " + elems["boss-personal-damage"].textContent);

// 2. Repeated tick
renderBossData({
  success: true,
  hasReward: false,
  weaponDamages: { poison: 300, gunshot: 80, knife: 40 },
  session: { bossId: 5, title: "Кирпич", mode: "blotnoy", currentHp: 10000, maxHp: 20000, personalDamage: 5000 }
});
if ((titleEl.innerHTML.match(/boss\\.webp/g) || []).length !== 1) throw new Error("Icon duplicated in title");
if (elems["boss-hp-percent"].textContent !== "50%") throw new Error("Tick hp pct failed");
if (elems["boss-personal-damage"].textContent !== formatNum(5000)) throw new Error("Tick dmg failed");

// 3. No active boss
renderBossData({ success: true, session: null, weaponDamages: {} });
if (elems["boss-active-card"].style.display !== "none") throw new Error("activeCard not hidden when idle");
if (titleTextEl.textContent !== "Поиск активного рейда...") throw new Error("Title not reset when idle");

console.log("OK_RENDER_BOSS_RUNTIME");
"""
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_RENDER_BOSS_RUNTIME" in proc.stdout


def test_render_boss_defeat_notification_runtime_node():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    start = js.index("  let defeatBarHtml = \"\";")
    end = js.index("  if (meta.outcome === \"victory\")", start)
    defeat_snippet = js[start:end]

    fn_start = js.index("function formatNum(")
    depth = 0
    in_fn = False
    fn_end = fn_start
    for idx in range(fn_start, len(js)):
        if js[idx] == "{":
            depth += 1
            in_fn = True
        elif js[idx] == "}":
            depth -= 1
            if in_fn and depth == 0:
                fn_end = idx + 1
                break
    format_num_code = js[fn_start:fn_end]

    node_script = format_num_code + "\nfunction renderDefeat(meta) {\n  const isDefeat = true;\n" + defeat_snippet + "\n  return defeatBarHtml;\n}\n" + """
const c1 = renderDefeat({ remaining_hp: 12450, max_hp: 50000, hp_percent: 24.9, hp_known: true });
if (!c1.includes("Осталось HP:") || !c1.includes("12") || !c1.includes("450") || !c1.includes("50") || !c1.includes("24.9%") || !c1.includes("width: 24.9%")) {
  throw new Error("Case 1 failed: " + c1);
}

const c2 = renderDefeat({ remaining_hp: 5, max_hp: 100000, hp_known: true });
if (!c2.includes("<0.1%") || !c2.includes("width: 1%")) {
  throw new Error("Case 2 (small HP) failed: " + c2);
}

const c3 = renderDefeat({ remaining_hp: 0, max_hp: 1 });
if (c3.includes("0 / 1") || c3.includes("0%") || c3.includes("defeat-hp-bar") || !c3.includes("нет данных")) {
  throw new Error("Case 3 (legacy 0/1) failed: " + c3);
}

console.log("OK_DEFEAT_NOTIF_RUNTIME");
"""
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_DEFEAT_NOTIF_RUNTIME" in proc.stdout


def test_wardrobe_currency_ru_hood_suppression_moscow_time_and_mobile_css():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    css = (root / "web" / "static" / "styles.css").read_text(encoding="utf-8")

    def _extract_fn(src: str, name: str) -> str:
        s = src.index(f"function {name}(")
        depth = 0
        in_fn = False
        for i in range(s, len(src)):
            if src[i] == "{":
                depth += 1
                in_fn = True
            elif src[i] == "}":
                depth -= 1
                if in_fn and depth == 0:
                    return src[s : i + 1]
        raise AssertionError(f"Could not extract {name}")

    fn_currency = _extract_fn(js, "formatShopCurrencyRu")
    fn_parse = _extract_fn(js, "parseUtcOrIsoDate")
    fn_msk = _extract_fn(js, "formatMoscowTime")
    fn_hood = _extract_fn(js, "applyClothingSuppressionRules")
    rules_start = js.index("const CLOTHING_SUPPRESS_RULES =")
    rules_end = js.index("function applyClothingSuppressionRules(")
    rules_code = js[rules_start:rules_end]

    node_script = "\n".join([fn_currency, fn_parse, fn_msk, rules_code, fn_hood]) + """
// 1. Локализация валют
const checks = [
  ["soap", 700, "мыла"],
  ["rubles", 1500, "руб."],
  ["cigarettes", 200, "папирос"],
  ["sugar", 50, "сахара"],
  ["paper", 15, "туал. бумаги"],
];
for (const [cur, amt, exp] of checks) {
  const got = formatShopCurrencyRu(cur, amt);
  if (got !== exp) throw new Error(`Currency mismatch for ${cur}: got ${got}, expected ${exp}`);
}

// 2. Капюшон «Буйство» скрывает головной убор (zone 1) и очки/маску (zone 2)
const hoodZones = {
  "1": "assets/PrisonV3/Clotch/hat1.png",
  "2": "assets/PrisonV3/Clotch/mask2.png",
  "4": { clothingId: 83, imageUrl: "assets/PrisonV3/Clotch/dubil1/C/4.png" },
  "5": "assets/PrisonV3/Clotch/dubil1/C/5.png",
};
applyClothingSuppressionRules(hoodZones);
if (hoodZones["1"] || hoodZones["2"]) throw new Error("Hood must suppress zones 1 and 2");
if (!hoodZones["4"] || !hoodZones["5"]) throw new Error("Hood must keep zones 4 and 5");

// Обычная кофта НЕ скрывает головной убор
const normalZones = {
  "1": "assets/PrisonV3/Clotch/hat1.png",
  "4": { clothingId: 10, imageUrl: "assets/PrisonV3/Clotch/jacket10.png" },
};
applyClothingSuppressionRules(normalZones);
if (!normalZones["1"]) throw new Error("Normal clothing must keep zone 1");

// 3. Часовой пояс МСК (UTC+3)
const t1 = formatMoscowTime("2026-11-26 00:28:00");
if (t1 !== "03:28") throw new Error(`Expected 03:28 MSK, got ${t1}`);
const t2 = formatMoscowTime("2026-11-25 21:37:00");
if (t2 !== "00:37") throw new Error(`Expected 00:37 MSK, got ${t2}`);

console.log("OK_WARDROBE_TIME_RUNTIME");
"""
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_WARDROBE_TIME_RUNTIME" in proc.stdout

    # 4. Проверка адаптивных CSS-правил
    for selector in (
        ".routine-action-row",
        ".routine-action-controls",
        ".kolsik-currency-select",
        ".prison-actions-row",
        ".master-train-row",
        ".wardrobe-subtabs-row",
    ):
        assert selector in css


def test_prisons_energy_bar_and_wardrobe_stat_badges_runtime_node():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    # 1. Проверка разметки прогресс-бара энергии под кнопками в Ходках
    pos_btns = html.index('id="btn-prison-work-all"')
    pos_bar = html.index('id="prison-energy-bar-wrap"')
    assert pos_bar > pos_btns
    for el_id in ("prison-stat-energy", "prison-energy-progress-fill", "prison-energy-restore-timer"):
        assert f'id="{el_id}"' in html

    # 2. Runtime-тест renderItemStatBadges и синхронного updateEnergyTimer
    def _extract_fn(src: str, name: str) -> str:
        s = src.index(f"function {name}(")
        depth = 0
        in_fn = False
        for i in range(s, len(src)):
            if src[i] == "{":
                depth += 1
                in_fn = True
            elif src[i] == "}":
                depth -= 1
                if in_fn and depth == 0:
                    return src[s : i + 1]
        raise AssertionError(f"Could not extract {name}")

    fn_badges = _extract_fn(js, "renderItemStatBadges")
    fn_energy = _extract_fn(js, "updateEnergyTimer")
    fn_num = _extract_fn(js, "formatNum")

    node_script = (
        "function gameIcon(k) { return `<img src=\"/static/assets/icons/${k}.webp\">`; }\n"
        "function setTextIfChanged(el, txt) { if (el) el.textContent = String(txt); }\n"
        "function setWidthIfChanged(el, w) { if (el) el.style.width = String(w); }\n"
        + "\n".join([fn_num, fn_badges, fn_energy])
        + """
// A. Проверка карточки тапок с authority: 100
const tapkiHtml = renderItemStatBadges({ authority: 100 }, true);
if (!tapkiHtml.includes("authority.webp") || !tapkiHtml.includes("+100")) {
  throw new Error("Expected authority badge +100, got: " + tapkiHtml);
}
const multiHtml = renderItemStatBadges({ authority: 200, poison: 9, gunshot: 4 }, false);
if (!multiHtml.includes("authority.webp") || !multiHtml.includes("poison.webp") || !multiHtml.includes("gunshot.webp")) {
  throw new Error("Expected all badges, got: " + multiHtml);
}

// B. Проверка синхронизации двух прогресс-баров энергии
const elems = {
  "stat-energy": { textContent: "" },
  "prison-stat-energy": { textContent: "" },
  "energy-progress-fill": { style: { width: "" } },
  "prison-energy-progress-fill": { style: { width: "" } },
  "energy-restore-timer": { textContent: "" },
  "prison-energy-restore-timer": { textContent: "" },
};
globalThis.document = { getElementById: (id) => elems[id] || null };

globalThis.playerProfile = {
  profile: {
    energy: 1,
    maxEnergy: 50,
    lastEnergyRestoreTime: new Date(Date.now() - 154 * 1000).toISOString(),
    energyRestoreIntervalSeconds: 300,
  },
};
updateEnergyTimer();
if (elems["stat-energy"].textContent !== "1/50" || elems["prison-stat-energy"].textContent !== "1/50") {
  throw new Error("Energy text out of sync");
}
if (elems["energy-progress-fill"].style.width !== "2%" || elems["prison-energy-progress-fill"].style.width !== "2%") {
  throw new Error("Energy fill out of sync");
}
if (!elems["prison-energy-restore-timer"].textContent.includes("02:") || elems["energy-restore-timer"].textContent !== elems["prison-energy-restore-timer"].textContent) {
  throw new Error("Energy timer out of sync: " + elems["prison-energy-restore-timer"].textContent);
}

// Полная энергия 50/50
globalThis.playerProfile.profile.energy = 50;
updateEnergyTimer();
if (elems["prison-stat-energy"].textContent !== "50/50" || elems["prison-energy-restore-timer"].textContent !== "восстановление: Максимум") {
  throw new Error("Full energy state mismatch");
}

console.log("OK_PRISONS_ENERGY_AND_BADGES");
"""
    )
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_PRISONS_ENERGY_AND_BADGES" in proc.stdout


def test_home_resource_deltas_html_and_node_runtime():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    for rk in ("cigarettes", "sugar", "rubles", "paper", "soap"):
        assert f'id="res-{rk}-delta"' in html

    def _extract_fn(src: str, name: str) -> str:
        s = src.index(f"function {name}(")
        depth = 0
        in_fn = False
        for i in range(s, len(src)):
            if src[i] == "{":
                depth += 1
                in_fn = True
            elif src[i] == "}":
                depth -= 1
                if in_fn and depth == 0:
                    return src[s : i + 1]
        raise AssertionError(f"Could not extract {name}")

    fn_num = _extract_fn(js, "formatNum")
    fn_parse = _extract_fn(js, "parseUtcOrIsoDate")
    fn_msk = _extract_fn(js, "formatMoscowTime")
    fn_fmt_delta = _extract_fn(js, "formatResourceDelta")
    fn_render_deltas = _extract_fn(js, "renderResourceDeltas")

    node_script = (
        "function setTextIfChanged(el, txt) { if (el) el.textContent = String(txt); }\n"
        + "\n".join([fn_num, fn_parse, fn_msk, fn_fmt_delta, fn_render_deltas])
        + """
const pos = formatResourceDelta(1250);
if (!pos.text.startsWith("+1") || !pos.text.includes("250") || pos.cls !== "is-positive") {
  throw new Error("Positive delta mismatch: " + JSON.stringify(pos));
}
const neg = formatResourceDelta(-340);
if (neg.text !== "-340" || neg.cls !== "is-negative") {
  throw new Error("Negative delta mismatch: " + JSON.stringify(neg));
}
const zero = formatResourceDelta(0);
if (zero.text !== "0" || zero.cls !== "is-zero") {
  throw new Error("Zero delta mismatch: " + JSON.stringify(zero));
}
const empty = formatResourceDelta(null);
if (empty.text !== "" || empty.cls !== "is-empty") {
  throw new Error("Empty delta mismatch: " + JSON.stringify(empty));
}

const elems = {
  "res-cigarettes-delta": { className: "", textContent: "", title: "" },
  "res-sugar-delta": { className: "", textContent: "", title: "" },
  "res-rubles-delta": { className: "", textContent: "", title: "" },
  "res-paper-delta": { className: "", textContent: "", title: "" },
  "res-soap-delta": { className: "", textContent: "", title: "" },
};
globalThis.document = { getElementById: (id) => elems[id] || null };

renderResourceDeltas(
  {
    day_msk: "2026-11-26",
    captured_at: "2026-11-26T00:05:00+03:00",
    baseline: { cigarettes: 5000, sugar: 30000, rubles: 200, paper: 100, soap: 10 },
    deltas: { cigarettes: 1250, sugar: -340, rubles: 0, paper: 5, soap: -2 },
  },
  { cigarettes: 6250, sugar: 29660, rubles: 200, paper: 105, soap: 8 }
);

if (!elems["res-cigarettes-delta"].className.includes("is-positive")) throw new Error("Missing is-positive");
if (!elems["res-cigarettes-delta"].title.includes("00:05") || !elems["res-cigarettes-delta"].title.includes("6") || !elems["res-cigarettes-delta"].title.includes("250")) {
  throw new Error("Bad tooltip: " + elems["res-cigarettes-delta"].title);
}
if (!elems["res-sugar-delta"].className.includes("is-negative")) throw new Error("Missing is-negative");
if (!elems["res-rubles-delta"].className.includes("is-zero")) throw new Error("Missing is-zero");

console.log("OK_RESOURCE_DELTAS_RUNTIME");
"""
    )
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_RESOURCE_DELTAS_RUNTIME" in proc.stdout


def test_katala_fail_closed_ui_and_node_runtime():
    """Проверка Fail-Closed дефолта в HTML, корректного URL /daily/katala-status и node runtime-теста renderKatalaFreeStatus."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    # 1. В исходном HTML нет ложного зеленого статуса и кнопка изначально disabled
    badge_idx = index_html.index('id="katala-free-status-badge"')
    badge_snippet = index_html[badge_idx:badge_idx + 180]
    assert "Бесплатная игра доступна (0 ₽)" not in badge_snippet
    assert "Проверяем статус" in badge_snippet
    assert 'id="btn-katala-play"' in index_html
    btn_idx = index_html.index('id="btn-katala-play"')
    btn_snippet = index_html[btn_idx:btn_idx + 140]
    assert "disabled" in btn_snippet

    # 2. Запрос к /daily/katala-status идет через apiFetch (не голый fetch('/api/...'))
    assert 'apiFetch("/daily/katala-status")' in js

    # 3. Node runtime-тест formatKatalaWaitTime + renderKatalaFreeStatus
    fn_start = js.index("function formatKatalaWaitTime(")
    fn_end = js.index("async function loadKatalaStatus()", fn_start)
    fn_code = js[fn_start:fn_end]

    node_script = (
        fn_code
        + """
const badgeEl = { textContent: "", style: {}, title: "" };
const btnEl = { disabled: false };
global.setTextIfChanged = (el, txt) => { el.textContent = txt; };
global.document = {
  getElementById: (id) => (id === "katala-free-status-badge" ? badgeEl : id === "btn-katala-play" ? btnEl : null),
  querySelector: () => btnEl,
};

// (a) Кулдаун 47647с -> 13ч 14м, кнопка disabled
const rCd = renderKatalaFreeStatus({
  success: true,
  free_available: false,
  seconds_left: 47647,
  next_free_at_msk: "2026-11-27 06:57 МСК",
  reason: "cooldown_24h_47647s",
});
if (rCd.disabled !== true || btnEl.disabled !== true) throw new Error("Cooldown should disable button");
if (!rCd.text.includes("13ч 14м") || !rCd.text.includes("использована")) throw new Error("Bad cooldown text: " + rCd.text);

// (b) Доступна бесплатная -> 0 ₽, кнопка активна
const rOk = renderKatalaFreeStatus({ success: true, free_available: true });
if (rOk.disabled !== false || btnEl.disabled !== false) throw new Error("Free available should enable button");
if (!rOk.text.includes("Бесплатная игра доступна (0 ₽)")) throw new Error("Bad free text: " + rOk.text);

// (c) Сработал Circuit Breaker -> красный статус, кнопка disabled
const rGuard = renderKatalaFreeStatus({ success: true, free_available: false, guard_tripped: true });
if (rGuard.disabled !== true || btnEl.disabled !== true) throw new Error("Guard tripped should disable button");
if (!rGuard.text.includes("остановлена защитой рублей")) throw new Error("Bad guard text: " + rGuard.text);

// (d) Ошибка / null -> fail-closed, кнопка disabled
const rErr = renderKatalaFreeStatus(null);
if (rErr.disabled !== true || btnEl.disabled !== true) throw new Error("Null status should disable button");
if (!rErr.text.includes("не проверен")) throw new Error("Bad null text: " + rErr.text);

const rFail = renderKatalaFreeStatus({ success: false, free_available: false, error: "timeout" });
if (rFail.disabled !== true || btnEl.disabled !== true) throw new Error("Failed status should disable button");

console.log("OK_KATALA_FAIL_CLOSED_RUNTIME");
"""
    )
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_KATALA_FAIL_CLOSED_RUNTIME" in proc.stdout


def test_friends_audit_and_requests_node_runtime():
    """Проверка верстки модалки/аудита и node runtime-тест filterAndSortAuditFriends + getAuditStatusMeta."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    for snippet in (
        'id="audit-summary-chips"',
        'id="audit-filter-tabs"',
        'id="audit-search-input"',
        'id="audit-sort-select"',
        'id="friends-cleanup-modal"',
        'id="btn-audit-select-candidates"',
    ):
        assert snippet in index_html

    assert "finally {" in js[js.index("handleFriendRequestAction"):js.index("async function loadFriendRequests")]

    fn_start = js.index("function getAuditStatusMeta(")
    fn_end = js.index("function updateAuditSelectionButtons(", fn_start)
    fn_code = js[fn_start:fn_end]

    node_script = (
        fn_code
        + """
const friends = [
  { userId: 1, nickname: "Боец", status: "active", totalDamageToMyBosses: 50000, avgDamage: 25000, bossHitsCount: 2, damage7d: 50000, authority: 1000, daysInactive: 1 },
  { userId: 2, nickname: "Балласт", status: "candidate", totalDamageToMyBosses: 0, avgDamage: 0, bossHitsCount: 0, damage7d: 0, authority: 200, daysInactive: 20 },
  { userId: 3, nickname: "Новичок", status: "newbie_protected", totalDamageToMyBosses: 0, avgDamage: 0, bossHitsCount: 0, damage7d: 0, authority: 500, daysInactive: 2 },
];
if (getAuditStatusMeta("candidate").label !== "Кандидат на чистку") throw new Error("Bad status meta");
const cands = filterAndSortAuditFriends(friends, "candidate", "", "damage_7d");
if (cands.length !== 1 || cands[0].userId !== 2) throw new Error("Bad candidate filter");
const byId = filterAndSortAuditFriends(friends, "all", "3", "damage_7d");
if (byId.length !== 1 || byId[0].userId !== 3) throw new Error("Bad search by ID");
const sortedCands = filterAndSortAuditFriends(friends, "all", "", "candidates_first");
if (sortedCands[0].userId !== 2) throw new Error("Bad candidates_first sort");
console.log("OK_AUDIT_RUNTIME");
"""
    )
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_AUDIT_RUNTIME" in proc.stdout


def test_maintenance_overlay_html_and_node_runtime():
    """Проверка верстки #maintenance-overlay и node runtime-теста formatMaintenanceDuration + renderMaintenanceOverlay."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    for snippet in (
        'id="maintenance-overlay"',
        'id="maintenance-duration"',
        'id="btn-maintenance-recheck"',
        "В игре технические работы",
        "Проверить снова",
    ):
        assert snippet in index_html

    fn_start = js.index("let _maintenancePollTimer = null;")
    fn_end = js.index('document.getElementById("btn-maintenance-recheck")', fn_start)
    fn_code = js[fn_start:fn_end]

    node_script = (
        fn_code
        + """
if (formatMaintenanceDuration(45) !== "Длится меньше минуты") throw new Error("Bad <60s");
if (formatMaintenanceDuration(185) !== "Длится 3 мин") throw new Error("Bad 185s");
if (formatMaintenanceDuration(3900) !== "Длится 1 ч 5 мин") throw new Error("Bad 3900s");

const overlayEl = { style: { display: "none" } };
const durEl = { textContent: "" };
const metaEl = { textContent: "", title: "" };
let refreshed = 0;
global.document = {
  getElementById: (id) => {
    if (id === "maintenance-overlay") return overlayEl;
    if (id === "maintenance-duration") return durEl;
    if (id === "maintenance-meta") return metaEl;
    return null;
  },
};
global.setInterval = () => 123;
global.clearInterval = () => {};
global.refreshState = () => { refreshed += 1; };
global.showToast = () => {};

const onRes = renderMaintenanceOverlay({ active: true, duration_sec: 185, check_attempts: 4, reason: "HTTP 503" });
if (!onRes.active || overlayEl.style.display !== "flex" || durEl.textContent !== "Длится 3 мин") {
  throw new Error("Failed showing overlay");
}
const offRes = renderMaintenanceOverlay({ active: false });
if (offRes.active || !offRes.recovered || overlayEl.style.display !== "none" || refreshed !== 1) {
  throw new Error("Failed hiding overlay and triggering refresh");
}
console.log("OK_MAINTENANCE_RUNTIME");
"""
    )
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_MAINTENANCE_RUNTIME" in proc.stdout



def test_new_game_icons_and_no_emoji_in_new_ui():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    icons_dir = root / "web" / "static" / "assets" / "icons"
    for icon_name in (
        "poker_chip_red.webp",
        "poker_icon.webp",
        "match_green.webp",
        "match_red.webp",
        "fartovy_icon.webp",
        "wheel_ticket.webp",
        "match_blue.webp",
        "wheel_icon.webp",
        "zaruby_icon.webp",
    ):
        p = icons_dir / icon_name
        assert p.exists() and p.stat().st_size > 100, f"Missing or empty icon {icon_name}"

    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    for sec_id in ('id="sec-poker"', 'id="sec-fartovy"', 'id="sec-wheel"', 'id="sec-zaruby"'):
        assert sec_id in html
    new_blocks_start = html.index('id="sec-poker"')
    new_blocks_end = html.index('id="sec-notifications"')
    new_blocks_html = html[new_blocks_start:new_blocks_end]
    for bad_emoji in ("🎰", "🎡", "⚔️", "🃏", "🎲"):
        assert bad_emoji not in new_blocks_html


def test_new_game_ui_runtime_node():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    node_script = """
const elems = {};
function makeEl(id) {
  if (!elems[id]) elems[id] = { id, textContent: "", innerHTML: "", style: {}, disabled: false, value: "" };
  return elems[id];
}
globalThis.document = {
  getElementById: (id) => makeEl(id),
  querySelectorAll: () => [],
};
globalThis.window = { location: { pathname: "/prison/", hash: "" }, addEventListener: () => {} };
globalThis.localStorage = { getItem: () => null, setItem: () => {} };
globalThis.navigator = {};
""" + app_js.split("if (typeof navigator !== \"undefined\"")[0] + """
function setTextIfChanged(el, t) { if (el) el.textContent = String(t ?? ""); }
function escapeHtml(s) { return String(s ?? ""); }
"""
    # Extract only the pure helper block from the appended section + setTextIfChanged/escapeHtml
    block = app_js[app_js.index("const FARTOVY_REGEN_INTERVAL_SEC"):]
    test_runner = f"""
const elems = {{}};
function makeEl(id) {{
  if (!elems[id]) elems[id] = {{ id, textContent: "", innerHTML: "", style: {{}}, disabled: false, value: "", addEventListener: () => {{}} }};
  return elems[id];
}}
globalThis.document = {{ getElementById: (id) => makeEl(id) }};
function setTextIfChanged(el, t) {{ if (el) el.textContent = String(t ?? ""); }}
function escapeHtml(s) {{ return String(s ?? ""); }}
function apiFetch() {{ return Promise.resolve({{}}); }}
function showToast() {{}}
function refreshState() {{}}
{block}
if (formatGreenMatchTimer(3665) !== "(+1 через 01:01:05)") throw new Error("Bad timer format");
renderHomeGameResources({{ poker_chips: 3, fartovy_green: 15, fartovy_cap: 15, fartovy_red: 7, wheel_tickets: 2 }});
if (elems["home-poker-chips"].textContent !== "3") throw new Error("Bad poker chips");
if (elems["home-fartovy-green-timer"].textContent !== "Максимум") throw new Error("Expected Максимум at cap");
if (elems["home-wheel-tickets"].textContent !== "2") throw new Error("Bad wheel tickets");
renderRoutineGameBadges({{ zaruby_completed: 4, zaruby_total: 8 }});
if (elems["routine-zaruby-progress"].textContent !== "Задания: 4/8 (50%)") throw new Error("Bad zaruby progress: " + elems["routine-zaruby-progress"].textContent);
clearInterval(_fartovyCountdownTimer);
console.log("OK_NEW_GAME_UI_NODE");
"""
    proc = subprocess.run(["node"], input=test_runner, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_NEW_GAME_UI_NODE" in proc.stdout


def test_handle_domain_revisions_sync_runtime_node():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    block = app_js[app_js.index("let _lastDomainRevisions = {};"):]

    test_runner = f"""
let activeSection = "bosses";
let bossLoaded = 0, prisonsLoaded = 0, catalogsLoaded = 0;
globalThis.document = {{
  getElementById: (id) => id === "modal-boss-menu" ? {{ style: {{ display: "flex" }} }} : null,
}};
function loadBoss() {{ bossLoaded += 1; }}
function loadPrisons() {{ prisonsLoaded += 1; }}
function loadCatalogs() {{ catalogsLoaded += 1; }}
{block}
handleDomainRevisionsSync({{ prisons: 1, boss: 1 }});
if (bossLoaded !== 0 || catalogsLoaded !== 0) throw new Error("Should not refresh on initial baseline");
const res = handleDomainRevisionsSync({{ prisons: 2, boss: 2 }});
if (bossLoaded !== 1 || prisonsLoaded !== 1 || catalogsLoaded !== 1) throw new Error("Did not trigger reactive refresh");
if (!res.refreshed.includes("boss")) throw new Error("Missing boss in refreshed");
console.log("OK_DOMAIN_REVS_SYNC_NODE");
"""
    proc = subprocess.run(["node"], input=test_runner, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node runtime failed: {proc.stderr or proc.stdout}"
    assert "OK_DOMAIN_REVS_SYNC_NODE" in proc.stdout



def test_boss_menu_live_sync_and_strategy_panel_ui_contract():
    """Контракт UI для live-синхронизации очереди боссов, панели стратегии и бейджей #N."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    css = (root / "web" / "static" / "styles.css").read_text(encoding="utf-8")

    for snippet in (
        'id="boss-queue-sync-status"',
        'id="boss-modal-strategy-panel"',
        'id="boss-modal-strategy-title"',
        'id="boss-modal-strategy-chain"',
    ):
        assert snippet in html

    for snippet in (
        "function renderBossStrategyPanel(",
        "function flushBossQueueSave(",
        "function scheduleBossQueueSave(",
        "function focusBossCardInMenu(",
        "boss-queue-pos-badge",
        "strategy-chip--moved",
        'aria-label="Повысить приоритет"',
        'aria-label="Понизить приоритет"',
    ):
        assert snippet in js

    for snippet in (
        ".boss-strategy-panel",
        ".boss-strategy-chip.strategy-chip--moved",
        ".boss-queue-pos-badge",
        ".boss-sync-status",
    ):
        assert snippet in css



def test_boss_menu_js_runtime_smoke_6_bosses():
    """
    Реальный runtime smoke-тест JS-логики в Node.js:
    проверяет отсутствие ReferenceError/TypeError при вызове updateBossQueueUI,
    renderBossMenuList, renderBossStrategyPanel, перестановке ▲/▼ и renderBossPresets.
    """
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js_path = (root / "web" / "static" / "app.js").as_posix()

    node_script = f"""
const fs = require('fs');
const vm = require('vm');

function makeEl(tag, id) {{
  const attrs = {{}};
  const classes = new Set();
  const listeners = {{}};
  const children = [];
  let _innerHTML = '';
  let _textContent = '';
  const el = {{
    tagName: (tag || 'div').toUpperCase(),
    id: id || '',
    style: {{}},
    dataset: {{}},
    value: '',
    checked: false,
    disabled: false,
    classList: {{
      add: (...c) => c.forEach(x => classes.add(x)),
      remove: (...c) => c.forEach(x => classes.delete(x)),
      toggle: (c, force) => (force === undefined ? (classes.has(c) ? classes.delete(c) : classes.add(c)) : (force ? classes.add(c) : classes.delete(c))),
      contains: (c) => classes.has(c),
    }},
    get className() {{ return Array.from(classes).join(' '); }},
    set className(v) {{ classes.clear(); String(v || '').split(/\\s+/).filter(Boolean).forEach(x => classes.add(x)); }},
    setAttribute: (k, v) => {{ attrs[k] = String(v); }},
    getAttribute: (k) => (k in attrs ? attrs[k] : null),
    addEventListener: (ev, fn) => {{ (listeners[ev] = listeners[ev] || []).push(fn); }},
    dispatchEvent: (ev) => {{ (listeners[ev.type] || []).forEach(fn => fn(ev)); }},
    click: () => {{ (listeners['click'] || []).forEach(fn => fn({{ target: el, preventDefault() {{}} }})); }},
    appendChild: (ch) => {{ children.push(ch); return ch; }},
    insertBefore: (ch, ref) => {{
      const idx = ref ? children.indexOf(ref) : -1;
      if (idx === -1) children.push(ch);
      else children.splice(idx, 0, ch);
      return ch;
    }},
    remove: () => {{}},
    scrollIntoView: () => {{}},
    querySelector: (sel) => el.querySelectorAll(sel)[0] || null,
    querySelectorAll: (sel) => {{
      if (sel === '.boss-strategy-chip') {{
        const matches = _innerHTML.match(/data-boss-id="(\\d+)"/g) || [];
        return matches.map(m => {{
          const ch = makeEl('button');
          ch.setAttribute('data-boss-id', m.match(/\\d+/)[0]);
          return ch;
        }});
      }}
      if (sel === '.btn-boss-up') return el._btnUp ? [el._btnUp] : [];
      if (sel === '.btn-boss-down') return el._btnDown ? [el._btnDown] : [];
      if (sel === '.boss-queue-toggle') return el._chk ? [el._chk] : [];
      if (sel === '.boss-mode-pill') return [];
      if (sel === '.boss-limit-input') return [];
      if (sel === '.boss-loot-item-chip') return [];
      return [];
    }},
    get children() {{ return children; }},
    get innerHTML() {{ return _innerHTML; }},
    set innerHTML(v) {{
      _innerHTML = String(v || '');
      if (!_innerHTML) children.length = 0;
      if (_innerHTML.includes('btn-boss-up')) {{
        el._btnUp = makeEl('button');
        el._btnDown = makeEl('button');
        el._chk = makeEl('input');
        el._chk.checked = _innerHTML.includes('checked');
      }}
    }},
    get textContent() {{ return _textContent; }},
    set textContent(v) {{ _textContent = String(v ?? ''); }},
  }};
  return el;
}}

const elements = {{}};
[
  'badge-boss-queue-count', 'boss-menu-header-badge', 'boss-active-queue-summary',
  'boss-modal-strategy-title', 'boss-modal-strategy-chain', 'boss-menu-list',
  'boss-queue-sync-status', 'boss-presets-list', 'modal-boss-menu', 'boss-menu-search'
].forEach(id => {{ elements[id] = makeEl('div', id); }});

const sandbox = {{
  console,
  setTimeout: () => 0,
  clearTimeout: () => {{}},
  setInterval: () => 0,
  clearInterval: () => {{}},
  Map, Set, Array, Object, Number, String, Boolean, JSON, Math, Promise, Date, RegExp, Error,
  localStorage: {{ getItem: () => null, setItem: () => {{}} }},
  navigator: {{}},
  location: {{ search: '', hostname: 'localhost' }},
  Telegram: {{ WebApp: {{ ready: () => {{}}, expand: () => {{}} }} }},
  addEventListener: () => {{}},
  removeEventListener: () => {{}},
  document: {{
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: (tag) => makeEl(tag),
    addEventListener: () => {{}},
  }},
  fetch: async () => ({{ ok: true, status: 200, json: async () => ({{ success: true, config: {{ boss_targets: sandbox.bossTargetsWorkingCopy }} }}) }}),
}};
sandbox.window = sandbox;
vm.createContext(sandbox);
const code = fs.readFileSync({json.dumps(js_path)}, 'utf8');
vm.runInContext(code, sandbox);

const sampleCatalog = [
  {{ id: 1, name: 'Кирпич', categoryId: 1, sortOrder: 0, modes: {{ pacansky: {{ hp: 500 }}, blotnoy: {{ hp: 1000 }}, avtoritetny: {{ hp: 2000 }} }} }},
  {{ id: 2, name: 'Сизый', categoryId: 1, sortOrder: 1, modes: {{ pacansky: {{ hp: 1000 }}, blotnoy: {{ hp: 2000 }}, avtoritetny: {{ hp: 5000 }} }} }},
  {{ id: 3, name: 'Махно', categoryId: 1, sortOrder: 2, modes: {{ pacansky: {{ hp: 2000 }}, blotnoy: {{ hp: 4000 }}, avtoritetny: {{ hp: 10000 }} }} }},
  {{ id: 4, name: 'Лютый', categoryId: 1, sortOrder: 3, modes: {{ pacansky: {{ hp: 5000 }}, blotnoy: {{ hp: 10000 }}, avtoritetny: {{ hp: 25000 }} }} }},
  {{ id: 5, name: 'Палыч', categoryId: 2, sortOrder: 4, modes: {{ pacansky: {{ hp: 10000 }} }} }},
  {{ id: 6, name: 'Воркута', categoryId: 3, sortOrder: 5, modes: {{ pacansky: {{ hp: 20000 }} }} }},
];
const sampleTargets = [
  {{ bossId: 1, mode: 'pacansky', limit: 7, enabled: true, priority: 0 }},
  {{ bossId: 2, mode: 'avtoritetny', limit: 7, enabled: true, priority: 1 }},
  {{ bossId: 3, mode: 'avtoritetny', limit: 7, enabled: true, priority: 2 }},
  {{ bossId: 4, mode: 'avtoritetny', limit: 7, enabled: true, priority: 3 }},
  {{ bossId: 5, mode: 'pacansky', limit: 7, enabled: true, priority: 4 }},
  {{ bossId: 6, mode: 'pacansky', limit: 7, enabled: true, priority: 5 }},
];

vm.runInContext(`
  bossCatalog = ${{JSON.stringify(sampleCatalog)}};
  bossCatalogMap = new Map(bossCatalog.map(b => [String(b.id), b.name]));
  botConfig = {{ boss_targets: ${{JSON.stringify(sampleTargets)}} }};
  bossTargetsWorkingCopy = normalizeBossTargetsWorkingCopy(botConfig.boss_targets);
  bossPresets = [{{ id: 10, name: 'Фарм', items: [{{ bossId: 1, mode: 'pacansky', count: 1 }}], is_running: false }}];
  updateBossQueueUI(botConfig.boss_targets);
  renderBossMenuList();
  renderBossPresets();
`, sandbox);

const summaryHtml = elements['boss-active-queue-summary'].innerHTML;
const strategyTitle = elements['boss-modal-strategy-title'].textContent;
const strategyHtml = elements['boss-modal-strategy-chain'].innerHTML;
const cardsAllCount = elements['boss-menu-list'].children.length;
const presetsHtml = elements['boss-presets-list'].innerHTML + elements['boss-presets-list'].children.map(c => c.innerHTML).join('');

if (elements['badge-boss-queue-count'].textContent !== 'выбрано: 6') throw new Error('bad badge count');
if (!summaryHtml.includes('Кирпич [Пац]') || !summaryHtml.includes('Лютый [Авторитет]') || summaryHtml.includes('#1 ') || summaryHtml.includes('Очередь автоатаки пуста')) {{
  throw new Error('bad summary: ' + summaryHtml);
}}
if (strategyTitle !== 'Порядок ротации (6):') throw new Error('bad strategy title: ' + strategyTitle);
if (elements['boss-modal-strategy-chain'].querySelectorAll('.boss-strategy-chip').length !== 6) throw new Error('expected 6 chips');
if (cardsAllCount !== 6) throw new Error('expected 6 cards, got ' + cardsAllCount);
if (!presetsHtml.includes('Фарм')) throw new Error('presets not rendered');

// Search filter 'лю' + move up ▲
vm.runInContext(`
  bossSearchQuery = 'лю';
  renderBossMenuList();
`, sandbox);
if (elements['boss-menu-list'].children.length !== 1) throw new Error('expected 1 filtered card for лю');
const lyutyyCard = elements['boss-menu-list'].children[0];
lyutyyCard.querySelector('.btn-boss-up').click();
const reorderedIds = vm.runInContext('bossTargetsWorkingCopy.map(t => t.bossId)', sandbox);
if (JSON.stringify(Array.from(reorderedIds)) !== '[1,2,4,3,5,6]') {{
  throw new Error('unexpected reorder: ' + JSON.stringify(reorderedIds));
}}
console.log('JS_RUNTIME_SMOKE_OK');
"""
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, encoding="utf-8", check=False)
    assert proc.returncode == 0, f"Node smoke failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    assert "JS_RUNTIME_SMOKE_OK" in proc.stdout



def test_home_stew_and_parcels_progress_runtime_node():
    """
    JS runtime smoke-тест: проверка отображения тушенки с дельтой (+1),
    прогресс-баров достижений (3 / 50) и гаранта посылки (6 / 20) на главной.
    """
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js_path = (root / "web" / "static" / "app.js").as_posix()

    node_script = f"""
const fs = require('fs');
const vm = require('vm');

function makeEl(id) {{
  return {{
    id, style: {{}}, className: '', textContent: '', title: '', innerHTML: '',
    classList: {{ toggle: () => {{}}, add: () => {{}}, remove: () => {{}} }},
    addEventListener: () => {{}},
  }};
}}
const ids = [
  'cur-cigs', 'cur-sugar', 'cur-rubles', 'cur-paper', 'cur-soap', 'cur-stew',
  'res-cigarettes-delta', 'res-sugar-delta', 'res-rubles-delta', 'res-paper-delta', 'res-soap-delta', 'res-stew-delta',
  'home-achiev-progress-text', 'home-achiev-progress-fill',
  'home-parcel-pity-text', 'home-parcel-pity-fill',
];
const els = Object.fromEntries(ids.map(i => [i, makeEl(i)]));
const sandbox = {{
  console, Map, Set, Array, Object, Number, String, Boolean, JSON, Math, Promise, Date, RegExp, Error,
  setTimeout: () => 0, clearTimeout: () => {{}}, setInterval: () => 0, clearInterval: () => {{}},
  localStorage: {{ getItem: () => null, setItem: () => {{}} }},
  navigator: {{}}, location: {{ search: '', hostname: 'localhost' }},
  Telegram: {{ WebApp: {{ ready: () => {{}}, expand: () => {{}} }} }},
  addEventListener: () => {{}}, removeEventListener: () => {{}},
  document: {{ getElementById: (id) => els[id] || null, querySelector: () => null, querySelectorAll: () => [], createElement: () => makeEl('x'), addEventListener: () => {{}} }},
  fetch: async () => ({{ ok: true, status: 200, json: async () => ({{}}) }}),
}};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync({json.dumps(js_path)}, 'utf8'), sandbox);

vm.runInContext(`
  applyStateData({{
    success: true,
    config: {{}},
    snapshot: {{ cigarettes: 100, sugar: 50, rubles: 10, paper: 5, soap: 2, stew: 1 }},
    resource_deltas: {{ deltas: {{ cigarettes: 10, sugar: 0, rubles: 0, paper: 0, soap: 0, stew: 1 }}, baseline: {{ stew: 0 }} }},
    parcels_progress: {{ stew_count: 1, achievements_current: 3, achievements_target: 50, guaranteed_item_current: 6, guaranteed_item_target: 20 }},
    counts: {{}}
  }});
`, sandbox);

if (els['cur-stew'].textContent !== '1') throw new Error('bad cur-stew: ' + els['cur-stew'].textContent);
if (els['res-stew-delta'].textContent !== '+1') throw new Error('bad stew delta: ' + els['res-stew-delta'].textContent);
if (els['home-achiev-progress-text'].textContent !== '3 / 50') throw new Error('bad achiev text: ' + els['home-achiev-progress-text'].textContent);
if (els['home-achiev-progress-fill'].style.width !== '6%') throw new Error('bad achiev width: ' + els['home-achiev-progress-fill'].style.width);
if (els['home-parcel-pity-text'].textContent !== '6 / 20') throw new Error('bad pity text: ' + els['home-parcel-pity-text'].textContent);
if (els['home-parcel-pity-fill'].style.width !== '30%') throw new Error('bad pity width: ' + els['home-parcel-pity-fill'].style.width);
console.log('HOME_STEW_PARCELS_SMOKE_OK');
"""
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, encoding="utf-8", check=False)
    assert proc.returncode == 0, f"Node smoke failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    assert "HOME_STEW_PARCELS_SMOKE_OK" in proc.stdout

    # Проверка HTML-контракта #home-parcels-card:
    # слева achievement.png и parcel_cloth.webp, справа в счетчиках нет <img>
    import re
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    card_m = re.search(r'<div class="card" id="home-parcels-card">.*?<!-- Weapons Inventory Card -->', html, re.S)
    assert card_m is not None
    card_html = card_m.group(0)
    assert re.search(r'achievement\.png[^>]*>\s*Достижения \(до \+1 тушенки\)', card_html)
    assert re.search(r'parcel_cloth\.webp[^>]*>\s*До гарантированной вещи', card_html)
    assert not re.search(r'stew\.webp[^>]*>\s*До гарантированной вещи', card_html)
    for val_block in re.findall(r'<span class="parcel-progress-val">(.*?)</span>\s*</div>', card_html, re.S):
        assert "<img" not in val_block


def test_js_smoke_friend_request_removal_and_news_raids_and_energy():
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    js_text = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")

    # Вкладка Рейды и Новости: строго 2 основные вкладки
    assert 'data-raids-tab="raids"' in html
    assert 'data-raids-tab="news"' in html
    assert 'data-raids-tab="radar"' not in html
    assert 'data-raids-tab="invites"' not in html
    assert 'id="unified-raids-players-list"' in html
    assert 'id="raids-auto-invite-toggle"' in html
    assert '<input type="checkbox" id="raids-auto-invite-toggle">\n                <span class="toggle-slider"></span>' in html.replace("\r\n", "\n")
    assert 'id="master-cycle-energy-info"' in html

    def extract_fn(src: str, sig: str) -> str:
        idx = src.index(sig)
        brace_start = src.index("{", idx)
        depth = 0
        for pos in range(brace_start, len(src)):
            ch = src[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return src[idx : pos + 1]
        raise AssertionError(f"Unclosed function: {sig}")

    extracted_js = "\n\n".join([
        extract_fn(js_text, "function getAppBasePrefix("),
        extract_fn(js_text, "function resolveAppAssetUrl("),
        extract_fn(js_text, "function getFriendRequestKey("),
        extract_fn(js_text, "function renderFriendRequestsData("),
        extract_fn(js_text, "function applySocialUpdatedEvent("),
        extract_fn(js_text, "function _stabilizePrisonEnergy("),
        extract_fn(js_text, "function _stabilizeMasterEnergy("),
        extract_fn(js_text, "function renderPrisonsGrid("),
        "function setWidthIfChanged(el, w) { if (el && el.style) el.style.width = w; }\nconst _prisonsEnergyCache = {};\nconst _mastersEnergyCache = {};\nlet currentMasterId = 1;\nlet _mastersCatalogCache = [];\n" + extract_fn(js_text, "function updateSelectedMasterCard("),
        extract_fn(js_text, "function renderMastersGrid("),
        extract_fn(js_text, "function renderMastersSection("),
        extract_fn(js_text, "function renderNewsPostCard("),
    ])

    node_script = f"""
const vm = require('vm');
const els = {{}};
function makeEl(id) {{
  let html = '';
  let text = '';
  const children = [];
  const attrs = {{}};
  const slots = {{}};
  const el = {{
    id,
    children,
    slots,
    style: {{}},
    dataset: {{}},
    parentNode: null,
    classList: {{
      _set: new Set(),
      add(...c) {{ c.forEach(x => this._set.add(x)); }},
      remove(...c) {{ c.forEach(x => this._set.delete(x)); }},
      toggle(c, force) {{
        if (force === undefined) {{ if (this._set.has(c)) this._set.delete(c); else this._set.add(c); }}
        else if (force) this._set.add(c); else this._set.delete(c);
      }},
      contains(c) {{ return this._set.has(c); }},
    }},
    get innerHTML() {{ return html; }},
    set innerHTML(v) {{ html = String(v); if (!html) children.length = 0; }},
    get textContent() {{ return text; }},
    set textContent(v) {{ text = String(v); }},
    setAttribute(k, v) {{ attrs[k] = String(v); }},
    getAttribute(k) {{ return attrs[k] || null; }},
    addEventListener() {{}},
    querySelectorAll() {{ return []; }},
    querySelector(sel) {{
      if (!slots[sel]) slots[sel] = makeEl(sel);
      return slots[sel];
    }},
    closest() {{ return null; }},
    appendChild(ch) {{ ch.parentNode = el; children.push(ch); return ch; }},
    remove() {{
      if (el.parentNode) {{
        const idx = el.parentNode.children.indexOf(el);
        if (idx >= 0) el.parentNode.children.splice(idx, 1);
      }}
    }},
  }};
  return el;
}}
for (const id of [
  'friend-requests-list', 'friend-requests-count', 'drawer-friends-badge',
  'prisons-catalog-grid', 'masters-catalog-grid', 'current-master-name',
  'current-master-subtitle', 'master-progress-text', 'master-progress-percent',
  'master-progress-fill', 'btn-master-train', 'btn-master-drain',
  'master-cycle-energy-info', 'news-list-container'
]) {{
  els[id] = makeEl(id);
}}

const sandbox = {{
  console, Math, Date, JSON, Array, Object, String, Number, Boolean, Set, Map, RegExp, Promise, URL, URLSearchParams,
  ASSET_VERSION: '20261127_16',
  currentPrisonId: 1,
  liveSlices: {{ data: {{}} }},
  domainRevisions: {{}},
  escapeHtml: (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
  formatNum: (n) => String(n ?? 0),
  formatCompactNumber: (n) => String(n ?? 0),
  formatMoscowTime: (s) => String(s ?? ''),
  gameIcon: (name) => `<img src="/static/assets/icons/${{name}}">`,
  setTextIfChanged: (el, val) => {{ if (el) el.textContent = String(val ?? ''); }},
  reconcileKeyedList: (container, items, keyFn, sigFn, createFn) => {{
    container.innerHTML = '';
    for (const item of items) {{
      container.appendChild(createFn(item));
    }}
  }},
  isSlowNetworkConnection: () => false,
  showToast: () => {{}},
  applyAuthQuery: (u) => String(u || ''),
  setTimeout: (fn) => {{ fn(); return 1; }},
  clearTimeout: () => {{}},
  navigator: {{}},
  location: {{ search: '', hostname: 'zvezdoed.space', origin: 'https://zvezdoed.space', pathname: '/prison/' }},
  IntersectionObserver: undefined,
  document: {{
    getElementById: (id) => els[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => makeEl('dyn'),
  }},
}};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext({json.dumps(extracted_js)}, sandbox);

// 1) Принятие 1 из 2 заявок не удаляет 2-ю заявку и ставит счетчик 1
vm.runInContext(`
  liveSlices.data.friend_requests = {{
    success: true,
    requests: [
      {{ userId: 101, nickname: 'First', authority: 100 }},
      {{ userId: 202, nickname: 'Second', authority: 200 }}
    ],
    total: 2
  }};
  renderFriendRequestsData(liveSlices.data.friend_requests);
  applySocialUpdatedEvent({{ accepted_ids: [101], revision: 2 }});
`, sandbox);

const frChildren = els['friend-requests-list'].children;
if (frChildren.length !== 1 || !frChildren[0].innerHTML.includes('Second')) {{
  throw new Error('Second friend request disappeared! children=' + frChildren.length);
}}
if (els['friend-requests-count'].textContent !== '1') {{
  throw new Error('Expected friend-requests-count === 1, got ' + els['friend-requests-count'].textContent);
}}

// 2) Все 15 тюрем + полная энергия тюрем и мастеров
vm.runInContext(`
  const fifteenPrisons = Array.from({{ length: 15 }}, (_, i) => ({{
    id: i + 1,
    name: 'Тюрьма ' + (i + 1),
    isUnlocked: i < 5,
    day_full_energy: 60 + i,
    day_remaining_energy: 60 + i,
    night_full_energy: 40 + i,
    night_remaining_energy: 25,
  }}));
  renderPrisonsGrid(fifteenPrisons);
  renderMastersSection([
    {{ id: 10, name: 'ПЕТЯ ВЕРСТАК', level: 1, full_cycle_energy: 50, remaining_cycle_energy: 20, step_energy: 2 }}
  ]);
`, sandbox);
if (els['prisons-catalog-grid'].children.length !== 15) {{
  throw new Error('Expected 15 prison cards, got ' + els['prisons-catalog-grid'].children.length);
}}
const prisonEnergyHtml = els['prisons-catalog-grid'].children[0]?.slots['.prison-tile-energy']?.innerHTML || '';
if (!prisonEnergyHtml.includes('60') || !prisonEnergyHtml.includes('40')) {{
  throw new Error('Prison full energy missing: ' + prisonEnergyHtml);
}}
const masterTileHtml = els['masters-catalog-grid'].children[0]?.slots['.master-tile-energy']?.innerHTML || '';
if (!masterTileHtml.includes('50')) {{
  throw new Error('Master full energy missing: ' + masterTileHtml);
}}
if (!els['master-cycle-energy-info'].innerHTML.includes('50')) {{
  throw new Error('Master energy info bar missing: ' + els['master-cycle-energy-info'].innerHTML);
}}

// 3) Новости (blockquote + lazy video + префикс /prison/)
const newsCardHtml = vm.runInContext(`
  renderNewsPostCard({{
    post_id: 77,
    published_at: '2026-11-27T12:00:00Z',
    views: '1.5K',
    html: '<b>Тест</b><blockquote>Цитата</blockquote>',
    media: [{{ id: 'm1', type: 'gif', url: '/api/v1/news/media/m1', poster_url: '/api/v1/news/media/p1' }}],
    url: 'https://t.me/itheprison/77'
  }}).innerHTML;
`, sandbox);
if (!newsCardHtml.includes('<blockquote>Цитата</blockquote>') || !newsCardHtml.includes('news-gif-video')) {{
  throw new Error('News render missing blockquote/video: ' + newsCardHtml);
}}
if (!newsCardHtml.includes('/prison/api/v1/news/media/m1') || !newsCardHtml.includes('/prison/api/v1/news/media/p1')) {{
  throw new Error('News media missing /prison/ prefix: ' + newsCardHtml);
}}
console.log('ALL_JS_SMOKES_OK');
"""
    proc = subprocess.run(["node"], input=node_script, capture_output=True, text=True, encoding="utf-8", check=False)
    assert proc.returncode == 0, f"Node smoke failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    assert "ALL_JS_SMOKES_OK" in proc.stdout


@pytest.mark.asyncio
async def test_live_prisons_returns_all_15_and_master_cycle_energy():
    mock_prison_api = AsyncMock()
    mock_prison_api.get_all_prisons = AsyncMock(return_value={
        "prisons": [{"id": i, "name": f"Тюрьма {i}", "isUnlocked": i <= 5} for i in range(1, 16)]
    })
    mock_prison_api.get_masters = AsyncMock(return_value={
        "masters": [{"id": 1, "name": "ПЕТЯ ВЕРСТАК"}, {"id": 2, "name": "ЯША В ПОЛЕДЫМ"}]
    })
    mock_prison_api.get_prison_state = AsyncMock(return_value={"data": {"dayRuns": 1, "nightRuns": 0}})
    mock_prison_api.get_checkpoints = AsyncMock(return_value={"data": [{"checkpointId": 1, "clicksRequired": 5, "energyCost": 2}]})

    async def _enter_master(mid):
        if mid == 1:
            return {
                "success": True,
                "data": {"masterId": 1, "progress": {"currentCheckpoint": 0, "clicksInCheckpoint": 0, "level": 1}},
                "checkpoints": [{"checkpointId": 1, "clicksRequired": 5, "energyCost": 3}],
            }
        return {"success": False, "locked": True}

    mock_prison_api.enter_master = AsyncMock(side_effect=_enter_master)
    orig_api = bot_context.prison_api
    bot_context.prison_api = mock_prison_api
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/live/prisons?force=true", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert len(data["prisons"]) == 15
            assert data["prisons"][0]["day_full_energy"] == 10
            assert data["masters"][0]["full_cycle_energy"] == 15
            assert data["masters"][1]["locked"] is True
    finally:
        bot_context.prison_api = orig_api




def test_js_runtime_timers_clock_skew_and_no_interval_leak():
    import subprocess
    from pathlib import Path

    app_txt = Path("web/static/app.js").read_text(encoding="utf-8")
    clock_block = app_txt[app_txt.index("let serverClockOffsetMs = 0;"):app_txt.index("async function apiFetch")]
    fmt_block = app_txt[app_txt.index("function formatCountdown(totalSeconds"):app_txt.index("// ============================================================================\n// 4. DATA LOADERS")]
    menyala_block = app_txt[app_txt.index("let _menyalaLastState = null;"):app_txt.index("async function loadMenyalaState()")]
    zaruby_block = app_txt[app_txt.index("let _zarubySelectedTaskId = null;"):app_txt.index("async function loadZarubyState()")]

    script = f"""
const elements = {{}};
const makeEl = (id) => {{
  if (!elements[id]) {{
    elements[id] = {{
      id, textContent: '', innerHTML: '', value: '1', disabled: false, title: '', style: {{}},
      classList: {{ add(){{}}, remove(){{}}, contains(){{ return false; }} }},
      selectedOptions: [], addEventListener(){{}}, querySelector(){{ return null; }}, querySelectorAll(){{ return []; }},
    }};
  }}
  return elements[id];
}};
global.document = {{ getElementById: (id) => makeEl(id) }};
function setTextIfChanged(el, t) {{ if (el) el.textContent = String(t ?? ''); }}
function escapeHtml(s) {{ return String(s ?? ''); }}
function resolveAppAssetUrl(u) {{ return u; }}
function formatNum(n) {{ return String(n ?? 0); }}
function apiFetch() {{ return Promise.resolve({{}}); }}
function showToast() {{}}
function refreshState() {{}}
function renderRoutineGameBadges() {{}}

let intervalCount = 0;
global.setInterval = () => {{ intervalCount += 1; return intervalCount; }};

// Эмулируем браузер, у которого локальные часы спешат на +3 часа (+10800 сек)
const REAL_SERVER_NOW = 1795820000;
Date.now = () => (REAL_SERVER_NOW + 10800) * 1000;

{clock_block}
{fmt_block}
{zaruby_block}
{menyala_block}

syncServerClock(REAL_SERVER_NOW);
if (Math.abs(getSyncedNowSec() - REAL_SERVER_NOW) > 1) {{
  throw new Error('Clock sync failed for +3h skew: ' + getSyncedNowSec());
}}

// Меняла: до отъезда ровно 3600 сек (01:00:00), при повторных рендерах setInterval не создается
renderMenyalaState({{
  is_active: true,
  server_now_ts: REAL_SERVER_NOW,
  departure_ts: REAL_SERVER_NOW + 3600,
  departure_msk: '30.11 00:00 МСК',
  promos: [],
  exchanges: []
}});
renderMenyalaState({{
  is_active: true,
  server_now_ts: REAL_SERVER_NOW,
  departure_ts: REAL_SERVER_NOW + 3600,
  promos: [],
  exchanges: []
}});
if (elements['menyala-timer'].textContent !== 'До отъезда: 01:00:00') {{
  throw new Error('Unexpected menyala timer: ' + elements['menyala-timer'].textContent);
}}

// Зарубы: ровно 900 сек (00:15:00)
renderZarubyState({{
  success: true,
  state: {{
    active: true,
    end_unix: REAL_SERVER_NOW + 900,
    tasks: [],
    leaderboard: [],
    level: 4, signets: 8, ore_signet: 16
  }}
}});
if (elements['zaruby-timer'].textContent !== '00:15:00') {{
  throw new Error('Unexpected zaruby timer: ' + elements['zaruby-timer'].textContent);
}}

// Просроченный target_ts не должен давать NaN или отрицательные числа
if (formatCountdown(-50) !== '00:00:00' || formatCountdown(NaN) !== '00:00:00') {{
  throw new Error('formatCountdown negative/NaN guard failed');
}}
if (intervalCount !== 0) {{
  throw new Error('Unexpected extra setInterval created: ' + intervalCount);
}}
console.log('TIMERS_CLOCK_SYNC_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True, check=True)
    assert "TIMERS_CLOCK_SYNC_OK" in res.stdout


def test_obshak_icons_exist_and_js_runtime_friend_requests():
    import subprocess
    from pathlib import Path

    icons_dir = Path("web/static/assets/icons")
    for tier in ("pacan", "blat", "avtoritet", "vor"):
        p = icons_dir / f"obshak_{tier}.webp"
        assert p.exists() and p.stat().st_size > 200, f"Missing or invalid icon: {p}"

    app_txt = Path("web/static/app.js").read_text(encoding="utf-8")

    def _extract_fn(src: str, sig: str) -> str:
        idx = src.index(sig)
        brace_start = src.index("{", idx)
        depth = 0
        for pos in range(brace_start, len(src)):
            if src[pos] == "{":
                depth += 1
            elif src[pos] == "}":
                depth -= 1
                if depth == 0:
                    return src[idx : pos + 1]
        raise AssertionError(f"Unclosed: {sig}")

    reconcile_block = _extract_fn(app_txt, "function reconcileKeyedList(")
    key_block = _extract_fn(app_txt, "function getFriendRequestKey(")
    fr_block = "\n".join([
        'let _frFilterMode = "all";',
        'let _frSortMode = "default";',
        _extract_fn(app_txt, "function renderObshakBadgeHtml("),
        _extract_fn(app_txt, "function renderFriendRequestsData("),
    ])

    script = f"""
const elements = {{}};
const makeEl = (id) => {{
  if (!elements[id]) {{
    const children = [];
    elements[id] = {{
      id, textContent: '', innerHTML: '', value: 'default', style: {{}}, dataset: {{}},
      children,
      classList: {{ add(){{}}, remove(){{}}, replace(){{}}, contains(){{ return false; }} }},
      appendChild(c) {{ c.parentNode = elements[id]; children.push(c); return c; }},
      insertBefore(c, ref) {{
        c.parentNode = elements[id];
        const i = children.indexOf(ref);
        if (i >= 0) children.splice(i, 0, c);
        else children.push(c);
        return c;
      }},
      querySelectorAll() {{ return children.slice(); }},
      addEventListener() {{}},
    }};
  }}
  return elements[id];
}};
['friend-requests-list','friend-requests-obshak-count','friend-requests-count','drawer-friends-badge'].forEach(makeEl);
global.document = {{
  getElementById: (id) => elements[id] || null,
  querySelectorAll: () => [],
  querySelector: () => null,
  createElement: () => {{
    const attrs = {{}};
    const ch = {{
      className: '', innerHTML: '', style: {{}}, dataset: {{}}, parentNode: null,
      setAttribute(k, v) {{ attrs[k] = v; }},
      getAttribute(k) {{ return attrs[k]; }},
      querySelector() {{ return {{ addEventListener(){{}}, style: {{}}, disabled: false, textContent: '' }}; }},
      querySelectorAll() {{ return []; }},
      remove() {{
        if (ch.parentNode && ch.parentNode.children) {{
          const idx = ch.parentNode.children.indexOf(ch);
          if (idx >= 0) ch.parentNode.children.splice(idx, 1);
        }}
      }},
    }};
    return ch;
  }},
}};
function setTextIfChanged(el, t) {{ if (el) el.textContent = String(t ?? ''); }}
function escapeHtml(s) {{ return String(s ?? ''); }}
function resolveAppAssetUrl(u) {{ return u; }}
function formatNum(n) {{ return String(n ?? 0); }}
function gameIcon(k) {{ return k; }}
function bindFriendshipButtons() {{}}
const liveSlices = {{ data: {{}} }};

{reconcile_block}
{key_block}
{fr_block}

const sample = {{
  requests: [
    {{ userId: 1, nickname: 'NoObshak', level: 10, authority: 100, has_obshak: false, obshak_tier: 'none', obshak_rank: 0, obshak_label: '', obshak_icon: '' }},
    {{ userId: 2, nickname: 'PacanUser', level: 20, authority: 200, has_obshak: true, obshak_tier: 'pacan', obshak_rank: 1, obshak_label: 'Пацанский', obshak_icon: 'assets/icons/obshak_pacan.webp' }},
    {{ userId: 3, nickname: 'VorUser', level: 30, authority: 300, has_obshak: true, obshak_tier: 'vor', obshak_rank: 4, obshak_label: 'Воровской', obshak_icon: 'assets/icons/obshak_vor.webp' }},
  ]
}};

_frSortMode = 'obshak_desc';
_frFilterMode = 'all';
renderFriendRequestsData(sample);
const listEl = elements['friend-requests-list'];
if (listEl.children.length !== 3) throw new Error('Expected 3 cards, got ' + listEl.children.length);
if (listEl.children[0].getAttribute('data-user-id') !== '3') throw new Error('Expected VorUser first when sorted');
if (!listEl.children[0].innerHTML.includes('obshak_vor.webp')) throw new Error('Missing obshak_vor.webp');
if (!listEl.children[2].innerHTML.includes('Без общака')) throw new Error('Missing Без общака badge');
if (elements['friend-requests-obshak-count'].textContent !== '2') throw new Error('Expected obshak count 2');

_frFilterMode = 'obshak';
renderFriendRequestsData(sample);
if (listEl.children.length !== 2) throw new Error('Expected 2 cards after filter, got ' + listEl.children.length);
console.log('OBSHAK_JS_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "OBSHAK_JS_OK" in res.stdout


def test_js_runtime_monthly_rewards_and_accordion_sse_preserve():
    import subprocess
    from pathlib import Path

    app_txt = Path("web/static/app.js").read_text(encoding="utf-8")

    def _extract_fn(src: str, sig: str) -> str:
        idx = src.index(sig)
        brace_start = src.index("{", idx)
        depth = 0
        for pos in range(brace_start, len(src)):
            if src[pos] == "{":
                depth += 1
            elif src[pos] == "}":
                depth -= 1
                if depth == 0:
                    return src[idx : pos + 1]
        raise AssertionError(f"Unclosed: {sig}")

    toggle_fn = _extract_fn(app_txt, "function toggleMonthlyScheduleAccordion(")
    render_fn = _extract_fn(app_txt, "function renderMonthlyStateData(")

    script = f"""
const elements = {{}};
const makeEl = (id) => {{
  if (!elements[id]) {{
    const attrs = {{}};
    elements[id] = {{
      id, textContent: '', innerHTML: '', style: {{}}, disabled: false,
      setAttribute(k, v) {{ attrs[k] = String(v); }},
      getAttribute(k) {{ return attrs[k] || null; }},
      querySelector() {{ return null; }},
      querySelectorAll() {{ return []; }},
    }};
  }}
  return elements[id];
}};
['monthly-progress-text','monthly-rewards-ribbon','monthly-schedule-title','monthly-schedule-badge','monthly-schedule-tbody','monthly-schedule-accordion','monthly-schedule-body'].forEach(makeEl);
global.document = {{ getElementById: (id) => elements[id] || null }};
const liveSlices = {{ data: {{}} }};
function setTextIfChanged(el, t) {{ if (el) el.textContent = String(t ?? ''); }}
function escapeHtml(s) {{ return String(s ?? ''); }}
function resolveAppAssetUrl(u) {{ return u; }}
function formatNum(n) {{ return String(n ?? 0); }}
function apiFetch() {{ return Promise.resolve({{}}); }}
function showToast() {{}}
function refreshState() {{}}
let monthlyScheduleExpanded = false;
let _monthlyScrolledOnce = false;

{toggle_fn}
{render_fn}

const sample = {{
  success: true,
  year_month: '2026-11',
  month_label: 'Ноябрь 2026',
  completed_count: 7,
  total_days: 30,
  today_day: 28,
  today_task: {{ day_num: 28, title: 'Убей босса: Кирпич', progress: 1, target: 1 }},
  rewards: [
    {{ index: 0, tier: 2, required_count: 2, current_count: 7, title: 'Рубли', amount: 30, icon: 'assets/icons/rubles.webp', status: 'claimed', claimable: false }},
    {{ index: 1, tier: 5, required_count: 5, current_count: 7, title: 'Чифир', amount: 2, icon: 'assets/icons/energy.webp', status: 'claimable', claimable: true }},
    {{ index: 2, tier: 10, required_count: 10, current_count: 7, title: 'Самопал', amount: 70, icon: 'assets/icons/gunshot.webp', status: 'locked', claimable: false }},
  ],
  schedule: [
    {{ day_num: 27, date_label: '27.11', weekday: 'ПТ', title: 'Харкни 14 раз', progress: 14, target: 14, status: 'completed', is_today: false }},
    {{ day_num: 28, date_label: '28.11', weekday: 'СБ', title: 'Убей босса: Кирпич', progress: 1, target: 1, status: 'today', is_today: true }},
    {{ day_num: 29, date_label: '29.11', weekday: 'ВС', title: '', progress: 0, target: 0, status: 'upcoming', is_today: false }},
  ]
}};

renderMonthlyStateData(sample);
if (!elements['monthly-rewards-ribbon'].innerHTML.includes('Выполни <b>10</b> делюг')) throw new Error('missing reward tier 10');
if (!elements['monthly-rewards-ribbon'].innerHTML.includes('Забрать')) throw new Error('missing claim button');
if (!elements['monthly-schedule-tbody'].innerHTML.includes('Сегодня') || !elements['monthly-schedule-tbody'].innerHTML.includes('Откроется 29.11')) {{
  throw new Error('missing today highlight or future fallback');
}}
if (elements['monthly-schedule-tbody'].innerHTML.includes('undefined') || elements['monthly-schedule-tbody'].innerHTML.includes('NaN')) {{
  throw new Error('unexpected undefined/NaN in schedule');
}}

toggleMonthlyScheduleAccordion(true);
if (elements['monthly-schedule-body'].style.display !== 'block') throw new Error('accordion did not expand');

// Повторный рендер (SSE) обязан сохранить раскрытое состояние аккордеона
renderMonthlyStateData(sample);
if (elements['monthly-schedule-body'].style.display !== 'block' || elements['monthly-schedule-accordion'].getAttribute('data-expanded') !== 'true') {{
  throw new Error('SSE re-render collapsed accordion');
}}
console.log('MONTHLY_JS_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "MONTHLY_JS_OK" in res.stdout


def test_masters_cards_prisons_energy_and_xor_js_runtime():
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    script = f"""
const fs = require('fs');
const vm = require('vm');

function makeEl(id) {{
  const attrs = {{}};
  const listeners = {{}};
  return {{
    id,
    innerHTML: '',
    textContent: '',
    className: '',
    value: '',
    checked: false,
    disabled: false,
    title: '',
    dataset: {{}},
    style: {{}},
    children: [],
    classList: {{
      _set: new Set(),
      add(c) {{ this._set.add(c); }},
      remove(c) {{ this._set.delete(c); }},
      contains(c) {{ return this._set.has(c) || (this._parentClass || '').split(/\\s+/).includes(c); }},
    }},
    setAttribute(k, v) {{ attrs[k] = String(v); }},
    getAttribute(k) {{ return attrs[k] ?? null; }},
    addEventListener(ev, fn) {{ (listeners[ev] = listeners[ev] || []).push(fn); }},
    dispatchEvent(ev) {{
      const list = listeners[ev.type || ev] || [];
      for (const fn of list) fn(ev);
    }},
    querySelector(sel) {{
      if (sel === '.prison-tile-name' || sel === '.master-tile-name') return this._nameEl || (this._nameEl = makeEl());
      if (sel === '.prison-tile-lock' || sel === '.master-tile-lock') return this._lockEl || (this._lockEl = makeEl());
      if (sel === '.prison-tile-meta' || sel === '.master-tile-meta') return this._metaEl || (this._metaEl = makeEl());
      if (sel === '.prison-tile-energy' || sel === '.master-tile-energy') return this._energyEl || (this._energyEl = makeEl());
      return makeEl();
    }},
    querySelectorAll() {{ return []; }},
    appendChild(ch) {{ this.children.push(ch); }},
    insertBefore(ch) {{ this.children.push(ch); }},
    remove() {{}},
    closest() {{ return null; }},
  }};
}}

const elements = {{}};
const ids = [
  'prisons-catalog-grid', 'masters-catalog-grid', 'current-prison-name',
  'prison-checkpoint-text', 'prison-checkpoint-percent', 'prison-checkpoint-fill',
  'btn-prison-work-one', 'btn-shift-day', 'btn-shift-night',
  'current-master-name', 'current-master-subtitle', 'master-progress-text',
  'master-progress-percent', 'master-progress-fill', 'master-cycle-energy-info',
  'btn-master-train', 'btn-master-drain', 'cfg-auto_prison', 'cfg-auto_masters'
];
for (const id of ids) elements[id] = makeEl(id);

const sandbox = {{
  console, Math, Date, JSON, Number, String, Boolean, Array, Object, Set, Map, URLSearchParams,
  setTimeout: () => 0, clearTimeout: () => {{}}, setInterval: () => 0, clearInterval: () => {{}},
  localStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  sessionStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  location: {{ hash: '', search: '', pathname: '/', hostname: 'localhost' }},
  navigator: {{}},
  window: {{ addEventListener: () => {{}}, Telegram: {{ WebApp: {{ initData: '', ready: () => {{}}, expand: () => {{}} }} }} }},
  document: {{
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => makeEl(),
    addEventListener: () => {{}},
  }},
  fetch: async () => ({{ ok: true, status: 200, json: async () => ({{ success: true }}) }}),
  apiFetch: async () => ({{ success: true }}),
  showToast: () => {{}},
  refreshState: () => {{}},
  EventSource: function() {{ return {{ addEventListener: () => {{}}, close: () => {{}} }}; }},
}};
sandbox.globalThis = sandbox;
vm.runInNewContext({json.dumps(app_js)}, sandbox);

const masters = Array.from({{ length: 16 }}, (_, idx) => ({{
  id: idx + 1,
  name: idx === 0 ? 'ПЕТЯ ВЕРСТАК' : `МАСТЕР #${{idx + 1}}`,
  level: 1,
  locked: false,
  full_cycle_energy: 443 + idx * 10,
  remaining_cycle_energy: 443 + idx * 10,
  step_energy: 2,
  step_current: 0,
  step_total: 7,
  progress_pct: 0,
}}));

const prisons = [
  {{ id: 4, name: 'КРЕСТЫ', isUnlocked: true, dayRuns: 1, nightRuns: 1, day_full_energy: 519, night_full_energy: 635 }},
  {{ id: 5, name: 'В.ЦЕНТРАЛ', isUnlocked: true, dayRuns: 0, nightRuns: 0, day_full_energy: 675, night_full_energy: 848 }},
];

sandbox.renderPrisonsData({{
  success: true,
  targetId: 4,
  targetMasterId: 1,
  isDay: true,
  prisons,
  masters,
  checkpoints: [],
}});

const pGrid = elements['prisons-catalog-grid'];
if (pGrid.children.length !== 2) throw new Error('expected 2 prisons');
if (!pGrid.children[0]._energyEl.innerHTML.includes('519') || !pGrid.children[0]._energyEl.innerHTML.includes('635')) {{
  throw new Error('Kresty energy missing');
}}

// Повторный рендер с обнуленными значениями (частичный SSE) не должен стирать цифры
sandbox.renderPrisonsData({{
  success: true,
  targetId: 4,
  targetMasterId: 1,
  isDay: true,
  prisons: [
    {{ id: 4, name: 'КРЕСТЫ', isUnlocked: true, dayRuns: 1, nightRuns: 1, day_full_energy: 0, night_full_energy: 0 }},
    {{ id: 5, name: 'В.ЦЕНТРАЛ', isUnlocked: true, dayRuns: 0, nightRuns: 0, day_full_energy: 675, night_full_energy: 0 }},
  ],
  masters: masters.map(m => Object.assign({{}}, m, {{ full_cycle_energy: 0 }})),
  checkpoints: [],
}});
if (!pGrid.children[0]._energyEl.innerHTML.includes('519') || !pGrid.children[1]._energyEl.innerHTML.includes('848')) {{
  throw new Error('SSE partial update wiped prison energy');
}}

const mGrid = elements['masters-catalog-grid'];
if (mGrid.children.length !== 16) throw new Error('expected 16 master cards, got ' + mGrid.children.length);
if (!mGrid.children[15]._energyEl.innerHTML.includes('593')) {{
  throw new Error('Master 16 energy missing');
}}

// Клик по карточке мастера 2 выбирает его и обновляет верхнюю панель
mGrid.children[1].dispatchEvent({{ type: 'click' }});
if (!elements['current-master-name'].textContent.includes('МАСТЕР #2')) {{
  throw new Error('clicking master card did not update top panel');
}}

// Проверка XOR тумблеров на фронтенде
elements['cfg-auto_prison'].checked = true;
elements['cfg-auto_masters'].checked = true;
elements['cfg-auto_masters'].dispatchEvent({{ type: 'change' }});
if (elements['cfg-auto_prison'].checked !== false) {{
  throw new Error('auto_masters=true did not uncheck auto_prison');
}}
elements['cfg-auto_prison'].checked = true;
elements['cfg-auto_prison'].dispatchEvent({{ type: 'change' }});
if (elements['cfg-auto_masters'].checked !== false) {{
  throw new Error('auto_prison=true did not uncheck auto_masters');
}}

console.log('MASTERS_XOR_JS_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "MASTERS_XOR_JS_OK" in res.stdout


def test_raids_clean_ui_and_outreach_criteria_panel_js_runtime():
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    assert "Закрытый источник рейдов @pro_prison_bot" not in html
    assert "raids-source-banner" not in html
    assert "Закрытый источник рейдов @pro_prison_bot" not in app_js
    assert "Источник ProPrisonBot" not in app_js
    assert 'id="outreach-criteria-accordion"' in html
    assert 'id="btn-save-outreach-criteria"' in html
    assert 'id="btn-run-outreach-now"' in html

    script = f"""
const vm = require('vm');
function makeEl(id) {{
  const attrs = {{}};
  const listeners = {{}};
  return {{
    id,
    innerHTML: '',
    textContent: '',
    className: '',
    value: '',
    checked: false,
    disabled: false,
    dataset: {{}},
    style: {{}},
    children: [],
    classList: {{
      _set: new Set(['active']),
      add(c) {{ this._set.add(c); }},
      remove(c) {{ this._set.delete(c); }},
      toggle(c, f) {{ if (f === undefined) {{ if (this._set.has(c)) this._set.delete(c); else this._set.add(c); }} else if (f) this._set.add(c); else this._set.delete(c); }},
      contains(c) {{ return this._set.has(c); }},
    }},
    setAttribute(k, v) {{ attrs[k] = String(v); }},
    getAttribute(k) {{ return attrs[k] ?? null; }},
    addEventListener(ev, fn) {{ (listeners[ev] = listeners[ev] || []).push(fn); }},
    dispatchEvent(ev) {{ const evtObj = {{ target: this, ...ev }}; for (const fn of (listeners[ev.type || ev] || [])) fn(evtObj); }},
    querySelector() {{ return makeEl(); }},
    querySelectorAll() {{ return []; }},
    appendChild(ch) {{ this.children.push(ch); }},
    remove() {{}},
    closest() {{ return null; }},
  }};
}}
const ids = [
  'outreach-criteria-accordion', 'outreach-criteria-toggle', 'outreach-criteria-body',
  'outreach-criteria-arrow', 'outreach-criteria-summary', 'outreach-telemetry-line',
  'outreach-min-damage', 'outreach-max-damage', 'outreach-min-authority', 'outreach-max-authority',
  'outreach-daily-limit', 'outreach-sort-by', 'outreach-exclude-keywords',
  'raids-auto-invite-toggle', 'raids-auto-invite-status', 'unified-raids-players-list',
  'btn-save-outreach-criteria', 'btn-run-outreach-now'
];
const elements = Object.fromEntries(ids.map(id => [id, makeEl(id)]));
const sandbox = {{
  console, Math, Date, JSON, Number, String, Boolean, Array, Object, Set, Map, URLSearchParams,
  setTimeout: () => 0, clearTimeout: () => {{}}, setInterval: () => 0, clearInterval: () => {{}},
  localStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  sessionStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  location: {{ hash: '', search: '', pathname: '/', hostname: 'localhost' }},
  navigator: {{}},
  window: {{ addEventListener: () => {{}}, Telegram: {{ WebApp: {{ initData: '', ready: () => {{}}, expand: () => {{}} }} }} }},
  document: {{
    activeElement: null,
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => makeEl(),
    addEventListener: () => {{}},
  }},
  fetch: async () => ({{ ok: true, status: 200, json: async () => ({{ success: true }}) }}),
  apiFetch: async () => ({{ success: true }}),
  showToast: () => {{}},
  refreshState: () => {{}},
  EventSource: function() {{ return {{ addEventListener: () => {{}}, close: () => {{}} }}; }},
}};
sandbox.globalThis = sandbox;
vm.runInNewContext({json.dumps(app_js)}, sandbox);

sandbox.toggleOutreachCriteriaAccordion(true);
if (elements['outreach-criteria-body'].style.display !== 'flex') throw new Error('accordion did not open');

sandbox.renderUnifiedRaidsPlayers({{
  success: true,
  sent_24h: 7,
  daily_limit: 50,
  matched_count: 12,
  worker_status: 'Активен',
  criteria: {{ enabled: true, daily_limit: 50, min_damage: 1000000, max_damage: 0, min_authority: 0, max_authority: 0, sort_by: 'damage', sources: ['weekly_top'], exclude_keywords: '' }},
  players: [{{ userId: 101, nickname: 'Боец', damage: 2000000, authority: 500, source: 'weekly_top', status: 'none', matchesCriteria: true }}],
}});

if (!elements['raids-auto-invite-status'].textContent.includes('7/50')) throw new Error('status counter not rendered');
if (!elements['raids-auto-invite-status'].textContent.includes('12')) throw new Error('matched_count not rendered');
if (elements['outreach-criteria-body'].style.display !== 'flex') throw new Error('SSE re-render collapsed criteria accordion');
console.log('OUTREACH_UI_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "OUTREACH_UI_OK" in res.stdout


def test_outreach_reactive_filtering_dirty_state_and_dark_inputs_js():
    import json
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    css = (root / "web" / "static" / "styles.css").read_text(encoding="utf-8")
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    # Проверка темных стилей инпутов (без белого фона)
    assert "#outreach-criteria-accordion input[type=\"number\"]" in css
    assert "background-color: #161822;" in css

    script = f"""
const vm = require('vm');
function makeEl(id) {{
  const attrs = {{}};
  const listeners = {{}};
  return {{
    id,
    innerHTML: '',
    textContent: '',
    className: '',
    value: '',
    checked: false,
    disabled: false,
    dataset: {{}},
    style: {{}},
    children: [],
    classList: {{
      _set: new Set(['active']),
      add(c) {{ this._set.add(c); }},
      remove(c) {{ this._set.delete(c); }},
      toggle(c, f) {{ if (f === undefined) {{ if (this._set.has(c)) this._set.delete(c); else this._set.add(c); }} else if (f) this._set.add(c); else this._set.delete(c); }},
      contains(c) {{ return this._set.has(c); }},
    }},
    setAttribute(k, v) {{ attrs[k] = String(v); }},
    getAttribute(k) {{ return attrs[k] ?? null; }},
    addEventListener(ev, fn) {{ (listeners[ev] = listeners[ev] || []).push(fn); }},
    dispatchEvent(ev) {{ const evtObj = {{ target: this, ...ev }}; for (const fn of (listeners[ev.type || ev] || [])) fn(evtObj); }},
    querySelector() {{ return makeEl(); }},
    querySelectorAll() {{ return []; }},
    appendChild(ch) {{ this.children.push(ch); }},
    remove() {{}},
    closest() {{ return null; }},
  }};
}}
const ids = [
  'outreach-criteria-accordion', 'outreach-criteria-toggle', 'outreach-criteria-body',
  'outreach-criteria-arrow', 'outreach-criteria-summary', 'outreach-telemetry-line',
  'outreach-min-damage', 'outreach-max-damage', 'outreach-min-authority', 'outreach-max-authority',
  'outreach-daily-limit', 'outreach-sort-by', 'outreach-exclude-keywords',
  'outreach-dirty-badge', 'btn-save-outreach-criteria', 'btn-run-outreach-now',
  'raids-auto-invite-toggle', 'raids-auto-invite-status', 'unified-raids-players-list',
  'raids-players-search', 'raids-players-sort', 'raids-players-source', 'raids-apply-criteria'
];
const elements = Object.fromEntries(ids.map(id => [id, makeEl(id)]));
elements['raids-apply-criteria'].checked = true;

const chipEls = ['weekly_top', 'achievements', 'tg_raids', 'brigades'].map(s => {{
  const c = makeEl('chip-' + s);
  c.setAttribute('data-source', s);
  return c;
}});

const sandbox = {{
  console, Math, Date, JSON, Number, String, Boolean, Array, Object, Set, Map, URLSearchParams,
  setTimeout: () => 0, clearTimeout: () => {{}}, setInterval: () => 0, clearInterval: () => {{}},
  localStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  sessionStorage: {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }},
  location: {{ hash: '', search: '', pathname: '/', hostname: 'localhost' }},
  navigator: {{}},
  window: {{ addEventListener: () => {{}}, Telegram: {{ WebApp: {{ initData: '', ready: () => {{}}, expand: () => {{}} }} }} }},
  document: {{
    activeElement: null,
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    querySelectorAll: (sel) => {{
      if (sel === '#outreach-sources-chips .outreach-chip') return chipEls;
      if (sel === '#outreach-sources-chips .outreach-chip.active') return chipEls.filter(c => c.classList.contains('active'));
      return [];
    }},
    createElement: () => makeEl(),
    addEventListener: () => {{}},
  }},
  fetch: async () => ({{ ok: true, status: 200, json: async () => ({{ success: true }}) }}),
  apiFetch: async () => ({{ success: true, players: [] }}),
  showToast: () => {{}},
  refreshState: () => {{}},
  EventSource: function() {{ return {{ addEventListener: () => {{}}, close: () => {{}} }}; }},
}};
sandbox.globalThis = sandbox;
vm.runInNewContext({json.dumps(app_js)}, sandbox);

sandbox.toggleOutreachCriteriaAccordion(true);
sandbox.renderUnifiedRaidsPlayers({{
  success: true,
  sent_24h: 15,
  daily_limit: 50,
  matched_count: 3,
  source_counts: {{ weekly_top: 10, achievements: 5, tg_raids: 2, brigades: 1 }},
  criteria: {{ enabled: true, daily_limit: 50, min_damage: 0, max_damage: 0, min_authority: 0, max_authority: 0, sort_by: 'fresh', sources: ['weekly_top', 'achievements', 'tg_raids', 'brigades'], exclude_keywords: '' }},
  players: [
    {{ userId: 1, nickname: 'WeeklyUser', damage: 50000000, authority: 1000, source: 'weekly_top', source_label: 'Топ недели', sources: ['weekly_top'], outreach_status: 'matched', matches_criteria: true }},
    {{ userId: 2, nickname: 'TgUser', damage: 200000, authority: 500, source: 'tg_raids', source_label: 'TG-каналы', sources: ['tg_raids'], outreach_status: 'matched', matches_criteria: true }},
    {{ userId: 3, nickname: 'ОПГ Bad', damage: 30000000, authority: 900, source: 'tg_raids', source_label: 'TG-каналы', sources: ['tg_raids'], outreach_status: 'matched', matches_criteria: true }},
  ],
}});

// 1. Оставляем только чип tg_raids -> таблица мгновенно фильтруется, аккордеон показывает Источников: 1, dirty=true
chipEls[0].dispatchEvent({{ type: 'click' }}); // off weekly_top
chipEls[1].dispatchEvent({{ type: 'click' }}); // off achievements
chipEls[3].dispatchEvent({{ type: 'click' }}); // off brigades
const htmlTg = elements['unified-raids-players-list'].innerHTML;
if (htmlTg.includes('WeeklyUser') || !htmlTg.includes('TgUser')) throw new Error('source chip did not filter table');
if (!elements['outreach-criteria-summary'].textContent.includes('Источников: 1')) throw new Error('summary not updated');
if (elements['outreach-dirty-badge'].style.display !== 'inline-block') throw new Error('dirty badge not shown');

// 2. Ввод исключения ОПГ скрывает ОПГ Bad мгновенно
elements['outreach-exclude-keywords'].value = 'ОПГ';
elements['outreach-exclude-keywords'].dispatchEvent({{ type: 'input' }});
if (elements['unified-raids-players-list'].innerHTML.includes('ОПГ Bad')) throw new Error('exclude_keywords did not filter');

// 3. Поиск по нику/ID
elements['raids-players-search'].value = 'TgUser';
elements['raids-players-search'].dispatchEvent({{ type: 'input' }});
if (!elements['unified-raids-players-list'].innerHTML.includes('TgUser')) throw new Error('search filtered out valid user');

// 4. SSE-апдейт при outreachCriteriaDirty=true не сбрасывает выбранный чип tg_raids и открытый аккордеон
sandbox.applyOutreachStatusData({{
  sent_24h: 16,
  daily_limit: 50,
  criteria: {{ enabled: true, daily_limit: 50, min_damage: 0, max_damage: 0, min_authority: 0, max_authority: 0, sort_by: 'fresh', sources: ['weekly_top', 'achievements', 'tg_raids', 'brigades'], exclude_keywords: '' }},
}});
if (!elements['outreach-criteria-summary'].textContent.includes('Источников: 1')) throw new Error('SSE wiped dirty draft criteria');
if (elements['outreach-criteria-body'].style.display !== 'flex') throw new Error('SSE closed accordion');

console.log('REACTIVE_OUTREACH_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "REACTIVE_OUTREACH_OK" in res.stdout


@pytest.mark.asyncio
async def test_friends_audit_sort_conversion_and_raids_obshak_brigades_api(tmp_path):
    """Проверка sort_by=conversion_desc/asc, /raids/brigades/scan, /raids/players/check-obshak и общак-фильтра."""
    from datetime import datetime
    from unittest.mock import AsyncMock, MagicMock
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import create_async_engine

    from core.database import get_session, init_db
    from core.models import FriendStats
    from web.app import app
    from web.routes import _flight_cache, bot_context, _get_hub

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audit_brigades.db'}")
    await init_db(engine)
    _flight_cache.invalidate()

    async with get_session(engine) as session:
        session.add(FriendStats(
            account_id=1, user_id=101, nickname="OlegTop", photo_url="assets/avatars/default.png",
            level=20, authority=5000, total_damage_to_my_bosses=500000, boss_hits_count=10,
            is_current_friend=True, first_seen_at=datetime.utcnow(), last_active_at=datetime.utcnow(),
        ))
        session.add(FriendStats(
            account_id=1, user_id=102, nickname="AlexZero", photo_url="assets/avatars/default.png",
            level=10, authority=1000, total_damage_to_my_bosses=0, boss_hits_count=0,
            is_current_friend=True, first_seen_at=datetime.utcnow(), last_active_at=datetime.utcnow(),
        ))
        await session.commit()

    mock_social = MagicMock()
    mock_social.get_recruitment_list = AsyncMock(return_value=[{"guildId": 348, "name": "LEPREKON_ZM"}])
    mock_social.get_guild_members = AsyncMock(return_value=[
        {"userId": 8801, "nickname": "VorRaider", "activityRating": 12000, "campActivity": {"damage": 90000}},
        {"userId": 8802, "nickname": "NoObRaider", "activityRating": 3000, "campActivity": {"damage": 10000}},
    ])
    mock_player = MagicMock()
    mock_player.get_me = AsyncMock(return_value={"id": 999999})
    mock_player.get_player_view = AsyncMock(side_effect=[
        {"userId": 8801, "vpiTier": "vorovskoy"},
        {"userId": 8802, "vpiTier": None},
    ])

    old_engine = bot_context.db_engine
    old_social = bot_context.social_api
    old_player = bot_context.player_api
    try:
        bot_context.db_engine = engine
        bot_context.social_api = mock_social
        bot_context.player_api = mock_player
        _get_hub().invalidate_slice(1, "friends_stats")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r_desc = await ac.get("/api/v1/friends/audit?sort_by=conversion_desc&force=true", headers=AUTH_HEADERS)
            assert r_desc.status_code == 200
            d_desc = r_desc.json()
            assert [f["userId"] for f in d_desc["friends"]] == [101, 102]

            r_asc = await ac.get("/api/v1/friends/audit?sort_by=conversion_asc&force=true", headers=AUTH_HEADERS)
            assert r_asc.status_code == 200
            assert [f["userId"] for f in r_asc.json()["friends"]] == [102, 101]

            r_scan = await ac.post("/api/v1/raids/brigades/scan", json={"top_brigades_limit": 5}, headers=AUTH_HEADERS)
            assert r_scan.status_code == 200
            assert r_scan.json()["players_saved"] == 2

            r_ob = await ac.post("/api/v1/raids/players/check-obshak", json={"user_ids": [8801, 8802], "max_profiles": 5}, headers=AUTH_HEADERS)
            assert r_ob.status_code == 200
            assert r_ob.json()["with_obshak"] == 1

            r_pl = await ac.get("/api/v1/raids/players?sources=brigades&obshak_filter=vor&apply_criteria=true", headers=AUTH_HEADERS)
            assert r_pl.status_code == 200
            pl_data = r_pl.json()
            assert pl_data["source_counts"]["brigades"] == 2
            assert len(pl_data["players"]) == 1
            assert pl_data["players"][0]["userId"] == 8801
            assert pl_data["players"][0]["obshak_type"] == "vor"
            assert pl_data["players"][0]["brigade_name"] == "LEPREKON_ZM"
            assert pl_data["obshak_coverage"]["total"] == 2
            assert pl_data["obshak_coverage"]["checked"] == 2

            r_st = await ac.get("/api/v1/outreach/status", headers=AUTH_HEADERS)
            assert r_st.status_code == 200
            assert r_st.json()["obshak_coverage"]["by_type"]["vor"] == 1
    finally:
        bot_context.db_engine = old_engine
        bot_context.social_api = old_social
        bot_context.player_api = old_player
        await engine.dispose()


def test_audit_nickname_onerror_and_conversion_sort_in_js():
    """Node.js runtime test: onerror on avatar img never wipes .fa-nick, and conversion_desc/asc sorting works."""
    import re
    import subprocess
    from pathlib import Path

    app_js = Path("web/static/app.js").read_text(encoding="utf-8")
    assert '<span class="fa-avatar-wrap"><img' in app_js
    assert "conversion_desc" in app_js and "conversion_asc" in app_js

    m_sort = re.search(r"function filterAndSortAuditFriends\(friends, filterStatus, searchText, sortKey\) \{[\s\S]*?\n\}", app_js)
    assert m_sort, "filterAndSortAuditFriends not found"

    script = f"""
{m_sort.group(0)}
const list = [
  {{ userId: 1, nickname: 'OlegTop', status: 'active', conversionPct: 80.0, totalDamageToMyBosses: 500000, bossHitsCount: 5, daysInactive: 0 }},
  {{ userId: 2, nickname: 'AlexZero', status: 'candidate', conversionPct: 0.0, totalDamageToMyBosses: 0, bossHitsCount: 0, daysInactive: 10 }},
];
const desc = filterAndSortAuditFriends(list, 'all', '', 'conversion_desc');
if (desc[0].userId !== 1) throw new Error('conversion_desc failed');
const asc = filterAndSortAuditFriends(list, 'all', '', 'conversion_asc');
if (asc[0].userId !== 2) throw new Error('conversion_asc failed');
console.log('AUDIT_JS_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "AUDIT_JS_OK" in res.stdout


def test_limit_banner_removed_and_obshak_coverage_ui():
    """Проверка удаления плашки лимита 24ч и работы updateObshakCoverageUI в JS."""
    import re
    import subprocess
    from pathlib import Path

    html = Path("web/static/index.html").read_text(encoding="utf-8")
    assert "raids-safety-limit-text" not in html
    assert "raids-safety-circuit-badge" not in html
    assert "obshak-coverage-pill" in html

    app_js = Path("web/static/app.js").read_text(encoding="utf-8")
    m_cov = re.search(r"function updateObshakCoverageUI\(cov, inProgressFlag\) \{[\s\S]*?\n\}", app_js)
    assert m_cov, "updateObshakCoverageUI not found"

    script = f"""
const pill = {{ textContent: '', classList: {{ _s: new Set(), remove(...a){{a.forEach(x=>this._s.delete(x));}}, add(x){{this._s.add(x);}} }} }};
const optVor = {{ value: 'vor', textContent: 'Воровской' }};
const sel = {{ options: [optVor] }};
const document = {{ getElementById: (id) => id === 'obshak-coverage-pill' ? pill : (id === 'raids-players-obshak' ? sel : null) }};
{m_cov.group(0)}
updateObshakCoverageUI({{ total: 10, checked: 6, unknown: 4, in_progress: true, by_type: {{ vor: 3 }} }}, true);
if (!pill.textContent.includes('6/10')) throw new Error('expected 6/10, got ' + pill.textContent);
if (!optVor.textContent.includes('(3)')) throw new Error('expected (3), got ' + optVor.textContent);
updateObshakCoverageUI({{ total: 10, checked: 10, unknown: 0, in_progress: false, by_type: {{ vor: 4 }} }}, false);
if (!pill.textContent.includes('все 10 проверены')) throw new Error('expected all checked, got ' + pill.textContent);
console.log('COVERAGE_UI_OK');
"""
    res = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed: {res.stderr}\n{res.stdout}"
    assert "COVERAGE_UI_OK" in res.stdout
