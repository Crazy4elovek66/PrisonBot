import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select
from core.database import get_engine, init_db, get_session
from core.models import Account, SessionData, PlayerSnapshot, ActionLog, BotConfig
from client.auth_provider import AuthProvider
from client.http_client import GameHttpClient
from client.api.player import PlayerAPI
from workers.routine_worker import RoutineWorker


@pytest_asyncio.fixture
async def worker_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79998887766", nickname="WorkerHero")
        session.add(acc)
        await session.flush()
        sess = SessionData(
            account_id=acc.id,
            access_token="mock_valid_token",
            access_exp=9999999999,
        )
        session.add(sess)
        cfg = BotConfig(
            account_id=acc.id,
            auto_toilet_paper=True,
            auto_business=True,
            auto_beard=True,
            auto_podogrev=True,
        )
        session.add(cfg)
        acc_id = acc.id
    yield engine, acc_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_routine_worker_full_cycle_with_paper(worker_setup):
    """Проверка выполнения полного цикла, когда туалетная бумага и бизнесы готовы к сбору."""
    engine, acc_id = worker_setup
    calls = []

    # Бизнесы собраны 9 часов назад (> 480 минут)
    five_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "level": 15,
                    "authority": 12500,
                    "biceps": 45,
                    "energy": 80,
                    "maxEnergy": 100,
                    "canClaimToiletPaper": True,
                    "lastBusinessCollectTime": five_hours_ago,
                    "currencies": {
                        "cigarettes": 300,
                        "sugar": 50,
                        "rubles": 100,
                        "paper": 5,
                        "soap": 2,
                    },
                },
            )
        elif request.url.path == "/api/daily/toilet-paper":
            return httpx.Response(200, json={"success": True, "balance": 6})
        elif request.url.path == "/api/player/business/all":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "lastCollectTime": five_hours_ago,
                    "playerBusinesses": [{"id": 1, "level": 2}],
                },
            )
        elif request.url.path == "/api/player/business/collect":
            return httpx.Response(200, json={"success": True, "rewards": {"cigarettes": 50}})
        elif request.url.path == "/api/beard/update":
            return httpx.Response(200, json={"success": True, "beardPhase": 1})
        elif request.url.path == "/api/podogrev/collect/all":
            return httpx.Response(200, json={"success": True, "appliedEnergy": 10, "leftQuota": 5})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    player_api = PlayerAPI(http_client=http_client)

    worker = RoutineWorker(
        account_id=acc_id,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    cycle_result = await worker.run_cycle()

    assert cycle_result["snapshot_saved"] is True
    assert cycle_result["toilet_paper_claimed"] is True
    assert cycle_result["business_collected"] is True
    assert cycle_result["beard_updated"] is True
    assert cycle_result["podogrev_collected"] is True
    assert len(cycle_result["errors"]) == 0

    assert ("POST", "/api/player/init") in calls
    assert ("POST", "/api/daily/toilet-paper") in calls
    assert ("GET", "/api/player/business/all") in calls
    assert ("POST", "/api/player/business/collect") in calls
    assert ("POST", "/api/beard/update") in calls
    assert ("POST", "/api/podogrev/collect/all") in calls

    async with get_session(engine) as session:
        stmt = select(PlayerSnapshot).where(PlayerSnapshot.account_id == acc_id)
        snaps = (await session.execute(stmt)).scalars().all()
        assert len(snaps) == 1
        s = snaps[0]
        assert s.level == 15
        assert s.authority == 12500
        assert s.paper == 5
        assert s.can_claim_toilet_paper is True

        log_stmt = select(ActionLog).where(ActionLog.account_id == acc_id)
        logs = (await session.execute(log_stmt)).scalars().all()
        action_types = [l.action_type for l in logs]
        assert "init_player" in action_types
        assert "claim_toilet_paper" in action_types
        assert "collect_business" in action_types
        assert "update_beard" in action_types
        assert "collect_podogrev" in action_types


@pytest.mark.asyncio
async def test_routine_worker_skips_paper_when_not_ready(worker_setup):
    """Проверка пропуска сбора туалетной бумаги, когда canClaimToiletPaper = False."""
    engine, acc_id = worker_setup
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "level": 10,
                    "authority": 5000,
                    "biceps": 20,
                    "energy": 50,
                    "maxEnergy": 100,
                    "canClaimToiletPaper": False,
                    "currencies": {},
                },
            )
        elif request.url.path == "/api/player/business/all":
            return httpx.Response(200, json={"success": True, "playerBusinesses": []})
        elif request.url.path == "/api/beard/update":
            return httpx.Response(200, json={"success": True, "beardPhase": 0})
        elif request.url.path == "/api/podogrev/collect/all":
            return httpx.Response(200, json={"success": True, "appliedEnergy": 0})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    player_api = PlayerAPI(http_client=http_client)

    worker = RoutineWorker(
        account_id=acc_id,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    cycle_result = await worker.run_cycle()

    assert cycle_result["snapshot_saved"] is True
    assert cycle_result["toilet_paper_claimed"] is False
    assert ("POST", "/api/daily/toilet-paper") not in calls


@pytest.mark.asyncio
async def test_routine_worker_skips_business_on_cooldown(worker_setup):
    """Тест пропуска сбора бизнесов, если lastCollectTime был 10 минут назад (< 60 минут)."""
    engine, acc_id = worker_setup
    calls = []

    ten_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "canClaimToiletPaper": False})
        elif request.url.path == "/api/player/business/all":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "lastCollectTime": ten_minutes_ago,
                    "playerBusinesses": [{"id": 1, "level": 1}],
                },
            )
        elif request.url.path == "/api/beard/update":
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/podogrev/collect/all":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    player_api = PlayerAPI(http_client=http_client)

    worker = RoutineWorker(
        account_id=acc_id,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    cycle_result = await worker.run_cycle()

    # Сбор бизнесов должен быть пропущен
    assert cycle_result["business_collected"] is False
    assert ("POST", "/api/player/business/collect") not in calls


@pytest.mark.asyncio
async def test_routine_worker_handles_business_400_gracefully(worker_setup):
    """Тест обработки 400 Bad Request от сервера при сборе бизнесов: запись в ActionLog и продолжение цикла."""
    engine, acc_id = worker_setup
    calls = []

    nine_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "canClaimToiletPaper": False})
        elif request.url.path == "/api/player/business/all":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "lastCollectTime": nine_hours_ago,
                    "playerBusinesses": [{"id": 1, "level": 2}],
                },
            )
        elif request.url.path == "/api/player/business/collect":
            # Сервер отвечает 400 Bad Request
            return httpx.Response(400, json={"success": False, "message": "cooldown_not_passed"})
        elif request.url.path == "/api/beard/update":
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/podogrev/collect/all":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    player_api = PlayerAPI(http_client=http_client)

    worker = RoutineWorker(
        account_id=acc_id,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    cycle_result = await worker.run_cycle()

    # Цикл не должен упасть!
    assert cycle_result["business_collected"] is False
    assert cycle_result["beard_updated"] is True
    assert cycle_result["podogrev_collected"] is True
    assert any("collect_business (HTTP 400)" in e for e in cycle_result["errors"])

    # Проверяем запись в ActionLog с success=False и status_code=400
    async with get_session(engine) as session:
        log_stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "collect_business"
        )
        log = (await session.execute(log_stmt)).scalar_one_or_none()
        assert log is not None
        assert log.success is False
        assert log.status_code == 400
        assert "cooldown_not_passed" in str(log.details)


