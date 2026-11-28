import sys
import hmac
import hashlib
import json
import urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select

from core.config import settings
from core.database import get_engine, init_db, get_session
from core.models import (
    Account,
    BotConfig,
    Notification,
    PlayerSnapshot,
    SentFriendRequest,
    TrackedCandidate,
    FriendStats,
    BossFriendDamageLog,
    FriendsCountSnapshot,
)
from bot.handlers import bot_context
from web.app import app


def generate_valid_init_data(bot_token: str, user_id: int) -> str:
    """Генерация валидной строки Telegram WebApp initData с подписью HMAC-SHA256."""
    user_str = json.dumps({"id": user_id, "first_name": "TestAdmin"}, separators=(",", ":"))
    params = {
        "auth_date": "1700000000",
        "query_id": "AAHdF60uAAAAAN0XrS4",
        "user": user_str,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    params["hash"] = hash_value
    return urllib.parse.urlencode(params)


@pytest_asyncio.fixture
async def web_setup(monkeypatch):
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)

    # Задаем тестовые параметры авторизации
    monkeypatch.setattr(settings, "TG_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setattr(settings, "ADMIN_TG_ID", 437225657)
    monkeypatch.setattr(settings, "WEB_ADMIN_TOKEN", "test_admin_token")

    async with get_session(engine) as session:
        acc = Account(id=1, phone="+79991234567", nickname="WebHero")
        session.add(acc)
        await session.flush()

        cfg = BotConfig(account_id=acc.id, is_paused=False)
        session.add(cfg)

        snap = PlayerSnapshot(
            account_id=acc.id,
            level=10,
            authority=5000,
            biceps=20,
            energy=75,
            max_energy=100,
        )
        session.add(snap)

        # Создаем уведомления разных категорий
        n1 = Notification(account_id=acc.id, category="bosses", title="Босс 1", is_read=False)
        n2 = Notification(account_id=acc.id, category="prisons", title="Ходка 1", is_read=False)
        n3 = Notification(account_id=acc.id, category="business", title="Бизнес 1", is_read=True)
        session.add_all([n1, n2, n3])

    bot_context.db_engine = engine
    bot_context._boss_api = None
    bot_context._player_api = None
    bot_context._prison_api = None
    bot_context._social_api = None
    bot_context.boss_worker = None
    bot_context.routine_worker = None
    bot_context.prison_worker = None
    bot_context.social_worker = None

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
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


@pytest.mark.asyncio
async def test_auth_rejection_without_token(web_setup):
    """Запросы без авторизации или с неверным токеном отклоняются с 401/403."""
    client, _ = web_setup

    # Без заголовков
    res_no_auth = await client.get("/api/v1/state")
    assert res_no_auth.status_code == 401

    # С неверным токеном браузера
    res_bad_token = await client.get("/api/v1/state", headers={"X-Admin-Token": "wrong_token"})
    assert res_bad_token.status_code == 401

    # С initData от чужого пользователя
    bad_init_data = generate_valid_init_data(settings.TG_BOT_TOKEN, user_id=999999999)
    res_bad_user = await client.get("/api/v1/state", headers={"X-Telegram-Init-Data": bad_init_data})
    assert res_bad_user.status_code == 403


@pytest.mark.asyncio
async def test_auth_success_with_telegram_init_data(web_setup):
    """Успешная авторизация через HMAC-SHA256 подпись Telegram WebApp initData."""
    client, _ = web_setup

    valid_init_data = generate_valid_init_data(settings.TG_BOT_TOKEN, user_id=437225657)
    res = await client.get("/api/v1/state", headers={"X-Telegram-Init-Data": valid_init_data})

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["snapshot"]["level"] == 10
    assert data["snapshot"]["authority"] == 5000
    assert data["counts"]["all"] == 3
    assert data["counts"]["unread"] == 2


@pytest.mark.asyncio
async def test_get_config_endpoint(web_setup):
    """Проверка получения текущей конфигурации через GET /api/v1/config."""
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    resp = await client.get("/api/v1/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "config" in data
    assert "is_paused" in data["config"]


@pytest.mark.asyncio
async def test_patch_config_live_update(web_setup):
    """Проверка обновления параметров BotConfig через PATCH /api/v1/config."""
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    update_payload = {
        "auto_boss_summon": True,
        "prison_target_id": 5,
        "prison_prefer_night": True,
        "boss_targets": [{"bossId": 1, "mode": "blotnoy", "enabled": True}],
        "is_paused": True,
    }

    res = await client.patch("/api/v1/config", json=update_payload, headers=headers)
    assert res.status_code == 200
    cfg = res.json()["config"]
    assert cfg["auto_boss_summon"] is True
    assert cfg["prison_target_id"] == 5
    assert cfg["prison_prefer_night"] is True
    assert cfg["is_paused"] is True
    assert len(cfg["boss_targets"]) == 1

    # Проверка сохранения в базе данных
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == 1)
        db_cfg = (await session.execute(stmt)).scalar_one()
        assert db_cfg.auto_boss_summon is True
        assert db_cfg.prison_target_id == 5
        assert db_cfg.is_paused is True


@pytest.mark.asyncio
async def test_notifications_filtering_read_and_delete(web_setup):
    """Проверка фильтрации уведомлений, пометки прочитанными и удаления."""
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Фильтрация по категории bosses
    res_bosses = await client.get("/api/v1/notifications?category=bosses", headers=headers)
    assert res_bosses.status_code == 200
    assert len(res_bosses.json()["notifications"]) == 1
    assert res_bosses.json()["notifications"][0]["category"] == "bosses"

    # 2. Фильтрация по unread
    res_unread = await client.get("/api/v1/notifications?category=unread", headers=headers)
    assert len(res_unread.json()["notifications"]) == 2

    # 3. Пометка всех прочитанными (read-all)
    res_read_all = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert res_read_all.status_code == 200

    # Проверяем, что непрочитанных не осталось
    res_unread_after = await client.get("/api/v1/notifications?category=unread", headers=headers)
    assert len(res_unread_after.json()["notifications"]) == 0

    # 4. Удаление прочитанных (delete)
    res_del = await client.delete("/api/v1/notifications?read_only=true", headers=headers)
    assert res_del.status_code == 200

    # Проверяем, что все удалились
    res_all_after = await client.get("/api/v1/notifications?category=all", headers=headers)
    assert len(res_all_after.json()["notifications"]) == 0


@pytest.mark.asyncio
async def test_get_live_profile_and_live_boss(web_setup):
    """Проверка эндпоинтов /api/v1/live/profile и /api/v1/live/boss."""
    from unittest.mock import AsyncMock
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player_api = AsyncMock()
    mock_player_api.init_player.return_value = {
        "id": 90001,
        "nickname": "TestPrisoner",
        "level": 12,
        "authority": 6500,
        "biceps": 45,
        "energy": 40,
        "maxEnergy": 50,
        "currencies": {
            "cigarettes": 1500,
            "sugar": 80,
            "rubles": 200,
            "paper": 10,
            "soap": 5,
            "keys": 3,
        },
        "weapons": {"poison": 3, "gunshot": 2, "knife": 1},
        "canClaimToiletPaper": True,
        "lastBusinessCollectTime": "2026-11-19T00:00:00Z",
    }
    mock_player_api.get_businesses.return_value = {
        "businesses": [{"id": 1, "title": "Ларек", "level": 2}]
    }
    bot_context.player_api = mock_player_api

    # 1. GET /api/v1/live/profile
    res_prof = await client.get("/api/v1/live/profile", headers=headers)
    assert res_prof.status_code == 200
    p_data = res_prof.json()
    assert p_data["success"] is True
    assert p_data["profile"]["nickname"] == "TestPrisoner"
    assert p_data["profile"]["authority"] == 6500
    assert p_data["weapons"]["poisonCount"] == 3
    assert len(p_data["businesses"]) == 1
    assert p_data["businesses"][0]["title"] == "Ларек"

    # Проверяем запись нового PlayerSnapshot в SQLite
    async with get_session(engine) as session:
        stmt = select(PlayerSnapshot).where(PlayerSnapshot.level == 12)
        snap = (await session.execute(stmt)).scalar_one_or_none()
        assert snap is not None
        assert snap.authority == 6500
        assert snap.biceps == 45

    # 2. GET /api/v1/live/boss
    mock_boss_api = AsyncMock()
    mock_boss_api.get_bootstrap.return_value = {
        "state": "active",
        "hasReward": False,
        "session": {
            "bossId": 2,
            "title": "Сизый",
            "mode": "pacansky",
            "currentHp": 1200,
            "maxHp": 1500,
            "personalDamage": 300,
            "endsAt": "2026-11-19T06:00:00Z",
        },
        "playerStats": {"wins": 5, "keys": 2},
    }
    mock_boss_api.get_weapons.return_value = {
        "lastPunchChestTime": "2026-11-19T00:00:00Z",
        "punchChestCooldownSec": 28800,
        "weaponStatsEffective": {"punchChest": {"damage": 50}},
    }
    bot_context.boss_api = mock_boss_api

    res_boss = await client.get("/api/v1/live/boss", headers=headers)
    assert res_boss.status_code == 200
    b_data = res_boss.json()
    assert b_data["success"] is True
    assert b_data["session"]["title"] == "Сизый"
    assert b_data["weaponStatsEffective"]["punchChest"]["damage"] == 50
    assert b_data["meleeTimestamps"]["lastPunchChestTime"] == "2026-11-19T00:00:00Z"


@pytest.mark.asyncio
async def test_post_action_boss_hit(web_setup):
    """Проверка валидации оружия, нанесения удара и логирования в ActionLog."""
    from unittest.mock import AsyncMock
    from core.models import ActionLog

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss_api = AsyncMock()
    mock_boss_api.hit_boss.return_value = {"damage": 50, "currentHp": 1150}
    bot_context.boss_api = mock_boss_api

    # 1. Недопустимое оружие -> 400
    res_bad = await client.post(
        "/api/v1/actions/boss/hit",
        json={"weapon": "laser_gun", "count": 1},
        headers=headers,
    )
    assert res_bad.status_code == 400

    # 2. Допустимое оружие -> 200
    res_ok = await client.post(
        "/api/v1/actions/boss/hit",
        json={"weapon": "punchChest", "count": 1},
        headers=headers,
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["success"] is True
    assert res_ok.json()["result"]["damage"] == 50

    # Проверка сохранения в ActionLog
    async with get_session(engine) as session:
        stmt = select(ActionLog).where(ActionLog.action_type == "manual_boss_hit")
        log = (await session.execute(stmt)).scalars().first()
        assert log is not None
        assert log.endpoint == "/api/boss/use-weapon"
        assert log.details["weapon"] == "punchChest"


@pytest.mark.asyncio
async def test_post_action_boss_claim_and_prison_work(web_setup):
    """Проверка сбора награды за босса и ходок в тюрьме с фиксацией в Notifications."""
    from unittest.mock import AsyncMock

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Boss Claim
    mock_boss_api = AsyncMock()
    mock_boss_api.claim_reward.return_value = {
        "authority": 1000,
        "cigarettes": 50,
        "stashes": 1,
    }
    bot_context.boss_api = mock_boss_api

    res_claim = await client.post("/api/v1/actions/boss/claim", json={}, headers=headers)
    assert res_claim.status_code == 200
    assert res_claim.json()["success"] is True

    # Проверяем создание Notification(category="bosses")
    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.category == "bosses").order_by(Notification.id.desc())
        notif = (await session.execute(stmt)).scalars().first()
        assert notif is not None
        assert any(r["currency"] == "authority" for r in notif.rewards)

    # 2. Prison Work (серия из 2 ходок)
    mock_prison_api = AsyncMock()
    mock_prison_api.do_prison_work.return_value = {
        "rewardAuthority": 100,
        "rewardCigarettes": 25,
        "stash": True,
    }
    bot_context.prison_api = mock_prison_api

    res_work = await client.post(
        "/api/v1/actions/prison/work",
        json={"prisonId": 1, "isDay": True, "count": 2},
        headers=headers,
    )
    assert res_work.status_code == 200
    assert res_work.json()["completed"] == 2

    # Проверяем агрегированное уведомление (новый формат Кликов: 2)
    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.category == "prisons").order_by(Notification.id.desc())
        p_notif = (await session.execute(stmt)).scalars().first()
        assert p_notif is not None
        assert p_notif.subtitle == "Кликов: 2"
        assert p_notif.meta_json.get("type") == "prison_action"
        # 100 * 2 = 200 авторитета
        auth_rew = next((r for r in p_notif.rewards if r["currency"] == "authority"), None)
        assert auth_rew is not None
        assert auth_rew["amount"] == 200


@pytest.mark.asyncio
async def test_post_action_routine_collect(web_setup):
    """Проверка ручного сбора прибыли бизнесов и подогревов."""
    from unittest.mock import AsyncMock

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player_api = AsyncMock()
    mock_player_api.collect_business_rewards.return_value = {
        "rubles": 25,
        "cigarettes": 150,
    }
    mock_player_api.collect_all_podogrev.return_value = {
        "cigarettes": 30,
        "paper": 2,
    }
    bot_context.player_api = mock_player_api

    # 1. Routine Business
    res_biz = await client.post(
        "/api/v1/actions/routine/collect",
        json={"target": "business"},
        headers=headers,
    )
    assert res_biz.status_code == 200
    assert res_biz.json()["success"] is True

    # 2. Routine Podogrev
    res_pod = await client.post(
        "/api/v1/actions/routine/collect",
        json={"target": "podogrev"},
        headers=headers,
    )
    assert res_pod.status_code == 200
    assert res_pod.json()["success"] is True

    # Проверяем уведомления
    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.category == "business").order_by(Notification.id.desc())
        biz_notif = (await session.execute(stmt)).scalars().first()
        assert biz_notif is not None
        assert any(r["currency"] == "rubles" for r in biz_notif.rewards)


