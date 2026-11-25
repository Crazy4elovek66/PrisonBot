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
    assert "prisonbot-assets-v11" in sw
    assert "skipWaiting" in sw
    assert "clients.claim" in sw
    assert "isCacheableAssetResponse" in sw
    assert "resp.ok" in sw

    # Синхронность версий в index.html, app.js и sw.js
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'const ASSET_VERSION = "20261125_16";' in js
    for icon_name in ("cigarettes.webp", "rubles.webp", "sugar.webp", "soap.webp"):
        assert f"/static/assets/icons/{icon_name}?v=20261125_16" in index_html

    # Проверка меню навигации и блока активного боя в index.html
    for expected_snippet in (
        'src="assets/icons/boss.webp?v=20261125_16"',
        'src="assets/icons/room_reward.webp?v=20261125_16"',
        'src="assets/icons/complect.webp?v=20261125_16"',
        'src="assets/icons/podogrev.webp?v=20261125_16"',
        'src="assets/icons/authority.webp?v=20261125_16"',
        'id="boss-title"><img class="boss-battle-icon" src="assets/icons/boss.webp?v=20261125_16"',
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
        "static/assets/icons/sugar.webp?v=20261125_16",
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
        + "    if (r1.includes('v=20261125_16')) throw new Error('Proxy url polluted with v=: ' + r1);\n"
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
        + "    if (!r1.includes('v=20261125_16')) throw new Error('Missing icon version: ' + r1);\n"
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
        for url in (f"/assets/icons/{name}", f"/static/assets/icons/{name}?v=20261125_16"):
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
        'const ASSET_VERSION = "20261125_16";',
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
const titleEl = makeEl("boss-title", "", '<img class="boss-battle-icon" src="assets/icons/boss.webp?v=20261125_16" alt="Босс"> <span id="boss-title-text">Поиск активного рейда...</span>');
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
if (!titleEl.innerHTML.includes("assets/icons/boss.webp?v=20261125_16")) throw new Error("Missing boss icon in title");
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
