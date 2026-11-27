import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from sqlalchemy import select

from core.database import get_engine, init_db, get_session
from core.models import Account, BotConfig, ActionLog, Notification
from client.api.social import SocialAPI
from workers.social_worker import SocialWorker


@pytest_asyncio.fixture
async def social_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)

    async with get_session(engine) as session:
        acc = Account(id=1, phone="+79993334455", nickname="SocialHero")
        session.add(acc)
        await session.flush()

        cfg = BotConfig(
            account_id=acc.id,
            auto_gifts=True,
            auto_friends=True,
            auto_events=True,
            is_paused=False,
        )
        session.add(cfg)

    yield engine, acc.id
    await engine.dispose()


@pytest.mark.asyncio
async def test_social_worker_executes_when_enabled(social_setup):
    """При включенных тумблерах воркер собирает подарки, принимает друзей и клеймит календарь."""
    engine, acc_id = social_setup

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_gifts_inbox = AsyncMock(return_value={"gifts": [{"id": "gift_101", "fromUserId": 555}]})
    mock_api.claim_gift = AsyncMock(return_value={"success": True})
    mock_api.get_friend_requests = AsyncMock(return_value={"requests": [{"fromUserId": 777}]})
    mock_api.accept_friend = AsyncMock(return_value={"success": True})
    mock_api.get_monthly_state = AsyncMock(return_value={"readyTier": 4})
    mock_api.claim_monthly_reward = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["gifts_claimed"] == 1
    assert res["friends_accepted"] == 1
    assert res["monthly_claimed"] is True

    mock_api.claim_gift.assert_awaited_once_with("gift_101")
    mock_api.accept_friend.assert_awaited_once_with(777)
    mock_api.claim_monthly_reward.assert_awaited_once_with(4)

    # Проверка записей в ActionLog и Notification
    async with get_session(engine) as session:
        action_stmt = select(ActionLog)
        logs = (await session.execute(action_stmt)).scalars().all()
        assert len(logs) >= 3

        notif_stmt = select(Notification)
        notifs = (await session.execute(notif_stmt)).scalars().all()
        assert len(notifs) >= 2


@pytest.mark.asyncio
async def test_social_worker_skips_when_disabled(social_setup):
    """При выключенных тумблерах воркер пропускает соответствующие действия."""
    engine, acc_id = social_setup

    # Выключаем тумблеры в BotConfig
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_gifts = False
        cfg.auto_friends = False
        cfg.auto_events = False
        await session.commit()

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_gifts_inbox = AsyncMock()
    mock_api.claim_gift = AsyncMock()
    mock_api.get_friend_requests = AsyncMock()
    mock_api.accept_friend = AsyncMock()
    mock_api.get_monthly_state = AsyncMock()
    mock_api.claim_monthly_reward = AsyncMock()

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["gifts_claimed"] == 0
    assert res["friends_accepted"] == 0
    assert res["monthly_claimed"] is False

    mock_api.get_gifts_inbox.assert_not_awaited()
    mock_api.claim_gift.assert_not_awaited()
    mock_api.get_friend_requests.assert_not_awaited()
    mock_api.accept_friend.assert_not_awaited()
    mock_api.get_monthly_state.assert_not_awaited()
    mock_api.claim_monthly_reward.assert_not_awaited()


@pytest.mark.asyncio
async def test_social_worker_friend_filtering_accepted_and_declined(social_setup):
    """
    Кандидат с talents=15, poisonDamage=300 принимается при порогах talents>=10, poisonDamage>=250.
    Кандидат с talents=5 отклоняется при friend_auto_decline_below=True.
    """
    engine, acc_id = social_setup

    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_gifts = False
        cfg.auto_events = False
        cfg.auto_friends = True
        cfg.friend_accept_all = False
        cfg.friend_min_talents = 10
        cfg.friend_min_poison_damage = 250
        cfg.friend_auto_decline_below = True
        await session.commit()

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_friend_requests = AsyncMock(return_value={
        "requests": [
            {
                "userId": 101,
                "nickname": "StrongCandidate",
                "talentsCount": 15,
                "weaponDamage": {"poison": 300, "gunshot": 50, "knife": 20},
                "level": 10,
                "authority": 500,
                "biceps": 100,
            },
            {
                "userId": 102,
                "nickname": "WeakCandidate",
                "talentsCount": 5,
                "weaponDamage": {"poison": 100, "gunshot": 20, "knife": 10},
                "level": 3,
                "authority": 50,
                "biceps": 20,
            },
        ]
    })
    mock_api.accept_friend = AsyncMock(return_value={"success": True})
    mock_api.decline_friend = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["friends_accepted"] == 1
    mock_api.accept_friend.assert_awaited_once_with(101)
    mock_api.decline_friend.assert_awaited_once_with(102)


