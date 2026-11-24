import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select
from core.database import get_engine, init_db, get_session
from core.models import Account, SessionData, ActionLog, BotConfig
from client.auth_provider import AuthProvider
from client.http_client import GameHttpClient
from client.api.boss import BossAPI
from workers.boss_worker import BossWorker


@pytest_asyncio.fixture
async def boss_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79997776655", nickname="BossHero")
        session.add(acc)
        await session.flush()
        sess = SessionData(
            account_id=acc.id,
            access_token="valid_boss_token",
            access_exp=9999999999,
        )
        session.add(sess)
        cfg = BotConfig(account_id=acc.id, auto_boss_hits=True)
        session.add(cfg)
        acc_id = acc.id
    yield engine, acc_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_worker_melee_cooldowns_and_hits(boss_setup):
    """
    Тест расчета кулдаунов:
    - 4 рукопашных удара:
      - punchChest: lastTime 9 часов назад (откатился, cooldown 8ч = 28800с) -> ГОТОВ
      - kickBalls: lastTime 1 час назад (на кулдауне) -> НЕ ГОТОВ
      - pokeEyes: lastTime 10 часов назад (откатился) -> ГОТОВ
      - kneeEar: отсутствует в equippedSlots -> НЕ ДОСТУПЕН
    - Воркер должен отправить ровно 2 удара: punchChest и pokeEyes.
    - Никакого платного оружия (poison, gunshot, knife).
    """
    engine, acc_id = boss_setup
    calls = []
    used_weapons = []

    nine_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ten_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "state": "active",
                    "hasReward": False,
                    "unclaimedRewards": [],
                    "session": {
                        "sessionId": "session_123",
                        "currentHp": 50000,
                        "maxHp": 100000,
                    },
                    "weaponStatsEffective": {
                        "punchChestCooldownSec": 28800,
                        "kickBallsCooldownSec": 28800,
                        "pokeEyesCooldownSec": 28800,
                        "kneeEarCooldownSec": 28800,
                    },
                },
            )
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(
                200,
                json={
                    "userId": 9000000000466709,
                    # В экипированных слотах только punchChest, kickBalls, pokeEyes (kneeEar отсутствует!)
                    "equippedSlots": ["punchChest", "kickBalls", "pokeEyes", "poison", "gunshot"],
                    "lastPunchChestTime": nine_hours_ago,
                    "lastKickBallsTime": one_hour_ago,
                    "lastPokeEyesTime": ten_hours_ago,
                    "lastKneeEarTime": None,
                },
            )
        elif request.url.path == "/api/boss/use-weapon":
            import json
            body = json.loads(request.content)
            w = body.get("weapon")
            used_weapons.append(w)
            return httpx.Response(200, json={"success": True, "currentHp": 45000})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["boss_active"] is True
    assert len(res["hits_performed"]) == 2
    assert used_weapons == ["punchChest", "pokeEyes"]
    # Проверяем отсутствие платного оружия
    assert "poison" not in used_weapons
    assert "gunshot" not in used_weapons
    assert "knife" not in used_weapons

    # Проверяем ActionLog
    async with get_session(engine) as session:
        log_stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "boss_melee_hit",
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) == 2
        logged_weapons = [l.details["weapon"] for l in logs]
        assert logged_weapons == ["punchChest", "pokeEyes"]


@pytest.mark.asyncio
async def test_boss_worker_no_active_boss(boss_setup):
    """Тест отсутствия активного босса: при state != 'active' удары не отправляются."""
    engine, acc_id = boss_setup
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "state": "idle",
                    "hasReward": False,
                    "session": None,
                },
            )
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["boss_active"] is False
    assert len(res["hits_performed"]) == 0
    assert ("POST", "/api/boss/use-weapon") not in calls
    assert ("GET", "/api/boss/weapons") not in calls


