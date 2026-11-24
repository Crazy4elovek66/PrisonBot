import pytest
from unittest.mock import AsyncMock, MagicMock
from client.api.player import PlayerAPI
from workers.prison_worker import PrisonWorker
from core.models import BotConfig, TrackedCandidate
from client.api.raids import RaidsAPI
from sqlalchemy.ext.asyncio import create_async_engine
from core.database import Base


@pytest.mark.asyncio
async def test_claim_toilet_paper_api():
    mock_client = AsyncMock()
    mock_client.post.return_value = MagicMock(status_code=200, json=lambda: {"success": True, "paper": 1})
    player_api = PlayerAPI(http_client=mock_client)

    res = await player_api.claim_toilet_paper()
    assert res.get("success") is True
    assert mock_client.post.call_args[0][0] == "/api/daily/toilet-paper"


@pytest.mark.asyncio
async def test_send_all_podogrev_safe_endpoint():
    mock_client = AsyncMock()
    # Эндпоинт друзей
    mock_client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"friends": [{"id": 101, "canSend": True}, {"id": 102, "canSend": True}]}
    )
    # Эндпоинт отправки
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"success": True, "sent": 2}
    )
    player_api = PlayerAPI(http_client=mock_client)

    res = await player_api.send_all_podogrev()
    assert res.get("sent") == 2
    assert "/api/podogrev/send" in [call[0][0] for call in mock_client.post.call_args_list]
    assert "/api/gifts/send" not in [call[0][0] for call in mock_client.post.call_args_list]


@pytest.mark.asyncio
async def test_smart_podogrev_in_prison_worker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    mock_prison_api = AsyncMock()
    mock_prison_api.get_all_prisons.return_value = [{"id": 1, "name": "Кресты", "isUnlocked": True}]
    mock_prison_api.get_prison_state.return_value = {"dayCurrentCheckpoint": 0}
    mock_prison_api.get_checkpoints.return_value = [{"energyCost": 10}]
    mock_prison_api.do_prison_work.return_value = {"success": True, "energy": 0}
    mock_prison_api.claim_checkpoints.return_value = {"success": True}

    mock_player_api = AsyncMock()
    # Вначале 10 энергии, макс 100
    mock_player_api.init_player.side_effect = [
        {"player": {"energy": 10, "maxEnergy": 100}}, # 1й опрос
        {"player": {"energy": 20, "maxEnergy": 100}}, # после сбора подогревов
    ]
    # При сборе подогревов вернули claimed=2
    mock_player_api.collect_all_podogrev.return_value = {"claimed": 2}

    worker = PrisonWorker(
        account_id=1,
        prison_api=mock_prison_api,
        player_api=mock_player_api,
        db_engine=engine,
    )
    worker._log_action = AsyncMock()
    worker._jitter = AsyncMock()

    from unittest.mock import patch
    mock_cfg = BotConfig(account_id=1, auto_prison=True, auto_podogrev=True, prison_target_id=1)
    with patch("workers.prison_worker.get_or_create_config", return_value=mock_cfg):
        result = await worker.run_cycle()

    assert result["status"] == "success"
    mock_player_api.collect_all_podogrev.assert_called_once()
    assert mock_prison_api.do_prison_work.call_count >= 2


@pytest.mark.asyncio
async def test_radar_unique_constraint_prevention():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    mock_social_api = AsyncMock()
    mock_social_api.get_weekly_top.return_value = {
        "top": [{"userId": 777, "nickname": "Дубликат", "damage": 50000, "authority": 12000}]
    }
    mock_social_api.get_top_achievements.return_value = {
        "achievements": [{"userId": 777, "nickname": "Дубликат", "damage": 60000, "authority": 13000}]
    }

    raids_api = RaidsAPI()
    res = await raids_api.sync_weekly_top_and_achievements(
        social_api=mock_social_api,
        db_engine=engine,
        account_id=1,
        force=True,
    )
    assert res.get("success") is True
    assert res.get("synced") == 1

    from core.database import get_session
    from sqlalchemy import select
    async with get_session(engine) as session:
        cand = (await session.execute(select(TrackedCandidate).where(TrackedCandidate.user_id == 777))).scalar_one_or_none()
        assert cand is not None
        assert cand.user_id == 777
        assert cand.total_damage == 60000
        assert cand.authority == 13000
        # Без фиктивной подстановки 250/60/30 до обогащения
        assert cand.poison_damage == 0
        assert cand.gunshot_damage == 0
        assert cand.knife_damage == 0
