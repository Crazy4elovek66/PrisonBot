import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select

from core.database import get_engine, init_db, get_session
from core.models import Account, SessionData, ActionLog, BotConfig
from core.config import settings
from client.auth_provider import AuthProvider
from client.http_client import GameHttpClient
from client.api.prison import PrisonAPI
from client.api.player import PlayerAPI
from workers.prison_worker import PrisonWorker


@pytest_asyncio.fixture
async def prison_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79997776655", nickname="PrisonHero")
        session.add(acc)
        await session.flush()
        sess = SessionData(
            account_id=acc.id,
            access_token="mock_valid_token",
            access_exp=9999999999,
        )
        session.add(sess)
        cfg = BotConfig(account_id=acc.id, auto_prison=True)
        session.add(cfg)
        acc_id = acc.id
    yield engine, acc_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_select_highest_unlocked_prison(prison_setup):
    """При PRISON_TARGET_ID=0 выбирается старшая открытая тюрьма (максимальный id)."""
    engine, acc_id = prison_setup

    client = httpx.AsyncClient()
    auth_mock = AuthProvider(account_id=acc_id)
    http_mock = GameHttpClient(auth_provider=auth_mock)
    prison_api = PrisonAPI(http_client=http_mock)
    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=prison_api,
        db_engine=engine,
        enable_jitter=False,
    )

    prisons = [
        {"id": 1, "name": "Бутырка", "isUnlocked": True},
        {"id": 2, "name": "Кресты", "isUnlocked": True},
        {"id": 3, "name": "Белый Лебедь", "isUnlocked": True},
        {"id": 4, "name": "Черный Дельфин", "isUnlocked": False},
        {"id": 5, "name": "Владимирский Централ", "isUnlocked": False},
    ]

    target = worker.select_target_prison(prisons)
    assert target is not None
    assert target["id"] == 3
    assert target["name"] == "Белый Лебедь"


@pytest.mark.asyncio
async def test_prison_worker_energy_drain_cycle(prison_setup, monkeypatch):
    """При энергии 25 и стоимости 10 воркер делает ровно 2 ходки и оставляет 5 энергии."""
    engine, acc_id = prison_setup
    monkeypatch.setattr(settings, "PRISON_MIN_ENERGY", 10)
    monkeypatch.setattr(settings, "PRISON_TARGET_ID", 0)

    energy_state = 25
    calls = []

    def mock_handler(request: httpx.Request):
        nonlocal energy_state
        calls.append((request.method, request.url.path))

        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "energy": energy_state, "maxEnergy": 100})
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "prisons": [
                        {"id": 1, "name": "Бутырка", "isUnlocked": True},
                        {"id": 2, "name": "Кресты", "isUnlocked": True},
                    ],
                },
            )
        elif request.url.path == "/api/player/prison/2":
            return httpx.Response(
                200,
                json={"success": True, "data": {"prisonId": 2, "dayCurrentCheckpoint": 0}},
            )
        elif request.url.path == "/api/player/prison/2/checkpoints":
            return httpx.Response(
                200,
                json={"success": True, "data": [{"energyCost": 10, "clicksRequired": 5}]},
            )
        elif request.url.path == "/api/player/prison/2/work":
            energy_state -= 10
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "energy": energy_state,
                    "rewardCigarettes": 2,
                    "rewardAuthority": 1,
                    "checkpointCompleted": False,
                },
            )
        return httpx.Response(404, json={"error": "Not Found"})

    mock_transport = httpx.MockTransport(mock_handler)
    mock_http_client = httpx.AsyncClient(
        transport=mock_transport,
        base_url=settings.API_BASE_URL,
    )

    auth = AuthProvider(account_id=acc_id)
    auth._access_token = "mock_tok"
    auth._access_exp = 9999999999

    game_http = GameHttpClient(auth_provider=auth)
    game_http._client = mock_http_client

    player_api = PlayerAPI(http_client=game_http)
    prison_api = PrisonAPI(http_client=game_http)

    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=prison_api,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["status"] == "success"
    assert res["works_done"] == 2
    assert res["remaining_energy"] == 5

    # Проверка записей в ActionLog
    async with get_session(engine) as session:
        stmt = select(ActionLog).where(ActionLog.action_type == "prison_work")
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) == 2


@pytest.mark.asyncio
async def test_prison_worker_skip_low_energy(prison_setup):
    """При энергии ниже стоимости 1 действия цикл пропускается со статусом skipped_low_energy."""
    engine, acc_id = prison_setup

    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "energy": 3, "maxEnergy": 100})
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={"success": True, "prisons": [{"id": 1, "name": "Бутырка", "isUnlocked": True}]})
        elif request.url.path == "/api/player/prison/1":
            return httpx.Response(200, json={"success": True, "data": {"prisonId": 1, "dayCurrentCheckpoint": 0}})
        elif request.url.path == "/api/player/prison/1/checkpoints":
            return httpx.Response(200, json={"success": True, "data": [{"energyCost": 5, "clicksRequired": 1}]})
        return httpx.Response(200, json={})

    mock_transport = httpx.MockTransport(mock_handler)
    mock_http_client = httpx.AsyncClient(
        transport=mock_transport,
        base_url=settings.API_BASE_URL,
    )

    auth = AuthProvider(account_id=acc_id)
    auth._access_token = "mock_tok"
    auth._access_exp = 9999999999

    game_http = GameHttpClient(auth_provider=auth)
    game_http._client = mock_http_client

    player_api = PlayerAPI(http_client=game_http)
    prison_api = PrisonAPI(http_client=game_http)

    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=prison_api,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["status"] == "skipped_low_energy"
    assert res["energy"] == 3
    # Убеждаемся, что запросов к ходкам не было
    assert not any("/work" in path for _, path in calls)