@pytest.mark.asyncio
async def test_boss_worker_claims_reward(boss_setup):
    """Тест сбора награды: при hasReward == True или наличии unclaimedRewards вызывается claim_reward()."""
    engine, acc_id = boss_setup
    claims = []

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "state": "reward",
                    "hasReward": True,
                    "unclaimedRewards": ["reward_abc_1", "reward_abc_2"],
                    "session": {"currentHp": 0},
                },
            )
        elif request.url.path == "/api/boss/claim":
            import json
            claims.append(json.loads(request.content) if request.content else {})
            return httpx.Response(200, json={"success": True, "rewards": {"soap": 10, "authority": 500}})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 2
    assert claims == [{"claimId": "reward_abc_1"}, {"claimId": "reward_abc_2"}]

    async with get_session(engine) as session:
        log_stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "claim_boss_reward",
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) == 2


@pytest.mark.asyncio
async def test_boss_api_get_all_bosses():
    """Тест get_all_bosses(): опрашивает категории 1, 2, 3 и возвращает дедуплицированный список с режимами и HP."""
    from unittest.mock import AsyncMock
    requested_cats = []

    def mock_handler(request: httpx.Request):
        cat = request.url.params.get("categoryId")
        requested_cats.append(cat)
        if cat == "1":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 1, "name": "Кирпич", "hp": 500, "categoryId": 1, "keyRequirement": 0},
                    {"id": 2, "name": "Сизый", "hp": 1500, "categoryId": 1, "keyRequirement": 3, "keyBoss": "Кирпич"},
                ]
            })
        elif cat == "2":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 9, "name": "Палыч", "hp": 100000, "categoryId": 2, "keyRequirement": 0},
                ]
            })
        elif cat == "3":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 30, "name": "Жестянщики", "hp": 50000000, "categoryId": 3, "keyRequirement": 5},
                ]
            })
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    mock_auth = AsyncMock()
    mock_auth.get_valid_token.return_value = "test_token"
    http_client = GameHttpClient(auth_provider=mock_auth, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    all_bosses = await boss_api.get_all_bosses()

    assert set(requested_cats) == {"1", "2", "3"}
    # Полный каталог игры насчитывает ровно 58 боссов
    assert len(all_bosses) == 58

    brick = next(b for b in all_bosses if b["id"] == 1)
    assert brick["name"] == "Кирпич"
    assert brick["categoryName"] == "Беспредельщики"
    assert brick["baseHp"] == 1000
    assert brick["modes"]["pacansky"]["hp"] == 1000
    assert brick["requiredKeyBossId"] is None
    assert brick["requiredKeysCount"] == 0

    sizy = next(b for b in all_bosses if b["id"] == 2)
    assert sizy["name"] == "Сизый"
    assert sizy["baseHp"] == 10000
    assert sizy["requiredKeyBossId"] == 1
    assert sizy["requiredKeysCount"] == 3
    assert sizy["requiredKeyBossName"] == "Кирпич"

    makhno = next(b for b in all_bosses if b["id"] == 3)
    assert makhno["name"] == "Махно"
    assert makhno["baseHp"] == 50000
    assert makhno["requiredKeyBossId"] == 2
    assert makhno["requiredKeysCount"] == 3
    assert makhno["requiredKeyBossName"] == "Сизый"

    vorkuta = next(b for b in all_bosses if b["id"] == 39)
    assert vorkuta["name"] == "Воркута"
    assert vorkuta["baseHp"] == 400000000

    palych = next(b for b in all_bosses if b["id"] == 9)
    assert palych["name"] == "Палыч"
    assert palych["categoryName"] == "Надзиратели"
    assert palych["baseHp"] == 100000


@pytest.mark.asyncio
async def test_boss_worker_auto_boss_enabled_summon_and_queue(boss_setup):
    """Тест авто-призыва босса из очереди при активном тумблере auto_boss_enabled."""
    engine, acc_id = boss_setup
    summon_calls = []

    # Обновляем конфиг: auto_boss_enabled=True, цель Кирпич в режиме blotnoy
    async with get_session(engine) as session:
        cfg_stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(cfg_stmt)).scalar_one()
        cfg.auto_boss_enabled = True
        cfg.boss_targets = [{"bossId": 1, "mode": "blotnoy", "enabled": True}]
        await session.commit()

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            # До призыва боя нет
            if not summon_calls:
                return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
            # После призыва активный бой
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "sess_1", "bossId": 1, "currentHp": 1500, "maxHp": 1500},
                "weaponStatsEffective": {"punchChestCooldownSec": 28800},
            })
        elif request.url.path == "/api/boss/start-attack":
            import json
            body = json.loads(request.content)
            summon_calls.append(body)
            return httpx.Response(200, json={"success": True, "state": "active"})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": [], "lastPunchChestTime": None})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert len(summon_calls) == 1
    assert summon_calls[0]["bossId"] == 1 and summon_calls[0]["mode"] == "blotnoy"
    assert res["boss_active"] is True