@pytest.mark.asyncio
async def test_social_worker_enriched_stats_filtering(social_setup):
    """
    Тест фильтрации кандидатов в друзья в SocialWorker по всем 6 обогащенным параметрам:
    level, authority, biceps, talents, poisonDamage, totalDamage.
    """
    engine, acc_id = social_setup

    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_gifts = False
        cfg.auto_events = False
        cfg.auto_friends = True
        cfg.friend_accept_all = False
        cfg.friend_min_level = 20
        cfg.friend_min_authority = 10000
        cfg.friend_min_biceps = 500
        cfg.friend_min_talents = 50
        cfg.friend_min_poison_damage = 2000
        cfg.friend_min_total_damage = 4000
        cfg.friend_auto_decline_below = True
        await session.commit()

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_enriched_friend_requests = AsyncMock(return_value=[
        {
            "userId": 201,
            "nickname": "BossCandidate",
            "level": 25,
            "authority": 15000,
            "biceps": 600,
            "talents": 70,
            "poisonDamage": 2500,
            "totalDamage": 5000,
        },
        {
            "userId": 202,
            "nickname": "WeakCandidate",
            "level": 15,
            "authority": 5000,
            "biceps": 200,
            "talents": 30,
            "poisonDamage": 500,
            "totalDamage": 1000,
        },
    ])
    mock_api.accept_friend = AsyncMock(return_value={"success": True})
    mock_api.decline_friend = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["friends_accepted"] == 1
    mock_api.accept_friend.assert_awaited_once_with(201)
    mock_api.decline_friend.assert_awaited_once_with(202)


@pytest.mark.asyncio
async def test_social_api_get_enriched_friend_requests_with_formula():
    """Тест реального метода SocialAPI.get_enriched_friend_requests с расчетом уровня и урона."""
    mock_http = MagicMock()
    api = SocialAPI(mock_http)

    api.get_friend_requests = AsyncMock(return_value={
        "requests": [
            {
                "userId": 301,
                "nickname": "FormulaCandidate",
                "authority": 20000,
                "biceps": 150,
                "level": 0,
                "talentsCount": 18,
                "weaponDamage": {"knife": 100, "poison": 500, "gunshot": 250},
            }
        ]
    })

    enriched = await api.get_enriched_friend_requests()
    assert len(enriched) == 1
    cand = enriched[0]
    assert cand["userId"] == 301
    assert cand["level"] == 30
    assert cand["authority"] == 20000
    assert cand["biceps"] == 150
    assert cand["talents"] == 18
    assert cand["knifeDamage"] == 100
    assert cand["poisonDamage"] == 500
    assert cand["gunshotDamage"] == 250
    assert cand["totalDamage"] == 850


@pytest.mark.asyncio
async def test_social_api_biceps_none_and_worker_acceptance(social_setup):
    """
    Тест: если сервер игры не отдает biceps, SocialAPI возвращает biceps: None,
    а SocialWorker не отклоняет кандидата при friend_min_biceps == 0.
    """
    engine, acc_id = social_setup

    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_gifts = False
        cfg.auto_events = False
        cfg.auto_friends = True
        cfg.friend_accept_all = False
        cfg.friend_min_level = 0
        cfg.friend_min_authority = 0
        cfg.friend_min_biceps = 0
        cfg.friend_min_talents = 0
        cfg.friend_min_poison_damage = 0
        cfg.friend_min_total_damage = 0
        cfg.friend_auto_decline_below = True
        await session.commit()

    mock_http = MagicMock()
    api = SocialAPI(mock_http)
    # Игровой сервер не вернул biceps
    api.get_friend_requests = AsyncMock(return_value={
        "requests": [
            {
                "userId": 401,
                "nickname": "NoBicepsCandidate",
                "authority": 500,
                "level": 5,
                "talentsCount": 10,
                "weaponDamage": {"knife": 10, "poison": 20, "gunshot": 30},
            }
        ]
    })

    enriched = await api.get_enriched_friend_requests()
    assert len(enriched) == 1
    assert enriched[0]["biceps"] is None

    # Проверка, что воркер успешно принимает кандидата с biceps is None
    api.accept_friend = AsyncMock(return_value={"success": True})
    api.decline_friend = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert res["friends_accepted"] == 1
    api.accept_friend.assert_awaited_once_with(401)


