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