@pytest.mark.asyncio
async def test_boss_worker_required_key_boss_mapping(boss_setup):
    """
    Тест строгого маппинга ключей:
    При keys = {"1": 0, "2": 14}:
    - Сизый (id=2, requiredKeyBossId=1, count=3): 0 ключей -> авто-призыв невозможен.
    - Махно (id=3, requiredKeyBossId=2, count=3): 14 ключей -> авто-призыв разрешен.
    """
    engine, acc_id = boss_setup
    summon_calls = []

    async with get_session(engine) as session:
        cfg_stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(cfg_stmt)).scalar_one()
        cfg.auto_boss_enabled = True
        # В очереди сначала Сизый, потом Махно
        cfg.boss_targets = [
            {"bossId": 2, "mode": "pacansky", "enabled": True},
            {"bossId": 3, "mode": "pacansky", "enabled": True},
        ]
        await session.commit()

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            if not summon_calls:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "inactive",
                    "session": None,
                    "playerStats": {
                        "keys": {"1": 0, "2": 14},  # 0 ключей от Кирпича, 14 от Сизого
                        "dailyWins": {},
                    }
                })
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "sess_makhno", "bossId": 3, "currentHp": 50000, "maxHp": 50000},
            })
        elif request.url.path == "/api/boss/start-attack":
            import json
            body = json.loads(request.content)
            summon_calls.append(body)
            return httpx.Response(200, json={"success": True, "state": "active"})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": [], "lastPunchChestTime": None})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": []})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    # Сизый пропущен из-за нехватки ключей Кирпича, призван Махно (было 14 ключей Сизого)
    assert len(summon_calls) == 1
    assert summon_calls[0]["bossId"] == 3
    assert res["boss_active"] is True


def test_boss_catalog_58_order_and_modes():
    """
    Тест каталога 58 боссов:
    - строго 58 боссов;
    - точный порядок sortOrder (0..57);
    - разбивка по категориям: 25 Беспредельщиков, 20 Надзирателей, 13 Рецидивистов;
    - правильный порядок имен;
    - различные реальные HP для режимов pacansky, blotnoy, avtoritetny;
    - наличие таблиц loot (currencies + items).
    """
    from client.api.boss import _load_bosses_catalog

    catalog = _load_bosses_catalog()
    assert len(catalog) == 58, f"Expected 58 bosses, got {len(catalog)}"

    # Проверка непрерывности sortOrder 0..57
    sort_orders = [b.get("sortOrder") for b in catalog]
    assert sort_orders == list(range(58)), "Bosses must be strictly sorted by sortOrder 0..57"

    # Разделение по категориям
    cat1 = [b for b in catalog if b["categoryId"] == 1]
    cat2 = [b for b in catalog if b["categoryId"] == 2]
    cat3 = [b for b in catalog if b["categoryId"] == 3]

    assert len(cat1) == 25, f"Expected 25 Беспредельщиков, got {len(cat1)}"
    assert len(cat2) == 20, f"Expected 20 Надзирателей, got {len(cat2)}"
    assert len(cat3) == 13, f"Expected 13 Рецидивистов, got {len(cat3)}"

    # Проверка порядка в Беспредельщиках
    expected_cat1 = [
        "Кирпич", "Сизый", "Махно", "Лютый", "Гастролёр", "Шайба", "Бурят", "Дядя Миша",
        "Бандяк", "Абу", "Гризли", "Феня", "Север", "Мазай", "Хирург", "Пресс",
        "Немой", "Бидон", "Воркута", "Старшой", "Полтос", "Бугор", "Змей", "Гвоздь", "Тротил"
    ]
    actual_cat1 = [b["name"] for b in cat1]
    assert actual_cat1 == expected_cat1, f"Cat 1 names mismatch:\nExpected: {expected_cat1}\nActual: {actual_cat1}"

    # Проверка Сизого: режимы pacansky (10 000), blotnoy (30 000), avtoritetny (60 000)
    siziy = next(b for b in catalog if b["name"] == "Сизый")
    assert siziy["modes"]["pacansky"]["hp"] == 10000
    assert siziy["modes"]["blotnoy"]["hp"] == 30000
    assert siziy["modes"]["avtoritetny"]["hp"] == 60000

    # Проверка лута Сизого в пацанском режиме
    pac_loot = siziy["modes"]["pacansky"]
    assert "currencies" in pac_loot
    assert "items" in pac_loot
    assert any(c["currency"] == "authority" for c in pac_loot["currencies"])
    assert any(it["name"] == "Комплект \"Биомеханика\"" for it in pac_loot["items"])