@pytest.mark.asyncio
async def test_social_api_accept_and_decline_friend_post_method_and_empty_body():
    """
    Тест SocialAPI.accept_friend и decline_friend:
    - строгий вызов метода POST с query-параметром fromUserId по контракту bundle.js;
    - корректная обработка пустого ответа (200/204) от игрового сервера без JSONDecodeError.
    """
    mock_http = MagicMock()
    # Имитация ответа от сервера игры с пустым телом (например, 204 No Content или пустой 200 OK)
    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.raise_for_status = MagicMock()
    empty_resp.json = MagicMock(side_effect=ValueError("No JSON object could be decoded"))

    mock_http.post = AsyncMock(return_value=empty_resp)

    api = SocialAPI(mock_http)
    test_uid = 9000000000408017

    # 1. Принятие
    res_acc = await api.accept_friend(test_uid)
    assert res_acc == {"success": True}
    mock_http.post.assert_awaited_once_with(f"/api/friendship/accept-request?fromUserId={test_uid}")

    # 2. Отклонение
    mock_http.post.reset_mock()
    res_dec = await api.decline_friend(test_uid)
    assert res_dec == {"success": True}
    mock_http.post.assert_awaited_once_with(f"/api/friendship/decline-request?fromUserId={test_uid}")

    # 3. Кейс с нормальным JSON ответом
    json_resp = MagicMock()
    json_resp.status_code = 200
    json_resp.raise_for_status = MagicMock()
    json_resp.json = MagicMock(return_value={"success": True, "code": 0})
    mock_http.post = AsyncMock(return_value=json_resp)

    res_json = await api.accept_friend(12345)
    assert res_json == {"success": True, "code": 0}


@pytest.mark.asyncio
async def test_social_worker_safe_auto_outreach(social_setup):
    """
    Тест безопасного авто-набора друзей:
    - отправляет не более 3 заявок за цикл только активным кандидатам;
    - соблюдает friend_outreach_daily_limit;
    - полностью молчит при auto_friend_outreach=False, is_paused=True или спящем режиме.
    """
    from core.models import TrackedCandidate, SentFriendRequest
    engine, acc_id = social_setup

    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_gifts = False
        cfg.auto_friends = False
        cfg.auto_events = False
        cfg.auto_friend_outreach = True
        cfg.friend_outreach_daily_limit = 25
        cfg.friend_outreach_only_active = True
        cfg.friend_outreach_min_damage = 0
        cfg.friend_outreach_max_damage = 0

        # Добавляем 4 активных кандидата
        for i in range(1, 5):
            session.add(TrackedCandidate(
                account_id=acc_id,
                user_id=9000000000500000 + i,
                nickname=f"ActiveCandidate_{i}",
                authority=50000 + i * 1000,
                authority_delta=1000 * i,
                total_damage=1000000 * i,
                is_active_recently=True,
                source="guild",
            ))
        await session.commit()

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_friends_list = AsyncMock(return_value=[])
    mock_api.send_friend_request = AsyncMock(return_value={"success": True, "message": "Заявка отправлена"})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    # 1. Запуск цикла: должно отправиться ровно 3 заявки (лимит цикла 3)
    res = await worker.run_cycle()
    assert res["outreach_sent"] == 3
    assert mock_api.send_friend_request.call_count == 3

    # Проверяем, что в SentFriendRequest записались ровно 3 игрока
    async with get_session(engine) as session:
        sent_recs = (await session.execute(select(SentFriendRequest).where(SentFriendRequest.account_id == acc_id))).scalars().all()
        assert len(sent_recs) == 3

    # 2. Проверка при паузе (is_paused=True): социалка должна быть полностью пропущена
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.is_paused = True
        await session.commit()

    mock_api.send_friend_request.reset_mock()
    res_paused = await worker.run_cycle()
    assert res_paused["status"] == "skipped"
    assert mock_api.send_friend_request.call_count == 0

    # 3. Проверка при auto_friend_outreach=False
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.is_paused = False
        cfg.auto_friend_outreach = False
        await session.commit()

    res_disabled = await worker.run_cycle()
    assert res_disabled.get("outreach_sent", 0) == 0
    assert mock_api.send_friend_request.call_count == 0