@pytest.mark.asyncio
async def test_prison_worker_night_mode(prison_setup):
    """При prison_prefer_night=True запрос ходки отправляется с параметром isDay=false."""
    from core.models import BotConfig

    engine, acc_id = prison_setup
    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(stmt)).scalar_one()
        cfg.prison_prefer_night = True
        cfg.auto_prison = True
        await session.commit()

    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, str(request.url)))
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "energy": 10, "maxEnergy": 100})
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={"success": True, "prisons": [{"id": 1, "name": "Бутырка", "isUnlocked": True}]})
        elif request.url.path == "/api/player/prison/1":
            return httpx.Response(200, json={"success": True, "data": {"prisonId": 1, "nightCurrentCheckpoint": 0}})
        elif request.url.path == "/api/player/prison/1/checkpoints":
            return httpx.Response(200, json={"success": True, "data": [{"energyCost": 5, "clicksRequired": 1}]})
        elif request.url.path == "/api/player/prison/1/work":
            return httpx.Response(200, json={"success": True, "energy": 5, "checkpointCompleted": False})
        return httpx.Response(200, json={})

    mock_transport = httpx.MockTransport(mock_handler)
    mock_http_client = httpx.AsyncClient(
        transport=mock_transport,
        base_url=settings.API_BASE_URL,
    )

    auth = AuthProvider(account_id=acc_id)
    auth._access_token = "mock_tok"
    auth._access_exp = 9999999999

    game_http = GameHttpClient(auth_provider=auth)
    game_http._client = mock_http_client

    player_api = PlayerAPI(http_client=game_http)
    prison_api = PrisonAPI(http_client=game_http)

    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=prison_api,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["status"] == "success"
    # Проверяем, что запрос /work был вызван с isDay=false
    work_calls = [url for method, url in calls if "/work" in url]
    assert len(work_calls) > 0
    assert any("isday=false" in u.lower() for u in work_calls)


@pytest.mark.asyncio
async def test_prison_worker_single_hit_energy_drain(prison_setup):
    """Ходки автоматически выполняются при любой энергии, достаточной для 1 удара (например, energy=5, cost=5)."""
    engine, acc_id = prison_setup

    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "energy": 5, "maxEnergy": 100})
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={"success": True, "prisons": [{"id": 1, "name": "Бутырка", "isUnlocked": True}]})
        elif request.url.path == "/api/player/prison/1":
            return httpx.Response(200, json={"success": True, "data": {"prisonId": 1, "dayCurrentCheckpoint": 0}})
        elif request.url.path == "/api/player/prison/1/checkpoints":
            return httpx.Response(200, json={"success": True, "data": [{"energyCost": 5, "clicksRequired": 1}]})
        elif request.url.path == "/api/player/prison/1/work":
            return httpx.Response(200, json={"success": True, "energy": 0, "checkpointCompleted": False})
        return httpx.Response(200, json={})

    mock_transport = httpx.MockTransport(mock_handler)
    mock_http_client = httpx.AsyncClient(
        transport=mock_transport,
        base_url=settings.API_BASE_URL,
    )

    auth = AuthProvider(account_id=acc_id)
    auth._access_token = "mock_tok"
    auth._access_exp = 9999999999

    game_http = GameHttpClient(auth_provider=auth)
    game_http._client = mock_http_client

    player_api = PlayerAPI(http_client=game_http)
    prison_api = PrisonAPI(http_client=game_http)

    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=prison_api,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["status"] == "success"
    assert res["works_done"] == 1
    assert any("/work" in path for _, path in calls)



@pytest.mark.asyncio
async def test_prison_worker_checkpoint_claim(prison_setup, monkeypatch):
    """При получении сигнала о завершении чекпоинта вызывается claim_checkpoints и логируется действие."""
    engine, acc_id = prison_setup
    monkeypatch.setattr(settings, "PRISON_MIN_ENERGY", 5)

    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))

        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={"success": True, "energy": 12, "maxEnergy": 100})
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(
                200,
                json={"success": True, "prisons": [{"id": 1, "name": "Бутырка", "isUnlocked": True}]},
            )
        elif request.url.path == "/api/player/prison/1":
            return httpx.Response(
                200,
                json={"success": True, "data": {"prisonId": 1, "dayCurrentCheckpoint": 0}},
            )
        elif request.url.path == "/api/player/prison/1/checkpoints":
            return httpx.Response(
                200,
                json={"success": True, "data": [{"energyCost": 10, "clicksRequired": 1}]},
            )
        elif request.url.path == "/api/player/prison/1/work":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "energy": 2,
                    "checkpointCompleted": True,
                    "rewardCigarettes": 10,
                },
            )
        return httpx.Response(404, json={})

    mock_transport = httpx.MockTransport(mock_handler)
    mock_http_client = httpx.AsyncClient(
        transport=mock_transport,
        base_url=settings.API_BASE_URL,
    )

    auth = AuthProvider(account_id=acc_id)
    auth._access_token = "mock_tok"
    auth._access_exp = 9999999999

    game_http = GameHttpClient(auth_provider=auth)
    game_http._client = mock_http_client

    player_api = PlayerAPI(http_client=game_http)
    prison_api = PrisonAPI(http_client=game_http)

    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=prison_api,
        player_api=player_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["status"] == "success"
    assert res["works_done"] == 1

    # Проверка вызова чекпоинта и записи в ActionLog
    async with get_session(engine) as session:
        stmt = select(ActionLog).where(ActionLog.action_type == "prison_checkpoint_claim")
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) == 1