@pytest.mark.asyncio
async def test_boss_worker_skips_locked_boss_target(boss_setup):
    """Тест пропуска заблокированных боссов (isLocked == True) воркером BossWorker при автоатаке."""
    engine, acc_id = boss_setup
    start_calls = []

    # Конфиг: включен авто-босс, в очереди заблокированный босс (например Тротил, id 56)
    async with get_session(engine) as session:
        cfg_stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(cfg_stmt)).scalar_one()
        cfg.auto_boss_enabled = True
        cfg.boss_targets = [{"bossId": 56, "mode": "pacansky", "enabled": True}]
        await session.commit()

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
        elif request.url.path == "/api/boss/start-attack":
            start_calls.append(request)
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    # Заблокированный босс Тротил должен быть пропущен, атака не вызывается
    assert len(start_calls) == 0
    assert res["boss_active"] is False


@pytest.mark.asyncio
async def test_boss_presets_schedule_and_execution(boss_setup):
    """
    Тест запуска пресетов по расписанию МСК и защиты от повторного запуска в те же сутки.
    """
    from core.models import BossPreset

    engine, acc_id = boss_setup
    today_date = "2026-11-23"
    utc_time_0900_msk = datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc)
    utc_time_0905_msk = datetime(2026, 11, 23, 6, 5, tzinfo=timezone.utc)

    preset_id = None
    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=acc_id,
            name="Утренний фарм",
            schedule_time_msk="09:00",
            daily_enabled=True,
            items=[{"boss_id": 1, "mode": "pacansky", "count": 1}],
            is_running=False,
            current_step_index=0,
            last_run_date_msk=None,
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        preset_id = preset.id

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
        elif request.url.path == "/api/boss/start-attack":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    # 1. Запуск в 09:00 МСК -> пресет должен запуститься
    launched = await worker.check_scheduled_presets(now_utc=utc_time_0900_msk)
    assert launched is not None
    assert launched["preset_id"] == preset_id

    # Проверяем last_run_date_msk в БД
    async with get_session(engine) as session:
        p = await session.get(BossPreset, preset_id)
        assert p.last_run_date_msk == today_date

    # 2. Повторный вызов в 09:05 МСК того же дня -> защита от повтора, не должен запускаться
    repeat = await worker.check_scheduled_presets(now_utc=utc_time_0905_msk)
    assert repeat is None