@pytest.mark.asyncio
async def test_ping_endpoint(web_setup):
    """GET /api/v1/ping возвращает ok: true и задержку game_ping_ms."""
    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    res = await client.get("/api/v1/ping", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "game_ping_ms" in data
    assert isinstance(data["game_ping_ms"], int)


@pytest.mark.asyncio
async def test_live_profile_business_merging_and_pending_resources(web_setup):
    """
    Проверка корректного слияния businesses и playerBusinesses в GET /api/v1/live/profile:
    подстановка реальных уровней игрока (2 и 3 вместо 1) и точный расчет pendingResources.
    """
    from unittest.mock import AsyncMock

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player_api = AsyncMock()
    mock_player_api.init_player.return_value = {
        "success": True,
        "energy": 50,
        "maxEnergy": 100,
        "rubles": 200,
        "cigarettes": 1500,
        "sugar": 50,
        "toiletPaper": 10,
        "soap": 5,
        "keys": 12,
        "nickname": "Baron",
        "level": 15,
        "authority": 12000,
        "biceps": 150,
        "talents": 8,
    }
    mock_player_api.get_businesses.return_value = {
        "success": True,
        "businesses": [
            {
                "businessId": 1,
                "prisonId": 1,
                "title": "Лесопилка",
                "level": 1,
                "maxLevel": 8,
                "rewardType": "cigarettes",
                "rewardPerLevel": 20,
            },
            {
                "businessId": 2,
                "prisonId": 1,
                "title": "Швейка",
                "level": 1,
                "maxLevel": 8,
                "rewardType": "rubles",
                "rewardPerLevel": 5,
            },
        ],
        "playerBusinesses": [
            {"businessId": 1, "prisonId": 1, "level": 2},
            {"businessId": 2, "prisonId": 1, "level": 3},
        ],
        "lastCollectTime": "2020-01-01T00:00:00Z",
    }

    mock_boss_api = AsyncMock()
    mock_boss_api.get_weapons.return_value = {
        "weapons": {"poisonCount": 5, "gunshotCount": 3, "knifeCount": 2}
    }

    bot_context.player_api = mock_player_api
    bot_context.boss_api = mock_boss_api

    res = await client.get("/api/v1/live/profile", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    biz_list = data["businesses"]
    assert len(biz_list) == 2
    b1 = next(b for b in biz_list if b["businessId"] == 1)
    b2 = next(b for b in biz_list if b["businessId"] == 2)

    # Реальные уровни из playerBusinesses
    assert b1["level"] == 2
    assert b2["level"] == 3

    # pendingResources: 2 * 20 = 40 папирос, 3 * 5 = 15 рублей
    pending = data["pendingResources"]
    assert pending["cigarettes"] == 40
    assert pending["rubles"] == 15


@pytest.mark.asyncio
async def test_patch_config_friend_filters_and_night_mode(web_setup):
    """Проверка сохранения фильтров друзей и prison_prefer_night через PATCH /api/v1/config."""
    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    patch_payload = {
        "prison_prefer_night": True,
        "friend_accept_all": False,
        "friend_min_talents": 12,
        "friend_min_poison_damage": 350,
        "friend_min_total_damage": 600,
        "friend_min_level": 8,
        "friend_min_authority": 2000,
        "friend_min_biceps": 150,
        "friend_auto_decline_below": True,
    }

    res_patch = await client.patch("/api/v1/config", json=patch_payload, headers=headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["success"] is True

    # Проверяем отражение в GET /api/v1/state
    res_state = await client.get("/api/v1/state", headers=headers)
    assert res_state.status_code == 200
    cfg = res_state.json()["config"]

    assert cfg["prison_prefer_night"] is True
    assert cfg["friend_accept_all"] is False
    assert cfg["friend_min_talents"] == 12
    assert cfg["friend_min_poison_damage"] == 350
    assert cfg["friend_min_total_damage"] == 600
    assert cfg["friend_min_level"] == 8
    assert cfg["friend_min_authority"] == 2000
    assert cfg["friend_min_biceps"] == 150
    assert cfg["friend_auto_decline_below"] is True


@pytest.mark.asyncio
async def test_bot_config_safe_defaults_for_new_account(web_setup):
    """
    Проверка безопасных дефолтов BotConfig для нового аккаунта:
    Все тумблеры автоматизации выключены (False) по умолчанию.
    """
    from core.database import get_or_create_config

    client, engine = web_setup
    async with get_session(engine) as session:
        new_acc = Account(phone="+79991112233", nickname="NewbiePlayer")
        session.add(new_acc)
        await session.flush()
        acc_id = new_acc.id

    cfg = await get_or_create_config(acc_id, engine)
    assert cfg.auto_toilet_paper is False
    assert cfg.auto_business is False
    assert cfg.auto_beard is False
    assert cfg.auto_podogrev is False
    assert cfg.auto_boss_hits is False
    assert cfg.auto_boss_summon is False
    assert cfg.boss_allow_paid_weapons is False
    assert cfg.auto_prison is False
    assert cfg.auto_masters is False
    assert cfg.auto_gifts is False
    assert cfg.auto_friends is False
    assert cfg.auto_events is False
    assert cfg.auto_kolsik is False
    assert cfg.kolsik_currency == "paper"
    assert cfg.friend_accept_all is False
    assert cfg.friend_auto_decline_below is False
    assert cfg.sleep_mode_enabled is False


@pytest.mark.asyncio
async def test_patch_config_auto_gifts_and_kolsik(web_setup):
    """Проверка переключения auto_gifts, auto_kolsik и валидации kolsik_currency через PATCH /api/v1/config."""
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Включение auto_gifts, auto_kolsik и выбор рублей
    patch_res = await client.patch("/api/v1/config", json={
        "auto_gifts": True,
        "auto_kolsik": True,
        "kolsik_currency": "rubles",
    }, headers=headers)
    assert patch_res.status_code == 200
    cfg = patch_res.json()["config"]
    assert cfg["auto_gifts"] is True
    assert cfg["auto_kolsik"] is True
    assert cfg["kolsik_currency"] == "rubles"

    # 2. Выключение auto_gifts и смена на бумагу
    patch_res2 = await client.patch("/api/v1/config", json={
        "auto_gifts": False,
        "kolsik_currency": "paper",
    }, headers=headers)
    assert patch_res2.status_code == 200
    cfg2 = patch_res2.json()["config"]
    assert cfg2["auto_gifts"] is False
    assert cfg2["kolsik_currency"] == "paper"

    # 3. Отклонение невалидной валюты с кодом 400
    bad_res = await client.patch("/api/v1/config", json={
        "kolsik_currency": "gold",
    }, headers=headers)
    assert bad_res.status_code == 400


@pytest.mark.asyncio
async def test_enriched_friend_requests_api(web_setup):
    """Проверка возврата обогащенных статов кандидатов в GET /api/v1/friendship/requests."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.social import SocialAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_enriched_friend_requests = AsyncMock(return_value=[
        {
            "userId": 99901,
            "nickname": "Авторитетный Вася",
            "photoUrl": "https://img.test/vasya.png",
            "level": 42,
            "authority": 500000,
            "biceps": 1800,
            "talents": 120,
            "poisonDamage": 6000,
            "totalDamage": 15000,
        }
    ])
    bot_context.social_api = mock_social

    res = await client.get("/api/v1/friendship/requests", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["total"] == 1
    candidate = body["requests"][0]
    assert candidate["userId"] == 99901
    assert candidate["nickname"] == "Авторитетный Вася"
    assert candidate["level"] == 42
    assert candidate["authority"] == 500000
    assert candidate["biceps"] == 1800
    assert candidate["talents"] == 120
    assert candidate["poisonDamage"] == 6000
    assert candidate["totalDamage"] == 15000


@pytest.mark.asyncio
async def test_action_kolsik_roll_api(web_setup):
    """Проверка ручной покупки наколки у Кольщика через POST /api/v1/actions/kolsik/roll."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.player import PlayerAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.roll_kolsik = AsyncMock(return_value={
        "success": True,
        "reward": {
            "id": 77,
            "title": "Купола на груди",
            "cardPreviewUrl": "assets/tattoos/cupola.png",
        }
    })
    bot_context.player_api = mock_player

    # 1. Покупка за туалетную бумагу
    res_paper = await client.post("/api/v1/actions/kolsik/roll", json={"currency": "paper"}, headers=headers)
    assert res_paper.status_code == 200
    data_paper = res_paper.json()
    assert data_paper["success"] is True
    assert data_paper["currency"] == "paper"
    assert data_paper["parsed"]["drops"][0]["title"] == "Купола на груди"

    # 2. Покупка за рубли
    res_rub = await client.post("/api/v1/actions/kolsik/roll", json={"currency": "rubles"}, headers=headers)
    assert res_rub.status_code == 200
    assert res_rub.json()["currency"] == "rubles"

    # 3. Невалидная валюта -> 400
    res_bad = await client.post("/api/v1/actions/kolsik/roll", json={"currency": "soap"}, headers=headers)
    assert res_bad.status_code == 400

    # Проверка сохранения уведомления в БД
    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.title == "Кольщик (Наколка)")
        notifs = (await session.execute(stmt)).scalars().all()
        assert len(notifs) >= 2


@pytest.mark.asyncio
async def test_get_monthly_state_api(web_setup):
    """Проверка эндпоинта GET /api/v1/monthly/state."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.social import SocialAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_monthly_state = AsyncMock(return_value={
        "active": True,
        "user": {
            "claimableTiers": [1, 2],
            "claimedTiers": [0],
        },
        "summary": {"completedDisplay": "2/30"},
        "today": {"title": "Сделать 3 ходки", "target": 3, "progress": 1},
    })
    bot_context.social_api = mock_social

    res = await client.get("/api/v1/monthly/state", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["state"]["summary"]["completedDisplay"] == "2/30"
    assert len(body["state"]["user"]["claimableTiers"]) == 2


@pytest.mark.asyncio
async def test_talents_api(web_setup):
    """Проверка возврата талантов, подсчета totalPoints и списка талантов."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.player import PlayerAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_talents_status = AsyncMock(return_value={
        "state": {
            "spentPoints": 12,
            "unspentPoints": 3,
            "currentDamage": 15000,
            "talentLevels": {"1": 4, "2": 2},
        },
        "requiredDamage": 20000,
        "biceps": 350,
        "config": {
            "1": {"name": "Сила удара", "description": "Увеличивает урон", "maxLevel": 10, "cost": 1},
            "2": {"name": "Ядовитый зуб", "description": "Бонус к яду", "maxLevel": 5, "cost": 2},
        }
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/talents", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["state"]["totalPoints"] == 15
    assert data["state"]["unspentPoints"] == 3
    assert data["state"]["currentDamage"] == 15000
    assert data["state"]["requiredDamage"] == 20000
    assert data["state"]["biceps"] == 350
    assert len(data["talents"]) == 2
    assert data["talents"][0]["id"] == 1
    assert data["talents"][0]["currentLevel"] == 4


@pytest.mark.asyncio
async def test_collections_api(web_setup):
    """Проверка возврата коллекций с проверкой canExchange и нычками."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.player import PlayerAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_collections = AsyncMock(return_value={
        "collections": [
            {
                "prisonId": 1,
                "collectionId": 101,
                "name": "Бутырка",
                "items": [
                    {"id": 1, "name": "Перо"},
                    {"id": 2, "name": "Заточка"},
                ]
            }
        ],
        "playerProgress": {
            "data": {"1": 3, "2": 1}
        }
    })
    mock_player.init_player = AsyncMock(return_value={
        "stashes": [{"id": 10, "name": "Золотая нычка"}]
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/collections", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["collections"]) == 1
    col = data["collections"][0]
    assert col["name"] == "Бутырка"
    assert col["collected"] == 2
    assert col["total"] == 2
    assert col["canExchange"] is True
    assert len(data["stashes"]) == 1
    assert data["stashes"][0]["name"] == "Золотая нычка"


@pytest.mark.asyncio
async def test_bauls_api(web_setup):
    """Проверка возврата статистики баула и распаковки stats."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.player import PlayerAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_bauls_stat = AsyncMock(return_value={
        "stats": {
            "active": True,
            "level": 17,
            "maxLevel": 30,
            "currentExp": 1700,
            "expToNext": 7000,
            "pendingRewards": [{"type": "rubles", "amount": 50}],
        }
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/bauls", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["stats"]["level"] == 17
    assert data["stats"]["maxLevel"] == 30
    assert data["stats"]["currentExp"] == 1700
    assert data["stats"]["expToNext"] == 7000
    assert len(data["stats"]["pendingRewards"]) == 1


@pytest.mark.asyncio
async def test_static_icons_available(web_setup):
    """Проверка доступности локальных иконок игры через /static/assets/icons/ с 200 OK."""
    client, _ = web_setup

    test_icons = ["knife.webp", "rubles.webp", "authority.webp", "PlayerSprite.png"]
    for icon_name in test_icons:
        res = await client.get(f"/static/assets/icons/{icon_name}")
        assert res.status_code == 200, f"Icon {icon_name} returned {res.status_code}"
        assert len(res.content) > 0
        content_type = res.headers.get("content-type", "")
        assert "image/" in content_type or "application/octet-stream" in content_type


