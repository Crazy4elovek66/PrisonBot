import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from core.database import get_engine, init_db, get_session
from core.models import Account, BotConfig
from web.app import app
from bot.handlers import bot_context
from client.api.player import PlayerAPI
from core.config import settings
from web.routes import _is_blind_kolsik, _build_wardrobe_sets, _calc_wardrobe_summary


@pytest_asyncio.fixture
async def wardrobe_setup(monkeypatch):
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)

    monkeypatch.setattr(settings, "WEB_ADMIN_TOKEN", "test_admin_token")

    async with get_session(engine) as session:
        acc = Account(id=1, phone="+79998887766", nickname="TattooBoss")
        session.add(acc)
        await session.flush()
        cfg = BotConfig(account_id=acc.id, is_paused=False)
        session.add(cfg)

    bot_context.db_engine = engine
    bot_context._boss_api = None
    bot_context._player_api = None
    bot_context._prison_api = None
    bot_context._social_api = None
    bot_context.boss_worker = None
    bot_context.routine_worker = None
    bot_context.prison_worker = None
    bot_context.social_worker = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, engine

    bot_context.db_engine = None
    bot_context._boss_api = None
    bot_context._player_api = None
    bot_context._prison_api = None
    bot_context._social_api = None
    bot_context.boss_worker = None
    bot_context.routine_worker = None
    bot_context.prison_worker = None
    bot_context.social_worker = None
    await engine.dispose()


def test_is_blind_kolsik_separation():
    """Тест строгого критерия отделения предметов Слепого кольщика от основных сетов."""
    # Слепой кольщик: описание или путь к картинке kolsik / Skull
    assert _is_blind_kolsik({"description": "Награда слепого кольщика"}) is True
    assert _is_blind_kolsik({"sourceDescription": "Выпадает у Слепого Кольщика"}) is True
    assert _is_blind_kolsik({"rewardPreviewUrl": "https://cdn.online/assets/kolsik.png"}) is True
    assert _is_blind_kolsik({"imageUrl": "https://cdn.online/assets/Tattoos/Kolsik/tattoo_1.png"}) is True
    assert _is_blind_kolsik({"imageUrl": "https://cdn.online/assets/Tattoos/Skull/skull_7.png"}) is True

    # Обычные сеты: боссы, тюрьмы, события, магазины
    assert _is_blind_kolsik({"name": "Крест", "description": "Победа над боссом Кирпич"}) is False
    assert _is_blind_kolsik({"sourceDescription": "Дроп с тюрьмы Кресты", "imageUrl": "https://cdn.online/assets/Tattoos/Cross.png"}) is False
    assert _is_blind_kolsik({"name": "Куртка кожаная", "description": "Покупка за рубли"}) is False