@pytest.mark.asyncio
async def test_boss_preset_skip_locked_boss_step(boss_setup):
    """
    Тест пропуска заблокированного босса внутри пресета с записью в ActionLog и переходом к следующему шагу.
    """
    from core.models import BossPreset
    from unittest.mock import AsyncMock

    engine, acc_id = boss_setup

    preset_id = None
    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=acc_id,
            name="Цепочка боссов",
            schedule_time_msk="10:00",
            daily_enabled=True,
            items=[
                {"boss_id": 4, "mode": "pacansky", "count": 1},  # Лютый (заблокирован)
                {"boss_id": 1, "mode": "pacansky", "count": 1},  # Кирпич (доступен)
            ],
            is_running=True,
            current_step_index=0,
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        preset_id = preset.id

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
        elif request.url.path == "/api/boss/start-attack":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    # Мокируем get_all_bosses, чтобы Лютый был заблокирован, а Кирпич открыт
    boss_api.get_all_bosses = AsyncMock(return_value=[
        {"id": 4, "name": "Лютый", "isLocked": True, "unlockReason": "Нужно 2 дневные ходки в Кресты"},
        {"id": 1, "name": "Кирпич", "isLocked": False},
    ])

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    # Запускаем цикл выполнения пресета
    res = await worker.run_cycle()

    # Проверяем, что первый шаг (Лютый) был пропущен, и current_step_index продвинулся
    async with get_session(engine) as session:
        p = await session.get(BossPreset, preset_id)
        assert p.current_step_index >= 1

        # Проверяем запись в ActionLog
        stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "boss_preset_step_skip"
        )
        skip_log = (await session.execute(stmt)).scalar_one_or_none()
        assert skip_log is not None
        assert "Лютый" in skip_log.details["boss"]
        assert "Кресты" in skip_log.details["reason"]


@pytest.mark.asyncio
async def test_boss_preset_pause_and_sleep(boss_setup):
    """Тест: планировщик пресетов не запускает пресеты при паузе или неактивности воркера."""
    from core.models import BossPreset
    from unittest.mock import MagicMock

    engine, acc_id = boss_setup
    async with get_session(engine) as session:
        p = BossPreset(
            account_id=acc_id,
            name="Тестовый",
            schedule_time_msk="09:00",
            daily_enabled=True,
            items=[{"boss_id": 1, "mode": "pacansky", "count": 1}],
            is_running=False,
        )
        session.add(p)
        await session.commit()

    boss_api = MagicMock()
    worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine, enable_jitter=False)

    # Ставим паузу
    worker.is_paused = True
    res = await worker.check_scheduled_presets(now_utc=datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc))
    assert res is None


@pytest.mark.asyncio
async def test_boss_worker_conveyor_claim_and_next_summon(boss_setup):
    """
    Конвейер: при сборе награды (state='reward') или убийстве босса ударом
    BossWorker немедленно призывает следующего босса в том же цикле run_cycle().
    """
    from core.models import BossPreset

    engine, acc_id = boss_setup
    summoned_ids = []
    claimed_ids = []

    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=acc_id,
            name="Конвейер",
            schedule_time_msk="09:00",
            daily_enabled=False,
            items=[
                {"boss_id": 1, "mode": "odin", "count": 1},
                {"boss_id": 1, "mode": "pacansky", "count": 1},
                {"boss_id": 1, "mode": "blotnoy", "count": 1},
            ],
            is_running=True,
            current_step_index=0,
        )
        session.add(preset)
        await session.commit()

    # Начинаем со старого state="reward" -> claim_reward -> сразу призыв #1 ->
    # смертельный удар -> claim_reward -> сразу призыв #2 в том же цикле!
    phase = "reward1"

    def mock_handler(request: httpx.Request):
        nonlocal phase
        import json as _json
        if request.url.path == "/api/boss/bootstrap":
            if phase == "reward1":
                return httpx.Response(200, json={
                    "success": True,
                    "state": "reward",
                    "hasReward": True,
                    "claimId": "claim_prev",
                    "currentBattle": {"sessionId": "s0", "bossId": 1, "currentHp": 0, "maxHp": 1000},
                })
            elif phase == "idle_for_1":
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None})
            elif phase == "battle_1":
                return httpx.Response(200, json={
                    "success": True,
                    "state": "active",
                    "currentBattle": {"sessionId": "s1", "bossId": 1, "currentHp": 500, "maxHp": 1000},
                })
            elif phase == "idle_for_2":
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None})
            else:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "active",
                    "currentBattle": {"sessionId": "s2", "bossId": 1, "mode": "blotnoy", "currentHp": 3000, "maxHp": 3000},
                })
        elif request.url.path == "/api/boss/claim":
            body = _json.loads(request.content) if request.content else {}
            claimed_ids.append(body.get("claimId"))
            if phase == "reward1":
                phase = "idle_for_1"
            return httpx.Response(200, json={"success": True, "rewards": {"cigarettes": 50}})
        elif request.url.path == "/api/boss/start-attack":
            body = _json.loads(request.content)
            summoned_ids.append((body.get("bossId"), body.get("mode")))
            if phase == "idle_for_1":
                phase = "battle_1"
            elif phase == "idle_for_2":
                phase = "battle_2"
            return httpx.Response(200, json={"success": True, "state": "active"})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": ["punchChest"], "lastPunchChestTime": None})
        elif request.url.path == "/api/boss/use-weapon":
            if phase == "battle_1":
                phase = "idle_for_2"
                return httpx.Response(200, json={"success": True, "currentHp": 0, "bossDefeated": True, "claimId": "claim_b1"})
            return httpx.Response(200, json={"success": True, "currentHp": 2500})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": [{"id": 1, "name": "Кирпич", "isLocked": False}]})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 2
    assert claimed_ids == ["claim_prev", "claim_b1"]
    assert summoned_ids == [(1, "pacansky"), (1, "blotnoy")]
    assert res["boss_active"] is True