@pytest.mark.asyncio
async def test_social_worker_filter_mode_or_vs_and(social_setup):
    """
    Тест режима фильтрации входящих заявок friend_filter_mode:
    - 'and': кандидат должен удовлетворять всем заданным ненулевым порогам.
    - 'or': кандидат принимается, если выполнен хотя бы один из ненулевых порогов.
    """
    engine, acc_id = social_setup

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_friend_requests = AsyncMock(return_value={
        "requests": [
            {
                "userId": 501,
                "nickname": "HighTalentsOnly",
                "level": 5,          # min_level=20 -> FAIL
                "authority": 100,    # min_authority=5000 -> FAIL
                "talentsCount": 60,  # min_talents=30 -> PASS
                "weaponDamage": {"poison": 10, "gunshot": 10, "knife": 10},
            }
        ]
    })
    mock_api.accept_friend = AsyncMock(return_value={"success": True})
    mock_api.decline_friend = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    # 1. Режим 'and' (по умолчанию): кандидат не проходит, так как level < 20
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_gifts = False
        cfg.auto_events = False
        cfg.auto_friends = True
        cfg.friend_accept_all = False
        cfg.friend_filter_mode = "and"
        cfg.friend_min_level = 20
        cfg.friend_min_authority = 5000
        cfg.friend_min_talents = 30
        cfg.friend_auto_decline_below = True
        await session.commit()

    res_and = await worker.run_cycle()
    assert res_and["friends_accepted"] == 0
    assert res_and.get("friends_declined", 0) == 1
    mock_api.accept_friend.assert_not_awaited()
    mock_api.decline_friend.assert_awaited_once_with(501)

    # 2. Режим 'or': кандидат принимается благодаря talents=60 >= 30
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.friend_filter_mode = "or"
        await session.commit()

    mock_api.accept_friend.reset_mock()
    mock_api.decline_friend.reset_mock()

    res_or = await worker.run_cycle()
    assert res_or["friends_accepted"] == 1
    mock_api.accept_friend.assert_awaited_once_with(501)
    mock_api.decline_friend.assert_not_awaited()


@pytest.mark.asyncio
async def test_social_worker_reconcile_sent_friend_requests(social_setup):
    """
    Тест сверки SentFriendRequest:
    - переводит 'sent' -> 'accepted' при появлении пользователя в списке друзей;
    - переводит 'sent' -> 'ignored' спустя > 72ч при отсутствии в списке друзей;
    - оставляет 'sent', если прошло < 72ч.
    Также проверяет создание FriendsCountSnapshot.
    """
    from datetime import datetime, timedelta
    from core.models import SentFriendRequest, FriendsCountSnapshot, FriendStats
    engine, acc_id = social_setup

    now = datetime.utcnow()
    async with get_session(engine) as session:
        # req1: добавлен в друзья
        session.add(SentFriendRequest(
            account_id=acc_id,
            target_user_id=1001,
            target_nickname="BecameFriend",
            source="tg_channel",
            status="sent",
            created_at=now - timedelta(hours=2),
        ))
        # req2: проигнорирован (> 72ч)
        session.add(SentFriendRequest(
            account_id=acc_id,
            target_user_id=1002,
            target_nickname="OldIgnored",
            source="guild",
            status="sent",
            created_at=now - timedelta(hours=80),
        ))
        # req3: висит меньше 72ч
        session.add(SentFriendRequest(
            account_id=acc_id,
            target_user_id=1003,
            target_nickname="StillPending",
            source="weekly_top",
            status="sent",
            created_at=now - timedelta(hours=10),
        ))
        await session.commit()

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_all_friend_profiles = AsyncMock(return_value=[
        {
            "userId": 1001,
            "nickname": "BecameFriend",
            "level": 15,
            "authority": 3000,
            "talents": 10,
            "weaponDamage": {"poison": 100, "gunshot": 50, "knife": 20},
        }
    ])

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    await worker.run_cycle()

    async with get_session(engine) as session:
        # Проверяем статусы SentFriendRequest
        reqs = (await session.execute(
            select(SentFriendRequest).where(SentFriendRequest.account_id == acc_id).order_by(SentFriendRequest.target_user_id)
        )).scalars().all()
        r_map = {r.target_user_id: r for r in reqs}

        assert r_map[1001].status == "accepted"
        assert r_map[1001].resolved_at is not None

        assert r_map[1002].status == "ignored"
        assert r_map[1002].resolved_at is not None

        assert r_map[1003].status == "sent"
        assert r_map[1003].resolved_at is None

        # Проверяем снимок FriendsCountSnapshot
        snaps = (await session.execute(
            select(FriendsCountSnapshot).where(FriendsCountSnapshot.account_id == acc_id)
        )).scalars().all()
        assert len(snaps) >= 1
        assert snaps[0].friends_count == 1

        # Проверяем FriendStats
        f_stats = (await session.execute(
            select(FriendStats).where(FriendStats.account_id == acc_id, FriendStats.user_id == 1001)
        )).scalar_one_or_none()
        assert f_stats is not None
        assert f_stats.is_current_friend is True
        assert f_stats.authority == 3000