@pytest.mark.asyncio
async def test_routine_worker_auto_kolsik_roll(worker_setup):
    """
    Тест автопокупки у Кольщика в RoutineWorker:
    1. При auto_kolsik=True и kolsik_currency="rubles" отправляется POST /api/kolsik/roll и создается Notification.
    2. При auto_kolsik=False прокрутка не выполняется.
    """
    from core.models import Notification

    engine, acc_id = worker_setup
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={
                "success": True,
                "canClaimToiletPaper": False,
                "currencies": {"paper": 50, "rubles": 30},
            })
        elif request.url.path == "/api/kolsik/roll":
            return httpx.Response(200, json={
                "success": True,
                "reward": {"id": 12, "name": "Звезда воровская", "cardPreviewUrl": "assets/tattoos/star.png"}
            })
        elif request.url.path == "/api/beard/update":
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/podogrev/collect/all":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json={})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    player_api = PlayerAPI(http_client=http_client)

    # 1. auto_kolsik = True, kolsik_currency = "rubles"
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_kolsik = True
        cfg.kolsik_currency = "rubles"
        await session.commit()

    worker = RoutineWorker(
        account_id=acc_id,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert res["kolsik_rolled"] is True
    assert ("POST", "/api/kolsik/roll") in calls

    # Проверяем сохранение Notification
    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.title == "Кольщик (Наколка)")
        notif = (await session.execute(stmt)).scalar_one_or_none()
        assert notif is not None
        assert notif.category == "other"
        assert notif.drops[0]["title"] == "Звезда воровская"

    # 2. auto_kolsik = False -> запрос не отправляется
    calls.clear()
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.auto_kolsik = False
        await session.commit()

    res2 = await worker.run_cycle()
    assert res2["kolsik_rolled"] is False
    assert ("POST", "/api/kolsik/roll") not in calls