@pytest.mark.asyncio
async def test_boss_worker_manual_force_ignores_pause(boss_setup):
    """Ручной запуск run_cycle(force_manual=True) работает даже при is_paused=True в BotConfig."""
    engine, acc_id = boss_setup
    summoned = []

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.is_paused = True
        cfg.auto_boss_enabled = True
        cfg.boss_targets = [1]  # Проверяем также нормализацию raw int ID
        await session.commit()

    def mock_handler(request: httpx.Request):
        import json as _json
        if request.url.path == "/api/boss/bootstrap":
            if not summoned:
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None})
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "currentBattle": {"sessionId": "s_man", "bossId": 1, "currentHp": 1000, "maxHp": 1000},
            })
        elif request.url.path == "/api/boss/start-attack":
            summoned.append(_json.loads(request.content))
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": []})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": [{"id": 1, "name": "Кирпич"}]})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    worker = BossWorker(account_id=acc_id, boss_api=BossAPI(http_client=http_client), db_engine=engine, enable_jitter=False)

    # Авто-тик на паузе пропускает
    res_auto = await worker.run_cycle(force_manual=False)
    assert res_auto["status"] == "skipped"
    assert len(summoned) == 0

    # Ручной запуск с force_manual=True призывает босса даже на паузе
    res_manual = await worker.run_cycle(force_manual=True)
    assert res_manual["boss_active"] is True
    assert len(summoned) == 1 and summoned[0]["bossId"] == 1