@pytest.mark.asyncio
async def test_social_worker_cleanup_inactive_friends(social_setup):
    """
    Тест cleanup_inactive_friends():
    - не удаляет is_whitelisted=True;
    - не удаляет новичков (first_seen_at < inactive_days);
    - не удаляет друзей с уроном за 7 дней (damage_7d > 0);
    - соблюдает суточный лимит удалений.
    """
    from datetime import datetime, timedelta
    from core.models import FriendStats, BossFriendDamageLog
    engine, acc_id = social_setup

    now = datetime.utcnow()
    async with get_session(engine) as session:
        # Настраиваем конфиг: inactive_days=14, daily_limit=2
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.friend_cleanup_inactive_days = 14
        cfg.friend_cleanup_daily_limit = 2

        # 1. Защищенный (whitelist) - не удалять
        session.add(FriendStats(
            account_id=acc_id, user_id=2001, nickname="Whitelisted",
            is_whitelisted=True, is_current_friend=True,
            first_seen_at=now - timedelta(days=40), last_active_at=now - timedelta(days=30),
        ))
        # 2. Новичок (first_seen_at 5 дней назад) - не удалять
        session.add(FriendStats(
            account_id=acc_id, user_id=2002, nickname="Newbie",
            is_whitelisted=False, is_current_friend=True,
            first_seen_at=now - timedelta(days=5), last_active_at=now - timedelta(days=20),
        ))
        # 3. Активный дамагер (бил босса 3 дня назад) - не удалять
        session.add(FriendStats(
            account_id=acc_id, user_id=2003, nickname="RecentDamager",
            is_whitelisted=False, is_current_friend=True,
            first_seen_at=now - timedelta(days=30), last_active_at=now - timedelta(days=20),
        ))
        session.add(BossFriendDamageLog(
            account_id=acc_id, boss_session_id="sess_123", user_id=2003,
            recorded_damage=100000, updated_at=now - timedelta(days=3),
        ))
        # 4, 5, 6. Неактивные кандидаты на удаление
        for i in range(4, 7):
            session.add(FriendStats(
                account_id=acc_id, user_id=2000 + i, nickname=f"Inactive_{i}",
                is_whitelisted=False, is_current_friend=True,
                total_damage_to_my_bosses=0,
                first_seen_at=now - timedelta(days=25 + i),
                last_active_at=now - timedelta(days=20 + i),
            ))
        await session.commit()

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.remove_friend = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    removed_count = await worker.cleanup_inactive_friends()
    # daily_limit равен 2, поэтому должно удалиться ровно 2 друга
    assert removed_count == 2
    assert mock_api.remove_friend.call_count == 2

    # Проверяем, что удаленные кандидаты имеют is_current_friend = False
    async with get_session(engine) as session:
        f2001 = (await session.execute(select(FriendStats).where(FriendStats.user_id == 2001))).scalar_one()
        assert f2001.is_current_friend is True  # whitelist остался

        f2002 = (await session.execute(select(FriendStats).where(FriendStats.user_id == 2002))).scalar_one()
        assert f2002.is_current_friend is True  # newbie остался

        f2003 = (await session.execute(select(FriendStats).where(FriendStats.user_id == 2003))).scalar_one()
        assert f2003.is_current_friend is True  # damager остался


@pytest.mark.asyncio
async def test_social_worker_never_calls_send_gift(social_setup):
    """
    Явная проверка: метод send_gift НИ ПРИ КАКИХ УСЛОВИЯХ не вызывается в SocialWorker.
    """
    engine, acc_id = social_setup

    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_gifts_inbox = AsyncMock(return_value={"gifts": [{"id": "g1", "fromUserId": 111}]})
    mock_api.claim_gift = AsyncMock(return_value={"success": True})
    mock_api.send_gift = AsyncMock(return_value={"success": True})

    worker = SocialWorker(
        account_id=acc_id,
        social_api=mock_api,
        db_engine=engine,
        enable_jitter=False,
    )

    await worker.run_cycle()

    # Подарки только собираются
    mock_api.claim_gift.assert_awaited_once_with("g1")
    # Отправка подарков СТРОГО не вызывается!
    mock_api.send_gift.assert_not_called()


