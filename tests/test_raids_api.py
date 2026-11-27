import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from client.api.raids import RaidsAPI, parse_damage_string
from client.api.social import SocialAPI


def test_parse_damage_string():
    assert parse_damage_string("600кк") == 600_000_000
    assert parse_damage_string("1.5ккк") == 1_500_000_000
    assert parse_damage_string("2 млрд") == 2_000_000_000
    assert parse_damage_string("500m") == 500_000_000
    assert parse_damage_string("100к") == 100_000
    assert parse_damage_string("750 тыс") == 750_000
    assert parse_damage_string("12345") == 12345
    assert parse_damage_string("") == 0
    assert parse_damage_string(None) == 0


@pytest.mark.asyncio
async def test_raids_api_get_raids_success():
    api = RaidsAPI(external_token="fake_token")
    mock_raids_data = [
        {"id": 1, "brigadeName": "Синдикат", "bossName": "Бурят", "minDamage": 500_000_000, "participants": []}
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_raids_data
        mock_get.return_value = mock_resp

        res = await api.get_raids(force_refresh=True)
        assert res["sourceStatus"] == "ok"
        assert res["isPaywalled"] is False
        assert len(res["raids"]) == 1
        assert res["raids"][0]["brigadeName"] == "Синдикат"


@pytest.mark.asyncio
async def test_raids_api_get_raids_paywall_403():
    api = RaidsAPI()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": "Требуется активная подписка", "code": "SUBSCRIPTION_REQUIRED"}
        mock_get.return_value = mock_resp

        res = await api.get_raids(force_refresh=True)
        assert res["sourceStatus"] == "paywall"
        assert res["isPaywalled"] is True
        assert res["raids"] == []
        assert "подписку" in res["sourceMessage"]


@pytest.mark.asyncio
async def test_raids_api_get_raids_unauthorized_401():
    api = RaidsAPI()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        res = await api.get_raids(force_refresh=True)
        assert res["sourceStatus"] == "unauthorized"
        assert res["isPaywalled"] is True
        assert res["raids"] == []


@pytest.mark.asyncio
async def test_raids_api_get_news_and_caching():
    api = RaidsAPI()
    news_payload = {"posts": [{"id": 10, "title": "Рейд выходного дня", "text": "Набор в гильдию"}]}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = news_payload
        mock_get.return_value = mock_resp

        res1 = await api.get_news(limit=10, force_refresh=True)
        assert res1 == news_payload
        assert mock_get.call_count == 1

        # Second call should use TTL cache without hitting network
        res2 = await api.get_news(limit=10, force_refresh=False)
        assert res2 == news_payload
        assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_get_active_players_radar():
    api = RaidsAPI()
    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_weekly_top = AsyncMock(return_value={
        "top": [
            {"userId": 9000000000100001, "nickname": "Топ1", "damage": 1_000_000_000, "authority": 50000, "rank": 1},
            {"userId": 9000000000100002, "nickname": "Топ2_Друг", "damage": 800_000_000, "authority": 40000, "rank": 2},
            {"userId": 9000000000100003, "nickname": "Топ3_Заявка", "damage": 600_000_000, "authority": 30000, "rank": 3},
            {"userId": 9000000000100004, "nickname": "Топ4_Слабый", "damage": 50_000_000, "authority": 10000, "rank": 4},
            {"userId": 437225657, "nickname": "Я_Сам", "damage": 999_000_000, "authority": 99999, "rank": 5},
        ]
    })

    friend_ids = {9000000000100002}
    sent_ids = {9000000000100003}
    my_uid = 437225657

    # 1. Filter with min_damage=100_000_000 and exclude_friends=False
    players = await api.get_active_players_radar(
        social_api=mock_social,
        current_user_id=my_uid,
        friend_ids=friend_ids,
        sent_user_ids=sent_ids,
        min_damage=100_000_000,
        limit=10,
        exclude_friends=False,
    )

    # 437225657 excluded because it's current user
    # Топ4_Слабый excluded because damage < 100M
    assert len(players) == 3
    assert players[0]["userId"] == 9000000000100001
    assert players[0]["friendStatus"] == "none"

    assert players[1]["userId"] == 9000000000100002
    assert players[1]["friendStatus"] == "friend"

    assert players[2]["userId"] == 9000000000100003
    assert players[2]["friendStatus"] == "sent"

    # 2. Filter with exclude_friends=True
    players_ex = await api.get_active_players_radar(
        social_api=mock_social,
        current_user_id=my_uid,
        friend_ids=friend_ids,
        sent_user_ids=sent_ids,
        min_damage=100_000_000,
        limit=10,
        exclude_friends=True,
    )
    assert len(players_ex) == 2
    assert all(p["userId"] != 9000000000100002 for p in players_ex)


@pytest.mark.asyncio
async def test_parse_raid_text():
    api = RaidsAPI()
    raw_text = """
    Рейд Бригады "Северный Ветер" на Хирурга!
    1. 9000000000141538 Барс 600кк
    2. 9000000000466709 Дым 500кк
    3. vk.com/id437225657 Волчара 1.2ккк
    """

    mock_player_api = MagicMock()
    async def fake_get_player_view(uid):
        if uid == 9000000000141538:
            return {"nickname": "Барс", "authority": 12000, "level": 35}
        elif uid == 9000000000466709:
            return {"nickname": "Дым", "authority": 8000, "level": 28}
        elif uid == 437225657:
            return {"nickname": "Волчара", "authority": 50000, "level": 55}
        return {"nickname": f"Игрок {uid}"}

    mock_player_api.get_player_view = AsyncMock(side_effect=fake_get_player_view)

    friend_ids = {9000000000466709}
    sent_ids = set()

    res = await api.parse_raid_text(
        raw_text=raw_text,
        player_api=mock_player_api,
        friend_ids=friend_ids,
        sent_user_ids=sent_ids,
        current_user_id=None,
    )

    assert "Северный Ветер" in res["title"]
    assert res["totalFound"] == 3
    participants = res["participants"]
    assert len(participants) == 3

    # Check that highest claimed damage is sorted first (Волчара 1.2kkk = 1_200_000_000)
    assert participants[0]["userId"] == 437225657
    assert participants[0]["claimedDamage"] == 1_200_000_000
    assert participants[0]["nickname"] == "Волчара"
    assert participants[0]["friendStatus"] == "none"

    # Check friend status on Дым
    dym = next(p for p in participants if p["userId"] == 9000000000466709)
    assert dym["claimedDamage"] == 500_000_000
    assert dym["friendStatus"] == "friend"


@pytest.mark.asyncio
async def test_social_api_send_friend_request():
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_http.post = AsyncMock(return_value=mock_resp)

    social = SocialAPI(mock_http)
    res = await social.send_friend_request(9000000000141538)

    assert res == {"success": True}
    mock_http.post.assert_awaited_once_with("/api/friendship/send-request?toUserId=9000000000141538")


@pytest.mark.asyncio
async def test_raids_activity_detector_24h():
    from datetime import datetime, timedelta
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import select
    from core.database import init_db, get_session
    from core.models import TrackedCandidate

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    raids_api = RaidsAPI()
    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_recruitment_list = AsyncMock(return_value={"items": [{"guildId": 101, "name": "Бригада 101"}]})
    mock_social.get_guild_members = AsyncMock(return_value={
        "members": [{"userId": 9000000000100001, "nickname": "Кабан", "authority": 100000, "level": 40, "bossDamage": 50000000}]
    })

    # 1. Первое сканирование: фиксация prev_authority = 100_000, is_active_recently = False
    res1 = await raids_api.scan_active_guilds(mock_social, test_engine, account_id=1, delay_range=(0, 0), force=True)
    assert res1["success"] is True
    assert res1["scannedGuilds"] == 1

    async with get_session(test_engine) as session:
        cand = (await session.execute(select(TrackedCandidate).where(TrackedCandidate.user_id == 9000000000100001))).scalar_one()
        assert cand.authority == 100000
        assert cand.prev_authority == 100000
        assert cand.authority_delta == 0
        assert cand.is_active_recently is False

        # Симулируем, что прошло 7 часов с момента фиксации снимка
        cand.last_snapshot_at = datetime.utcnow() - timedelta(hours=7)
        await session.commit()

    # 2. Повторное сканирование: авторитет вырос до 125_000 -> дельта 25_000, is_active_recently = True
    mock_social.get_guild_members = AsyncMock(return_value={
        "members": [{"userId": 9000000000100001, "nickname": "Кабан", "authority": 125000, "level": 42, "bossDamage": 70000000}]
    })
    res2 = await raids_api.scan_active_guilds(mock_social, test_engine, account_id=1, delay_range=(0, 0), force=True)
    assert res2["success"] is True

    async with get_session(test_engine) as session:
        cand = (await session.execute(select(TrackedCandidate).where(TrackedCandidate.user_id == 9000000000100001))).scalar_one()
        assert cand.authority == 125000
        assert cand.prev_authority == 100000
        assert cand.authority_delta == 25000
        assert cand.is_active_recently is True

    # 3. Проверка get_active_players_radar с фильтром source='active'
    active_players = await raids_api.get_active_players_radar(
        social_api=mock_social,
        db_engine=test_engine,
        account_id=1,
        source="active",
        limit=10,
    )
    assert len(active_players) == 1
    assert active_players[0]["userId"] == 9000000000100001
    assert active_players[0]["authorityDelta"] == 25000
    assert active_players[0]["isActiveRecently"] is True


@pytest.mark.asyncio
async def test_scan_active_guilds_rotation_and_cooldown():
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.database import init_db

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    raids_api = RaidsAPI()
    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_recruitment_list = AsyncMock(return_value={
        "items": [{"guildId": i, "name": f"Guild_{i}"} for i in range(1, 26)]
    })
    mock_social.get_guild_members = AsyncMock(return_value={"members": []})

    # Первый проход берет ровно 8 бригад (1..8)
    res1 = await raids_api.scan_active_guilds(mock_social, test_engine, max_guilds=8, delay_range=(0, 0), force=True)
    assert res1["success"] is True
    assert res1["scannedGuilds"] == 8
    assert raids_api._guild_cursor == 8

    # Второй проход берет следующие 8 бригад (9..16)
    res2 = await raids_api.scan_active_guilds(mock_social, test_engine, max_guilds=8, delay_range=(0, 0), force=True)
    assert res2["success"] is True
    assert res2["scannedGuilds"] == 8
    assert raids_api._guild_cursor == 16

    # Вызов без force раньше 300с возвращает cooldown без новых сетевых запросов
    res3 = await raids_api.scan_active_guilds(mock_social, test_engine, max_guilds=8, delay_range=(0, 0), force=False)
    assert res3["status"] == "cooldown"
    assert res3["cooldownSeconds"] > 0
    assert mock_social.get_guild_members.call_count == 16


@pytest.mark.asyncio
async def test_outreach_rate_guard_and_circuit_breaker():
    from datetime import datetime, timedelta
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.database import init_db, get_session
    from core.models import SentFriendRequest
    from client.api.raids import OutreachRateGuard

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    guard = OutreachRateGuard()

    # 1. При 25 заявках за 24 часа отправка блокируется (allowed=False)
    async with get_session(test_engine) as session:
        for i in range(25):
            session.add(SentFriendRequest(
                account_id=1,
                target_user_id=1000 + i,
                status="sent",
                created_at=datetime.utcnow() - timedelta(minutes=10),
            ))
        await session.commit()

    allowed, rem, reason = await guard.can_send(1, daily_limit=25, db_engine=test_engine)
    assert allowed is False
    assert rem == 0
    assert "исчерпан" in reason

    # 2. При 429 активируется Circuit Breaker на 60 мин
    guard.record_error(429)
    assert guard.is_circuit_open() is True
    allowed_cb, _, reason_cb = await guard.can_send(1, daily_limit=50, db_engine=test_engine)
    assert allowed_cb is False
    assert "Предохранитель активен" in reason_cb

    # 3. При friends_limit_reached активируется пауза на 24ч
    guard._circuit_open = False
    guard.record_friends_limit_reached()
    assert guard.is_circuit_open() is True
    assert "лимит друзей" in guard._circuit_reason


@pytest.mark.asyncio
async def test_raid_channel_scanner_success_and_flood_wait():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import select
    from core.database import init_db, get_session
    from core.models import CachedRaidPost
    from telegram.raid_channel_scanner import RaidChannelScanner

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    scanner = RaidChannelScanner()
    raids_api = RaidsAPI()

    class FakeMessage:
        def __init__(self, id, text):
            self.id = id
            self.text = text
            self.date = None

    class FakeClient:
        async def connect(self): pass
        async def disconnect(self): pass
        async def is_user_authorized(self): return True
        async def get_entity(self, ch): return ch
        async def iter_messages(self, entity, limit=15):
            yield FakeMessage(
                101,
                "Рейд бригады 'Северный Ветер' на Хирурга!\n1. 9000000000100001 Дым 500кк\n2. 9000000000100002 Волк 300кк"
            )

    # 1. Успешный парсинг канала
    with patch("telegram.raid_channel_scanner.get_telegram_client", return_value=FakeClient()):
        res = await scanner.scan_channels(
            ["pro_prison"],
            test_engine,
            raids_api,
            account_id=1,
            force=True,
            delay_between_channels=0,
        )
        assert res["success"] is True
        assert res["foundPosts"] == 1

        async with get_session(test_engine) as session:
            post = (await session.execute(select(CachedRaidPost))).scalar_one_or_none()
            assert post is not None
            assert post.channel_username == "pro_prison"
            assert len(post.participants) == 2

    # 2. Обработка FloodWaitError
    class FloodWaitClient(FakeClient):
        async def get_entity(self, ch):
            import telethon.errors
            exc = telethon.errors.FloodWaitError(request=None, capture=0)
            exc.seconds = 120
            raise exc

    with patch("telegram.raid_channel_scanner.get_telegram_client", return_value=FloodWaitClient()):
        res_flood = await scanner.scan_channels(
            ["pro_prison"],
            test_engine,
            raids_api,
            account_id=1,
            force=True,
            delay_between_channels=0,
        )
        assert res_flood["status"] == "flood_wait"
        assert res_flood["floodWaitSeconds"] >= 180
        assert raids_api.rate_guard.is_circuit_open() is True


@pytest.mark.asyncio
async def test_radar_enrichment_and_stats_caching_24h():
    from datetime import datetime, timedelta
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import select
    from core.database import init_db, get_session
    from core.models import TrackedCandidate

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    api = RaidsAPI()
    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_weekly_top = AsyncMock(return_value={
        "top": [
            {"userId": 9000000000999001, "nickname": "Кабан999", "damage": 500_000_000, "authority": 12500, "rank": 1},
        ]
    })

    mock_player_api = MagicMock()
    mock_player_api.get_player_view = AsyncMock(return_value={
        "data": {
            "authority": 12500,
            "level": 0,
            "nickname": "Кабан999_Enriched",
            "weaponDamage": {
                "poison": 1500,
                "gunshot": 2500,
                "knife": 3500,
            }
        }
    })

    # 1. Первый вызов: игрок попадает в TrackedCandidate и обогащается через player_api.get_player_view
    players1 = await api.get_active_players_radar(
        social_api=mock_social,
        player_api=mock_player_api,
        db_engine=test_engine,
        account_id=1,
        limit=10,
    )
    assert len(players1) == 1
    p1 = players1[0]
    assert p1["userId"] == 9000000000999001
    assert p1["authority"] == 12500
    assert p1["level"] > 1
    assert p1["poisonDamage"] == 1500
    assert p1["gunshotDamage"] == 2500
    assert p1["knifeDamage"] == 3500
    assert mock_player_api.get_player_view.call_count == 1

    # Проверяем запись в БД
    async with get_session(test_engine) as session:
        cand = (await session.execute(
            select(TrackedCandidate).where(TrackedCandidate.user_id == 9000000000999001)
        )).scalar_one()
        assert cand.poison_damage == 1500
        assert cand.gunshot_damage == 2500
        assert cand.knife_damage == 3500
        assert cand.enriched_at is not None

    # 2. Второй вызов: берется из кэша БД, get_player_view НЕ вызывается повторно
    mock_player_api.get_player_view.reset_mock()
    players2 = await api.get_active_players_radar(
        social_api=mock_social,
        player_api=mock_player_api,
        db_engine=test_engine,
        account_id=1,
        limit=10,
    )
    assert len(players2) == 1
    p2 = players2[0]
    assert p2["poisonDamage"] == 1500
    assert p2["gunshotDamage"] == 2500
    assert p2["knifeDamage"] == 3500
    assert mock_player_api.get_player_view.call_count == 0


@pytest.mark.asyncio
async def test_radar_no_fake_250_60_30_and_real_stats_extraction():
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.database import init_db, get_session
    from core.models import TrackedCandidate
    from client.api.social import extract_player_combat_stats

    # 1. Единый парсер НЕ подставляет фиктивные 250/60/30
    empty_stats = extract_player_combat_stats({"authority": 1288250875})
    assert empty_stats["authority"] == 1288250875
    assert empty_stats["level"] > 7000
    assert empty_stats["poisonDamage"] == 0
    assert empty_stats["gunshotDamage"] == 0
    assert empty_stats["knifeDamage"] == 0

    real_stats = extract_player_combat_stats(
        {"resources": {"authority": 500000}, "weaponDamage": {"Poison": 895, "Gunshot": 246, "Knife": 432}},
        summary_payload={"data": {"overview": {"talentPointsTotal": 985}}},
    )
    assert real_stats["authority"] == 500000
    assert real_stats["talents"] == 985
    assert real_stats["poisonDamage"] == 895
    assert real_stats["gunshotDamage"] == 246
    assert real_stats["knifeDamage"] == 432

    # 2. Переобогащение кандидатов в RaidsAPI с реальными статами и сбросом старых 250/60/30
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    # Имитируем устаревшую запись в БД с нулевым авторитетом и фейковыми 250/60/30
    from datetime import datetime
    async with get_session(test_engine) as session:
        session.add(TrackedCandidate(
            account_id=1,
            user_id=9000000000179416,
            nickname="RV ГАРИК",
            authority=0,
            poison_damage=250,
            gunshot_damage=60,
            knife_damage=30,
            total_damage=1000000,
            enriched_at=datetime.utcnow(),
        ))
        session.add(TrackedCandidate(
            account_id=1,
            user_id=9000000000475579,
            nickname="TheCheesechddr",
            authority=127707,
            poison_damage=250,
            gunshot_damage=60,
            knife_damage=30,
            total_damage=500000,
            enriched_at=datetime.utcnow(),
        ))
        await session.commit()

    api = RaidsAPI()
    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_friend_requests = AsyncMock(return_value=[
        {"userId": 9000000000475579, "talentsCount": 80, "weaponDamage": {"poison": 895, "gunshot": 246, "knife": 432}},
    ])

    mock_player = MagicMock()
    async def _view(uid):
        if uid == 9000000000179416:
            return {"userId": uid, "nickname": "RV ГАРИК", "authority": 1288250875}
        return {"userId": uid, "nickname": "TheCheesechddr", "authority": 127707}

    async def _summary(uid):
        return {"success": True, "data": {"overview": {"talentPointsTotal": 985 if uid == 9000000000179416 else 80}}}

    mock_player.get_player_view = AsyncMock(side_effect=_view)
    mock_player.get_player_summary = AsyncMock(side_effect=_summary)

    players = await api.get_active_players_radar(
        social_api=mock_social,
        player_api=mock_player,
        db_engine=test_engine,
        account_id=1,
        limit=10,
    )
    by_uid = {p["userId"]: p for p in players}

    # RV ГАРИК получил реальный авторитет, уровень, таланты и рассчитанный урон 3 оружий (база + таланты >=973)
    garik = by_uid[9000000000179416]
    assert garik["authority"] == 1288250875
    assert garik["level"] > 7000
    assert garik["talents"] == 985
    assert garik["poisonDamage"] == 1100
    assert garik["gunshotDamage"] == 630
    assert garik["knifeDamage"] == 642

    # Игрок из входящей заявки получил точный серверный урон 895/246/432
    cheese = by_uid[9000000000475579]
    assert cheese["poisonDamage"] == 895
    assert cheese["gunshotDamage"] == 246
    assert cheese["knifeDamage"] == 432
    assert cheese["talents"] == 80


@pytest.mark.asyncio
async def test_outreach_rate_guard_limit_50_plus():
    from datetime import datetime, timedelta
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.database import init_db, get_session
    from core.models import SentFriendRequest
    from client.api.raids import OutreachRateGuard

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    guard = OutreachRateGuard()
    async with get_session(test_engine) as session:
        for i in range(30):
            session.add(SentFriendRequest(
                account_id=1,
                target_user_id=2000 + i,
                status="sent",
                created_at=datetime.utcnow() - timedelta(minutes=15),
            ))
        await session.commit()

    # Дефолтный/рабочий лимит 50 пропускает при 30 отправленных (раньше стопорилось на 25!)
    allowed50, rem50, _ = await guard.can_send(1, daily_limit=50, db_engine=test_engine)
    assert allowed50 is True
    assert rem50 == 20

    # Кастомный лимит 80 работает без искусственного потолка 50
    status80 = await guard.get_safety_status(1, daily_limit=80, db_engine=test_engine)
    assert status80["dailyLimit"] == 80
    assert status80["sentLast24h"] == 30
    assert status80["remaining24h"] == 50


@pytest.mark.asyncio
async def test_radar_weapon_damage_calculation_from_wearables_and_migration():
    """Проверка расчёта реального урона 3 оружий по надетым тату/шмоту/талантам и сброса нулей при миграции."""
    from datetime import datetime
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import select
    from core.database import init_db, get_session, _migrate_tracked_candidates
    from core.models import TrackedCandidate
    from client.api.social import extract_player_combat_stats

    # Расчёт с надетым шмотом (id=13: poison+10), тату (Skull_Zone1: poison+6) и талантами 985 (+850/+570/+612)
    stats = extract_player_combat_stats(
        {
            "authority": 500000,
            "clothingFrontIds": {"1": 13},
            "tattooZones": {"1": "assets/PrisonV3/Tattoos/Skull/T/Skull_Zone1.png"},
        },
        summary_payload={"data": {"overview": {"talentPointsTotal": 985}}},
    )
    assert stats["weaponDamageEstimated"] is True
    assert stats["poisonDamage"] == 250 + 10 + 6 + 850
    assert stats["gunshotDamage"] == 60 + 570
    assert stats["knifeDamage"] == 30 + 612

    # Проверка сброса enriched_at в _migrate_tracked_candidates для записей с 0/0/0 по 3 оружиям
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)
    async with get_session(test_engine) as session:
        session.add(TrackedCandidate(
            account_id=1,
            user_id=9000000000199999,
            nickname="NoWepCached",
            authority=1000000,
            poison_damage=0,
            gunshot_damage=0,
            knife_damage=0,
            enriched_at=datetime.utcnow(),
        ))
        await session.commit()

    async with test_engine.begin() as conn:
        await conn.run_sync(_migrate_tracked_candidates)

    async with get_session(test_engine) as session:
        row = (
            await session.execute(
                select(TrackedCandidate).where(TrackedCandidate.user_id == 9000000000199999)
            )
        ).scalar_one()
        assert row.enriched_at is None


