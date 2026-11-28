import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from core.database import (
    count_outreach_sent_last_24h,
    get_or_create_config,
    get_outreach_excluded_ids,
    get_session,
    init_db,
    record_outreach_history,
)
from core.models import TrackedCandidate
from workers.friend_outreach_worker import FriendOutreachWorker, filter_outreach_candidates


def test_filter_outreach_candidates_all_rules_and_sorting():
    now = datetime(2026, 11, 28, 12, 0, 0)
    cands = [
        {"userId": 1, "nickname": "Self", "damage": 5_000_000, "authority": 1000, "source": "weekly_top", "last_seen_at": (now - timedelta(minutes=1)).isoformat()},
        {"userId": 2, "nickname": "AlreadyFriend", "damage": 5_000_000, "authority": 1000, "source": "weekly_top", "last_seen_at": now.isoformat()},
        {"userId": 3, "nickname": "AlreadySent", "damage": 5_000_000, "authority": 1000, "source": "weekly_top", "last_seen_at": now.isoformat()},
        {"userId": 4, "nickname": "LowDmg", "damage": 50_000, "authority": 1000, "source": "weekly_top", "last_seen_at": now.isoformat()},
        {"userId": 5, "nickname": "HighDmg", "damage": 900_000_000, "authority": 1000, "source": "weekly_top", "last_seen_at": now.isoformat()},
        {"userId": 6, "nickname": "LowAuth", "damage": 1_000_000, "authority": 50, "source": "weekly_top", "last_seen_at": now.isoformat()},
        {"userId": 7, "nickname": "WrongSource", "damage": 1_000_000, "authority": 500, "source": "news_ad", "last_seen_at": now.isoformat()},
        {"userId": 8, "nickname": "BadTag ЧС", "damage": 2_000_000, "authority": 500, "source": "weekly_top", "last_seen_at": now.isoformat()},
        {"userId": 9, "nickname": "ValidA", "damage": 2_000_000, "authority": 500, "source": "weekly_top", "last_seen_at": (now - timedelta(hours=2)).isoformat()},
        {"userId": 10, "nickname": "ValidB", "damage": 8_000_000, "authority": 900, "source": "tg_channel", "last_seen_at": (now - timedelta(hours=1)).isoformat()},
    ]
    criteria = {
        "min_damage": 100_000,
        "max_damage": 100_000_000,
        "min_authority": 100,
        "max_authority": 10_000,
        "sources": ["weekly_top", "tg_channel"],
        "exclude_keywords": "ЧС, враг",
        "sort_by": "damage",
    }
    matched, stats = filter_outreach_candidates(
        cands,
        criteria=criteria,
        excluded_ids={3},
        friend_ids={2},
        self_id=1,
    )
    assert [m["userId"] for m in matched] == [10, 9]
    assert stats["self_skipped"] == 1
    assert stats["already_friend"] == 1
    assert stats["already_sent"] == 1
    assert stats["damage_out_of_range"] == 2
    assert stats["authority_out_of_range"] == 1
    assert stats["source_filtered"] == 1
    assert stats["keyword_excluded"] == 1

    # Сортировка по authority и fresh
    matched_auth, _ = filter_outreach_candidates(cands, {**criteria, "sort_by": "authority"}, {3}, {2}, 1)
    assert [m["userId"] for m in matched_auth] == [10, 9]
    matched_fresh, _ = filter_outreach_candidates(cands, {**criteria, "sort_by": "fresh"}, {3}, {2}, 1)
    assert [m["userId"] for m in matched_fresh] == [10, 9]