@pytest.mark.asyncio
async def test_fast_friend_requests_job_interval_and_instant_hub_sync(social_setup):
    from core.scheduler import SchedulerController, create_scheduler
    from core.state_hub import state_hub
    from core.models import BotConfig
    from unittest.mock import MagicMock

    engine, acc_id = social_setup
    state_hub.clear(acc_id)
    q = state_hub.subscribe(acc_id)

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.auto_friends = True
        cfg.friend_accept_all = False
        cfg.friend_min_poison_damage = 10000
        cfg.friend_auto_decline_below = False
        await session.commit()

    reqs = [
        {"userId": 1, "nickname": "parlik16", "poisonDamage": 21844},
        {"userId": 2, "nickname": "strong2", "poisonDamage": 15000},
        {"userId": 3, "nickname": "Иван", "poisonDamage": 500},
        {"userId": 4, "nickname": "youngSniff", "poisonDamage": 400},
        {"userId": 5, "nickname": "Июльский", "poisonDamage": 300},
        {"userId": 6, "nickname": "Бывалый 2", "poisonDamage": 200},
    ]
    mock_api = MagicMock(spec=SocialAPI)
    mock_api.get_enriched_friend_requests = AsyncMock(return_value=reqs)
    mock_api.accept_friend = AsyncMock(return_value={"success": True})

    worker = SocialWorker(account_id=acc_id, social_api=mock_api, db_engine=engine, enable_jitter=False)
    res = await worker.check_incoming_friend_requests()
    assert res["accepted"] == 2
    assert res["remaining"] == 4

    sl = state_hub.get_slice(acc_id, "friend_requests")
    assert sl is not None
    assert sl.data["total"] == 4
    assert all(r["userId"] not in (1, 2) for r in sl.data["requests"])

    events = []
    while not q.empty():
        events.append(q.get_nowait())
    social_evts = [e for e in events if e.get("type") == "social_updated"]
    assert len(social_evts) == 1
    assert social_evts[0]["incoming_count"] == 4
    assert social_evts[0]["accepted_ids"] == [1, 2]
    state_hub.unsubscribe(acc_id, q)

    assert SchedulerController.FRIEND_REQUESTS_FAST_SEC <= 45
    sched = create_scheduler(routine_worker=MagicMock(account_id=acc_id, db_engine=None), social_worker=worker)
    job = sched.get_job(f"friend_requests_fast_{acc_id}")
    assert job is not None
    assert int(job.trigger.interval.total_seconds()) <= 45


@pytest.mark.asyncio
async def test_enriched_friend_requests_many_with_429_retry():
    """Все 25 заявок в кореша получают level > 0 и authority > 0 даже при временных 429 от API."""
    from unittest.mock import AsyncMock, MagicMock
    from client.api.social import SocialAPI

    reqs = [{"userId": 9000 + i, "nickname": f"Player_{i}", "talentsCount": 10 + i} for i in range(25)]
    attempts = {}

    async def _get_player_view(uid):
        attempts[uid] = attempts.get(uid, 0) + 1
        if attempts[uid] == 1 and uid % 3 == 0:
            raise RuntimeError("HTTP 429 Too many requests. Slow down.")
        return {
            "userId": uid,
            "nickname": f"Player_{uid - 9000}",
            "resources": {"authority": 1000 + (uid - 9000) * 100},
        }

    mock_http = MagicMock()
    social_api = SocialAPI(http_client=mock_http)
    social_api.get_friend_requests = AsyncMock(return_value=reqs)
    player_api = MagicMock()
    player_api.get_player_view = AsyncMock(side_effect=_get_player_view)

    enriched = await social_api.get_enriched_friend_requests(player_api=player_api)
    assert len(enriched) == 25
    for idx, item in enumerate(enriched):
        assert item["userId"] == 9000 + idx
        assert item["authority"] == 1000 + idx * 100
        assert item["level"] > 0


