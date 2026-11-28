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


def test_parse_monthly_state_full_month_and_hidden_future_and_rewards():
    from datetime import datetime, timezone
    from client.api.monthly import parse_monthly_state

    now = datetime(2026, 11, 28, 9, 0, tzinfo=timezone.utc)
    raw_full = {
        "active": True,
        "global": {
            "year": 2026,
            "month": 11,
            "daysInMonth": 30,
            "days": [
                {"dayId": 1, "action": "ScamGambler", "target": 5, "title": "Разведи каталу 5 раз"},
                {"dayId": 27, "action": "SpitSoup", "target": 14, "title": "Харкни в баланду 14 раз"},
                {"dayId": 28, "action": "KillBoss", "target": 1, "title": "Убей босса: Кирпич"},
                {"dayId": 29, "action": "AddYeast", "target": 10, "title": "Подкинь дрожжей 10 раз"},
                {"dayId": 30, "action": "PrisonRun", "target": 1, "title": "Выполни 1 ходку в БУТЫРКА"},
            ],
            "tierRewards": {
                "2": {"currencies": {"rubles": 30}},
                "5": {"currencies": {"chefir": 2}},
                "10": {"currencies": {}, "gunshot": 70},
                "20": {"currencies": {"stew": 4}},
                "30": {"currencies": {"rubles": 130, "stew": 3}, "clothingIds": [382, 383]},
            },
        },
        "user": {
            "activeDayId": 28,
            "completedCount": 7,
            "days": {
                "1": {"progress": 0, "completed": False, "expired": True},
                "27": {"progress": 14, "completed": True, "expired": False},
                "28": {"progress": 1, "completed": True, "expired": False},
            },
            "claimableTiers": [5],
            "claimedTiers": [2],
        },
    }
    parsed = parse_monthly_state(raw_full, now_utc=now)
    assert parsed["year_month"] == "2026-11"
    assert parsed["completed_count"] == 7
    assert parsed["total_days"] == 30
    assert parsed["today_day"] == 28
    assert parsed["future_tasks_available"] is True
    assert len(parsed["schedule"]) == 30
    assert parsed["schedule"][0]["status"] == "missed"
    assert parsed["schedule"][26]["status"] == "completed"
    assert parsed["schedule"][27]["is_today"] is True
    assert parsed["schedule"][29]["title"] == "Выполни 1 ходку в БУТЫРКА"
    assert parsed["schedule"][29]["status"] == "upcoming"

    assert len(parsed["rewards"]) == 5
    assert parsed["rewards"][0]["status"] == "claimed" and parsed["rewards"][0]["required_count"] == 2
    assert parsed["rewards"][1]["status"] == "claimable" and parsed["rewards"][1]["claimable"] is True
    assert parsed["rewards"][2]["status"] == "locked" and parsed["rewards"][2]["remaining_count"] == 3
    assert parsed["rewards"][2]["amount"] == 70 and parsed["rewards"][2]["icon"] == "assets/icons/gunshot.webp"

    # Сценарий B: сервер скрыл будущие задания
    raw_hidden = {
        "active": True,
        "global": {"year": 2026, "month": 11, "daysInMonth": 30, "days": [{"dayId": 28, "target": 1, "title": "Убей Кирпича"}], "tierRewards": {}},
        "user": {"activeDayId": 28, "completedCount": 1, "days": {"28": {"progress": 0, "completed": False}}},
    }
    parsed_b = parse_monthly_state(raw_hidden, history_rows=[{"day_num": 27, "task_title": "Харкни 14 раз", "target_value": 14, "progress_value": 14}], now_utc=now)
    assert parsed_b["future_tasks_available"] is False
    assert parsed_b["schedule"][26]["title"] == "Харкни 14 раз"
    assert parsed_b["schedule"][28]["title"] == ""


@pytest.mark.asyncio
async def test_monthly_tasks_schedule_atomic_overwrite_and_guards(tmp_path):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.database import get_monthly_tasks, get_session, init_db, upsert_monthly_tasks

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'monthly_sched.db'}")
    await init_db(engine)

    # 1. Сохраняем два старых месяца (2026-10 и 2026-11)
    await upsert_monthly_tasks(
        "2026-10",
        [{"day_num": 15, "date_iso": "2026-10-15", "task_key": "OldTask", "title": "Октябрь 15", "target": 1, "progress": 1, "status": "completed"}],
        engine=engine,
    )
    await upsert_monthly_tasks(
        "2026-11",
        [{"day_num": 27, "date_iso": "2026-11-27", "task_key": "SpitSoup", "title": "Харкни 14 раз", "target": 14, "progress": 10, "status": "today"}],
        engine=engine,
    )

    # 2. Внутри одного месяца повторный upsert с пустым title сохраняет старый task_title и обновляет status/progress
    saved_same = await upsert_monthly_tasks(
        "2026-11",
        [{"day_num": 27, "date_iso": "2026-11-27", "task_key": "", "title": "", "target": 0, "progress": 14, "status": "completed"}],
        engine=engine,
    )
    assert saved_same == 1
    nov = await get_monthly_tasks("2026-11", engine=engine)
    assert len(nov) == 1
    assert nov[0]["task_title"] == "Харкни 14 раз"
    assert nov[0]["status"] == "completed"
    assert nov[0]["progress_value"] == 14

    # 3. При наступлении нового месяца (2026-12) старые месяцы (2026-10, 2026-11) атомарно удаляются
    saved_dec = await upsert_monthly_tasks(
        "2026-12",
        [{"day_num": 1, "date_iso": "2026-12-01", "title": "Декабрь день 1", "target": 5, "progress": 0, "status": "today"}],
        engine=engine,
    )
    assert saved_dec == 1
    assert await get_monthly_tasks("2026-10", engine=engine) == []
    assert await get_monthly_tasks("2026-11", engine=engine) == []
    dec = await get_monthly_tasks("2026-12", engine=engine)
    assert len(dec) == 1 and dec[0]["task_title"] == "Декабрь день 1"

    async with get_session(engine) as session:
        res = await session.execute(text("SELECT DISTINCT year_month FROM monthly_tasks_schedule"))
        months_in_db = [row[0] for row in res.fetchall()]
    assert months_in_db == ["2026-12"]

    # 4. Защита от пустого/невалидного ввода: 2026-12 не должен удалиться
    assert await upsert_monthly_tasks("2026-12", [], engine=engine) == 0
    assert await upsert_monthly_tasks("2026-12", [{"day_num": 99, "title": "Bad"}], engine=engine) == 0
    assert await upsert_monthly_tasks("invalid", [{"day_num": 1, "title": "Bad"}], engine=engine) == 0
    dec_after_guards = await get_monthly_tasks("2026-12", engine=engine)
    assert len(dec_after_guards) == 1 and dec_after_guards[0]["task_title"] == "Декабрь день 1"

    await engine.dispose()