@pytest.mark.asyncio
async def test_collections_api_two_level_structure(web_setup):
    """Проверка двухуровневой структуры /api/collection/player/full с реальными именами и прогрессом."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.player import PlayerAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_collections = AsyncMock(return_value={
        "collections": [
            {
                "prisonid": 1,
                "prison": "Бутырка",
                "collections": [
                    {
                        "id": 101,
                        "name": "Мастера закатки",
                        "items": [
                            {"id": 1, "name": "Банка"},
                            {"id": 2, "name": "Крышка"},
                        ],
                        "rewards": {"rubles": 100}
                    }
                ]
            }
        ],
        "playerProgress": {
            "data": {
                "1": {
                    "101": {"1": 5, "2": 0}
                }
            }
        }
    })
    mock_player.init_player = AsyncMock(return_value={
        "stashes": [{"id": 10, "name": "Золотая нычка"}]
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/collections", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["collections"]) == 1
    col = data["collections"][0]
    assert col["prisonName"] == "Бутырка"
    assert col["name"] == "Мастера закатки"
    assert col["name"] != "Коллекция #0"
    assert col["collected"] == 1
    assert col["total"] == 2
    assert col["canExchange"] is False


@pytest.mark.asyncio
async def test_asset_proxy_endpoint(web_setup):
    """Проверка валидации путей в /api/v1/assets/proxy."""
    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # Недопустимый путь с ..
    res_bad = await client.get("/api/v1/assets/proxy?path=../secret.txt", headers=headers)
    assert res_bad.status_code == 400

    # Недопустимый путь не из разрешенных префиксов
    res_bad2 = await client.get("/api/v1/assets/proxy?path=etc/passwd", headers=headers)
    assert res_bad2.status_code == 400





@pytest.mark.asyncio
async def test_public_asset_proxy_security_and_no_auth(web_setup):
    """
    Проверка GET /api/v1/assets/proxy:
    - не требует авторизации (X-Admin-Token)
    - блокирует path traversal (..) со статусом 400
    - блокирует внешние URL со статусом 400
    - блокирует неразрешенные префиксы со статусом 400
    """
    client, _ = web_setup

    res_traversal = await client.get("/api/v1/assets/proxy?path=../etc/passwd")
    assert res_traversal.status_code == 400

    res_external = await client.get("/api/v1/assets/proxy?path=https://malicious.site/script.js")
    assert res_external.status_code == 400

    res_disallowed = await client.get("/api/v1/assets/proxy?path=secret/keys.json")
    assert res_disallowed.status_code == 400


@pytest.mark.asyncio
async def test_asset_proxy_disk_cache_and_cors(web_setup, monkeypatch):
    """Проверка CORS заголовков и дискового кэширования в GET /api/v1/assets/proxy."""
    client, _ = web_setup
    import hashlib
    from pathlib import Path
    from web.routes import ASSET_CACHE_DIR

    test_path = "assets/PrisonV3/TestSprite.png"
    test_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest_png_bytes"
    path_hash = hashlib.sha256(test_path.encode("utf-8")).hexdigest()
    cached_file = ASSET_CACHE_DIR / f"{path_hash}.png"

    # Создаем тестовый файл в кэше
    cached_file.parent.mkdir(parents=True, exist_ok=True)
    cached_file.write_bytes(test_content)

    try:
        res = await client.get(f"/api/v1/assets/proxy?path={test_path}")
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "*"
        assert "max-age=" in res.headers.get("cache-control", "")
        assert res.content == test_content
    finally:
        if cached_file.exists():
            cached_file.unlink()


@pytest.mark.asyncio
async def test_catalogs_boss_keys_mapping(web_setup):
    """
    Проверка GET /api/v1/catalogs:
    - 58 боссов в каталоге
    - Сизый (требует ключи Кирпича): availableKeys == 0 при keys["1"] == 0
    - Махно (требует ключи Сизого): availableKeys == 14 при keys["2"] == 14
    """
    from unittest.mock import MagicMock, AsyncMock
    from client.api.boss import BossAPI
    from bot.handlers import bot_context
    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss = MagicMock(spec=BossAPI)
    mock_boss.get_bootstrap = AsyncMock(return_value={
        "playerStats": {
            "keys": {"1": 0, "2": 14},
            "dailyWins": {},
        }
    })
    from client.api.boss import _load_bosses_catalog
    catalog = _load_bosses_catalog()
    mock_boss.get_all_bosses = AsyncMock(return_value=[dict(b) for b in catalog])

    mock_worker = MagicMock()
    mock_worker.api = mock_boss
    bot_context.boss_worker = mock_worker

    res = await client.get("/api/v1/catalogs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["bosses"]) == 58

    sizy = next(b for b in data["bosses"] if b["id"] == 2)
    assert sizy["requiredKeyBossId"] == 1
    assert sizy["availableKeys"] == 0

    makhno = next(b for b in data["bosses"] if b["id"] == 3)
    assert makhno["requiredKeyBossId"] == 2
    assert makhno["availableKeys"] == 14


@pytest.mark.asyncio
async def test_talents_list_config_handling(web_setup):
    """Проверка GET /api/v1/talents при формате config как list[dict] (реальный формат игрового сервера)."""
    from unittest.mock import MagicMock, AsyncMock
    from client.api.player import PlayerAPI
    from bot.handlers import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_talents_status = AsyncMock(return_value={
        "state": {
            "spentPoints": 15,
            "unspentPoints": 5,
            "currentDamage": 250000,
            "requiredDamage": 1000000,
        },
        "config": [
            {"id": 1, "name": "Удар в челюсть", "maxLevel": 10, "currentLevel": 4, "description": "Повышает урон"},
            {"id": 2, "name": "Финт", "maxLevel": 5, "currentLevel": 1, "description": "Шанс комбо"},
        ]
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/talents", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["state"]["totalPoints"] == 20
    assert len(data["talents"]) == 2
    assert data["talents"][0]["name"] == "Удар в челюсть"
    assert data["talents"][0]["currentLevel"] == 4


@pytest.mark.asyncio
async def test_collections_nested_items_handling(web_setup):
    """Проверка GET /api/v1/collections на реальной вложенной структуре playerProgress.data[p][c]['items']."""
    from unittest.mock import MagicMock, AsyncMock
    from client.api.player import PlayerAPI
    from bot.handlers import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_collections = AsyncMock(return_value={
        "collections": [
            {
                "prisonid": 2,
                "prison": "Кресты",
                "collections": [
                    {
                        "id": 205,
                        "name": "Набор арестанта",
                        "items": [
                            {"id": 1, "name": "Чай", "icon": "assets/item1.png"},
                            {"id": 2, "name": "Папиросы", "icon": "assets/item2.png"},
                        ]
                    }
                ]
            }
        ],
        "playerProgress": {
            "data": {
                "2": {
                    "205": {
                        "items": {"1": 4, "2": 2}
                    }
                }
            }
        }
    })
    mock_player.init_player = AsyncMock(return_value={
        "stashes": [{"id": 5, "name": "Заначка"}]
    })
    mock_player.get_stashgear_all = AsyncMock(return_value={
        "camera": [{"id": 501, "name": "Шмотка из нычки"}],
        "baryga": [],
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/collections", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["collections"]) == 1
    c = data["collections"][0]
    assert c["name"] == "Набор арестанта"
    assert c["collected"] == 2
    assert c["total"] == 2
    assert c["canExchange"] is True
    assert len(data["stashes"]) == 1
    assert len(data["stashItems"]) == 1


@pytest.mark.asyncio
async def test_bauls_rewards_enrichment(web_setup):
    """Проверка обогащения наград баулов иконками и подписями в GET /api/v1/bauls."""
    from unittest.mock import MagicMock, AsyncMock
    from client.api.player import PlayerAPI
    from bot.handlers import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    mock_player.get_bauls_stat = AsyncMock(return_value={
        "stats": {
            "level": 5,
            "maxLevel": 30,
            "currentExp": 120,
            "expToNext": 500,
            "pendingRewards": [
                {"type": "currency", "id": "soap", "amount": 25},
                {"type": "weapon", "id": "poison", "amount": 10},
                {"type": "key", "id": 1, "amount": 3},
                {"type": "stash", "id": 2, "amount": 1},
                {"type": "tattoo", "id": 101, "amount": 1},
            ]
        }
    })
    bot_context.player_api = mock_player

    res = await client.get("/api/v1/bauls", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    rewards = data["stats"]["pendingRewards"]
    assert len(rewards) == 5

    for r in rewards:
        assert "iconKey" in r
        assert "label" in r
        assert "imageUrl" in r
        assert r["amount"] > 0

    assert rewards[0]["label"] == "Мыло"
    assert rewards[1]["label"] == "Яд"
    assert "Кирпич" in rewards[2]["label"]


@pytest.mark.asyncio
async def test_notifications_event_key_deduplication(web_setup):
    """Проверка дедупликации уведомлений по полю event_key."""
    from core.drop_parser import DropParser
    from core.models import Notification
    from sqlalchemy import select

    _, engine = web_setup

    payload = {
        "title": "Победа над боссом Кирпич",
        "subtitle": "Собрана награда",
        "category": "bosses",
        "rewards": [{"type": "soap", "amount": 5, "label": "Мыло"}],
        "event_key": "boss_win_1_20261121",
    }

    n1 = await DropParser.save_notification(1, payload, engine)
    assert n1 is not None

    n2 = await DropParser.save_notification(1, payload, engine)
    assert n2 is not None
    assert n1.id == n2.id  # Тот же самый объект, не создан дубликат!

    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.event_key == "boss_win_1_20261121")
        all_notifs = (await session.execute(stmt)).scalars().all()
        assert len(all_notifs) == 1


@pytest.mark.asyncio
async def test_boss_buffs_nested_unpacking_and_string_activation(web_setup):
    """
    Тест разбора data.buffs в GET /api/v1/boss/buffs и активации строкового ID в POST /api/v1/actions/boss/buffs/activate:
    - Ответ игрового сервера: {"success": true, "data": {"buffs": [...]}}
    - Проверка id: "buff_skuns", title: "Скунс", priceTp: 8
    - Активация {"buffId": "buff_skuns"}
    """
    from unittest.mock import MagicMock, AsyncMock
    from client.api.boss import BossAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss = MagicMock(spec=BossAPI)
    mock_boss.get_boss_buffs = AsyncMock(return_value={
        "success": True,
        "data": {
            "buffs": [
                {
                    "id": "buff_skuns",
                    "titleRu": "Скунс",
                    "descriptionRu": "Время действия: 8 часов. Увеличивает урон ядом на 30.",
                    "type": "temporary",
                    "category": "temporary",
                    "icon": "assets/PrisonV3/bafss/icon/time/5.png",
                    "priceTp": 8,
                    "cooldownSeconds": 28800,
                    "durationHits": 0,
                    "isPurchasable": True,
                    "buffs": [{"stat": "poisonDamage", "value": 30}]
                },
                {
                    "id": "buff_olympiec",
                    "titleRu": "Олимпиец",
                    "descriptionRu": "Даёт +12 к максимальной энергии.",
                    "type": "permanent",
                    "category": "permanent",
                    "icon": "assets/PrisonV3/bafss/icon/Constant/1.png",
                    "priceTp": 3,
                    "cooldownSeconds": 0,
                    "durationHits": 0,
                    "isPurchasable": False,
                    "buffs": [{"stat": "energyMax", "value": 12}]
                }
            ]
        }
    })
    mock_boss.get_bootstrap = AsyncMock(return_value={
        "activeBuffsByCategory": {"temporary": ["buff_skuns"]},
        "buffCooldowns": [{"id": "buff_skuns", "endsAt": "2026-11-22T08:00:00Z"}]
    })
    mock_boss.activate_boss_buff = AsyncMock(return_value={"success": True, "activated": "buff_skuns"})
    bot_context.boss_api = mock_boss

    # 1. GET /api/v1/boss/buffs
    res = await client.get("/api/v1/boss/buffs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    buffs = data["buffs"]
    assert len(buffs) == 2

    skuns = next(b for b in buffs if b["id"] == "buff_skuns")
    assert skuns["title"] == "Скунс"
    assert skuns["priceTp"] == 8
    assert skuns["isActive"] is True
    assert skuns["category"] == "temporary"

    olympiec = next(b for b in buffs if b["id"] == "buff_olympiec")
    assert olympiec["title"] == "Олимпиец"
    assert olympiec["priceTp"] == 3
    assert olympiec["isActive"] is False
    assert olympiec["category"] == "permanent"

    # 2. POST /api/v1/actions/boss/buffs/activate
    act_res = await client.post(
        "/api/v1/actions/boss/buffs/activate",
        json={"buffId": "buff_skuns"},
        headers=headers
    )
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert act_data["success"] is True
    mock_boss.activate_boss_buff.assert_awaited_once_with("buff_skuns")


@pytest.mark.asyncio
async def test_catalogs_boss_order_and_loot_enrichment(web_setup):
    """
    Тест каталога боссов в GET /api/v1/catalogs:
    - наличие sortOrder (0..57);
    - наличие totalWins, dailyWins, dailyLimit;
    - наличие modes c hp и loot (currencies + items).
    """
    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    res = await client.get("/api/v1/catalogs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    bosses = data["bosses"]
    assert len(bosses) == 58

    # Проверка первого босса (Кирпич)
    b0 = bosses[0]
    assert b0["sortOrder"] == 0
    assert b0["name"] == "Кирпич"
    assert "totalWins" in b0
    assert "dailyWins" in b0
    assert "dailyLimit" in b0
    assert "modes" in b0
    assert "pacansky" in b0["modes"]
    assert b0["modes"]["pacansky"]["hp"] == 1000
    assert "currencies" in b0["modes"]["pacansky"]
    assert "items" in b0["modes"]["pacansky"]


@pytest.mark.asyncio
async def test_catalogs_boss_loot_items_and_preview_urls(web_setup):
    """
    Тест обогащения лута боссов в GET /api/v1/catalogs:
    - строгое отсутствие talents.webp в previewUrl предметов лута;
    - нычки (stash) имеют путь к craftZS/items/... или /static/assets/icons/stash.webp;
    - комплекты (tattoo_set, clothing_set) имеют непустые previewUrl и previewParts;
    - хаты (camera) имеют previewUrl.
    """
    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    res = await client.get("/api/v1/catalogs", headers=headers)
    assert res.status_code == 200
    bosses = res.json()["bosses"]

    total_items = 0
    sets_checked = 0
    stashes_checked = 0

    for b in bosses:
        for mode_key, mode_data in b.get("modes", {}).items():
            for item in mode_data.get("items", []):
                total_items += 1
                p_url = item.get("previewUrl", "")
                assert "talents.webp" not in p_url, f"talents.webp found in item {item['name']} for boss {b['name']}"

                kind = item.get("kind")
                if kind == "stash":
                    stashes_checked += 1
                    assert ("craftZS/items" in p_url or "stash.webp" in p_url), f"Invalid stash previewUrl: {p_url}"
                elif kind in ("tattoo_set", "clothing_set"):
                    sets_checked += 1
                    assert p_url, f"Set {item['name']} must have non-empty previewUrl"
                    parts = item.get("previewParts", [])
                    assert isinstance(parts, list) and len(parts) > 0, f"Set {item['name']} must have non-empty previewParts"

    assert total_items > 0
    assert sets_checked > 0
    assert stashes_checked > 0


@pytest.mark.asyncio
async def test_action_accept_and_decline_friendship_with_64bit_id(web_setup):
    """
    Тест ручного принятия и отклонения заявок в друзья через:
    POST /api/v1/actions/friendship/accept
    POST /api/v1/actions/friendship/decline
    - поддержка 64-битного ID (например, 9000000000408017);
    - фиксация вызова в ActionLog.
    """
    from unittest.mock import AsyncMock, MagicMock
    from client.api.social import SocialAPI
    from core.models import ActionLog

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_social = MagicMock(spec=SocialAPI)
    mock_social.accept_friend = AsyncMock(return_value={"success": True})
    mock_social.decline_friend = AsyncMock(return_value={"success": True})
    bot_context.social_api = mock_social

    test_uid = 9000000000408017

    # 1. Принятие
    res_acc = await client.post(
        "/api/v1/actions/friendship/accept",
        json={"fromUserId": test_uid},
        headers=headers,
    )
    assert res_acc.status_code == 200
    assert res_acc.json()["success"] is True
    mock_social.accept_friend.assert_awaited_once_with(test_uid)

    # 2. Отклонение
    res_dec = await client.post(
        "/api/v1/actions/friendship/decline",
        json={"fromUserId": test_uid},
        headers=headers,
    )
    assert res_dec.status_code == 200
    assert res_dec.json()["success"] is True
    mock_social.decline_friend.assert_awaited_once_with(test_uid)

    # 3. Проверка ActionLog
    async with get_session(engine) as session:
        stmt = select(ActionLog).where(ActionLog.action_type.in_(["accept_friend", "decline_friend"]))
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) == 2
        names = {log.action_type for log in logs}
        assert "accept_friend" in names
        assert "decline_friend" in names


@pytest.mark.asyncio
async def test_proxy_game_asset_json(web_setup, monkeypatch):
    """
    Тест проксирования JSON файлов анимаций (EyesAnim, BrushAnim) через GET /api/v1/assets/proxy:
    - правильный Content-Type: application/json;
    - заголовки CORS Access-Control-Allow-Origin: *;
    - дисковое/памятное кэширование.
    """
    from unittest.mock import AsyncMock, MagicMock
    import web.routes as web_routes

    client, _ = web_setup

    sample_json = b'{"frames": [{"filename": "frame_0.png", "frame": {"x": 0, "y": 0, "w": 32, "h": 32}}]}'

    mock_cdn_resp = MagicMock()
    mock_cdn_resp.status_code = 200
    mock_cdn_resp.headers = {"content-type": "application/json"}
    mock_cdn_resp.content = sample_json

    mock_http_client = MagicMock()
    mock_http_client.get = AsyncMock(return_value=mock_cdn_resp)

    monkeypatch.setattr(web_routes, "_get_asset_client", lambda: mock_http_client)

    test_path = "assets/PrisonV3/Face/EyesAnim/Eyes3/Eyes3.json"
    res = await client.get(f"/api/v1/assets/proxy?path={test_path}")

    assert res.status_code == 200
    assert "application/json" in res.headers.get("content-type", "")
    assert res.headers.get("access-control-allow-origin") == "*"
    data = res.json()
    assert "frames" in data
    assert len(data["frames"]) >= 1


@pytest.mark.asyncio
async def test_catalogs_dynamic_ownership_buryat_camera(web_setup):
    """
    Проверка динамического вычисления владения хатами и вещами в GET /api/v1/catalogs:
    - Хата «Бурят» (id: 15) имеет owned: False, ownedCount: 0 когда отсутствует в ownedCameras;
    - Хата «Бурят» (id: 15) становится owned: True, ownedCount: 1 когда присутствует в ownedCameras;
    - Статический флаг owned: true полностью исключен.
    """
    from unittest.mock import AsyncMock, MagicMock
    from client.api.player import PlayerAPI

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock(spec=PlayerAPI)
    bot_context.player_api = mock_player

    # 1. Инвентарь без хаты Бурята (id 15)
    mock_player.get_wardrobe_inventory = AsyncMock(return_value={
        "ownedCameras": [1, 2],
        "ownedTattoos": [],
        "ownedClothing": [],
    })

    res = await client.get("/api/v1/catalogs", headers=headers)
    assert res.status_code == 200
    bosses = res.json()["bosses"]
    buryat = next(b for b in bosses if b["name"] == "Бурят")
    items = buryat["modes"]["pacansky"]["items"]
    buryat_camera = next(it for it in items if it.get("kind") == "camera")
    assert buryat_camera["name"] == "Хата «Бурят»"
    assert buryat_camera["owned"] is False
    assert buryat_camera["ownedCount"] == 0

    # 2. Инвентарь с хатой Бурята (id 15)
    mock_player.get_wardrobe_inventory = AsyncMock(return_value={
        "ownedCameras": [1, 2, 15],
        "ownedTattoos": [],
        "ownedClothing": [],
    })

    res2 = await client.get("/api/v1/catalogs", headers=headers)
    assert res2.status_code == 200
    bosses2 = res2.json()["bosses"]
    buryat2 = next(b for b in bosses2 if b["name"] == "Бурят")
    items2 = buryat2["modes"]["pacansky"]["items"]
    buryat_camera2 = next(it for it in items2 if it.get("kind") == "camera")
    assert buryat_camera2["owned"] is True
    assert buryat_camera2["ownedCount"] == 1


@pytest.mark.asyncio
async def test_boss_buffs_ordinary_and_brigade(web_setup):
    """
    Проверка GET /api/v1/boss/buffs:
    - возвращает структуру с вкладками ordinary (14 личных усилений) и brigade (бригадные усиления);
    - в brigade присутствуют группы Усиление бригады (Навались, Смотри не разбей) и Сходняк 1..20 (Злоба, Отрава и др.).
    """
    from unittest.mock import AsyncMock, MagicMock
    from client.api.boss import BossAPI

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss = MagicMock(spec=BossAPI)
    mock_boss.get_boss_buffs = AsyncMock(return_value={
        "buffs": [{"id": 1, "name": "Удар ярости", "cost": 10}],
    })
    mock_boss.get_guild_buffs = AsyncMock(return_value={
        "success": True,
        "buffs": [
            {"id": "guild_buff_poison", "name": "Навались", "level": 1, "cost": 50},
            {"id": "guild_buff_gunshot", "name": "Смотри не разбей", "level": 1, "cost": 50},
        ],
    })
    mock_boss.get_shodnyak_buffs = AsyncMock(return_value={
        "success": True,
        "buffs": [
            {"id": "shodnyak_rage", "name": "Злоба", "requiredRank": 1, "cost": 100},
            {"id": "shodnyak_poison", "name": "Отрава", "requiredRank": 16, "cost": 250},
        ],
    })
    bot_context.boss_api = mock_boss

    res = await client.get("/api/v1/boss/buffs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "ordinary" in data
    assert "brigade" in data
    assert len(data["ordinary"]) >= 1

    brigade = data["brigade"]
    assert isinstance(brigade, list)
    assert len(brigade) >= 6
    guild_group = next(g for g in brigade if g.get("category") == "guild")
    assert guild_group["categoryTitle"] == "Усиление бригады"
    assert len(guild_group["items"]) == 2

    shodnyak_groups = [g for g in brigade if "shodnyak" in g.get("category", "")]
    assert len(shodnyak_groups) >= 5


@pytest.mark.asyncio
async def test_single_boss_attack_odin_mode_and_locked_rejection(web_setup):
    """
    Проверка ручной атаки босса POST /api/v1/actions/boss/start:
    - поддержка режима 'odin' (В одного);
    - отказ со статусом 400 и unlockReason при попытке напасть на заблокированного босса (например Тротил).
    """
    from unittest.mock import AsyncMock, MagicMock
    from client.api.boss import BossAPI

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss = MagicMock(spec=BossAPI)
    mock_boss.start_battle = AsyncMock(return_value={"success": True, "battleId": 999})
    bot_context.boss_api = mock_boss

    # 1. Успешный старт в режиме 'odin' на открытого босса (Кирпич, id 1)
    res_odin = await client.post(
        "/api/v1/actions/boss/start",
        json={"bossId": 1, "mode": "odin"},
        headers=headers,
    )
    assert res_odin.status_code == 200
    assert res_odin.json()["success"] is True
    mock_boss.start_battle.assert_awaited_with(1, "odin")

    # 2. Попытка напасть на заблокированного босса (Тротил, id 56)
    res_locked = await client.post(
        "/api/v1/actions/boss/start",
        json={"bossId": 56, "mode": "pacansky"},
        headers=headers,
    )
    assert res_locked.status_code == 400
    data = res_locked.json()
    detail_str = str(data.get("detail", data))
    assert "Тротил" in detail_str or "заблокирован" in detail_str.lower()


@pytest.mark.asyncio
async def test_brigade_buff_activation_routes(web_setup):
    """
    Проверка роутинга активации усилений POST /api/v1/actions/boss/buffs/activate:
    - guild_buff_* -> boss_api.activate_guild_buff()
    - shodnyak_* -> boss_api.activate_shodnyak_buff()
    - обычные id -> boss_api.activate_boss_buff()
    """
    from unittest.mock import AsyncMock, MagicMock
    from client.api.boss import BossAPI

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss = MagicMock(spec=BossAPI)
    mock_boss.activate_guild_buff = AsyncMock(return_value={"success": True, "activated": "guild"})
    mock_boss.activate_shodnyak_buff = AsyncMock(return_value={"success": True, "activated": "shodnyak"})
    mock_boss.activate_boss_buff = AsyncMock(return_value={"success": True, "activated": "boss"})
    bot_context.boss_api = mock_boss

    # 1. Guild buff
    res1 = await client.post(
        "/api/v1/actions/boss/buffs/activate",
        json={"buffId": "guild_buff_poison", "guildId": 1},
        headers=headers,
    )
    assert res1.status_code == 200
    mock_boss.activate_guild_buff.assert_awaited_once_with(1, "guild_buff_poison")

    # 2. Shodnyak buff
    res2 = await client.post(
        "/api/v1/actions/boss/buffs/activate",
        json={"buffId": "shodnyak_rage"},
        headers=headers,
    )
    assert res2.status_code == 200
    mock_boss.activate_shodnyak_buff.assert_awaited_once_with("shodnyak_rage")

    # 3. Ordinary buff
    res3 = await client.post(
        "/api/v1/actions/boss/buffs/activate",
        json={"buffId": 5},
        headers=headers,
    )
    assert res3.status_code == 200
    mock_boss.activate_boss_buff.assert_awaited_once_with("5")


@pytest.mark.asyncio
async def test_catalogs_attribute_error_regression_with_routine_worker(web_setup):
    """
    Регрессионный тест бага AttributeError: 'RoutineWorker' object has no attribute 'player_api':
    Проверяет, что при наличии routine_worker с полем .api (без .player_api)
    GET /api/v1/catalogs и GET /api/v1/bosses/catalog возвращают 200 OK без AttributeError.
    """
    from unittest.mock import MagicMock, AsyncMock
    from bot.handlers import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # Создаем RoutineWorker строго без атрибута player_api (только с .api)
    class DummyRoutineWorker:
        def __init__(self):
            self.api = MagicMock()
            self.api.get_wardrobe_inventory = AsyncMock(return_value={
                "ownedCameras": [1, 2],
                "ownedTattoos": [10, 20],
                "ownedClothing": [100, 200],
            })

    dummy_worker = DummyRoutineWorker()
    assert not hasattr(dummy_worker, "player_api")

    old_worker = bot_context.routine_worker
    old_player_api = bot_context._player_api
    bot_context.routine_worker = dummy_worker
    bot_context._player_api = None

    try:
        res = await client.get("/api/v1/catalogs", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "prisons" in data
        assert "bosses" in data
    finally:
        bot_context.routine_worker = old_worker
        bot_context._player_api = old_player_api


@pytest.mark.asyncio
async def test_brigade_buffs_availability_real_checks(web_setup):
    """
    Проверка реального расчета доступности бригадных усилений GET /api/v1/boss/buffs:
    1) Игрок без гильдии -> все баффы заблокированы с unlockReason="Вы не состоите в бригаде";
    2) Игрок в гильдии 50 уровня с правами и победой в Сходняке 1 -> Навались и Злоба доступны для активации.
    """
    from unittest.mock import MagicMock, AsyncMock
    from client.api.boss import BossAPI
    from bot.handlers import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_boss = MagicMock(spec=BossAPI)
    mock_boss.get_boss_buffs = AsyncMock(return_value={"buffs": []})
    mock_boss.get_bootstrap = AsyncMock(return_value={"activeBuffsByCategory": {}, "buffCooldowns": []})
    mock_boss.get_guild_buffs = AsyncMock(return_value={"buffs": []})
    bot_context.boss_api = mock_boss

    # Сценарий 1: игрок не в бригаде
    mock_boss.get_guild_status = AsyncMock(return_value={"inGuild": False})
    mock_boss.get_shodnyak_buffs = AsyncMock(return_value={"buffs": []})

    res1 = await client.get("/api/v1/boss/buffs", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    brigade1 = data1["brigade"]

    # Ищем Навались и Смотри не разбей
    guild_group = next(g for g in brigade1 if g["category"] == "guild")
    for b in guild_group["items"]:
        assert b["isLocked"] is True
        assert b["canActivate"] is False
        assert "не состоите в бригаде" in b["unlockReason"]

    # Сценарий 2: игрок в бригаде 50 уровня, ранг Пахан (1), Сходняк 1 место
    mock_boss.get_guild_status = AsyncMock(return_value={
        "inGuild": True,
        "guild": {"level": 50, "shodnyakRank": 1},
        "myRank": {"rankId": 1, "name": "Пахан"},
        "myPrivileges": ["activateGuildBuff"],
    })
    mock_boss.get_shodnyak_buffs = AsyncMock(return_value={
        "place": 1,
        "buffs": [
            {"id": "shodnyak_zloba", "unlocked": True},
            {"id": "shodnyak_pepel", "unlocked": True},
        ]
    })

    res2 = await client.get("/api/v1/boss/buffs", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    brigade2 = data2["brigade"]

    # Навались должно быть доступно (уровень 50, есть полномочия)
    guild_group2 = next(g for g in brigade2 if g["category"] == "guild")
    poison_buff = next(b for b in guild_group2["items"] if b["id"] == "guild_buff_poison")
    assert poison_buff["isLocked"] is False
    assert poison_buff["canActivate"] is True

    # Злоба (Сходняк 1) должна быть доступна
    shod_group1 = next(g for g in brigade2 if g["category"] == "shodnyak_1")
    zloba_buff = next(b for b in shod_group1["items"] if b["id"] == "shodnyak_zloba")
    assert zloba_buff["isLocked"] is False
    assert zloba_buff["canActivate"] is True


@pytest.mark.asyncio
async def test_all_48_cameras_valid_urls(web_setup):
    """
    Проверка всех 48 хат:
    - 48 камер возвращаются в /api/v1/wardrobe/overview;
    - Все imageUrl непустые и валидные;
    - Ни одна хата не содержит сырой Spine spritesheet skeleton.webp;
    - Все 10 проблемных хат резолвятся в валидные WebP-изображения (не 1x1 заглушки).
    """
    from unittest.mock import MagicMock, AsyncMock
    from client.api.player import PlayerAPI
    from bot.handlers import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_http = MagicMock()
    mock_http.get.side_effect = Exception("offline")
    player_api = PlayerAPI(http_client=mock_http)
    player_api.init_player = AsyncMock(return_value={"roomCameraUrl": ""})
    player_api.get_wardrobe_inventory = AsyncMock(return_value={"ownedCameras": [1]})
    player_api.get_tattoos_catalog = AsyncMock(return_value=[])
    player_api.get_clothing_catalog = AsyncMock(return_value=[])
    bot_context.player_api = player_api

    res = await client.get("/api/v1/wardrobe/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    cameras = data["cameras"]
    assert len(cameras) == 48

    problem_folders = {"27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "54"}
    for cam in cameras:
        img_url = cam.get("imageUrl")
        assert img_url, f"Камера {cam.get('id')} имеет пустой imageUrl"
        assert "skeleton.webp" not in img_url, f"Камера {cam.get('id')} ссылается на сырой Spine-атлас: {img_url}"
        for folder in problem_folders:
            if f"room_{folder}.webp" in img_url:
                # Проверяем, что локальный статический файл реально отдается сервером и не является заглушкой
                r_img = await client.get(img_url)
                assert r_img.status_code == 200
                assert len(r_img.content) > 1000, f"Хата {folder} слишком мала ({len(r_img.content)} байт)"


@pytest.mark.asyncio
async def test_batch_assets_endpoint_and_lru_cache(web_setup):
    """
    Тест пакетного загрузчика POST /api/v1/assets/batch и RAM LRU-кэша /api/v1/assets/proxy.
    """
    from web.routes import _lru_get, _lru_set, _ASSET_LRU_CACHE

    client, _ = web_setup

    # 1. Проверка LRU кэша напрямую
    test_key = "test/asset/sample.png"
    sample_bytes = b"\x89PNG\r\n\x1a\nTESTDATA"
    _lru_set(test_key, sample_bytes, "image/png")
    hit = _lru_get(test_key)
    assert hit is not None
    assert hit[0] == sample_bytes
    assert hit[1] == "image/png"

    # 2. Проверка пакетного эндпоинта POST /api/v1/assets/batch
    batch_payload = {
        "paths": [
            "assets/PrisonV3/RoomCameraUrl/30/1.png",
            "assets/PrisonV3/RoomCameraUrl/34/1.png",
            "assets/PrisonV3/RoomCameraUrl/54/1.png",
        ]
    }
    res = await client.post("/api/v1/assets/batch", json=batch_payload)
    assert res.status_code == 200
    b_data = res.json()
    assert b_data["success"] is True
    assert "items" in b_data
    items = b_data["items"]
    # Все 3 пути должны быть успешно отрезолвлены в Base64 Data URL (из локальных статических WebP хат)
    for p in batch_payload["paths"]:
        assert p in items
        assert items[p].startswith("data:image/")
        assert len(items[p]) > 100




@pytest.mark.asyncio
async def test_raids_and_news_endpoints(web_setup):
    from unittest.mock import MagicMock, AsyncMock
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. GET /api/v1/raids
    res_raids = await client.get("/api/v1/raids", headers=headers)
    assert res_raids.status_code == 200
    r_data = res_raids.json()
    assert "sourceStatus" in r_data
    assert "isPaywalled" in r_data

    # 2. GET /api/v1/news
    res_news = await client.get("/api/v1/news", headers=headers)
    assert res_news.status_code == 200
    n_data = res_news.json()
    assert "posts" in n_data or "news" in n_data

    # 3. GET /api/v1/raids/active-players
    bot_context.social_api = MagicMock()
    bot_context.social_api.get_weekly_top = AsyncMock(return_value={
        "top": [
            {"userId": 9000000000141538, "nickname": "Барс", "damage": 500_000_000, "authority": 10000, "rank": 1}
        ]
    })
    bot_context.social_api.get_friends_list = AsyncMock(return_value=[])

    res_players = await client.get("/api/v1/raids/active-players?minDamage=1000000&limit=10", headers=headers)
    assert res_players.status_code == 200
    p_data = res_players.json()
    assert p_data["success"] is True
    assert p_data["total"] >= 1
    assert p_data["players"][0]["userId"] == 9000000000141538

    # 4. POST /api/v1/raids/parse-text
    res_parse = await client.post("/api/v1/raids/parse-text", json={"text": "Рейд бригады\n1. 9000000000141538 Барс 600кк"}, headers=headers)
    assert res_parse.status_code == 200
    parse_data = res_parse.json()
    assert parse_data["success"] is True
    assert len(parse_data["result"]["participants"]) == 1

    # 5. POST /api/v1/actions/friendship/send
    bot_context.social_api.send_friend_request = AsyncMock(return_value={"success": True})
    res_send = await client.post("/api/v1/actions/friendship/send", json={"toUserId": 9000000000141538, "nickname": "Барс"}, headers=headers)
    assert res_send.status_code == 200
    send_data = res_send.json()
    assert send_data["success"] is True
    assert send_data["userId"] == 9000000000141538

    # 6. POST /api/v1/actions/friendship/send-batch
    res_batch = await client.post(
        "/api/v1/actions/friendship/send-batch",
        json={"userIds": [9000000000141539, 9000000000141540], "maxCount": 2, "minDelay": 0.01, "maxDelay": 0.02},
        headers=headers,
    )
    assert res_batch.status_code == 200
    batch_data = res_batch.json()
    assert batch_data["success"] is True
    assert batch_data["sentCount"] == 2


@pytest.mark.asyncio
async def test_raids_scan_guilds_endpoint_and_cooldown(web_setup):
    """Тест POST /api/v1/raids/scan-guilds и серверного кулдауна."""
    from unittest.mock import MagicMock, AsyncMock
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    bot_context.social_api = MagicMock()
    bot_context.social_api.get_recruitment_list = AsyncMock(return_value={
        "items": [{"guildId": 1, "name": "Бригада 1"}, {"guildId": 2, "name": "Бригада 2"}]
    })
    bot_context.social_api.get_guild_members = AsyncMock(return_value={
        "members": [{"userId": 9000000000100001, "nickname": "Кабан", "authority": 50000}]
    })

    # 1. Первый запуск с force=True
    res = await client.post("/api/v1/raids/scan-guilds", json={"force": True}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["scannedGuilds"] == 2

    # 2. Повторный запуск без force -> кулдаун
    res_cd = await client.post("/api/v1/raids/scan-guilds", json={"force": False}, headers=headers)
    assert res_cd.status_code == 200
    data_cd = res_cd.json()
    assert data_cd["status"] == "cooldown"
    assert data_cd["cooldownSeconds"] > 0


@pytest.mark.asyncio
async def test_raids_safety_status_endpoint(web_setup):
    """Тест GET /api/v1/raids/safety-status."""
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    res = await client.get("/api/v1/raids/safety-status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    safety = data["safety"]
    assert "sentLast24h" in safety
    assert "dailyLimit" in safety
    assert "remaining24h" in safety
    assert "circuitOpen" in safety


@pytest.mark.asyncio
async def test_patch_config_outreach_validation(web_setup):
    """Тест валидации суточного лимита заявок (1..500, дефолт 50) и списка каналов (<= 10) в PATCH /config."""
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Успешная установка лимита 50 и 100 (без потолка 50)
    res_ok = await client.patch("/api/v1/config", json={"friend_outreach_daily_limit": 50}, headers=headers)
    assert res_ok.status_code == 200
    assert res_ok.json()["config"]["friend_outreach_daily_limit"] == 50

    res_ok_100 = await client.patch("/api/v1/config", json={"friend_outreach_daily_limit": 100}, headers=headers)
    assert res_ok_100.status_code == 200
    assert res_ok_100.json()["config"]["friend_outreach_daily_limit"] == 100

    # Немедленное отражение в GET /api/v1/raids/safety-status
    res_safety = await client.get("/api/v1/raids/safety-status", headers=headers)
    assert res_safety.status_code == 200
    assert res_safety.json()["safety"]["dailyLimit"] == 100

    # 2. Выход за 500 -> 400
    res_err1 = await client.patch("/api/v1/config", json={"friend_outreach_daily_limit": 501}, headers=headers)
    assert res_err1.status_code == 400

    # 3. Меньше 1 -> 400
    res_err2 = await client.patch("/api/v1/config", json={"friend_outreach_daily_limit": 0}, headers=headers)
    assert res_err2.status_code == 400

    # 4. Список каналов > 10 -> 400
    too_many_channels = [f"ch_{i}" for i in range(12)]
    res_ch_err = await client.patch("/api/v1/config", json={"raid_tg_channels": too_many_channels}, headers=headers)
    assert res_ch_err.status_code == 400

    # 5. Корректный список каналов -> 200
    valid_channels = ["pro_prison", "pro_prison_chat"]
    res_ch_ok = await client.patch("/api/v1/config", json={"raid_tg_channels": valid_channels}, headers=headers)
    assert res_ch_ok.status_code == 200
    assert res_ch_ok.json()["config"]["raid_tg_channels"] == valid_channels


@pytest.mark.asyncio
async def test_friendship_send_and_batch_daily_limit_enforcement(web_setup):
    """Тест блокировки одиночной и пакетной отправки при исчерпании суточного лимита."""
    from unittest.mock import MagicMock, AsyncMock
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    from core.models import SentFriendRequest
    from datetime import datetime, timedelta

    bot_context.social_api = MagicMock()
    bot_context.social_api.send_friend_request = AsyncMock(return_value={"success": True})
    bot_context.social_api.get_friends_list = AsyncMock(return_value=[])

    # Устанавливаем суточный лимит 2
    await client.patch("/api/v1/config", json={"friend_outreach_daily_limit": 2}, headers=headers)

    # Заполняем таблицу 2 отправленными заявками за последние 24ч
    async with get_session(bot_context.db_engine) as session:
        for i in range(2):
            session.add(SentFriendRequest(
                account_id=1,
                target_user_id=8888000 + i,
                status="sent",
                created_at=datetime.utcnow() - timedelta(minutes=5),
            ))
        await session.commit()

    # 1. Одиночная отправка должна отклониться
    res_single = await client.post("/api/v1/actions/friendship/send", json={"toUserId": 999999}, headers=headers)
    assert res_single.status_code == 200
    data_single = res_single.json()
    assert data_single["success"] is False
    assert data_single["limitReached"] is True

    # 2. Пакетная отправка должна вернуть limitReached = True и sentCount = 0
    res_batch = await client.post(
        "/api/v1/actions/friendship/send-batch",
        json={"userIds": [999901, 999902], "maxCount": 2},
        headers=headers,
    )
    assert res_batch.status_code == 200
    data_batch = res_batch.json()
    assert data_batch["limitReached"] is True
    assert data_batch["sentCount"] == 0


@pytest.mark.asyncio
async def test_friends_summary_deltas_and_conversion(web_setup):
    """
    Тест GET /api/v1/friends/summary:
    - Расчет totalFriends и delta24h для положительной (+15), отрицательной (-15) и нулевой (0) дельт;
    - Корректная структура conversionBySource (sent, accepted, ignored, pending, conversionRate, avgDamage).
    """
    from datetime import datetime, timedelta
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    now = datetime.utcnow()

    # 1. Сценарий: 1200 друзей сейчас, 1185 было 24 часа назад -> дельта +15
    async with get_session(engine) as session:
        # Добавляем снимок 24ч назад
        session.add(FriendsCountSnapshot(
            account_id=1,
            friends_count=1185,
            created_at=now - timedelta(hours=24, minutes=10),
        ))
        # Добавляем 1200 текущих друзей в FriendStats
        for i in range(1200):
            session.add(FriendStats(
                account_id=1,
                user_id=1000000 + i,
                is_current_friend=True,
            ))
        # Добавляем заявки из разных источников
        # tg_channel: 20 sent, 14 accepted, 4 ignored, 2 pending
        for i in range(14):
            uid = 2000000 + i
            session.add(SentFriendRequest(
                account_id=1, target_user_id=uid, source="tg_channel", status="accepted",
            ))
            session.add(TrackedCandidate(
                account_id=1, user_id=uid, total_damage=450000,
            ))
        for i in range(4):
            session.add(SentFriendRequest(
                account_id=1, target_user_id=2100000 + i, source="tg_channel", status="ignored",
            ))
        for i in range(2):
            session.add(SentFriendRequest(
                account_id=1, target_user_id=2200000 + i, source="tg_channel", status="sent",
            ))
        await session.commit()

    resp = await client.get("/api/v1/friends/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalFriends"] == 1200
    assert data["delta24h"] == 15
    assert data["baselineCount"] == 1185
    assert data["has24hHistory"] is True
    assert len(data["conversionBySource"]) >= 1

    tg_src = next(s for s in data["conversionBySource"] if s["source"] == "tg_channel")
    assert tg_src["sent"] == 20
    assert tg_src["accepted"] == 14
    assert tg_src["ignored"] == 4
    assert tg_src["pending"] == 2
    assert tg_src["conversionRate"] == 70.0
    assert tg_src["avgDamage"] == 450000

    # 2. Сценарий: дельта -15 (было 1215, стало 1200)
    async with get_session(engine) as session:
        # Обновляем снимок 24ч назад на 1215
        snap = (await session.execute(
            select(FriendsCountSnapshot).where(FriendsCountSnapshot.account_id == 1)
        )).scalar_one()
        snap.friends_count = 1215
        await session.commit()

    from web.routes import _flight_cache
    _flight_cache.invalidate("friends")

    resp_neg = await client.get("/api/v1/friends/summary", headers=headers)
    assert resp_neg.status_code == 200
    assert resp_neg.json()["delta24h"] == -15

    # 3. Сценарий: дельта 0 (было 1200, стало 1200)
    async with get_session(engine) as session:
        snap_zero = (await session.execute(
            select(FriendsCountSnapshot).where(FriendsCountSnapshot.account_id == 1)
        )).scalar_one()
        snap_zero.friends_count = 1200
        await session.commit()

    _flight_cache.invalidate("friends")

    resp_zero = await client.get("/api/v1/friends/summary", headers=headers)
    assert resp_zero.status_code == 200
    assert resp_zero.json()["delta24h"] == 0


@pytest.mark.asyncio
async def test_friends_stats_whitelist_cleanup_preview(web_setup):
    """
    Тест эндпоинтов:
    - GET /api/v1/friends/stats (сортировка damage_7d, total_damage, inactive);
    - POST /api/v1/friends/whitelist;
    - GET /api/v1/friends/cleanup/preview;
    - POST /api/v1/friends/cleanup/run.
    """
    from datetime import datetime, timedelta
    from unittest.mock import AsyncMock, MagicMock
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    now = datetime.utcnow()

    async with get_session(engine) as session:
        # Друг 1: топовый дамагер
        session.add(FriendStats(
            account_id=1, user_id=3001, nickname="TopDamager",
            level=30, authority=50000, is_current_friend=True, is_whitelisted=False,
            total_damage_to_my_bosses=200000, last_active_at=now,
        ))
        session.add(BossFriendDamageLog(
            account_id=1, boss_session_id="s1", user_id=3001, recorded_damage=80000, updated_at=now - timedelta(days=2),
        ))

        # Друг 2: неактивный, кандидат на удаление
        session.add(FriendStats(
            account_id=1, user_id=3002, nickname="InactiveOne",
            level=10, authority=2000, is_current_friend=True, is_whitelisted=False,
            total_damage_to_my_bosses=0, last_active_at=now - timedelta(days=20),
            first_seen_at=now - timedelta(days=25),
        ))
        await session.commit()

    # 1. GET /api/v1/friends/stats
    res_stats = await client.get("/api/v1/friends/stats?sort=damage_7d", headers=headers)
    assert res_stats.status_code == 200
    s_data = res_stats.json()
    assert s_data["success"] is True
    assert s_data["total"] >= 2
    top_f = s_data["friends"][0]
    assert top_f["userId"] == 3001
    assert top_f["damage7d"] == 80000
    assert top_f["totalDamageToMyBosses"] == 200000

    # 2. POST /api/v1/friends/whitelist
    res_wl = await client.post("/api/v1/friends/whitelist", json={"userId": 3002, "whitelisted": True}, headers=headers)
    assert res_wl.status_code == 200
    assert res_wl.json()["isWhitelisted"] is True

    async with get_session(engine) as session:
        f3002 = (await session.execute(select(FriendStats).where(FriendStats.user_id == 3002))).scalar_one()
        assert f3002.is_whitelisted is True

    # 3. GET /api/v1/friends/cleanup/preview (с защищенным f3002 кандидатов 0)
    res_prev = await client.get("/api/v1/friends/cleanup/preview", headers=headers)
    assert res_prev.status_code == 200
    assert res_prev.json()["totalEligible"] == 0

    # Снимаем whitelist с 3002
    await client.post("/api/v1/friends/whitelist", json={"userId": 3002, "whitelisted": False}, headers=headers)

    res_prev2 = await client.get("/api/v1/friends/cleanup/preview", headers=headers)
    assert res_prev2.status_code == 200
    assert res_prev2.json()["totalEligible"] == 1
    assert res_prev2.json()["candidates"][0]["userId"] == 3002

    # 4. POST /api/v1/friends/cleanup/run
    bot_context.social_api = MagicMock()
    bot_context.social_api.remove_friend = AsyncMock(return_value={"success": True})

    res_run = await client.post("/api/v1/friends/cleanup/run", json={"userIds": [3002]}, headers=headers)
    assert res_run.status_code == 200
    assert res_run.json()["removedCount"] == 1
    bot_context.social_api.remove_friend.assert_awaited_once_with(3002)


@pytest.mark.asyncio
async def test_patch_config_new_social_fields(web_setup):
    """
    Тест валидации и сохранения новых полей BotConfig через PATCH /api/v1/config:
    - friend_filter_mode ('and' / 'or');
    - auto_parse_news_raids (bool);
    - auto_friend_cleanup (bool);
    - friend_cleanup_inactive_days (1-365);
    - friend_cleanup_daily_limit (1-50);
    - friend_cleanup_trigger_threshold (>= 0).
    """
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Успешное сохранение валидных параметров
    payload_valid = {
        "friend_filter_mode": "or",
        "auto_parse_news_raids": True,
        "auto_friend_cleanup": True,
        "friend_cleanup_inactive_days": 10,
        "friend_cleanup_daily_limit": 7,
        "friend_cleanup_trigger_threshold": 50000,
    }
    res_ok = await client.patch("/api/v1/config", json=payload_valid, headers=headers)
    assert res_ok.status_code == 200
    cfg_data = res_ok.json()["config"]
    assert cfg_data["friend_filter_mode"] == "or"
    assert cfg_data["auto_parse_news_raids"] is True
    assert cfg_data["auto_friend_cleanup"] is True
    assert cfg_data["friend_cleanup_inactive_days"] == 10
    assert cfg_data["friend_cleanup_daily_limit"] == 7
    assert cfg_data["friend_cleanup_trigger_threshold"] == 50000

    # 2. Ошибка: невалидный friend_filter_mode
    res_bad_mode = await client.patch("/api/v1/config", json={"friend_filter_mode": "invalid"}, headers=headers)
    assert res_bad_mode.status_code == 400

    # 3. Ошибка: лимит чистки вне диапазона
    res_bad_lim = await client.patch("/api/v1/config", json={"friend_cleanup_daily_limit": 100}, headers=headers)
    assert res_bad_lim.status_code == 400


@pytest.mark.asyncio
async def test_raids_scan_news_and_sync_top_endpoints(web_setup):
    """
    Тест ручных триггеров:
    - POST /api/v1/raids/scan-news;
    - POST /api/v1/raids/sync-top.
    """
    from unittest.mock import AsyncMock, MagicMock
    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    bot_context.social_api = MagicMock()
    bot_context.social_api.http = MagicMock()
    bot_context.social_api.http.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"posts": []}))
    bot_context.social_api.get_weekly_top = AsyncMock(return_value={"top": []})
    bot_context.social_api.get_top_achievements = AsyncMock(return_value={"achievements": []})

    # 1. scan-news
    res_news = await client.post("/api/v1/raids/scan-news", headers=headers)
    assert res_news.status_code == 200
    assert res_news.json()["success"] is True

    # 2. sync-top
    res_top = await client.post("/api/v1/raids/sync-top", json={"force": True}, headers=headers)
    assert res_top.status_code == 200
    assert res_top.json()["success"] is True


@pytest.mark.asyncio
async def test_boss_58_availability_locks_and_reasons(web_setup):
    """
    Тест точной оценки доступности всех 58 боссов:
    - Кирпич: доступен (isLocked = False, canAttack = True)
    - Лютый (id=4): закрыт по 2 дневным ходкам в Кресты (0 из 2)
    - Шайба (id=5): закрыт по 3 дневным ходкам в В.Централ (0 из 3)
    - Бурят (id=6): закрыт по 3 дневным ходкам в Угольки (0 из 3)
    - Дядя Миша (id=7): закрыт по 6 ночным бунтам в Матросская Тишина (0 из 6)
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from web.routes import bot_context

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # Мокируем boss_api для эндпоинта /api/v1/live/boss
    bot_context.boss_api = MagicMock()
    bot_context.boss_api.get_bootstrap = AsyncMock(return_value={"success": True, "state": "inactive", "session": None})
    bot_context.boss_api.get_weapons = AsyncMock(return_value={"equippedSlots": ["punchChest", "kickBalls", "pokeEyes"]})
    bot_context.boss_api.get_all_bosses = AsyncMock(return_value=None)

    bot_context.prison_api = MagicMock()
    # Нулевой прогресс по тюрьмам (0 ходок и 0 бунтов)
    bot_context.prison_api.get_all_prisons = AsyncMock(return_value={
        "prisons": [
            {"id": 4, "name": "Кресты", "runs": 0, "nightRuns": 0},
            {"id": 5, "name": "В.Централ", "runs": 0, "nightRuns": 0},
            {"id": 6, "name": "Угольки", "runs": 0, "nightRuns": 0},
            {"id": 7, "name": "Матросская Тишина", "runs": 0, "nightRuns": 0},
        ]
    })

    res = await client.get("/api/v1/live/boss", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    bosses = {b["id"]: b for b in data["bosses"]}

    # Кирпич (1)
    brick = bosses[1]
    assert brick["isLocked"] is False
    assert brick["canAttack"] is True

    # Лютый (4)
    lyutiy = bosses[4]
    assert lyutiy["isLocked"] is True
    assert lyutiy["canAttack"] is False
    assert "2 дневные ходки в Кресты" in lyutiy["unlockReason"]
    assert lyutiy["progressText"] == "0 из 2"

    # Шайба (5)
    shayba = bosses[5]
    assert shayba["isLocked"] is True
    assert shayba["canAttack"] is False
    assert "3 дневные ходки в В.Централ" in shayba["unlockReason"]
    assert shayba["progressText"] == "0 из 3"

    # Бурят (6)
    buryat = bosses[6]
    assert buryat["isLocked"] is True
    assert buryat["canAttack"] is False
    assert "3 дневные ходки в Угольки" in buryat["unlockReason"]
    assert buryat["progressText"] == "0 из 3"

    # Дядя Миша (7)
    misha = bosses[7]
    assert misha["isLocked"] is True
    assert misha["canAttack"] is False
    assert "6 ночных бунтов в Матросская Тишина" in misha["unlockReason"]
    assert misha["progressText"] == "0 из 6"


@pytest.mark.asyncio
async def test_boss_presets_crud_and_run_api(web_setup):
    """
    Тест REST API маршрутов для управления пресетами боссов:
    - POST /api/v1/boss/presets (создание, валидация)
    - GET /api/v1/boss/presets (чтение)
    - PATCH /api/v1/boss/presets/{id} (редактирование)
    - POST /api/v1/boss/presets/{id}/run (запуск)
    - POST /api/v1/boss/presets/{id}/stop (остановка)
    - DELETE /api/v1/boss/presets/{id} (удаление)
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from web.routes import bot_context

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Валидация: неверный формат времени -> 400
    res_bad_time = await client.post("/api/v1/boss/presets", json={
        "name": "Неверное время",
        "schedule_time_msk": "25:61",
        "items": [{"boss_id": 1, "mode": "pacansky", "count": 1}]
    }, headers=headers)
    assert res_bad_time.status_code == 400

    # 2. Валидация: пустое имя -> 400
    res_bad_name = await client.post("/api/v1/boss/presets", json={
        "name": "   ",
        "schedule_time_msk": "09:00",
        "items": [{"boss_id": 1, "mode": "pacansky", "count": 1}]
    }, headers=headers)
    assert res_bad_name.status_code == 400

    # 3. Валидация: пустые items -> 400
    res_bad_items = await client.post("/api/v1/boss/presets", json={
        "name": "Пустые шаги",
        "schedule_time_msk": "09:00",
        "items": []
    }, headers=headers)
    assert res_bad_items.status_code == 400

    # 4. Успешное создание пресета
    payload = {
        "name": "Утренний проход",
        "schedule_time_msk": "08:30",
        "daily_enabled": True,
        "items": [
            {"boss_id": 1, "mode": "pacansky", "count": 2},
            {"boss_id": 2, "mode": "blotnoy", "count": 1},
        ]
    }
    res_create = await client.post("/api/v1/boss/presets", json=payload, headers=headers)
    assert res_create.status_code == 200
    data_create = res_create.json()
    assert data_create["success"] is True
    preset_id = data_create["preset"]["id"]
    assert preset_id > 0
    assert data_create["preset"]["name"] == "Утренний проход"
    assert data_create["preset"]["schedule_time_msk"] == "08:30"

    # 5. GET /api/v1/boss/presets
    res_list = await client.get("/api/v1/boss/presets", headers=headers)
    assert res_list.status_code == 200
    presets = res_list.json()["presets"]
    assert any(p["id"] == preset_id for p in presets)

    # 6. PATCH /api/v1/boss/presets/{id}
    res_patch = await client.patch(f"/api/v1/boss/presets/{preset_id}", json={
        "name": "Утренний проход VIP",
        "schedule_time_msk": "07:45"
    }, headers=headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["preset"]["name"] == "Утренний проход VIP"
    assert res_patch.json()["preset"]["schedule_time_msk"] == "07:45"

    # 7. POST /api/v1/boss/presets/{id}/run
    bot_context.boss_worker = MagicMock()
    bot_context.boss_worker.run_cycle = AsyncMock(return_value={"success": True})

    res_run = await client.post(f"/api/v1/boss/presets/{preset_id}/run", headers=headers)
    assert res_run.status_code == 200
    assert res_run.json()["preset"]["is_running"] is True
    await asyncio.sleep(0.05)
    assert bot_context.boss_worker.run_cycle.call_count == 1

    # 8. POST /api/v1/boss/presets/{id}/stop
    res_stop = await client.post(f"/api/v1/boss/presets/{preset_id}/stop", headers=headers)
    assert res_stop.status_code == 200
    assert res_stop.json()["preset"]["is_running"] is False

    # 9. DELETE /api/v1/boss/presets/{id}
    res_del = await client.delete(f"/api/v1/boss/presets/{preset_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Проверка, что пресет удален
    res_list2 = await client.get("/api/v1/boss/presets", headers=headers)
    assert not any(p["id"] == preset_id for p in res_list2.json()["presets"])


@pytest.mark.asyncio
async def test_friends_summary_initial_snapshot_auto_created(web_setup):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from client.api.social import SocialAPI
    from core.models import FriendsCountSnapshot
    from sqlalchemy import select, delete

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # Очищаем снимки
    async with get_session(engine) as session:
        await session.execute(delete(FriendsCountSnapshot))
        await session.commit()

    # Сбрасываем SingleFlightCache для summary
    from web.routes import _flight_cache
    _flight_cache.invalidate("friends")

    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_all_friend_ids = AsyncMock(return_value={9000000000100001, 9000000000100002, 9000000000100003})
    bot_context.social_api = mock_social

    res = await client.get("/api/v1/friends/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["totalFriends"] == 3
    assert data["friendsCount"] == 3
    assert data["delta24h"] == 0

    # Проверяем, что снимок записался в БД
    async with get_session(engine) as session:
        snaps = (await session.execute(select(FriendsCountSnapshot))).scalars().all()
        assert len(snaps) == 1
        assert snaps[0].friends_count == 3


@pytest.mark.asyncio
async def test_web_app_gzip_cache_control_and_versioning(web_setup):
    client, _ = web_setup

    # 1. GET / with gzip
    res_root = await client.get("/", headers={"Accept-Encoding": "gzip"})
    assert res_root.status_code == 200
    assert "no-cache" in res_root.headers.get("Cache-Control", "")
    assert "styles.css?v=" in res_root.text
    assert "app.js?v=" in res_root.text

    # 2. GET /static/app.js has no-cache
    res_js = await client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "no-cache" in res_js.headers.get("Cache-Control", "")

    # 3. GET /static/assets/icons/back_poworot.webp has public max-age
    res_icon = await client.get("/static/assets/icons/back_poworot.webp")
    assert res_icon.status_code == 200
    assert "public" in res_icon.headers.get("Cache-Control", "")
    assert "max-age=86400" in res_icon.headers.get("Cache-Control", "")


@pytest.mark.asyncio
async def test_single_flight_cache_deduplication_and_invalidation():
    import asyncio
    from web.routes import _SingleFlightCache
    cache = _SingleFlightCache()

    call_count = 0

    async def expensive_work():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.02)
        return {"value": 42}

    # Одновременный запуск двух одинаковых запросов
    res1, res2 = await asyncio.gather(
        cache.get_or_set("key_1", 5.0, expensive_work),
        cache.get_or_set("key_1", 5.0, expensive_work),
    )
    assert res1 == {"value": 42}
    assert res2 == {"value": 42}
    assert call_count == 1  # Вызвано ровно 1 раз благодаря SingleFlightLock

    # После инвалидации
    cache.invalidate("key_1")
    res3 = await cache.get_or_set("key_1", 5.0, expensive_work)
    assert res3 == {"value": 42}
    assert call_count == 2


def test_back_poworot_icon_integrity():
    from pathlib import Path
    from PIL import Image

    icon_path = Path("web/static/assets/icons/back_poworot.webp")
    assert icon_path.exists()
    assert icon_path.stat().st_size > 1000

    img = Image.open(icon_path)
    assert img.format == "WEBP"
    assert img.size[0] > 0 and img.size[1] > 0


@pytest.mark.asyncio
async def test_live_profile_toilet_paper_timer_and_js_syntax(web_setup):
    """Проверка поля toiletPaper в /api/v1/live/profile и синтаксиса JS (node --check)."""
    import subprocess
    from unittest.mock import AsyncMock, MagicMock

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    mock_player = MagicMock()
    mock_player.init_player = AsyncMock(return_value={
        "success": True,
        "id": 123,
        "nickname": "Тест",
        "canClaimToiletPaper": False,
        "currencies": {"paper": 10},
    })
    mock_player.get_businesses = AsyncMock(return_value={"businesses": [], "playerBusinesses": []})
    bot_context.player_api = mock_player

    from web.routes import _flight_cache
    _flight_cache.invalidate("profile:")

    res = await client.get("/api/v1/live/profile", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "toiletPaper" in data
    tp = data["toiletPaper"]
    assert tp["canClaim"] is False
    assert tp["resetMode"] == "midnight_msk"
    assert tp["secondsUntilReset"] > 0
    assert "nextResetAt" in tp

    # Проверка синтаксиса фронтенд JS и vendor-рантаймов
    for js_file in [
        "web/static/app.js",
        "web/static/spine_room_player.js",
        "web/static/vendor/spine-runtime.js",
        "web/static/vendor/bundle-codec.js",
    ]:
        proc = subprocess.run(["node", "--check", js_file], capture_output=True, text=True)
        assert proc.returncode == 0, f"JS syntax error in {js_file}: {proc.stderr}"


@pytest.mark.asyncio
async def test_config_auto_podogrev_send_and_routine_toggles_persistence(web_setup):
    """Проверка сохранения auto_podogrev_send, auto_katala, auto_monthly_tasks через GET/PATCH и HTML label-оберток."""
    from pathlib import Path
    import re

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. PATCH /api/v1/config сохраняет auto_podogrev_send, auto_katala, auto_monthly_tasks
    patch_res = await client.patch(
        "/api/v1/config",
        json={
            "auto_podogrev_send": True,
            "auto_katala": True,
            "auto_monthly_tasks": True,
        },
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["success"] is True

    get_res = await client.get("/api/v1/config", headers=headers)
    assert get_res.status_code == 200
    cfg = get_res.json()["config"]
    assert cfg["auto_podogrev_send"] is True
    assert cfg["auto_katala"] is True
    assert cfg["auto_monthly_tasks"] is True

    # GET /api/v1/state также обязан возвращать актуальные флаги после обновления/F5
    state_res = await client.get("/api/v1/state", headers=headers)
    assert state_res.status_code == 200
    st_cfg = state_res.json()["config"]
    assert st_cfg["auto_podogrev_send"] is True
    assert st_cfg["auto_katala"] is True
    assert st_cfg["auto_monthly_tasks"] is True

    # Выключение тоже корректно сохраняется
    patch_off = await client.patch(
        "/api/v1/config",
        json={"auto_podogrev_send": False},
        headers=headers,
    )
    assert patch_off.status_code == 200
    cfg_off = (await client.get("/api/v1/config", headers=headers)).json()["config"]
    assert cfg_off["auto_podogrev_send"] is False
    st_off = (await client.get("/api/v1/state", headers=headers)).json()["config"]
    assert st_off["auto_podogrev_send"] is False

    # 2. Все .toggle-switch в index.html кликабельны (не обернуты в некликабельный <div> без <label>)
    html_text = Path("web/static/index.html").read_text(encoding="utf-8")
    assert not re.search(r'<div\s+class=["\'][^"\']*toggle-switch', html_text), (
        "Обнаружен некликабельный <div class='toggle-switch'> в index.html"
    )
    assert 'id="cfg-auto_podogrev_send"' in html_text
    assert 'vendor/spine-runtime.js' in html_text
    assert 'vendor/bundle-codec.js' in html_text


@pytest.mark.asyncio
async def test_room_render_authentic_assets_and_no_fake_crop(web_setup):
    """Проверка отсутствия фейкового room_54_foreground.webp и отдачи аутентичных дескрипторов Spine/bundle/effects."""
    from pathlib import Path

    assert not Path("web/static/assets/rooms/room_54_foreground.webp").exists()

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    r54 = (await client.get("/api/v1/wardrobe/room-render/54", headers=headers)).json()
    assert r54["renderMode"] == "bundle"
    assert r54["hasForeground"] is True
    assert r54["foregroundSource"] == "room.bundle:gameBirthday_back_front"
    assert "room.bundle" in r54["bundleUrl"]

    r30 = (await client.get("/api/v1/wardrobe/room-render/30", headers=headers)).json()
    assert r30["renderMode"] == "spine"
    assert r30["spine"]["altRootOffset"] is True

    r42 = (await client.get("/api/v1/wardrobe/room-render/42", headers=headers)).json()
    assert r42["renderMode"] == "bundle"
    assert r42["effectConfigUrl"] is not None


@pytest.mark.asyncio
async def test_forwarded_prefix_proxy_rewriting(web_setup):
    """Проверка работы за HTTPS reverse-proxy под префиксом /prison (X-Forwarded-Prefix)."""
    client, _ = web_setup
    proxy_headers = {"X-Admin-Token": "test_admin_token", "X-Forwarded-Prefix": "/prison"}

    res_html = await client.get("/", headers=proxy_headers)
    assert res_html.status_code == 200
    assert '"/prison/static/assets/' in res_html.text

    res_js = await client.get("/app.js", headers=proxy_headers)
    assert res_js.status_code == 200
    assert 'const API_BASE = "/prison/api/v1"' in res_js.text

    res_room = await client.get("/api/v1/wardrobe/room-render/54", headers=proxy_headers)
    assert res_room.status_code == 200
    d54 = res_room.json()
    assert d54["bundleUrl"].startswith("/prison/api/v1/assets/proxy")
    assert d54["previewUrl"].startswith("/prison/static/assets/rooms/")

    # Без X-Forwarded-Prefix все пути остаются от корня /
    res_plain = (await client.get("/api/v1/wardrobe/room-render/54", headers={"X-Admin-Token": "test_admin_token"})).json()
    assert res_plain["bundleUrl"].startswith("/api/v1/assets/proxy")


@pytest.mark.asyncio
async def test_prisons_drain_endpoint(web_setup):
    """POST /api/v1/prisons/drain сливает всю доступную энергию и возвращает runsCompleted / remainingEnergy."""
    from unittest.mock import AsyncMock
    from client.api.prison import PrisonAPI
    from client.api.player import PlayerAPI

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    energy_state = 25

    def mock_handler(request: httpx.Request):
        nonlocal energy_state
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "energy": energy_state, "maxEnergy": 50})
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={"success": True, "prisons": [{"id": 1, "name": "Бутырка", "isUnlocked": True}]})
        elif request.url.path == "/api/player/prison/1":
            return httpx.Response(200, json={"success": True, "data": {"prisonId": 1, "dayCurrentCheckpoint": 0}})
        elif request.url.path == "/api/player/prison/1/checkpoints":
            return httpx.Response(200, json={"success": True, "data": [{"energyCost": 6, "clicksRequired": 2}]})
        elif request.url.path == "/api/player/prison/1/work":
            energy_state -= 6
            return httpx.Response(200, json={"success": True, "energy": energy_state, "rewardCigarettes": 5})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url=settings.API_BASE_URL)
    mock_auth = AsyncMock()
    mock_auth.get_valid_token.return_value = "tok"
    from client.http_client import GameHttpClient
    game_http = GameHttpClient(auth_provider=mock_auth, custom_client=mock_client)

    bot_context.player_api = PlayerAPI(http_client=game_http)
    bot_context.prison_api = PrisonAPI(http_client=game_http)

    res = await client.post("/api/v1/prisons/drain", json={"prisonId": 1, "isDay": True}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["runsCompleted"] == 4
    assert data["remainingEnergy"] == 1
    assert data["stageCost"] == 6


@pytest.mark.asyncio
async def test_live_delta_and_sse_stream_with_query_token(web_setup):
    """GET /api/v1/live/delta и SSE GET /api/v1/live/stream?token=...&once=true отдают валидный snapshot."""
    client, _ = web_setup
    from web.routes import _get_hub
    hub = _get_hub()
    hub.clear()
    hub.update_slice(1, "profile", {"profile": {"nickname": "StreamHero", "energy": 33}})

    # Delta check
    res_delta = await client.get('/api/v1/live/delta?versions={"profile":0}', headers={"X-Admin-Token": "test_admin_token"})
    assert res_delta.status_code == 200
    d = res_delta.json()
    assert d["versions"]["profile"] >= 1
    assert "profile" in d["changed"]

    # SSE stream check (query-string token auth)
    res_sse = await client.get("/api/v1/live/stream?token=test_admin_token&once=true")
    assert res_sse.status_code == 200
    assert "text/event-stream" in res_sse.headers.get("content-type", "")
    assert "event: snapshot" in res_sse.text
    assert "StreamHero" in res_sse.text


def test_normalize_db_url_resolves_to_storage():
    """normalize_db_url приводит относительный путь SQLite к <PROJECT_ROOT>/storage/prison_bot.db."""
    from core.database import normalize_db_url, PROJECT_ROOT

    expected_path = (PROJECT_ROOT / "storage" / "prison_bot.db").as_posix()
    assert normalize_db_url("sqlite+aiosqlite:///storage/prison_bot.db") == f"sqlite+aiosqlite:///{expected_path}"
    assert normalize_db_url("sqlite+aiosqlite:///prison_bot.db") == f"sqlite+aiosqlite:///{expected_path}"
    assert normalize_db_url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"


@pytest.mark.asyncio
async def test_new_dashboard_contracts_prisons_business_config_and_assets(web_setup):
    """Проверка /live/prisons (progressInfo + dayRuns/nightRuns), /live/profile (cooldown бизнесов), config и _get_asset_client."""
    from unittest.mock import AsyncMock
    from datetime import datetime, timedelta, timezone
    from web.routes import _get_asset_client, close_asset_client, _flight_cache, _get_hub

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    _flight_cache.invalidate()
    _get_hub().clear()

    # 1. Config: boss_auto_melee + friends_parser_*
    r_cfg = await client.patch(
        "/api/v1/config",
        json={
            "boss_auto_melee": True,
            "friends_parser_tier": "mid",
            "friends_parser_min_authority": 200000,
            "friends_parser_max_authority": 15000000,
        },
        headers=headers,
    )
    assert r_cfg.status_code == 200
    cfg_d = r_cfg.json()["config"]
    assert cfg_d["boss_auto_melee"] is True
    assert cfg_d["friends_parser_tier"] == "mid"
    assert cfg_d["friends_parser_min_authority"] == 200000

    # 2. /live/prisons: data checkpoints + dayRuns/nightRuns on all unlocked prisons
    mock_prison_api = AsyncMock()
    mock_prison_api.get_all_prisons.return_value = {
        "prisons": [
            {"id": 1, "name": "Бутырка", "isUnlocked": True},
            {"id": 4, "name": "Кресты", "isUnlocked": True},
        ]
    }
    mock_prison_api.get_masters.return_value = {"masters": []}
    mock_prison_api.get_prison_state.side_effect = lambda pid: {
        "data": {
            "prisonId": pid,
            "dayCurrentCheckpoint": 4 if pid == 4 else 1,
            "dayClicksInCheckpoint": 7 if pid == 4 else 0,
            "dayRuns": 3 if pid == 1 else 2,
            "nightRuns": 1 if pid == 1 else 4,
        }
    }
    mock_prison_api.get_checkpoints.return_value = {
        "data": [{"checkpointId": i + 1, "clicksRequired": 11 if i == 4 else 7, "energyCost": 5} for i in range(7)]
    }
    bot_context.prison_api = mock_prison_api

    await client.patch("/api/v1/config", json={"prison_target_id": 4, "prison_prefer_night": False}, headers=headers)
    _flight_cache.invalidate()
    _get_hub().clear()

    r_pr = await client.get("/api/v1/live/prisons?force=1", headers=headers)
    assert r_pr.status_code == 200
    pr_json = r_pr.json()
    p_info = pr_json["progressInfo"]
    assert p_info["totalCheckpoints"] == 7
    assert p_info["completedCheckpoints"] == 4
    assert p_info["currentClicks"] == 7
    assert p_info["requiredClicks"] == 11
    assert p_info["energyCost"] == 5
    # ((4 + 7/11) / 7) * 100 = 66.2%
    assert 65.5 <= p_info["progressPercent"] <= 66.9
    kresty = next(p for p in pr_json["prisons"] if p["id"] == 4)
    assert kresty["dayRuns"] == 2
    assert kresty["nightRuns"] == 4

    # 3. /live/profile exposes nextBusinessCollectAt & businessCooldownSec from businesses_data.lastCollectTime
    recent_collect = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    mock_player_api = AsyncMock()
    mock_player_api.init_player.return_value = {"id": 1, "nickname": "Test", "energy": 50, "maxEnergy": 50, "currencies": {}}
    mock_player_api.get_businesses.return_value = {"lastCollectTime": recent_collect, "businesses": [], "playerBusinesses": []}
    bot_context.player_api = mock_player_api
    _flight_cache.invalidate()
    _get_hub().clear()

    r_prof = await client.get("/api/v1/live/profile?force=1", headers=headers)
    assert r_prof.status_code == 200
    prof_j = r_prof.json()
    assert prof_j["nextBusinessCollectAt"]
    assert 5 * 3600 < prof_j["businessCooldownSec"] <= 6 * 3600

    # 4. _get_asset_client does not crash even without h2 installed
    ac = _get_asset_client()
    assert ac is not None
    await close_asset_client()


@pytest.mark.asyncio
async def test_katala_status_endpoint_fail_closed_4_states(web_setup):
    """Проверка GET /api/v1/daily/katala-status в 4 состояниях + Cache-Control: no-store."""
    from types import SimpleNamespace
    from datetime import datetime, timedelta, timezone
    from core.database import trip_katala_rubles_guard, reset_katala_rubles_guard

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    class _Resp:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    class _HttpOk:
        def __init__(self, state_payload):
            self.payload = state_payload
        async def get(self, url):
            return _Resp(self.payload)

    # (a) Бесплатная игра доступна
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%S.1234567Z")
    bot_context.player_api = SimpleNamespace(http=_HttpOk({"level": 7, "lastFreePlayTime": old_ts, "totalPlays": 10}))
    r1 = await client.get("/api/v1/daily/katala-status", headers=headers)
    assert r1.status_code == 200
    assert r1.headers.get("cache-control") == "no-store"
    j1 = r1.json()
    assert j1["success"] is True
    assert j1["free_available"] is True
    assert j1["guard_tripped"] is False

    # (b) Идет кулдаун / уже сыграна сегодня
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.5039281Z")
    bot_context.player_api = SimpleNamespace(http=_HttpOk({"level": 7, "lastFreePlayTime": recent_ts, "totalPlays": 11}))
    r2 = await client.get("/api/v1/daily/katala-status", headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("cache-control") == "no-store"
    j2 = r2.json()
    assert j2["success"] is True
    assert j2["free_available"] is False
    assert j2["seconds_left"] > 70000
    assert j2["next_free_at_msk"] and "МСК" in j2["next_free_at_msk"]

    # (c) Сработал guard_tripped
    await trip_katala_rubles_guard(account_id=1, reason="test_guard", engine=engine)
    bot_context.player_api = SimpleNamespace(http=_HttpOk({"level": 7, "lastFreePlayTime": old_ts, "totalPlays": 10}))
    r3 = await client.get("/api/v1/daily/katala-status", headers=headers)
    j3 = r3.json()
    assert j3["free_available"] is False
    assert j3["guard_tripped"] is True
    await reset_katala_rubles_guard(account_id=1, engine=engine)

    # (d) Сбой игрового API -> fail-closed
    class _HttpErr:
        async def get(self, url):
            raise RuntimeError("upstream_timeout")

    bot_context.player_api = SimpleNamespace(http=_HttpErr())
    r4 = await client.get("/api/v1/daily/katala-status", headers=headers)
    assert r4.status_code == 200
    assert r4.headers.get("cache-control") == "no-store"
    j4 = r4.json()
    assert j4["success"] is False
    assert j4["free_available"] is False
    assert "upstream_timeout" in j4["error"]


@pytest.mark.asyncio
async def test_friendship_accept_400_and_friends_audit_summary_cleanup(web_setup):
    """Проверка /actions/friendship/accept при 400 Bad Request, /friends/stats (summary, avgDamage, % конв) и /friends/cleanup/run."""
    from types import SimpleNamespace
    from datetime import datetime, timedelta
    from core.models import FriendStats, BossFriendDamageLog
    from web.routes import _get_hub

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    _get_hub().clear()

    class _MockSocialAPI:
        async def accept_friend(self, uid):
            return {
                "success": False,
                "code": "target_friends_limit_reached",
                "message": "У этого игрока уже максимальное количество друзей (5000).",
                "remove_from_list": False,
                "status_code": 400,
            }
        async def get_all_friend_profiles(self):
            return []
        async def remove_friend(self, uid):
            if uid == 9002:
                return {"success": False, "code": "temporary_error", "message": "Ошибка сервера", "remove_from_list": False}
            return {"success": True, "code": "ok"}

    bot_context.social_api = _MockSocialAPI()

    # 1. Accept 400 -> понятный русский ответ без 500 и сырых URL
    r_acc = await client.post("/api/v1/actions/friendship/accept", json={"fromUserId": 966716319}, headers=headers)
    assert r_acc.status_code == 200
    j_acc = r_acc.json()
    assert j_acc["success"] is False
    assert j_acc["code"] == "target_friends_limit_reached"
    assert "5000" in j_acc["message"]
    assert "http" not in j_acc["message"].lower()

    # 2. Заполняем FriendStats и BossFriendDamageLog для проверки /friends/stats и /friends/cleanup/run
    now = datetime.utcnow()
    async with get_session(engine) as s:
        s.add_all([
            FriendStats(
                account_id=1, user_id=9001, nickname="Боец", level=100, authority=50000,
                total_damage_to_my_bosses=200000, boss_hits_count=2, is_current_friend=True,
                is_whitelisted=False, first_seen_at=now - timedelta(days=30), last_active_at=now,
            ),
            FriendStats(
                account_id=1, user_id=9002, nickname="Новичок", level=50, authority=10000,
                total_damage_to_my_bosses=0, boss_hits_count=0, is_current_friend=True,
                is_whitelisted=False, first_seen_at=now - timedelta(days=2), last_active_at=now,
            ),
            FriendStats(
                account_id=1, user_id=9003, nickname="Балласт", level=30, authority=5000,
                total_damage_to_my_bosses=0, boss_hits_count=0, is_current_friend=True,
                is_whitelisted=False, first_seen_at=now - timedelta(days=30), last_active_at=now - timedelta(days=20),
            ),
            FriendStats(
                account_id=1, user_id=9004, nickname="Брат", level=200, authority=90000,
                total_damage_to_my_bosses=0, boss_hits_count=0, is_current_friend=True,
                is_whitelisted=True, first_seen_at=now - timedelta(days=30), last_active_at=now - timedelta(days=20),
            ),
            BossFriendDamageLog(account_id=1, boss_session_id="b1", user_id=9001, recorded_damage=120000, created_at=now, updated_at=now),
            BossFriendDamageLog(account_id=1, boss_session_id="b2", user_id=9001, recorded_damage=80000, created_at=now, updated_at=now),
        ])
        await s.commit()

    r_st = await client.get("/api/v1/friends/stats?sort=candidates_first&limit=500", headers=headers)
    assert r_st.status_code == 200
    j_st = r_st.json()
    assert j_st["summary"]["total"] == 4
    assert j_st["summary"]["tracked_battles"] == 2
    assert j_st["summary"]["active"] == 1
    assert j_st["summary"]["newbie_protected"] == 1
    assert j_st["summary"]["candidates"] == 1
    assert j_st["summary"]["whitelisted"] == 1
    by_id = {f["userId"]: f for f in j_st["friends"]}
    assert by_id[9001]["avgDamage"] == 100000
    assert by_id[9001]["conversionPct"] == 100.0
    assert by_id[9002]["status"] == "newbie_protected"
    assert by_id[9003]["status"] == "candidate"
    assert by_id[9004]["status"] == "whitelisted"

    # 3. Удаление: 9004 (whitelisted -> skipped), 9003 (успех), 9002 (ошибка)
    r_cl = await client.post("/api/v1/friends/cleanup/run", json={"userIds": [9004, 9003, 9002]}, headers=headers)
    assert r_cl.status_code == 200
    j_cl = r_cl.json()
    assert j_cl["removedCount"] == 1
    assert 9003 in j_cl["removedIds"]
    assert 9004 in j_cl["skippedIds"]
    assert len(j_cl["errors"]) == 1


@pytest.mark.asyncio
async def test_server_health_endpoints_and_state_maintenance_field(web_setup):
    """Проверка GET /api/v1/server-health (no-store), POST /api/v1/server-health/check и поля maintenance в /state."""
    from core.server_health import server_health_monitor

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    await server_health_monitor.record_failure(status_code=503)
    r_h = await client.get("/api/v1/server-health", headers=headers)
    assert r_h.status_code == 200
    assert r_h.headers.get("cache-control") == "no-store"
    assert r_h.json()["active"] is True

    r_st = await client.get("/api/v1/state", headers=headers)
    assert r_st.status_code == 200
    assert r_st.json()["maintenance"]["active"] is True

    orig_probe = server_health_monitor.probe_fn
    orig_delay = server_health_monitor.confirm_delay_sec
    server_health_monitor.confirm_delay_sec = 0.0
    server_health_monitor.probe_fn = lambda: __import__("asyncio").sleep(0, result=(True, 200, "ok"))
    try:
        r_chk = await client.post("/api/v1/server-health/check", headers=headers)
        assert r_chk.status_code == 200
        assert r_chk.headers.get("cache-control") == "no-store"
        j_chk = r_chk.json()
        assert j_chk["recovered"] is True
        assert j_chk["active"] is False
    finally:
        server_health_monitor.probe_fn = orig_probe
        server_health_monitor.confirm_delay_sec = orig_delay








@pytest.mark.asyncio
async def test_new_game_endpoints_and_workers_status(web_setup):
    """Проверка /api/v1/poker/*, /fartovy/*, /wheel/*, /zaruby/* и /workers/status."""
    from unittest.mock import AsyncMock
    from web.routes import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    bot_context.poker_api = AsyncMock()
    bot_context.poker_api.get_state.return_value = {"level": 22, "chips": 2, "pinkMatches": 5, "handActive": False}
    bot_context.poker_api.get_hand_payouts.return_value = {"rows": []}
    bot_context.fartovy_api = AsyncMock()
    bot_context.fartovy_api.get_state.return_value = {
        "success": True,
        "data": {"state": {"slotsGrass": 12, "energyRegenCap": 15, "slotsRed": 3, "freeSpins": 1, "energyTsUtc": "2026-11-26T20:00:00Z"}},
    }
    bot_context.wheel_api = AsyncMock()
    bot_context.wheel_api.get_state.return_value = {"tickets": 0, "blueMatches": 4, "jackpotBank": 5000, "wheelLevel": 1}
    bot_context.wheel_api.spin.return_value = {"skipped": True, "reason": "no_tickets"}
    bot_context.zaruby_api = AsyncMock()
    bot_context.zaruby_api.get_state.return_value = {
        "active": {"mode": 1, "completedCount": 2, "tasks": [{"taskId": 1, "type": 9, "title": "Терпила", "currentAmount": 1, "requiredAmount": 1, "status": 1}], "participants": []},
        "progress": {"level": 2},
        "balances": {"signet": 5, "ore_signet": 3},
    }
    bot_context.zaruby_api.get_well_state.return_value = {}

    r_poker = await client.get("/api/v1/poker/state", headers=headers)
    assert r_poker.status_code == 200
    assert r_poker.json()["state"]["chips"] == 2

    # Paid soap without confirm_paid=true must be blocked (400)
    r_poker_paid = await client.post("/api/v1/poker/play", json={"mode": "soap", "confirm_paid": False}, headers=headers)
    assert r_poker_paid.status_code == 400

    r_fartovy = await client.get("/api/v1/fartovy/state", headers=headers)
    assert r_fartovy.status_code == 200
    assert r_fartovy.json()["state"]["green_matches"] == 12

    r_wheel = await client.get("/api/v1/wheel/state", headers=headers)
    assert r_wheel.status_code == 200
    assert r_wheel.json()["state"]["tickets"] == 0

    # Wheel spin with 0 tickets must be skipped cleanly (success=False, skipped=True)
    r_wheel_spin = await client.post("/api/v1/wheel/spin", json={}, headers=headers)
    assert r_wheel_spin.status_code == 200
    assert r_wheel_spin.json()["skipped"] is True

    r_zaruby = await client.get("/api/v1/zaruby/state", headers=headers)
    assert r_zaruby.status_code == 200
    assert r_zaruby.json()["state"]["completed_count"] == 1

    r_workers = await client.get("/api/v1/workers/status", headers=headers)
    assert r_workers.status_code == 200
    assert r_workers.json()["success"] is True


@pytest.mark.asyncio
async def test_state_and_workers_status_include_domain_revisions(web_setup):
    """Проверка телеметрии domain_revisions / domains в /api/v1/state и /api/v1/workers/status."""
    from core.state_hub import state_hub

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}
    state_hub.notify_mutation(1, "prison_completed", reason="test_telemetry")

    r_st = await client.get("/api/v1/state", headers=headers)
    assert r_st.status_code == 200
    d_st = r_st.json()
    assert "domain_revisions" in d_st
    assert "sync_meta" in d_st
    assert d_st["domain_revisions"].get("boss", 0) >= 1

    r_ws = await client.get("/api/v1/workers/status", headers=headers)
    assert r_ws.status_code == 200
    d_ws = r_ws.json()
    assert "state_revision" in d_ws
    assert "domains" in d_ws
    assert "prisons" in d_ws["domains"]



@pytest.mark.asyncio
async def test_patch_config_boss_targets_normalizes_reorders_and_wakes_scheduler(web_setup):
    """
    PATCH /api/v1/config нормализует boss_targets, сохраняет порядок priority,
    обновляет ревизию домена boss в StateHub и немедленно будит планировщик боссов.
    """
    from unittest.mock import MagicMock
    from core.state_hub import state_hub
    from web.routes import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    fake_ctrl = MagicMock()
    orig_ctrl = getattr(bot_context, "scheduler_controller", None)
    bot_context.scheduler_controller = fake_ctrl
    try:
        rev_before = state_hub.get_domain_state(1, "boss").revision
        payload = {
            "auto_boss_enabled": True,
            "boss_targets": [
                {"bossId": 4, "name": "Лютый", "mode": "authority", "daily_limit": 5},
                {"bossId": 1, "name": "Кирпич", "mode": "pacansky", "limit": 7},
            ],
        }
        r1 = await client.patch("/api/v1/config", json=payload, headers=headers)
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["success"] is True
        assert d1["boss_config_version"] > rev_before
        assert d1["config_updated_at"] is not None

        targets = d1["config"]["boss_targets"]
        assert [t["bossId"] for t in targets] == [4, 1]
        assert [t["priority"] for t in targets] == [0, 1]
        assert targets[0]["mode"] == "avtoritetny"
        assert targets[0]["limit"] == 5
        assert fake_ctrl.trigger_boss_now.called

        # Повторный GET /api/v1/config возвращает тот же порядок приоритета
        r_get = await client.get("/api/v1/config", headers=headers)
        assert r_get.status_code == 200
        got_targets = r_get.json()["config"]["boss_targets"]
        assert [t["bossId"] for t in got_targets] == [4, 1]
        assert [t["priority"] for t in got_targets] == [0, 1]
    finally:
        bot_context.scheduler_controller = orig_ctrl



@pytest.mark.asyncio
async def test_catalogs_gladiator_full_bonus_and_owned_count(web_setup):
    """
    Проверка полного бонуса комплекта (+90 Самопал для Гладиатора) и точного
    подсчёта прогресса ownedCount/totalCount по всем ID комплекта (3/34 при [167, 173, 181]).
    """
    from unittest.mock import AsyncMock
    from web.routes import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    orig_player = bot_context.player_api
    orig_boss = bot_context.boss_api
    orig_prison = bot_context.prison_api
    try:
        mock_player = AsyncMock()
        mock_player.get_wardrobe_inventory.return_value = {
            "ownedTattoos": [167, 173, 181],
            "ownedClothing": [],
            "ownedCameras": [],
        }
        bot_context.player_api = mock_player
        bot_context.boss_api = None
        bot_context.prison_api = None

        r = await client.get("/api/v1/catalogs", headers=headers)
        assert r.status_code == 200
        data = r.json()
        by_id = {b["id"]: b for b in data["bosses"]}

        lyutyy_items = by_id[4]["modes"]["avtoritetny"]["items"]
        gladiator = next(it for it in lyutyy_items if it["id"] == 166)
        assert gladiator["bonusText"] == "+90 Самопал"
        assert gladiator["ownedCount"] == 3
        assert gladiator["totalCount"] == 34
        assert gladiator["owned"] is False

        cyclop_items = by_id[10]["modes"]["pacansky"]["items"]
        tapki = next(it for it in cyclop_items if it["id"] == 73)
        assert tapki["totalCount"] == 1
        assert tapki["ownedCount"] == 0
    finally:
        bot_context.player_api = orig_player
        bot_context.boss_api = orig_boss
        bot_context.prison_api = orig_prison



@pytest.mark.asyncio
async def test_stew_daily_delta_and_parcels_progress_in_state(web_setup):
    """
    Проверка подсчёта суточной дельты тушенки (stew: 0 -> 2 -> 1) и отдачи
    parcels_progress (достижения X/50, гарант вещи X/20) через /api/v1/state.
    """
    from datetime import datetime
    from core.config import MSK_TZ
    from core.database import compute_daily_resource_deltas
    from core.state_hub import state_hub
    from client.api.player import PlayerAPI
    from web.routes import _hub_source_tag

    client, engine = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    now_msk = datetime(2026, 11, 27, 15, 0, tzinfo=MSK_TZ)
    base_res = {"cigarettes": 100, "sugar": 50, "rubles": 10, "paper": 5, "soap": 2, "stew": 0}
    d0 = await compute_daily_resource_deltas(base_res, now_msk=now_msk, engine=engine)
    assert d0["deltas"]["stew"] == 0

    d1 = await compute_daily_resource_deltas({**base_res, "stew": 2}, now_msk=now_msk, engine=engine)
    assert d1["deltas"]["stew"] == 2

    d2 = await compute_daily_resource_deltas({**base_res, "stew": 1}, now_msk=now_msk, engine=engine)
    assert d2["deltas"]["stew"] == 1

    parsed_p = PlayerAPI.parse_parcels_progress({
        "success": True,
        "stewBalance": 1,
        "progress": {"current": 3, "step": 50},
        "clothingProgress": {"opensSinceClothing": 6, "pityOpenings": 20},
    })
    assert parsed_p == {
        "stew_count": 1,
        "achievements_current": 3,
        "achievements_target": 50,
        "guaranteed_item_current": 6,
        "guaranteed_item_target": 20,
    }
    state_hub.update_slice(1, "parcels_progress", parsed_p, source_tag=_hub_source_tag())

    r = await client.get("/api/v1/state", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["parcels_progress"]["achievements_current"] == 3
    assert body["parcels_progress"]["guaranteed_item_current"] == 6


@pytest.mark.asyncio
async def test_monthly_state_and_claim_endpoints(web_setup):
    from unittest.mock import AsyncMock
    from web.routes import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    bot_context.social_api = AsyncMock()
    bot_context.social_api.get_monthly_state.return_value = {
        "active": True,
        "global": {
            "year": 2026,
            "month": 11,
            "daysInMonth": 30,
            "days": [
                {"dayId": 28, "action": "KillBoss", "target": 1, "title": "Убей босса: Кирпич"},
                {"dayId": 29, "action": "AddYeast", "target": 10, "title": "Подкинь дрожжей 10 раз"},
            ],
            "tierRewards": {"2": {"currencies": {"rubles": 30}}, "5": {"currencies": {"chefir": 2}}},
        },
        "user": {"activeDayId": 28, "completedCount": 7, "days": {"28": {"progress": 1, "completed": True}}, "claimableTiers": [5], "claimedTiers": [2]},
    }
    bot_context.social_api.claim_monthly_reward.return_value = {"success": True, "reward": {"currencies": {"chefir": 2}}}

    r = await client.get("/api/v1/monthly/state?force=true", headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True
    assert d["future_tasks_available"] is True
    assert len(d["schedule"]) == 30
    assert len(d["rewards"]) == 2
    assert d["server_now_ts"] > 0

    r_claim = await client.post("/api/v1/monthly/claim", json={"tier": 5}, headers=headers)
    assert r_claim.status_code == 200
    assert r_claim.json()["success"] is True
    bot_context.social_api.claim_monthly_reward.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_energy_target_xor_mutex_and_master_drain(web_setup):
    from web.routes import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    # 1. Включаем auto_prison -> auto_masters должен быть False
    r1 = await client.patch("/api/v1/config", json={"auto_prison": True}, headers=headers)
    assert r1.status_code == 200
    c1 = r1.json()["config"]
    assert c1["auto_prison"] is True
    assert c1["auto_masters"] is False

    # 2. Включаем auto_masters -> auto_prison автоматически выключается
    r2 = await client.patch("/api/v1/config", json={"auto_masters": True}, headers=headers)
    assert r2.status_code == 200
    d2 = r2.json()["config"]
    assert d2["auto_masters"] is True
    assert d2["auto_prison"] is False
    assert d2["disabled_conflict_target"] == "auto_prison"

    # 3. Включаем auto_prison -> auto_masters автоматически выключается
    r3 = await client.patch("/api/v1/config", json={"auto_prison": True}, headers=headers)
    assert r3.status_code == 200
    d3 = r3.json()["config"]
    assert d3["auto_prison"] is True
    assert d3["auto_masters"] is False
    assert d3["disabled_conflict_target"] == "auto_masters"

    # 4. Одновременная передача обоих True нормализуется к одному активному флагу
    r4 = await client.patch("/api/v1/config", json={"auto_prison": True, "auto_masters": True}, headers=headers)
    assert r4.status_code == 200
    d4 = r4.json()["config"]
    assert not (d4["auto_prison"] and d4["auto_masters"])

    # 5. Ручной слив энергии у мастера
    from unittest.mock import AsyncMock
    orig_player = bot_context.player_api
    orig_prison = bot_context.prison_api
    orig_pw = bot_context.prison_worker
    bot_context.player_api = AsyncMock()
    bot_context.prison_api = AsyncMock()
    bot_context.prison_worker = None
    try:
        bot_context.player_api.init_player.return_value = {"energy": 4, "maxEnergy": 50}
        bot_context.prison_api.enter_master.return_value = {
            "checkpoints": [{"clicksRequired": 5, "energyCost": 2}],
            "data": {"progress": {"currentCheckpoint": 0, "clicksInCheckpoint": 0, "level": 0}},
        }
        bot_context.prison_api.do_master_work.side_effect = [{"energy": 2}, {"energy": 0}]
        r_drain = await client.post("/api/v1/actions/master/drain", json={"masterId": 1}, headers=headers)
        assert r_drain.status_code == 200
        assert r_drain.json()["success"] is True
        assert r_drain.json()["works_done"] == 2
    finally:
        bot_context.player_api = orig_player
        bot_context.prison_api = orig_prison
        bot_context.prison_worker = orig_pw


@pytest.mark.asyncio
async def test_outreach_criteria_status_run_now_and_no_proprisonbot(web_setup):
    from unittest.mock import AsyncMock
    from web.routes import bot_context

    client, _ = web_setup
    headers = {"X-Admin-Token": "test_admin_token"}

    r_raids = await client.get("/api/v1/raids", headers=headers)
    assert r_raids.status_code == 200
    d_raids = r_raids.json()
    assert d_raids["success"] is True
    assert d_raids["isPaywalled"] is False
    assert d_raids["sourceStatus"] != "unauthorized"

    r_patch = await client.patch(
        "/api/v1/outreach/criteria",
        json={"daily_limit": 35, "min_damage": 1_000_000, "sources": ["weekly_top", "tg_channel"], "sort_by": "damage"},
        headers=headers,
    )
    assert r_patch.status_code == 200
    d_patch = r_patch.json()
    assert d_patch["criteria"]["daily_limit"] == 35
    assert d_patch["criteria"]["min_damage"] == 1_000_000
    assert "server_now_ts" in d_patch

    r_status = await client.get("/api/v1/outreach/status", headers=headers)
    assert r_status.status_code == 200
    assert r_status.json()["daily_limit"] == 35

    orig_social = bot_context.social_api
    orig_ow = getattr(bot_context, "friend_outreach_worker", None)
    bot_context.social_api = AsyncMock()
    bot_context.social_api.get_all_friend_ids.return_value = set()
    bot_context.friend_outreach_worker = None
    try:
        r_run = await client.post("/api/v1/outreach/run-now", headers=headers)
        assert r_run.status_code == 200
        assert r_run.json()["success"] is True
    finally:
        bot_context.social_api = orig_social
        bot_context.friend_outreach_worker = orig_ow