@pytest.mark.asyncio
async def test_wardrobe_overview_api(wardrobe_setup):
    """
    Проверка GET /api/v1/wardrobe/overview:
    - корректная группировка по сетам
    - строгое отсутствие дубликатов между regular и blind_kolsik
    - расчет summaryStats (collected, missing, special)
    - наличие камер и characterLayers
    """
    client, engine = wardrobe_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.init_player = AsyncMock(return_value={
        "tattooZones": {"1": {"tattooId": 101, "imageUrl": "https://cdn/t101.png"}},
        "clothingZones": {"2": {"clothingId": 201, "imageUrl": "https://cdn/c201.png"}},
        "clothingFrontIds": {"2": 201},
        "face": {"eyesUrl": "https://cdn/eyes.png"},
        "beardPhase": 3,
        "roomCameraUrl": "https://cdn/camera_1.png",
    })
    mock_player.get_wardrobe_inventory = AsyncMock(return_value={
        "ownedTattoos": [101, 102],
        "ownedClothing": [201],
        "ownedCameras": [1, 2],
    })
    mock_player.get_cameras = AsyncMock(return_value={
        "cameras": [
            {"id": 1, "name": "Обычная камера", "price": 0, "currency": "rubles", "imageUrl": "https://cdn/camera_1.png"},
            {"id": 2, "name": "Люкс камера", "price": 500, "currency": "rubles", "imageUrl": "https://cdn/camera_2.png"},
            {"id": 3, "name": "Золотая камера", "price": 1000, "currency": "rubles", "imageUrl": "https://cdn/camera_3.png"},
        ]
    })
    # Каталог татуировок: 2 в обычном сете, 1 в сете слепого кольщика
    mock_player.get_tattoos_catalog = AsyncMock(return_value=[
        {
            "id": 101,
            "setName": "Сет Авторитета",
            "name": "Наколка на грудь",
            "zone": 1,
            "description": "Босс Борз",
            "combat_stats_bonus": {"knife": 10, "energy": 5},
            "price": 0,
            "currency": "",
        },
        {
            "id": 102,
            "setName": "Сет Авторитета",
            "name": "Наколка на спину",
            "zone": 2,
            "description": "Босс Борз",
            "combat_stats_bonus": {"knife": 15, "energy": 5},
            "price": 100,
            "currency": "rubles",
        },
        {
            "id": 901,
            "setName": "Слепой Череп",
            "name": "Череп Кольщика",
            "zone": 3,
            "description": "Выпадает у слепого кольщика",
            "combat_stats_bonus": {"poison": 30},
            "price": 0,
            "currency": "",
        },
    ])
    # Каталог одежды
    mock_player.get_clothing_catalog = AsyncMock(return_value=[
        {
            "id": 201,
            "setName": "Спортивный костюм",
            "name": "Олимпийка",
            "zone": 2,
            "description": "Магазин одежды",
            "combat_stats_bonus": {"gunshot": 20},
            "price": 50,
            "currency": "rubles",
        },
        {
            "id": 202,
            "setName": "Спортивный костюм",
            "name": "Штаны",
            "zone": 3,
            "description": "Магазин одежды",
            "combat_stats_bonus": {"gunshot": 25},
            "price": 60,
            "currency": "rubles",
        },
    ])

    bot_context.player_api = mock_player

    res = await client.get("/api/v1/wardrobe/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # 1. Проверка структуры сетов и отсутствия дубликатов между группами
    reg_tattoo_sets = data["sets"]["regular"]["tattoos"]
    blind_tattoo_sets = data["sets"]["blind_kolsik"]["tattoos"]

    reg_part_ids = {p["id"] for s in reg_tattoo_sets for p in s["parts"]}
    blind_part_ids = {p["id"] for s in blind_tattoo_sets for p in s["parts"]}

    assert len(reg_part_ids) == 2
    assert 101 in reg_part_ids and 102 in reg_part_ids
    assert len(blind_part_ids) == 1
    assert 901 in blind_part_ids
    # СТРОГО без пересечений!
    assert len(reg_part_ids.intersection(blind_part_ids)) == 0

    # 2. Проверка статусов частей (owned, equipped, canBuy)
    set_auth = reg_tattoo_sets[0]
    assert set_auth["setName"] == "Сет Авторитета"
    assert set_auth["totalParts"] == 2
    assert set_auth["ownedParts"] == 2
    assert set_auth["isComplete"] is True

    part_101 = next(p for p in set_auth["parts"] if p["id"] == 101)
    assert part_101["owned"] is True
    assert part_101["equipped"] is True

    part_102 = next(p for p in set_auth["parts"] if p["id"] == 102)
    assert part_102["owned"] is True
    assert part_102["equipped"] is False

    # 3. Проверка одежды и canBuy
    reg_clothing_sets = data["sets"]["regular"]["clothing"]
    cloth_set = reg_clothing_sets[0]
    assert cloth_set["totalParts"] == 2
    assert cloth_set["ownedParts"] == 1
    assert cloth_set["isComplete"] is False

    part_202 = next(p for p in cloth_set["parts"] if p["id"] == 202)
    assert part_202["owned"] is False
    assert part_202["canBuy"] is True
    assert part_202["price"] == 60
    assert part_202["currency"] == "rubles"

    # 4. Проверка summaryStats
    summ_reg_tat = data["summaryStats"]["sets_tattoos"]
    # 101: knife 10, energy 5; 102: knife 15, energy 5 -> collected knife=25, energy=10
    assert summ_reg_tat["collected"]["knife"] == 25
    assert summ_reg_tat["collected"]["energy"] == 10
    assert summ_reg_tat["missing"]["knife"] == 0

    summ_reg_cloth = data["summaryStats"]["sets_clothing"]
    # 201: gunshot 20 (owned); 202: gunshot 25 (not owned) -> collected=20, max=45, missing=25
    assert summ_reg_cloth["collected"]["gunshot"] == 20
    assert summ_reg_cloth["max"]["gunshot"] == 45
    assert summ_reg_cloth["missing"]["gunshot"] == 25

    # 5. Проверка камер
    assert data["ownedCamerasCount"] == 2
    assert data["totalCamerasCount"] == 3
    cameras = data["cameras"]
    assert cameras[0]["equipped"] is True
    assert cameras[1]["owned"] is True
    assert cameras[2]["owned"] is False

    # 6. Проверка characterLayers
    layers = data["characterLayers"]
    assert layers["roomCameraUrl"] == "https://cdn/camera_1.png"
    assert layers["basePlayerSprite"] == "/static/assets/icons/PlayerSprite.png"
    assert layers["face"]["eyesUrl"] == "https://cdn/eyes.png"


@pytest.mark.asyncio
async def test_action_wardrobe_equip_and_buy(wardrobe_setup):
    """Проверка POST /api/v1/actions/wardrobe/equip и POST /api/v1/actions/wardrobe/buy."""
    client, engine = wardrobe_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.equip_tattoo = AsyncMock(return_value={"success": True})
    mock_player.unequip_tattoo = AsyncMock(return_value={"success": True})
    mock_player.equip_tattoo_set = AsyncMock(return_value={"success": True})
    mock_player.equip_clothing = AsyncMock(return_value={"success": True})
    mock_player.unequip_clothing = AsyncMock(return_value={"success": True})
    mock_player.select_camera = AsyncMock(return_value={"success": True})
    mock_player.buy_tattoo = AsyncMock(return_value={"success": True})
    mock_player.buy_clothing = AsyncMock(return_value={"success": True})
    mock_player.buy_camera = AsyncMock(return_value={"success": True})

    bot_context.player_api = mock_player

    # 1. Надевание татуировки
    res = await client.post("/api/v1/actions/wardrobe/equip", json={
        "kind": "tattoo",
        "action": "equip",
        "id": 101,
        "zone": 1,
        "imageUrl": "https://cdn/t101.png"
    }, headers=headers)
    assert res.status_code == 200
    mock_player.equip_tattoo.assert_awaited_once_with(1, 101, "https://cdn/t101.png")

    # 2. Снятие татуировки
    res = await client.post("/api/v1/actions/wardrobe/equip", json={
        "kind": "tattoo",
        "action": "unequip",
        "zone": 1
    }, headers=headers)
    assert res.status_code == 200
    mock_player.unequip_tattoo.assert_awaited_once_with(1)

    # 3. Надевание сета татуировок
    res = await client.post("/api/v1/actions/wardrobe/equip", json={
        "kind": "tattoo_set",
        "zonesMap": {"1": {"id": 101, "imageUrl": "https://cdn/t101.png"}}
    }, headers=headers)
    assert res.status_code == 200
    mock_player.equip_tattoo_set.assert_awaited_once_with({"1": {"id": 101, "imageUrl": "https://cdn/t101.png"}})

    # 4. Выбор хаты
    res = await client.post("/api/v1/actions/wardrobe/equip", json={
        "kind": "camera",
        "id": 2
    }, headers=headers)
    assert res.status_code == 200
    mock_player.select_camera.assert_awaited_once_with(2)

    # 5. Покупка предметов
    res = await client.post("/api/v1/actions/wardrobe/buy", json={
        "kind": "tattoo",
        "id": 102
    }, headers=headers)
    assert res.status_code == 200
    mock_player.buy_tattoo.assert_awaited_once_with(102)

    res = await client.post("/api/v1/actions/wardrobe/buy", json={
        "kind": "camera",
        "id": 3
    }, headers=headers)
    assert res.status_code == 200
    mock_player.buy_camera.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_wardrobe_overview_with_real_cache(wardrobe_setup):
    """Тест загрузки реального кэша storage/tattoo_clothing_cache.json в GET /api/v1/wardrobe/overview."""
    client, engine = wardrobe_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.init_player = AsyncMock(return_value={
        "tattooZones": {},
        "clothingZones": {},
        "clothingFrontIds": {},
        "face": {},
        "beardPhase": 0,
        "roomCameraUrl": "",
    })
    mock_player.get_wardrobe_inventory = AsyncMock(return_value={
        "ownedTattoos": [],
        "ownedClothing": [],
        "ownedCameras": [1],
    })
    mock_player.get_cameras = AsyncMock(return_value={"cameras": []})
    # Передаем пустые списки, чтобы сработал fallback загрузки реального кэша storage/tattoo_clothing_cache.json
    mock_player.get_tattoos_catalog = AsyncMock(return_value=[])
    mock_player.get_clothing_catalog = AsyncMock(return_value=[])

    bot_context.player_api = mock_player

    res = await client.get("/api/v1/wardrobe/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Проверяем, что загрузились реальные сеты
    reg_tat_sets = data["sets"]["regular"]["tattoos"]
    reg_cloth_sets = data["sets"]["regular"]["clothing"]
    blind_tat_sets = data["sets"]["blind_kolsik"]["tattoos"]

    assert len(reg_tat_sets) > 50, f"Expected > 50 tattoo sets, got {len(reg_tat_sets)}"
    assert len(reg_cloth_sets) > 50, f"Expected > 50 clothing sets, got {len(reg_cloth_sets)}"
    assert len(blind_tat_sets) > 0, "Expected non-empty blind kolsik tattoo sets"

    # Проверяем, что summaryStats.missing положительные числа (не нули)
    summ = data["summaryStats"]["sets_tattoos"]
    assert summ["missing"]["knife"] > 0
    assert summ["missing"]["poison"] > 0
    assert summ["missing"]["gunshot"] > 0
    assert summ["missing"]["energy"] > 0

    # Проверяем камеры
    assert data["totalCamerasCount"] > 0


def test_parse_set_description_tier_bonuses():
    """Тест парсера пороговых бонусов сета (Module 980493 в Тюряге)."""
    from web.routes import parse_set_description

    # Шаблон 1: бонус за (\d+) [^:\n]*:\s*([^\n]+)
    t1 = parse_set_description("Бонус за 20 татуировок: +25 к яду, +10 к самопалу")
    assert t1 is not None
    assert t1["threshold"] == 20
    assert t1["bonus"] == {"poison": 25, "gunshot": 10}

    # Шаблон 2: увеличивает ... на (\d+) ... эффект за ... (\d+)
    t2 = parse_set_description("Увеличивает урон атаки \"Шмальнуть из самопала\" на 25 (эффект за полный комплект из 20 татуировок)")
    assert t2 is not None
    assert t2["threshold"] == 20
    assert t2["bonus"] == {"gunshot": 25}

    # Проверка включения бонуса сета в _build_wardrobe_sets
    items = [
        {"id": 1, "setName": "Тест Сет", "zone": 1, "combat_stats_bonus": {"poison": 5}, "setDescription": "Бонус за 2 татуировки: +15 к яду"},
        {"id": 2, "setName": "Тест Сет", "zone": 2, "combat_stats_bonus": {"poison": 5}, "setDescription": "Бонус за 2 татуировки: +15 к яду"},
    ]
    # 1 куплена (порог 2 не достигнут)
    sets_1 = _build_wardrobe_sets(items, owned_ids={1}, equipped_zones={})
    assert sets_1[0]["maxBonus"]["poison"] == 25  # 5 + 5 + 15
    assert sets_1[0]["collectedBonus"]["poison"] == 5  # Только 1 часть

    # 2 куплены (порог 2 достигнут)
    sets_2 = _build_wardrobe_sets(items, owned_ids={1, 2}, equipped_zones={})
    assert sets_2[0]["collectedBonus"]["poison"] == 25  # 5 + 5 + 15 (бонус сета начислен)


@pytest.mark.asyncio
async def test_wardrobe_character_layers_animation_metadata(wardrobe_setup):
    """Проверка формирования анимационных слоев (EyesAnim, BrushAnim) в characterLayers."""
    from web.routes import _build_character_layers

    sample_init = {
        "face": {
            "eyes": "assets/PrisonV3/Face/EyesAnim/Eyes3",
            "nose": "assets/PrisonV3/Face/Nose/Nose2.png",
            "mouth": "assets/PrisonV3/Face/Mouth/Mouth5.png",
        },
        "beardPhase": 3,
        "roomCameraUrl": "assets/PrisonV3/RoomCameraUrl/2/1.png",
        "clothingZones": {
            "1": "assets/PrisonV3/Clotch/Sizi/C/2.png",
            "6": "assets/Clotch/BrushAnim/12/Brush12.webp",
        },
        "clothingFrontIds": {"1": 48, "6": 0},
        "tattooZones": {
            "1": "assets/PrisonV3/Tattoos/T/10.png",
        },
    }

    layers = _build_character_layers(sample_init)

    # Проверка EyesAnim
    assert "eyesAtlas" in layers["face"]
    assert "Eyes3.json" in layers["face"]["eyesAtlas"]
    assert "Eyes3_config.json" in layers["face"]["eyesConfig"]
    assert "Eyes3.png" in layers["face"]["eyes"]

    # Проверка BrushAnim в zone 6
    assert "6" in layers["clothingZones"]
    assert "BrushAnim" in layers["clothingRawZones"]["6"]

    # Проверка камеры и бороды
    assert "RoomCameraUrl/2" in layers["roomCameraUrl"]
    assert layers["beardPhase"] == 3


@pytest.mark.asyncio
async def test_character_layers_and_wardrobe_sets_front_and_back_sides():
    """
    Проверка разделения зон на front (1..22) и back (23..42):
    1) _build_character_layers отдает PlayerSpriteBack.png, back_poworot.webp, back_Mask.webp;
    2) Зоны татуировок содержат атрибут side ('front' или 'back');
    3) _build_wardrobe_sets проставляет side='front' для зон < 23 и side='back' для зон >= 23.
    """
    from web.routes import _build_character_layers, _build_wardrobe_sets

    sample_init = {
        "roomCameraUrl": "assets/PrisonV3/RoomCameraUrl/1/1.png",
        "tattooZones": {
            "1": "assets/PrisonV3/Tattoos/T/10.png",
            "12": "assets/PrisonV3/Tattoos/T/12.png",
            "25": "assets/PrisonV3/Tattoos/T/25.png",
            "34": "assets/PrisonV3/Tattoos/T/34.png",
        },
        "clothingZones": {},
        "clothingBackZones": {"4": "assets/PrisonV3/Clotch/Back/4.png"},
    }

    layers = _build_character_layers(sample_init)

    # 1. Ассеты спины и кнопки разворота
    assert layers["basePlayerSprite"] == "/static/assets/icons/PlayerSprite.png"
    assert layers["basePlayerSpriteBack"] == "/static/assets/icons/PlayerSpriteBack.png"
    assert layers["backMask"] == "/static/assets/icons/back_Mask.webp"
    assert layers["rotateButton"] == "/static/assets/icons/back_poworot.webp"

    # 2. Зоны татуировок со стороной (front vs back)
    tz = layers["tattooZones"]
    assert tz["1"]["side"] == "front"
    assert tz["12"]["side"] == "front"
    assert tz["25"]["side"] == "back"
    assert tz["34"]["side"] == "back"

    # 3. Сетовые части в _build_wardrobe_sets
    sample_items = [
        {"id": 1, "name": "Наколка на грудь", "zone": 1, "setName": "Большой Сет", "price": 10, "currency": "rubles"},
        {"id": 2, "name": "Наколка на плечо", "zone": 8, "setName": "Большой Сет", "price": 10, "currency": "rubles"},
        {"id": 3, "name": "Наколка на спину", "zone": 25, "setName": "Большой Сет", "price": 20, "currency": "rubles"},
        {"id": 4, "name": "Наколка на лопатку", "zone": 36, "setName": "Большой Сет", "price": 20, "currency": "rubles"},
    ]
    sets = _build_wardrobe_sets(sample_items, owned_ids={1, 3}, equipped_zones={})
    assert len(sets) == 1
    parts = sets[0]["parts"]
    assert len(parts) == 4

    p1 = next(p for p in parts if p["id"] == 1)
    p3 = next(p for p in parts if p["id"] == 3)
    p4 = next(p for p in parts if p["id"] == 4)

    assert p1["side"] == "front"
    assert p3["side"] == "back"
    assert p4["side"] == "back"

    # 4. Проверка одежды с backImageUrl / imageBackUrl
    clothing_items = [
        {"id": 201, "name": "Куртка байкера", "zone": 2, "setName": "Байкер", "imageBackUrl": "assets/Clotch/Back/2.png"},
        {"id": 202, "name": "Шорты Рэп", "zone": 1, "setName": "Байкер", "imageUrl": "assets/Clotch/Sizi/1.png"},
    ]
    c_sets = _build_wardrobe_sets(clothing_items, owned_ids={201, 202}, equipped_zones={})
    c_parts = c_sets[0]["parts"]
    jacket = next(p for p in c_parts if p["id"] == 201)
    shorts = next(p for p in c_parts if p["id"] == 202)
    assert jacket["hasBack"] is True
    assert "assets/Clotch/Back/2.png" in jacket["imageBackUrl"]
    assert shorts["hasBack"] is False
    assert shorts["imageBackUrl"] == ""