@pytest.mark.asyncio
async def test_outreach_sliding_24h_limit_and_worker_cycle(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'outreach.db'}")
    await init_db(engine)

    now_ts = time.time()
    # Старая запись (> 24ч) не должна блокировать лимит, но исключает повторную отправку тому же игроку
    await record_outreach_history(1, 1001, "OldPlayer", "weekly_top", 500_000, 100, status="sent", sent_at=now_ts - 90000, engine=engine)
    # Свежая запись (< 24ч) учитывается в скользящем окне
    await record_outreach_history(1, 1002, "RecentPlayer", "weekly_top", 500_000, 100, status="sent", sent_at=now_ts - 100, engine=engine)

    assert await count_outreach_sent_last_24h(1, now_ts=now_ts, engine=engine) == 1
    excluded = await get_outreach_excluded_ids(1, engine=engine)
    assert {1001, 1002}.issubset(excluded)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as session:
        cfg_db = await session.merge(cfg)
        cfg_db.is_paused = False
        cfg_db.auto_friend_outreach = False
        cfg_db.outreach_criteria = {"enabled": False, "daily_limit": 2, "min_damage": 100_000, "sources": ["weekly_top"], "batch_size": 5}
        session.add_all([
            TrackedCandidate(account_id=1, user_id=2001, nickname="Cand1", total_damage=1_000_000, authority=500, source="weekly_top"),
            TrackedCandidate(account_id=1, user_id=2002, nickname="Cand2", total_damage=2_000_000, authority=600, source="weekly_top"),
            TrackedCandidate(account_id=1, user_id=2003, nickname="Cand3", total_damage=3_000_000, authority=700, source="weekly_top"),
        ])
        await session.commit()

    social_api = AsyncMock()
    social_api.get_all_friend_ids.return_value = set()
    social_api.send_friend_request.side_effect = [
        {"success": False, "code": "already_friends", "message": "Уже в друзьях"},
        {"success": True, "message": "OK"},
    ]
    player_api = AsyncMock()
    player_api.get_me.return_value = {"id": 999999}

    worker = FriendOutreachWorker(1, social_api=social_api, player_api=player_api, db_engine=engine, enable_jitter=False)

    # 1. При enabled=False авто-цикл не шлет заявки
    res_skip = await worker.run_cycle(manual=False)
    assert res_skip["status"] == "skipped"
    social_api.send_friend_request.assert_not_awaited()

    # 2. Включаем enabled=True -> remaining = 2 - 1 = 1; первый already_friends не сжигает лимит, второй уходит и закрывает лимит
    async with get_session(engine) as session:
        cfg_db = await session.merge(cfg)
        cfg_db.auto_friend_outreach = True
        cfg_db.outreach_criteria = {"enabled": True, "daily_limit": 2, "min_damage": 100_000, "sources": ["weekly_top"], "batch_size": 5}
        await session.commit()

    res_ok = await worker.run_cycle(manual=False)
    assert res_ok["status"] == "success"
    assert res_ok["sent_count"] == 1
    assert res_ok["sent_24h"] == 2

    # 3. Следующий цикл видит лимит 2/2
    res_lim = await worker.run_cycle(manual=False)
    assert res_lim["status"] == "limit_reached"
    await engine.dispose()


@pytest.mark.asyncio
async def test_outreach_worker_429_backoff(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'outreach_429.db'}")
    await init_db(engine)
    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as session:
        cfg_db = await session.merge(cfg)
        cfg_db.is_paused = False
        cfg_db.auto_friend_outreach = True
        cfg_db.outreach_criteria = {"enabled": True, "daily_limit": 50, "sources": ["weekly_top"], "batch_size": 5}
        session.add(TrackedCandidate(account_id=1, user_id=3001, nickname="Cand429", total_damage=500_000, authority=100, source="weekly_top"))
        await session.commit()

    social_api = AsyncMock()
    social_api.get_all_friend_ids.return_value = set()
    social_api.send_friend_request.side_effect = RuntimeError("429 Too Many Requests")
    worker = FriendOutreachWorker(1, social_api=social_api, db_engine=engine, enable_jitter=False)

    res = await worker.run_cycle(manual=False)
    assert res["sent_count"] == 0
    assert worker.cooldown_until_ts > time.time()
    assert "429" in worker.last_error
    res_cd = await worker.run_cycle(manual=False)
    assert res_cd["status"] == "cooldown"
    await engine.dispose()