@pytest.mark.asyncio
async def test_friends_stats_and_summary_auto_sync_from_api(social_setup):
    """
    При пустой таблице FriendStats эндпоинты /api/v1/friends/stats и /api/v1/friends/summary
    автоматически синхронизируют список друзей, урон по боссу, % конверсии и средний урон.
    """
    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timedelta
    from core.models import SentFriendRequest
    from web.routes import get_friends_stats, get_friends_summary, bot_context, _flight_cache

    engine, acc_id = social_setup
    _flight_cache.invalidate()

    async with get_session(engine) as session:
        session.add(SentFriendRequest(
            account_id=acc_id,
            target_user_id=7001,
            source="radar_batch",
            status="sent",
            created_at=datetime.utcnow() - timedelta(hours=1),
        ))
        session.add(SentFriendRequest(
            account_id=acc_id,
            target_user_id=7002,
            source="radar_batch",
            status="sent",
            created_at=datetime.utcnow() - timedelta(hours=1),
        ))
        await session.commit()

    mock_social = MagicMock()
    mock_social.get_all_friend_profiles = AsyncMock(return_value=[
        {"userId": 7001, "nickname": "ActiveBro", "authority": 50000},
        {"userId": 7003, "nickname": "BallastBro", "authority": 1000},
    ])
    mock_social.get_all_friend_ids = AsyncMock(return_value={7001, 7003})

    mock_boss = MagicMock()
    mock_boss.get_friend_damage = AsyncMock(return_value={
        "sessionId": "sess_sync_1",
        "items": [{"userId": 7001, "nickname": "ActiveBro", "totalDamage": 250000}],
    })

    old_engine = bot_context.db_engine
    old_social = bot_context.social_api
    old_boss = bot_context.boss_api
    try:
        bot_context.db_engine = engine
        bot_context.social_api = mock_social
        bot_context.boss_api = mock_boss

        stats_res = await get_friends_stats(sort="damage_7d", limit=100, account_id=acc_id, force=False)
        assert stats_res["success"] is True
        assert stats_res["total"] == 2
        f_map = {f["userId"]: f for f in stats_res["friends"]}
        assert f_map[7001]["damage7d"] == 250000
        assert f_map[7001]["level"] > 0
        assert f_map[7003]["damage7d"] == 0

        sum_res = await get_friends_summary(account_id=acc_id, force=True)
        assert sum_res["totalFriends"] == 2
        assert len(sum_res["conversionBySource"]) == 1
        row = sum_res["conversionBySource"][0]
        assert row["sent"] == 2
        assert row["accepted"] == 1
        assert row["conversionRate"] == 50.0
        assert row["avgDamage"] == 250000
    finally:
        bot_context.db_engine = old_engine
        bot_context.social_api = old_social
        bot_context.boss_api = old_boss


@pytest.mark.asyncio
async def test_accept_friend_400_classification_and_retries():
    """Проверка классификации 400 Bad Request, ретраев на 429/503 и остановки при лимите."""
    from client.api.social import SocialAPI, extract_player_combat_stats

    class _Resp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data
            self.text = str(data)
        def json(self):
            return self._data

    class _FakeHttp:
        def __init__(self, seq):
            self.seq = list(seq)
            self.calls = 0
        async def post(self, url):
            self.calls += 1
            return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]

    # 1. 400 Bad Request (лимит у игрока 966716319) -> структурированный ответ без падения
    api_target_lim = SocialAPI(_FakeHttp([
        _Resp(400, {"success": False, "message": "У этого игрока уже максимальное количество друзей (5000). Он не может принять новые заявки."})
    ]))
    r_lim = await api_target_lim.accept_friend(966716319)
    assert r_lim["success"] is False
    assert r_lim["code"] == "target_friends_limit_reached"
    assert r_lim["remove_from_list"] is False

    # 2. Заявка не найдена / уже в друзьях -> remove_from_list=True
    api_gone = SocialAPI(_FakeHttp([_Resp(400, {"message": "Заявка не найдена или отозвана"})]))
    r_gone = await api_gone.accept_friend(111)
    assert r_gone["code"] == "request_not_found"
    assert r_gone["remove_from_list"] is True

    # 3. Ретрай при 429 -> 200 OK
    http_retry = _FakeHttp([_Resp(429, {"message": "Too many"}), _Resp(200, {"success": True})])
    api_retry = SocialAPI(http_retry)
    r_ok = await api_retry.accept_friend(222)
    assert r_ok["success"] is True
    assert http_retry.calls == 2

    # 4. Кейс 966716319: извлечение authority & level из /api/player/view/{uid} без затирания
    stats = extract_player_combat_stats({
        "userId": 966716319,
        "nickname": "Режиссер",
        "authority": 9657926,
        "tattooZones": {"1": "a"},
    })
    assert stats["authority"] == 9657926
    assert stats["level"] > 500


