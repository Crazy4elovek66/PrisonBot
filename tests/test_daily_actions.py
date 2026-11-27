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


@pytest.mark.asyncio
async def test_daily_deltas_matches_tickets_and_weapons_migration_and_reset(tmp_path):
    from datetime import datetime, timedelta
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.config import MSK_TZ
    from core.database import compute_daily_resource_deltas, get_session, init_db

    db_path = tmp_path / "deltas_ext.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)

    day1 = datetime(2026, 11, 27, 15, 0, tzinfo=MSK_TZ)
    # Имитируем старую строку без новых колонок (NULL) — не должно быть ложной дельты
    async with get_session(engine) as session:
        await session.execute(
            text(
                "INSERT INTO daily_resource_snapshots "
                "(day_msk, cigarettes, sugar, rubles, paper, soap, stew, captured_at) "
                "VALUES ('2026-11-27', 1000, 500, 100, 20, 5, 1, '2026-11-27T10:00:00+03:00')"
            )
        )
        await session.commit()

    first = await compute_daily_resource_deltas(
        {
            "cigarettes": 1000, "sugar": 500, "rubles": 100, "paper": 20, "soap": 5, "stew": 1,
            "match_red": 10, "match_green": 15, "match_blue": 3, "wheel_tickets": 2,
            "weapon_poison": 25, "weapon_gunshot": 12, "weapon_knife": 7,
        },
        now_msk=day1,
        engine=engine,
    )
    assert first["deltas"]["match_red"] == 0
    assert first["deltas"]["wheel_tickets"] == 0
    assert first["deltas"]["weapon_poison"] == 0

    second = await compute_daily_resource_deltas(
        {
            "cigarettes": 1050, "sugar": 500, "rubles": 100, "paper": 20, "soap": 5, "stew": 1,
            "match_red": 14, "match_green": 12, "match_blue": 5, "wheel_tickets": 4,
            "weapon_poison": 30, "weapon_gunshot": 10, "weapon_knife": 9,
        },
        now_msk=day1,
        engine=engine,
    )
    assert second["deltas"]["match_red"] == 4
    assert second["deltas"]["match_green"] == -3
    assert second["deltas"]["match_blue"] == 2
    assert second["deltas"]["wheel_tickets"] == 2
    assert second["deltas"]["weapon_poison"] == 5
    assert second["deltas"]["weapon_gunshot"] == -2
    assert second["deltas"]["weapon_knife"] == 2

    # Сброс на новые сутки (00:00+ МСК следующего дня)
    day2 = day1 + timedelta(days=1)
    reset_res = await compute_daily_resource_deltas(
        {
            "cigarettes": 1050, "sugar": 500, "rubles": 100, "paper": 20, "soap": 5, "stew": 1,
            "match_red": 14, "match_green": 12, "match_blue": 5, "wheel_tickets": 4,
            "weapon_poison": 30, "weapon_gunshot": 10, "weapon_knife": 9,
        },
        now_msk=day2,
        engine=engine,
    )
    assert reset_res["deltas"]["match_red"] == 0
    assert reset_res["deltas"]["weapon_poison"] == 0
    await engine.dispose()