@pytest.mark.asyncio
async def test_multi_tier_guild_scan_and_authority_bounds():
    """Проверка фильтрации бригад по доступным/средним тирам и ограничения по авторитету."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.database import init_db

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(test_engine)

    raids_api = RaidsAPI()
    mock_social = MagicMock(spec=SocialAPI)
    mock_social.get_recruitment_list = AsyncMock(return_value={
        "items": [
            {"guildId": 1, "name": "Top50Full", "level": 50, "memberCount": 80, "maxMembers": 80},
            {"guildId": 2, "name": "Accessible10", "level": 10, "memberCount": 20, "maxMembers": 50},
        ]
    })

    async def _get_members(gid):
        if gid == 2:
            return {
                "members": [
                    {"userId": 9001, "nickname": "LowAuth", "authority": 50000, "bossDamage": 100000},
                    {"userId": 9002, "nickname": "MidAuth", "authority": 1500000, "bossDamage": 500000},
                    {"userId": 9003, "nickname": "MegaWhale", "authority": 90000000, "bossDamage": 9000000},
                ]
            }
        return {"members": []}

    mock_social.get_guild_members = AsyncMock(side_effect=_get_members)
    res_scan = await raids_api.scan_active_guilds(
        mock_social, test_engine, account_id=1, max_guilds=1, delay_range=(0, 0), force=True, tier="accessible"
    )
    assert res_scan["success"] is True
    # В accessible выбрана открытая низкоуровневая бригада (id=2), а не закрытый топ-50 (id=1)
    mock_social.get_guild_members.assert_awaited_once_with(2)

    mid_only = await raids_api.get_active_players_radar(
        social_api=mock_social,
        db_engine=test_engine,
        account_id=1,
        tier="accessible",
        limit=10,
    )
    uids = {p["userId"] for p in mid_only}
    assert 9001 in uids and 9002 in uids
    assert 9003 not in uids  # > 2M отсечен доступным тиром

    await test_engine.dispose()


def test_news_feed_service_parse_sanitize_and_ssrf():
    from telegram.news_feed_service import parse_telegram_channel_html, is_allowed_telegram_media_url

    assert is_allowed_telegram_media_url("https://cdn4.telesco.pe/file/abc.mp4") is True
    assert is_allowed_telegram_media_url("https://cdn1.cdn-telegram.org/file/x.jpg") is True
    assert is_allowed_telegram_media_url("http://127.0.0.1:8080/secret") is False
    assert is_allowed_telegram_media_url("https://evil.example.com/file.mp4") is False

    sample_html = """
    <div class="tgme_widget_message" data-post="itheprison/42">
      <div class="tgme_widget_message_text">
        <b>Обновление</b>
        <blockquote>Важная цитата</blockquote>
        <script>alert(1)</script>
        <a href="javascript:alert(2)" onclick="evil()">bad</a>
        <a href="https://t.me/itheprison/42">link</a>
      </div>
      <div class="tgme_widget_message_video_thumb" style="background-image:url('https://cdn4.telesco.pe/file/poster.jpg')"></div>
      <video src="https://cdn4.telesco.pe/file/anim.mp4"></video>
      <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://evil.com/ssrf.jpg')"></a>
      <time datetime="2026-11-27T12:00:00+00:00"></time>
      <span class="tgme_widget_message_views">1.2K</span>
    </div>
    """
    posts, media_reg = parse_telegram_channel_html(sample_html, channel="itheprison")
    assert len(posts) == 1
    p = posts[0]
    assert p["post_id"] == 42
    assert "<b>Обновление</b>" in p["html"]
    assert "<blockquote>Важная цитата</blockquote>" in p["html"]
    assert "<script" not in p["html"]
    assert "javascript:" not in p["html"]
    assert 'href="https://t.me/itheprison/42"' in p["html"]
    assert len(p["media"]) == 1
    assert p["media"][0]["type"] == "gif"
    assert p["media"][0]["poster_url"] is not None
    assert all("evil.com" not in v["url"] for v in media_reg.values())


@pytest.mark.asyncio
async def test_web_news_media_range_and_raids_players_endpoint(tmp_path, monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from core.config import settings
    from core.database import get_engine, init_db, get_session
    from core.models import Account, BotConfig, TrackedCandidate
    from web.app import app
    from web.routes import bot_context
    from telegram.news_feed_service import news_feed_service

    monkeypatch.setattr(settings, "WEB_ADMIN_TOKEN", "test_admin_token")
    headers = {"X-Admin-Token": "test_admin_token"}

    # Подготовим локальный кэш медиа для проверки Range 206
    media_id = "abcdef1234567890abcdef12"
    media_file = tmp_path / f"{media_id}.mp4"
    media_file.write_bytes(b"0123456789abcdef")
    orig_media_dir = news_feed_service.media_dir
    news_feed_service.media_dir = tmp_path
    news_feed_service._media_registry[media_id] = {"url": "https://cdn4.telesco.pe/file/test.mp4", "kind": "gif"}
    monkeypatch.setattr(
        news_feed_service,
        "get_feed",
        AsyncMock(return_value={"posts": [{"post_id": 99, "html": "<b>News</b>", "media": []}], "has_more": False, "next_before": None, "cached": True}),
    )
    monkeypatch.setattr(
        news_feed_service,
        "get_or_fetch_media",
        AsyncMock(return_value=(media_file, "video/mp4")),
    )

    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79995554433", nickname="RaidsTester")
        session.add(acc)
        await session.flush()
        session.add(BotConfig(account_id=acc.id, auto_friend_outreach=True))
        session.add_all([
            TrackedCandidate(account_id=acc.id, user_id=101, nickname="First", total_damage=900, authority=1000, source="channel"),
            TrackedCandidate(account_id=acc.id, user_id=202, nickname="Second", total_damage=2000, authority=3000, source="radar"),
        ])
        acc_id = acc.id

    orig_engine = bot_context.db_engine
    bot_context.db_engine = engine

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r_news = await ac.get("/api/v1/news?limit=12", headers=headers)
            assert r_news.status_code == 200
            assert r_news.json()["posts"][0]["post_id"] == 99

            # Публичный доступ к медиа без заголовка авторизации (браузерные <img>/<video>)
            r_media_public = await ac.get(f"/api/v1/news/media/{media_id}")
            assert r_media_public.status_code == 200
            assert r_media_public.content == b"0123456789abcdef"

            r_media = await ac.get(f"/api/v1/news/media/{media_id}", headers={"Range": "bytes=0-3"})
            assert r_media.status_code == 206
            assert r_media.content == b"0123"
            assert r_media.headers.get("content-range") == "bytes 0-3/16"

            from telegram.news_feed_service import _is_valid_media_bytes
            assert _is_valid_media_bytes(b"<html><body>403 Forbidden</body></html>", "text/html") is False
            assert _is_valid_media_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01", "image/jpeg") is True

            r_players = await ac.get(f"/api/v1/raids/players?sort=damage&account_id={acc_id}", headers=headers)
            assert r_players.status_code == 200
            pdata = r_players.json()
            assert pdata["success"] is True
            assert pdata["auto_invite"]["enabled"] is True
            assert len(pdata["players"]) == 2
            assert pdata["players"][0]["userId"] == 202
            assert pdata["players"][1]["userId"] == 101
    finally:
        news_feed_service.media_dir = orig_media_dir
        bot_context.db_engine = orig_engine
        await engine.dispose()





def test_news_filter_dedup_and_media_css():
    from telegram.news_feed_service import deduplicate_news_posts, is_game_news_post

    assert is_game_news_post({"text": "Дорожная карта на декабрь: новый босс и таланты!"}) is True
    assert is_game_news_post({"text": "Технические работы на сервере завершены, фикс урона"}) is True
    assert is_game_news_post({"text": "Новый босс и акция на урон уже в игре"}) is True
    assert is_game_news_post({"text": "Итоги активности сообщества за неделю!\n1. @user1\n2. @user2"}) is False
    assert is_game_news_post({"text": "Розыгрыш призов! Победители: @winner1 @winner2"}) is False

    deduped = deduplicate_news_posts([
        {"post_id": 10, "text": "Обновление игры", "media": [{"id": "a"}]},
        {"post_id": 10, "text": "Обновление игры", "media": [{"id": "a"}]},
        {"post_id": 11, "text": "  обновление игры ", "media": [{"id": "a"}]},
        {"post_id": 12, "text": "Фикс багов в рейдах", "media": []},
    ])
    assert [p["post_id"] for p in deduped] == [10, 12]

    css = Path("web/static/styles.css").read_text(encoding="utf-8")
    assert "object-fit: contain;" in css
    assert ".news-media-wrap.is-gif {\n  aspect-ratio: 16 / 9;" not in css
