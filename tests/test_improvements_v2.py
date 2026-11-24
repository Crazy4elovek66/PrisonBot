import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.database import get_engine, get_session, init_db, prune_old_notifications
from core.drop_parser import DropParser
from core.models import Account, Notification
from workers.boss_worker import BossWorker
from workers.routine_worker import RoutineWorker


@pytest.mark.asyncio
async def test_boss_melee_loop_reschedules_earliest_cooldown():
    now = datetime.now(timezone.utc)
    weapons_data = {
        "equippedSlots": ["punchChest", "kickBalls"],
        "lastPunchChestTime": (now - timedelta(seconds=500)).isoformat(),  # ready
        "lastKickBallsTime": (now - timedelta(seconds=100)).isoformat(),  # on cooldown (50s left)
    }
    bootstrap = {
        "state": "active",
        "session": {"currentHp": 5000, "maxHp": 10000, "bossId": 1, "mode": "pacansky"},
        "weaponStatsEffective": {"punchChestCooldownSec": 150, "kickBallsCooldownSec": 150},
    }
    boss_api = SimpleNamespace(
        get_weapons=AsyncMock(return_value=weapons_data),
        hit_boss=AsyncMock(return_value={"currentHp": 4500, "state": "active"}),
    )
    rescheduled = []
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        enable_jitter=False,
        on_melee_reschedule=lambda sec: rescheduled.append(sec),
    )
    cfg = SimpleNamespace(boss_auto_melee=True, auto_boss_enabled=False, is_paused=False)

    res = await worker.execute_ready_melee_hits(bootstrap=bootstrap, config=cfg)

    assert len(res["hits_performed"]) == 1
    assert res["hits_performed"][0]["weapon"] == "punchChest"
    assert res["next_melee_ready_at"] is not None
    assert 40.0 <= res["next_melee_wait_sec"] <= 60.0
    assert len(rescheduled) == 1


@pytest.mark.asyncio
async def test_routine_stress_victim_sorts_by_biceps_and_skips_loss():
    player_api = SimpleNamespace(
        get_monthly_state=AsyncMock(return_value={
            "user": {"activeDayId": 1, "days": {"1": {"progress": 0, "completed": False}}},
            "global": {"days": [{"dayId": 1, "action": "StressVictim", "target": 2, "title": "Напряги терпилу"}]},
        }),
        init_player=AsyncMock(return_value={"userId": 999, "currencies": {"cigarettes": 500}}),
    )
    fought = []

    async def _perform(from_id, to_id, inter_type):
        fought.append(to_id)
        if to_id == 10:
            return {"success": True, "message": "Ты проиграл бой"}
        return {"success": True, "message": "Ты победил в бою!"}

    social_api = SimpleNamespace(
        get_all_friend_profiles=AsyncMock(return_value=[
            {"userId": 20, "biceps": 500, "authority": 100},
            {"userId": 10, "biceps": 100, "authority": 900},
            {"userId": 30, "biceps": 150, "authority": 200},
            {"userId": 40, "biceps": 200, "authority": 300},
        ]),
        perform_interaction=AsyncMock(side_effect=_perform),
    )
    worker = RoutineWorker(account_id=1, player_api=player_api, enable_jitter=False, social_api=social_api)
    summary = await worker.process_monthly_quests()

    # Weakest biceps first: 10 (loss, not counted), 30 (win), 40 (win) -> stops at target=2
    assert fought == [10, 30, 40]
    assert summary["actions_performed"] == 2


def test_drop_parser_resolves_collection_drop_from_catalog():
    DropParser.update_collection_cache({
        "collections": [{
            "prison": "Бутырка",
            "collections": [{
                "name": "Воровская масть",
                "items": [{"id": 777, "image": "assets/col/777.png"}],
            }],
        }]
    })
    parsed = DropParser.parse_prison_work(
        {"collectionDrop": {"id": 777, "image": "assets/col/777.png"}},
        prison_name="Бутырка",
    )
    assert len(parsed["drops"]) == 1
    assert "Воровская масть" in parsed["drops"][0]["title"]
    assert "Коллекционный предмет" not in parsed["drops"][0]["title"]


@pytest.mark.asyncio
async def test_prune_old_notifications_keeps_last_7_days(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test_prune.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    now = datetime.now(timezone.utc)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="+70000000001", is_active=True))
        session.add(Notification(
            account_id=1,
            category="other",
            title="Old",
            created_at=now - timedelta(days=9),
        ))
        session.add(Notification(
            account_id=1,
            category="other",
            title="Recent",
            created_at=now - timedelta(days=2),
        ))
        await session.commit()

    deleted = await prune_old_notifications(engine, days=7)
    assert deleted == 1

    async with get_session(engine) as session:
        from sqlalchemy import select
        rows = (await session.execute(select(Notification))).scalars().all()
        assert [r.title for r in rows] == ["Recent"]
    await engine.dispose()
