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


@pytest.mark.asyncio
async def test_prison_drain_all_energy_across_circle_completion(prison_setup):
    """
    drain_all_energy при energy=50 и стоимости 6 НЕ останавливается на runCompleted=True,
    делает ровно 8 ходок до исчерпания энергии и оставляет remainingEnergy=2.
    """
    engine, acc_id = prison_setup
    energy_state = 50
    work_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal energy_state, work_count
        if request.url.path == "/api/player/init":
            return httpx.Response(200, json={
                "success": True,
                "energy": energy_state,
                "maxEnergy": 50,
                "lastEnergyRestoreTime": "2026-11-24T00:00:00Z",
                "energyRestoreIntervalSeconds": 300,
            })
        elif request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={
                "success": True,
                "prisons": [{"id": 4, "name": "Черный Дельфин", "isUnlocked": True}],
            })
        elif request.url.path == "/api/player/prison/4":
            return httpx.Response(200, json={"success": True, "data": {"prisonId": 4, "dayCurrentCheckpoint": 0}})
        elif request.url.path == "/api/player/prison/4/checkpoints":
            if request.method == "POST":
                return httpx.Response(200, json={"success": True})
            return httpx.Response(200, json={"success": True, "data": [{"energyCost": 6, "clicksRequired": 3}]})
        elif request.url.path == "/api/player/prison/4/work":
            work_count += 1
            energy_state -= 6
            # Имитируем завершение круга на 3-й ходке — слив обязан продолжиться дальше!
            run_done = (work_count == 3)
            return httpx.Response(200, json={
                "success": True,
                "energy": energy_state,
                "rewardCigarettes": 10,
                "rewardAuthority": 5,
                "checkpointCompleted": run_done,
                "runCompleted": run_done,
            })
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url=settings.API_BASE_URL)
    auth = AuthProvider(account_id=acc_id)
    auth._access_token = "mock_tok"
    auth._access_exp = 9999999999
    game_http = GameHttpClient(auth_provider=auth)
    game_http._client = mock_client

    scheduled_waits = []
    worker = PrisonWorker(
        account_id=acc_id,
        prison_api=PrisonAPI(http_client=game_http),
        player_api=PlayerAPI(http_client=game_http),
        db_engine=engine,
        enable_jitter=False,
        on_reschedule=lambda sec: scheduled_waits.append(sec),
    )

    res = await worker.drain_all_energy(prison_id=4, mode="day", collect_podogrev=False, source="manual")
    assert res["status"] == "success"
    assert res["runsCompleted"] == 8
    assert res["works_done"] == 8
    assert res["remainingEnergy"] == 2
    assert res["remaining_energy"] == 2
    assert res["circles_completed"] == 1
    assert res["rewards"]["cigarettes"] == 80
    assert len(scheduled_waits) == 1
    assert scheduled_waits[0] <= 300.0


def test_compute_next_stage_wait_seconds():
    """При energy=4, stage_cost=5 и регене 300с расчёт ожидания возвращает ~300с (минус прошедшие секунды тика)."""
    from datetime import datetime, timezone
    from workers.prison_worker import compute_next_stage_wait_seconds

    now = datetime(2026, 11, 24, 3, 5, 0, tzinfo=timezone.utc)
    # 0 секунд прошло с последнего тика -> ровно 300с
    w_exact = compute_next_stage_wait_seconds(
        current_energy=4,
        stage_cost=5,
        regen_interval_sec=300,
        last_restore_time="2026-11-24T03:05:00Z",
        now_utc=now,
        jitter_sec=4.0,
    )
    assert 300.0 <= w_exact <= 306.0

    # 120 секунд прошло с последнего тика -> осталось 180с (+4с буфер)
    w_partial = compute_next_stage_wait_seconds(
        current_energy=4,
        stage_cost=5,
        regen_interval_sec=300,
        last_restore_time="2026-11-24T03:03:00Z",
        now_utc=now,
        jitter_sec=4.0,
    )
    assert abs(w_partial - 184.0) < 0.1


def test_compute_prison_shift_energy_and_master_cycle_energy():
    from client.api.prison import compute_prison_shift_energy, compute_master_cycle_energy

    checkpoints = [
        {"checkpointId": 1, "clicksRequired": 5, "energyCost": 2},   # 10
        {"checkpointId": 2, "clicksRequired": 10, "energyCost": 3},  # 30
        {"checkpointId": 3, "clicksRequired": 4, "energyCost": 5},   # 20
    ]
    full, rem = compute_prison_shift_energy(checkpoints, completed_cps=0, current_clicks=0)
    assert (full, rem) == (60, 60)

    full_mid, rem_mid = compute_prison_shift_energy(checkpoints, completed_cps=1, current_clicks=4)
    assert full_mid == 60
    assert rem_mid == (10 - 4) * 3 + 20  # 38

    full_done, rem_done = compute_prison_shift_energy(checkpoints, completed_cps=3, current_clicks=0)
    assert (full_done, rem_done) == (60, 0)

    m_full, m_rem = compute_master_cycle_energy({"energyCost": 4, "maxProgress": 10, "progress": 3})
    assert (m_full, m_rem) == (40, 28)

    m_steps_full, m_steps_rem = compute_master_cycle_energy(
        {"steps": [{"clicksRequired": 3, "energyCost": 5}, {"clicksRequired": 2, "energyCost": 5}], "currentStep": 1, "currentClicks": 1}
    )
    assert (m_steps_full, m_steps_rem) == (25, 5)

    # Реальная структура ответа /api/player/masters/{id}/enter
    real_enter_payload = {
        "success": True,
        "data": {
            "masterId": 1,
            "progress": {"masterId": 1, "currentCheckpoint": 1, "clicksInCheckpoint": 2, "level": 0},
        },
        "checkpoints": [
            {"checkpointId": 1, "clicksRequired": 5, "energyCost": 2},  # 10 (пройден)
            {"checkpointId": 2, "clicksRequired": 6, "energyCost": 2},  # 12 (2 клика сделано -> ост. 8)
            {"checkpointId": 3, "clicksRequired": 7, "energyCost": 4},  # 28
        ],
    }
    r_full, r_rem = compute_master_cycle_energy(real_enter_payload)
    assert (r_full, r_rem) == (50, 36)