@pytest.mark.asyncio
async def test_boss_worker_prisons_data_unlocks_boss(boss_setup):
    """Передача prison_api разблокирует боссов с requiredPrisonId (не маркирует их ложно isLocked=True)."""
    from client.api.prison import PrisonAPI

    engine, acc_id = boss_setup
    summoned = []

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.auto_boss_enabled = True
        # Сизый (id=2): требует прохождения Бутырки (id=1) и/или ключей
        # Лютый (id=4): требует ходки в Крестах (prison_id=2)
        cfg.boss_targets = [{"bossId": 4, "mode": "pacansky", "enabled": True}]
        await session.commit()

    def mock_handler(request: httpx.Request):
        import json as _json
        if request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={
                "success": True,
                "prisons": [
                    {"id": 1, "name": "Бутырка", "dayRuns": 20, "nightRuns": 20, "isUnlocked": True},
                    {"id": 4, "name": "Кресты", "dayRuns": 5, "nightRuns": 0, "isUnlocked": True},
                ],
            })
        elif request.url.path == "/api/boss/bootstrap":
            if not summoned:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "idle",
                    "session": None,
                    "playerStats": {"keys": {"1": 10, "2": 10, "3": 10}, "wins": {"1": 5, "2": 5, "3": 5}, "dailyWins": {}},
                })
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "s4", "bossId": 4, "currentHp": 100000, "maxHp": 100000},
            })
        elif request.url.path == "/api/boss/start-attack":
            summoned.append(_json.loads(request.content))
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": []})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": []})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    worker = BossWorker(
        account_id=acc_id,
        boss_api=BossAPI(http_client=http_client),
        prison_api=PrisonAPI(http_client=http_client),
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(summoned) == 1
    assert summoned[0]["bossId"] == 4
    assert res["boss_active"] is True


@pytest.mark.asyncio
async def test_boss_worker_auto_melee_and_preset_defeat_reset(boss_setup):
    """Проверка авто-рукопашной (boss_auto_melee) и сброса пресета на поражении + очистки в state_hub."""
    from core.models import BossPreset, Notification
    from core.state_hub import LiveStateHub

    engine, acc_id = boss_setup
    hits = []
    hub = LiveStateHub()

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.boss_auto_melee = True
        cfg.auto_boss_hits = False
        preset = BossPreset(
            account_id=acc_id,
            name="Defeat Test",
            items=[{"bossId": 1, "bossName": "Кирпич", "mode": "pacansky", "count": 2}],
            is_running=True,
            current_step_index=0,
            last_status="В процессе",
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        preset_id = preset.id

    def mock_handler(request: httpx.Request):
        import json as _json
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "s_melee", "bossId": 1, "bossName": "Кирпич", "mode": "pacansky", "currentHp": 5000, "maxHp": 10000},
                "weaponStatsEffective": {"punchChestCooldownSec": 28800},
            })
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={
                "equippedSlots": ["punchChest", "kickBalls"],
                "lastPunchChestTime": None,
                "lastKickBallsTime": "2020-01-01T00:00:00Z",
            })
        elif request.url.path == "/api/boss/use-weapon":
            body = _json.loads(request.content)
            hits.append(body.get("weapon"))
            return httpx.Response(200, json={"success": True, "currentHp": 4000})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    worker = BossWorker(
        account_id=acc_id,
        boss_api=BossAPI(http_client=http_client),
        db_engine=engine,
        enable_jitter=False,
        state_hub=hub,
    )

    hub.update_slice(acc_id, "boss", {"meleeTimestamps": {}, "session": {"currentHp": 5000}})
    melee_res = await worker.trigger_auto_melee()
    assert len(hits) == 2
    assert set(hits) == {"punchChest", "kickBalls"}
    assert melee_res["boss_hp_remaining"] == 4000

    # Проверяем сброс пресета и сохранение уведомления при поражении
    async with get_session(engine) as session:
        p_loaded = await session.get(BossPreset, preset_id)

    await worker.on_boss_fight_finished(
        {
            "outcome": "defeat",
            "bossName": "Кирпич",
            "mode": "pacansky",
            "remainingHp": 4000,
            "maxHp": 10000,
            "sessionId": "s_melee",
        },
        active_preset=p_loaded,
        preset_steps=[{"bossId": 1, "bossName": "Кирпич", "mode": "pacansky"}] * 2,
    )

    async with get_session(engine) as session:
        p_after = await session.get(BossPreset, preset_id)
        assert p_after.is_running is False
        assert "поражение" in (p_after.last_status or "").lower()
        defeat_notif = (
            await session.execute(select(Notification).where(Notification.title.like("%Поражение%")))
        ).scalar_one_or_none()
        assert defeat_notif is not None
        assert defeat_notif.meta_json["outcome"] == "defeat"
        assert defeat_notif.meta_json["remaining_hp"] == 4000
        assert defeat_notif.meta_json["max_hp"] == 10000
    presets_slice = hub.get_slice(acc_id, "presets")
    assert presets_slice is not None
    assert presets_slice.data["activeRun"] is None