@pytest.mark.asyncio
async def test_social_worker_stops_on_friends_limit_and_filters_real_stats():
    """SocialWorker останавливает массовый прием при friends_limit_reached и использует реальные level/authority."""
    from types import SimpleNamespace
    from workers.social_worker import SocialWorker

    accepted_calls = []

    class _MockAPI:
        async def get_enriched_friend_requests(self):
            return [
                {"userId": 101, "nickname": "A", "level": 694, "authority": 9657926, "talents": 408, "totalDamage": 5000},
                {"userId": 102, "nickname": "B", "level": 694, "authority": 9657926, "talents": 408, "totalDamage": 5000},
            ]
        async def accept_friend(self, uid):
            accepted_calls.append(uid)
            return {"success": False, "code": "friends_limit_reached", "message": "Достигнут ваш лимит друзей.", "remove_from_list": False}

    worker = SocialWorker(account_id=1, social_api=_MockAPI(), db_engine=None, enable_jitter=False)
    cfg = SimpleNamespace(
        is_paused=False,
        auto_friends=True,
        friend_accept_all=False,
        friend_filter_mode="and",
        friend_min_level=500,
        friend_min_authority=1000000,
        friend_min_biceps=0,
        friend_min_talents=100,
        friend_min_poison_damage=0,
        friend_min_total_damage=0,
        friend_auto_decline_below=False,
    )
    res = await worker.check_incoming_friend_requests(config=cfg)
    assert res["status"] == "ok"
    assert accepted_calls == [101]  # Остановился сразу на первом friends_limit_reached!








def test_parse_obshak_info_all_tiers_expired_and_none():
    from client.api.social import parse_obshak_info

    for raw_tier, exp_tier, exp_rank, exp_label in [
        ("pacansky", "pacan", 1, "Пацанский"),
        ("blatnoy", "blat", 2, "Блатной"),
        ("avtoritetny", "avtoritet", 3, "Авторитетный"),
        ("vorovskoy", "vor", 4, "Воровской"),
    ]:
        res = parse_obshak_info({"vpiTier": raw_tier})
        assert res["has_obshak"] is True
        assert res["obshak_tier"] == exp_tier
        assert res["obshak_rank"] == exp_rank
        assert res["obshak_label"] == exp_label
        assert res["obshak_icon"] == f"assets/icons/obshak_{exp_tier}.webp"

    none_res = parse_obshak_info({"userId": 123, "vpiTier": None})
    assert none_res["has_obshak"] is False
    assert none_res["obshak_tier"] == "none"
    assert none_res["obshak_rank"] == 0
    assert none_res["obshak_icon"] == ""

    expired_res = parse_obshak_info({"vpiTier": "vorovskoy", "vpiExpiresAt": 1700000000}, now_ts=1700000100.0)
    assert expired_res["has_obshak"] is False
    assert expired_res["obshak_tier"] == "none"


@pytest.mark.asyncio
async def test_enrich_friend_requests_with_obshak_cache_and_resilience():
    from client.api.social import _OBSHAK_PROFILE_CACHE, enrich_friend_requests_with_obshak

    _OBSHAK_PROFILE_CACHE.clear()
    calls = []

    async def fake_fetch(uid):
        calls.append(uid)
        if int(uid) == 101:
            return {"userId": 101, "vpiTier": "vorovskoy"}
        if int(uid) == 102:
            raise RuntimeError("transient_error")
        return {"userId": uid, "vpiTier": None}

    reqs = [
        {"userId": 101, "nickname": "VorUser"},
        {"userId": 102, "nickname": "ErrUser"},
        {"userId": 103, "nickname": "InlineUser", "vpiTier": "blatnoy"},
    ]
    res1 = await enrich_friend_requests_with_obshak(reqs, fetch_profile_fn=fake_fetch)
    assert len(res1) == 3
    assert res1[0]["has_obshak"] is True and res1[0]["obshak_tier"] == "vor"
    assert res1[1]["has_obshak"] is False and res1[1]["obshak_tier"] == "none"
    assert res1[2]["has_obshak"] is True and res1[2]["obshak_tier"] == "blat"
    assert calls == [101, 102]  # 103 parsed inline without HTTP fetch

    # Second call uses TTL cache for 101 (no extra HTTP call)
    res2 = await enrich_friend_requests_with_obshak([{"userId": 101, "nickname": "VorUser"}], fetch_profile_fn=fake_fetch)
    assert res2[0]["obshak_tier"] == "vor"
    assert calls == [101, 102]
    _OBSHAK_PROFILE_CACHE.clear()
