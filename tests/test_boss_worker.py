import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select
from core.database import get_engine, init_db, get_session
from core.models import Account, SessionData, ActionLog, BotConfig
from client.auth_provider import AuthProvider
from client.http_client import GameHttpClient
from client.api.boss import BossAPI
from workers.boss_worker import BossWorker


@pytest_asyncio.fixture
async def boss_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79997776655", nickname="BossHero")
        session.add(acc)
        await session.flush()
        sess = SessionData(
            account_id=acc.id,
            access_token="valid_boss_token",
            access_exp=9999999999,
        )
        session.add(sess)
        cfg = BotConfig(account_id=acc.id, auto_boss_hits=True)
        session.add(cfg)
        acc_id = acc.id
    yield engine, acc_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_vorkuta_0859_expired_defeat_not_classified_as_victory(tmp_path):
    """
    Воспроизведение инцидента 08:59 (Воркута Пацанский, 08:01:01):
    claim возвращает {"success": True, "status": "claimed", "rewards": {"result": "defeat", ...}},
    таймер истёк, last_hp > 0, дельта профиля 0 -> строго defeat, без ложной победы и без 'получены'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_vorkuta_defeat.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    vorkuta_claim = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b7d5b677e19377f0da45d4f52a",
        "rewards": {
            "mode": "pacansky",
            "time": "2026-11-26T05:58:42.0221039Z",
            "title": "Воркута",
            "bossId": 39,
            "result": "defeat",
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
        },
    }
    started_iso = (datetime.now(timezone.utc) - timedelta(hours=8, minutes=1, seconds=1)).isoformat()
    ends_iso = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 39,
            "title": "Воркута",
            "mode": "pacansky",
            "currentHp": 149444357,
            "maxHp": 400000000,
            "personalDamage": 67,
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
            "startedAt": started_iso,
            "endsAt": ends_iso,
        },
        "unclaimedRewards": [{"claimId": "01a214b7d5b677e19377f0da45d4f52a", "bossId": 39}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value=vorkuta_claim),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(
        init_player=AsyncMock(return_value={"currencies": {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 12}})
    )
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res.get("victories") or []) == 0
    assert len(res.get("defeats") or []) == 1
    df = res["defeats"][0]
    assert df["boss_name"] == "Воркута"
    assert df["remaining_hp"] == 149444357
    assert df["max_hp"] == 400000000
    assert df["personal_damage"] == 67

    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Поражение от босса: Воркута (Пацанский)" in tg_msg
    assert "Победа над боссом" not in tg_msg
    assert "получены" not in tg_msg

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert notifs[0].meta_json["outcome"] == "defeat"

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_victory_empty_claim_uses_fresh_profile_currencies_delta(tmp_path):
    """
    Победа с явным victory=True без массива rewards в ответе claim:
    свежий запрос player_api.init_player() возвращает currencies -> дельта дополняет награды в TG и Web.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_delta_currencies.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    notifier = SimpleNamespace(notify=AsyncMock())
    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"currencies": {"cigarettes": 1000, "sugar": 100, "authority": 500}, "authority": 500}
        return {"currencies": {"cigarettes": 1150, "sugar": 130, "authority": 1000}, "authority": 1000}

    bootstrap = {
        "state": "reward",
        "session": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_delta_cur"},
        "unclaimedRewards": [{"claimId": "cid_delta_cur", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value={"success": True, "victory": True}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res["victories"]) == 1
    cur_map = {r["currency"]: r["amount"] for r in res["victories"][0]["rewards"]}
    assert cur_map["cigarettes"] == 150
    assert cur_map["sugar"] == 30
    assert cur_map["authority"] == 500

    tg_msg = notifier.notify.call_args[0][0]
    assert "Папиросы +150" in tg_msg
    assert "Сахар +30" in tg_msg
    assert "Авторитет +500" in tg_msg
    assert "получены" not in tg_msg

    await engine.dispose()


def test_night_mode_windows_msk_and_worker_isolation():
    """Проверка окон Ночного режима по МСК и того, что is_worker_active не блокирует другие воркеры."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from core.database import is_night_mode_active, is_worker_active

    # 23:00-08:00 МСК: 02:30 МСК = 23:30 UTC предыдущего дня
    cfg_cross = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=23, sleep_end_hour=8)
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)) is False  # 12:00 МСК
    assert is_worker_active(cfg_cross) is True

    # 00:00-08:00 МСК: 03:00 МСК = 00:00 UTC
    cfg_same = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=0, sleep_end_hour=8)
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)) is False  # 08:00 МСК
    assert is_worker_active(cfg_same) is True

    # start == end -> не блокирует 24/7
    cfg_eq = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=5, sleep_end_hour=5)
    assert is_night_mode_active(cfg_eq, now_utc=datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_boss_worker_night_mode_allows_claim_blocks_summon_and_attack(tmp_path, monkeypatch):
    """В Ночной режим BossWorker забирает награды (claim), но не призывает и не атакует боссов."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_or_create_config, get_session
    from core.models import BotConfig
    import workers.boss_worker as bw_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'night_boss.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as s:
        db_cfg = await s.get(BotConfig, cfg.id)
        db_cfg.sleep_mode_enabled = True
        db_cfg.sleep_start_hour = 0
        db_cfg.sleep_end_hour = 8
        db_cfg.auto_boss_enabled = True
        db_cfg.auto_boss_summon = True
        db_cfg.auto_boss_hits = True
        db_cfg.boss_auto_melee = True
        db_cfg.boss_targets = [1]
        await s.commit()

    monkeypatch.setattr(bw_mod, "is_night_mode_active", lambda c: True)

    bootstraps = [
        # 1. Завершенный бой с наградой -> должен быть заклеймлен ночью!
        {
            "state": "reward",
            "battle": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_night_1"},
            "prisons": [],
        },
        # 2. После клейма слот свободен -> призывать нового ночью НЕЛЬЗЯ!
        {
            "state": "idle",
            "battle": None,
            "prisons": [],
        },
    ]
    claim_mock = AsyncMock(return_value={
        "success": True,
        "rewards": {"result": "victory", "globalReward": {"cigarettes": 100}},
    })
    summon_mock = AsyncMock()
    attack_mock = AsyncMock()
    notifier = SimpleNamespace(notify=AsyncMock())

    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(side_effect=lambda: bootstraps.pop(0) if len(bootstraps) > 1 else bootstraps[0]),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=claim_mock,
        start_boss=summon_mock,
        attack_boss=attack_mock,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=AsyncMock(return_value={"currencies": {"cigarettes": 500, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0, "authority": 0}}))

    worker = BossWorker(account_id=1, boss_api=boss_api, player_api=player_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 1
    assert res.get("night_mode_paused") is True
    assert claim_mock.await_count == 1
    assert summon_mock.await_count == 0
    assert attack_mock.await_count == 0
    assert notifier.notify.await_count == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_finalizing_retry_profile_delta_duration_and_tg_format(tmp_path):
    """
    Быстрая победа между опросами + 'Reward is being finalized' ->
    система НЕ шлет поражение, ретраит claim, дополняет награды из дельты профиля,
    считает длительность ЧЧ:ММ:СС и шлет строгий TG-формат победы без промежуточных атак/призывов.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_finalizing.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    claim_calls = 0

    async def _claim(cid=None):
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 1:
            return {"success": False, "status": "not_ready", "message": "Reward is being finalized", "retryAfterMs": 500}
        return {
            "success": True,
            "rewards": [{"type": "cigarettes", "amount": 200}],
            "tattoo": {"id": 12, "name": "Перстень", "set": "Мафия"},
        }

    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"player": {"resources": {"cigarettes": 1000, "authority": 500, "sugar": 10}}}
        return {"player": {"resources": {"cigarettes": 1200, "authority": 550, "sugar": 25}}}

    started_iso = (datetime.now(timezone.utc) - timedelta(seconds=95)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 1,
            "title": "Кирпич",
            "mode": "pacansky",
            "currentHp": 891,
            "maxHp": 1000,
            "sessionId": "sess_kirpich_fast",
            "startedAt": started_iso,
        },
        "unclaimedRewards": [{"claimId": "cid_fast_1", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=_claim,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert claim_calls == 2
    assert len(res.get("defeats") or []) == 0
    assert len(res["victories"]) == 1
    vic = res["victories"][0]
    assert vic["boss_name"] == "Кирпич"
    assert vic["duration_sec"] >= 90
    assert ":" in vic["duration_formatted"]

    # Проверяем, что дельта профиля добавила authority (+50) и sugar (+15) без дублирования cigarettes (+200)
    cur_map = {r["currency"]: r["amount"] for r in vic["rewards"]}
    assert cur_map["cigarettes"] == 200
    assert cur_map["authority"] == 50
    assert cur_map["sugar"] == 15

    # Проверяем строгий формат TG-уведомления
    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Победа над боссом: Кирпич (Пацанский)" in tg_msg
    assert "🔥 Награды:" in tg_msg
    assert "⏱️ Бой продлился:" in tg_msg
    assert "Битва с боссом:" not in tg_msg
    assert "Призвано боссов:" not in tg_msg

    # Проверяем сохранение в БД для Web
    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert "Победа над боссом: Кирпич (Пацанский)" in notifs[0].title
        assert notifs[0].meta_json.get("duration_formatted")
        assert len(notifs[0].meta_json.get("rewards") or []) >= 3

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_vorkuta_0859_expired_defeat_not_classified_as_victory(tmp_path):
    """
    Воспроизведение инцидента 08:59 (Воркута Пацанский, 08:01:01):
    claim возвращает {"success": True, "status": "claimed", "rewards": {"result": "defeat", ...}},
    таймер истёк, last_hp > 0, дельта профиля 0 -> строго defeat, без ложной победы и без 'получены'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_vorkuta_defeat.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    vorkuta_claim = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b7d5b677e19377f0da45d4f52a",
        "rewards": {
            "mode": "pacansky",
            "time": "2026-11-26T05:58:42.0221039Z",
            "title": "Воркута",
            "bossId": 39,
            "result": "defeat",
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
        },
    }
    started_iso = (datetime.now(timezone.utc) - timedelta(hours=8, minutes=1, seconds=1)).isoformat()
    ends_iso = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 39,
            "title": "Воркута",
            "mode": "pacansky",
            "currentHp": 149444357,
            "maxHp": 400000000,
            "personalDamage": 67,
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
            "startedAt": started_iso,
            "endsAt": ends_iso,
        },
        "unclaimedRewards": [{"claimId": "01a214b7d5b677e19377f0da45d4f52a", "bossId": 39}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value=vorkuta_claim),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(
        init_player=AsyncMock(return_value={"currencies": {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 12}})
    )
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res.get("victories") or []) == 0
    assert len(res.get("defeats") or []) == 1
    df = res["defeats"][0]
    assert df["boss_name"] == "Воркута"
    assert df["remaining_hp"] == 149444357
    assert df["max_hp"] == 400000000
    assert df["personal_damage"] == 67

    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Поражение от босса: Воркута (Пацанский)" in tg_msg
    assert "Победа над боссом" not in tg_msg
    assert "получены" not in tg_msg

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert notifs[0].meta_json["outcome"] == "defeat"

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_victory_empty_claim_uses_fresh_profile_currencies_delta(tmp_path):
    """
    Победа с явным victory=True без массива rewards в ответе claim:
    свежий запрос player_api.init_player() возвращает currencies -> дельта дополняет награды в TG и Web.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_delta_currencies.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    notifier = SimpleNamespace(notify=AsyncMock())
    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"currencies": {"cigarettes": 1000, "sugar": 100, "authority": 500}, "authority": 500}
        return {"currencies": {"cigarettes": 1150, "sugar": 130, "authority": 1000}, "authority": 1000}

    bootstrap = {
        "state": "reward",
        "session": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_delta_cur"},
        "unclaimedRewards": [{"claimId": "cid_delta_cur", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value={"success": True, "victory": True}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res["victories"]) == 1
    cur_map = {r["currency"]: r["amount"] for r in res["victories"][0]["rewards"]}
    assert cur_map["cigarettes"] == 150
    assert cur_map["sugar"] == 30
    assert cur_map["authority"] == 500

    tg_msg = notifier.notify.call_args[0][0]
    assert "Папиросы +150" in tg_msg
    assert "Сахар +30" in tg_msg
    assert "Авторитет +500" in tg_msg
    assert "получены" not in tg_msg

    await engine.dispose()


def test_night_mode_windows_msk_and_worker_isolation():
    """Проверка окон Ночного режима по МСК и того, что is_worker_active не блокирует другие воркеры."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from core.database import is_night_mode_active, is_worker_active

    # 23:00-08:00 МСК: 02:30 МСК = 23:30 UTC предыдущего дня
    cfg_cross = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=23, sleep_end_hour=8)
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)) is False  # 12:00 МСК
    assert is_worker_active(cfg_cross) is True

    # 00:00-08:00 МСК: 03:00 МСК = 00:00 UTC
    cfg_same = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=0, sleep_end_hour=8)
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)) is False  # 08:00 МСК
    assert is_worker_active(cfg_same) is True

    # start == end -> не блокирует 24/7
    cfg_eq = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=5, sleep_end_hour=5)
    assert is_night_mode_active(cfg_eq, now_utc=datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_boss_worker_night_mode_allows_claim_blocks_summon_and_attack(tmp_path, monkeypatch):
    """В Ночной режим BossWorker забирает награды (claim), но не призывает и не атакует боссов."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_or_create_config, get_session
    from core.models import BotConfig
    import workers.boss_worker as bw_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'night_boss.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as s:
        db_cfg = await s.get(BotConfig, cfg.id)
        db_cfg.sleep_mode_enabled = True
        db_cfg.sleep_start_hour = 0
        db_cfg.sleep_end_hour = 8
        db_cfg.auto_boss_enabled = True
        db_cfg.auto_boss_summon = True
        db_cfg.auto_boss_hits = True
        db_cfg.boss_auto_melee = True
        db_cfg.boss_targets = [1]
        await s.commit()

    monkeypatch.setattr(bw_mod, "is_night_mode_active", lambda c: True)

    bootstraps = [
        # 1. Завершенный бой с наградой -> должен быть заклеймлен ночью!
        {
            "state": "reward",
            "battle": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_night_1"},
            "prisons": [],
        },
        # 2. После клейма слот свободен -> призывать нового ночью НЕЛЬЗЯ!
        {
            "state": "idle",
            "battle": None,
            "prisons": [],
        },
    ]
    claim_mock = AsyncMock(return_value={
        "success": True,
        "rewards": {"result": "victory", "globalReward": {"cigarettes": 100}},
    })
    summon_mock = AsyncMock()
    attack_mock = AsyncMock()
    notifier = SimpleNamespace(notify=AsyncMock())

    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(side_effect=lambda: bootstraps.pop(0) if len(bootstraps) > 1 else bootstraps[0]),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=claim_mock,
        start_boss=summon_mock,
        attack_boss=attack_mock,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=AsyncMock(return_value={"currencies": {"cigarettes": 500, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0, "authority": 0}}))

    worker = BossWorker(account_id=1, boss_api=boss_api, player_api=player_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 1
    assert res.get("night_mode_paused") is True
    assert claim_mock.await_count == 1
    assert summon_mock.await_count == 0
    assert attack_mock.await_count == 0
    assert notifier.notify.await_count == 1
    await engine.dispose()



@pytest.mark.asyncio
async def test_boss_worker_melee_cooldowns_and_hits(boss_setup):
    """
    Тест расчета кулдаунов:
    - 4 рукопашных удара:
      - punchChest: lastTime 9 часов назад (откатился, cooldown 8ч = 28800с) -> ГОТОВ
      - kickBalls: lastTime 1 час назад (на кулдауне) -> НЕ ГОТОВ
      - pokeEyes: lastTime 10 часов назад (откатился) -> ГОТОВ
      - kneeEar: отсутствует в equippedSlots -> НЕ ДОСТУПЕН
    - Воркер должен отправить ровно 2 удара: punchChest и pokeEyes.
    - Никакого платного оружия (poison, gunshot, knife).
    """
    engine, acc_id = boss_setup
    calls = []
    used_weapons = []

    nine_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ten_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "state": "active",
                    "hasReward": False,
                    "unclaimedRewards": [],
                    "session": {
                        "sessionId": "session_123",
                        "currentHp": 50000,
                        "maxHp": 100000,
                    },
                    "weaponStatsEffective": {
                        "punchChestCooldownSec": 28800,
                        "kickBallsCooldownSec": 28800,
                        "pokeEyesCooldownSec": 28800,
                        "kneeEarCooldownSec": 28800,
                    },
                },
            )
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(
                200,
                json={
                    "userId": 9000000000466709,
                    # В экипированных слотах только punchChest, kickBalls, pokeEyes (kneeEar отсутствует!)
                    "equippedSlots": ["punchChest", "kickBalls", "pokeEyes", "poison", "gunshot"],
                    "lastPunchChestTime": nine_hours_ago,
                    "lastKickBallsTime": one_hour_ago,
                    "lastPokeEyesTime": ten_hours_ago,
                    "lastKneeEarTime": None,
                },
            )
        elif request.url.path == "/api/boss/use-weapon":
            import json
            body = json.loads(request.content)
            w = body.get("weapon")
            used_weapons.append(w)
            return httpx.Response(200, json={"success": True, "currentHp": 45000})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["boss_active"] is True
    assert len(res["hits_performed"]) == 2
    assert used_weapons == ["punchChest", "pokeEyes"]
    # Проверяем отсутствие платного оружия
    assert "poison" not in used_weapons
    assert "gunshot" not in used_weapons
    assert "knife" not in used_weapons

    # Проверяем ActionLog
    async with get_session(engine) as session:
        log_stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "boss_melee_hit",
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) == 2
        logged_weapons = [l.details["weapon"] for l in logs]
        assert logged_weapons == ["punchChest", "pokeEyes"]


@pytest.mark.asyncio
async def test_boss_worker_no_active_boss(boss_setup):
    """Тест отсутствия активного босса: при state != 'active' удары не отправляются."""
    engine, acc_id = boss_setup
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "state": "idle",
                    "hasReward": False,
                    "session": None,
                },
            )
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["boss_active"] is False
    assert len(res["hits_performed"]) == 0
    assert ("POST", "/api/boss/use-weapon") not in calls
    assert ("GET", "/api/boss/weapons") not in calls


@pytest.mark.asyncio
async def test_boss_worker_claims_reward(boss_setup):
    """Тест сбора награды: при hasReward == True или наличии unclaimedRewards вызывается claim_reward()."""
    engine, acc_id = boss_setup
    claims = []

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "state": "reward",
                    "hasReward": True,
                    "unclaimedRewards": ["reward_abc_1", "reward_abc_2"],
                    "session": {"currentHp": 0},
                },
            )
        elif request.url.path == "/api/boss/claim":
            import json
            claims.append(json.loads(request.content) if request.content else {})
            return httpx.Response(200, json={"success": True, "rewards": {"soap": 10, "authority": 500}})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 2
    assert claims == [{"claimId": "reward_abc_1"}, {"claimId": "reward_abc_2"}]

    async with get_session(engine) as session:
        log_stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "claim_boss_reward",
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) == 2


@pytest.mark.asyncio
async def test_boss_api_get_all_bosses():
    """Тест get_all_bosses(): опрашивает категории 1, 2, 3 и возвращает дедуплицированный список с режимами и HP."""
    from unittest.mock import AsyncMock
    requested_cats = []

    def mock_handler(request: httpx.Request):
        cat = request.url.params.get("categoryId")
        requested_cats.append(cat)
        if cat == "1":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 1, "name": "Кирпич", "hp": 500, "categoryId": 1, "keyRequirement": 0},
                    {"id": 2, "name": "Сизый", "hp": 1500, "categoryId": 1, "keyRequirement": 3, "keyBoss": "Кирпич"},
                ]
            })
        elif cat == "2":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 9, "name": "Палыч", "hp": 100000, "categoryId": 2, "keyRequirement": 0},
                ]
            })
        elif cat == "3":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 30, "name": "Жестянщики", "hp": 50000000, "categoryId": 3, "keyRequirement": 5},
                ]
            })
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    mock_auth = AsyncMock()
    mock_auth.get_valid_token.return_value = "test_token"
    http_client = GameHttpClient(auth_provider=mock_auth, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    all_bosses = await boss_api.get_all_bosses()

    assert set(requested_cats) == {"1", "2", "3"}
    # Полный каталог игры насчитывает ровно 58 боссов
    assert len(all_bosses) == 58

    brick = next(b for b in all_bosses if b["id"] == 1)
    assert brick["name"] == "Кирпич"
    assert brick["categoryName"] == "Беспредельщики"
    assert brick["baseHp"] == 1000
    assert brick["modes"]["pacansky"]["hp"] == 1000
    assert brick["requiredKeyBossId"] is None
    assert brick["requiredKeysCount"] == 0

    sizy = next(b for b in all_bosses if b["id"] == 2)
    assert sizy["name"] == "Сизый"
    assert sizy["baseHp"] == 10000
    assert sizy["requiredKeyBossId"] == 1
    assert sizy["requiredKeysCount"] == 3
    assert sizy["requiredKeyBossName"] == "Кирпич"

    makhno = next(b for b in all_bosses if b["id"] == 3)
    assert makhno["name"] == "Махно"
    assert makhno["baseHp"] == 50000
    assert makhno["requiredKeyBossId"] == 2
    assert makhno["requiredKeysCount"] == 3
    assert makhno["requiredKeyBossName"] == "Сизый"

    vorkuta = next(b for b in all_bosses if b["id"] == 39)
    assert vorkuta["name"] == "Воркута"
    assert vorkuta["baseHp"] == 400000000

    palych = next(b for b in all_bosses if b["id"] == 9)
    assert palych["name"] == "Палыч"
    assert palych["categoryName"] == "Надзиратели"
    assert palych["baseHp"] == 100000


@pytest.mark.asyncio
async def test_boss_worker_auto_boss_enabled_summon_and_queue(boss_setup):
    """Тест авто-призыва босса из очереди при активном тумблере auto_boss_enabled."""
    engine, acc_id = boss_setup
    summon_calls = []

    # Обновляем конфиг: auto_boss_enabled=True, цель Кирпич в режиме blotnoy
    async with get_session(engine) as session:
        cfg_stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(cfg_stmt)).scalar_one()
        cfg.auto_boss_enabled = True
        cfg.boss_targets = [{"bossId": 1, "mode": "blotnoy", "enabled": True}]
        await session.commit()

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            # До призыва боя нет
            if not summon_calls:
                return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
            # После призыва активный бой
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "sess_1", "bossId": 1, "currentHp": 1500, "maxHp": 1500},
                "weaponStatsEffective": {"punchChestCooldownSec": 28800},
            })
        elif request.url.path == "/api/boss/start-attack":
            import json
            body = json.loads(request.content)
            summon_calls.append(body)
            return httpx.Response(200, json={"success": True, "state": "active"})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": [], "lastPunchChestTime": None})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    assert len(summon_calls) == 1
    assert summon_calls[0]["bossId"] == 1 and summon_calls[0]["mode"] == "blotnoy"
    assert res["boss_active"] is True


@pytest.mark.asyncio
async def test_boss_worker_required_key_boss_mapping(boss_setup):
    """
    Тест строгого маппинга ключей:
    При keys = {"1": 0, "2": 14}:
    - Сизый (id=2, requiredKeyBossId=1, count=3): 0 ключей -> авто-призыв невозможен.
    - Махно (id=3, requiredKeyBossId=2, count=3): 14 ключей -> авто-призыв разрешен.
    """
    engine, acc_id = boss_setup
    summon_calls = []

    async with get_session(engine) as session:
        cfg_stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(cfg_stmt)).scalar_one()
        cfg.auto_boss_enabled = True
        # В очереди сначала Сизый, потом Махно
        cfg.boss_targets = [
            {"bossId": 2, "mode": "pacansky", "enabled": True},
            {"bossId": 3, "mode": "pacansky", "enabled": True},
        ]
        await session.commit()

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            if not summon_calls:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "inactive",
                    "session": None,
                    "playerStats": {
                        "keys": {"1": 0, "2": 14},  # 0 ключей от Кирпича, 14 от Сизого
                        "dailyWins": {},
                    }
                })
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "sess_makhno", "bossId": 3, "currentHp": 50000, "maxHp": 50000},
            })
        elif request.url.path == "/api/boss/start-attack":
            import json
            body = json.loads(request.content)
            summon_calls.append(body)
            return httpx.Response(200, json={"success": True, "state": "active"})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": [], "lastPunchChestTime": None})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": []})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    # Сизый пропущен из-за нехватки ключей Кирпича, призван Махно (было 14 ключей Сизого)
    assert len(summon_calls) == 1
    assert summon_calls[0]["bossId"] == 3
    assert res["boss_active"] is True


def test_boss_catalog_58_order_and_modes():
    """
    Тест каталога 58 боссов:
    - строго 58 боссов;
    - точный порядок sortOrder (0..57);
    - разбивка по категориям: 25 Беспредельщиков, 20 Надзирателей, 13 Рецидивистов;
    - правильный порядок имен;
    - различные реальные HP для режимов pacansky, blotnoy, avtoritetny;
    - наличие таблиц loot (currencies + items).
    """
    from client.api.boss import _load_bosses_catalog

    catalog = _load_bosses_catalog()
    assert len(catalog) == 58, f"Expected 58 bosses, got {len(catalog)}"

    # Проверка непрерывности sortOrder 0..57
    sort_orders = [b.get("sortOrder") for b in catalog]
    assert sort_orders == list(range(58)), "Bosses must be strictly sorted by sortOrder 0..57"

    # Разделение по категориям
    cat1 = [b for b in catalog if b["categoryId"] == 1]
    cat2 = [b for b in catalog if b["categoryId"] == 2]
    cat3 = [b for b in catalog if b["categoryId"] == 3]

    assert len(cat1) == 25, f"Expected 25 Беспредельщиков, got {len(cat1)}"
    assert len(cat2) == 20, f"Expected 20 Надзирателей, got {len(cat2)}"
    assert len(cat3) == 13, f"Expected 13 Рецидивистов, got {len(cat3)}"

    # Проверка порядка в Беспредельщиках
    expected_cat1 = [
        "Кирпич", "Сизый", "Махно", "Лютый", "Гастролёр", "Шайба", "Бурят", "Дядя Миша",
        "Бандяк", "Абу", "Гризли", "Феня", "Север", "Мазай", "Хирург", "Пресс",
        "Немой", "Бидон", "Воркута", "Старшой", "Полтос", "Бугор", "Змей", "Гвоздь", "Тротил"
    ]
    actual_cat1 = [b["name"] for b in cat1]
    assert actual_cat1 == expected_cat1, f"Cat 1 names mismatch:\nExpected: {expected_cat1}\nActual: {actual_cat1}"

    # Проверка Сизого: режимы pacansky (10 000), blotnoy (30 000), avtoritetny (60 000)
    siziy = next(b for b in catalog if b["name"] == "Сизый")
    assert siziy["modes"]["pacansky"]["hp"] == 10000
    assert siziy["modes"]["blotnoy"]["hp"] == 30000
    assert siziy["modes"]["avtoritetny"]["hp"] == 60000

    # Проверка лута Сизого в пацанском режиме
    pac_loot = siziy["modes"]["pacansky"]
    assert "currencies" in pac_loot
    assert "items" in pac_loot
    assert any(c["currency"] == "authority" for c in pac_loot["currencies"])
    assert any(it["name"] == "Комплект \"Биомеханика\"" for it in pac_loot["items"])


@pytest.mark.asyncio
async def test_boss_worker_skips_locked_boss_target(boss_setup):
    """Тест пропуска заблокированных боссов (isLocked == True) воркером BossWorker при автоатаке."""
    engine, acc_id = boss_setup
    start_calls = []

    # Конфиг: включен авто-босс, в очереди заблокированный босс (например Тротил, id 56)
    async with get_session(engine) as session:
        cfg_stmt = select(BotConfig).where(BotConfig.account_id == acc_id)
        cfg = (await session.execute(cfg_stmt)).scalar_one()
        cfg.auto_boss_enabled = True
        cfg.boss_targets = [{"bossId": 56, "mode": "pacansky", "enabled": True}]
        await session.commit()

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
        elif request.url.path == "/api/boss/start-attack":
            start_calls.append(request)
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()

    # Заблокированный босс Тротил должен быть пропущен, атака не вызывается
    assert len(start_calls) == 0
    assert res["boss_active"] is False


@pytest.mark.asyncio
async def test_boss_presets_schedule_and_execution(boss_setup):
    """
    Тест запуска пресетов по расписанию МСК и защиты от повторного запуска в те же сутки.
    """
    from core.models import BossPreset

    engine, acc_id = boss_setup
    today_date = "2026-11-23"
    utc_time_0900_msk = datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc)
    utc_time_0905_msk = datetime(2026, 11, 23, 6, 5, tzinfo=timezone.utc)

    preset_id = None
    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=acc_id,
            name="Утренний фарм",
            schedule_time_msk="09:00",
            daily_enabled=True,
            items=[{"boss_id": 1, "mode": "pacansky", "count": 1}],
            is_running=False,
            current_step_index=0,
            last_run_date_msk=None,
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        preset_id = preset.id

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
        elif request.url.path == "/api/boss/start-attack":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    # 1. Запуск в 09:00 МСК -> пресет должен запуститься
    launched = await worker.check_scheduled_presets(now_utc=utc_time_0900_msk)
    assert launched is not None
    assert launched["preset_id"] == preset_id

    # Проверяем last_run_date_msk в БД
    async with get_session(engine) as session:
        p = await session.get(BossPreset, preset_id)
        assert p.last_run_date_msk == today_date

    # 2. Повторный вызов в 09:05 МСК того же дня -> защита от повтора, не должен запускаться
    repeat = await worker.check_scheduled_presets(now_utc=utc_time_0905_msk)
    assert repeat is None


@pytest.mark.asyncio
async def test_boss_preset_skip_locked_boss_step(boss_setup):
    """
    Тест пропуска заблокированного босса внутри пресета с записью в ActionLog и переходом к следующему шагу.
    """
    from core.models import BossPreset
    from unittest.mock import AsyncMock

    engine, acc_id = boss_setup

    preset_id = None
    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=acc_id,
            name="Цепочка боссов",
            schedule_time_msk="10:00",
            daily_enabled=True,
            items=[
                {"boss_id": 4, "mode": "pacansky", "count": 1},  # Лютый (заблокирован)
                {"boss_id": 1, "mode": "pacansky", "count": 1},  # Кирпич (доступен)
            ],
            is_running=True,
            current_step_index=0,
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        preset_id = preset.id

    def mock_handler(request: httpx.Request):
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "inactive", "session": None})
        elif request.url.path == "/api/boss/start-attack":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    # Мокируем get_all_bosses, чтобы Лютый был заблокирован, а Кирпич открыт
    boss_api.get_all_bosses = AsyncMock(return_value=[
        {"id": 4, "name": "Лютый", "isLocked": True, "unlockReason": "Нужно 2 дневные ходки в Кресты"},
        {"id": 1, "name": "Кирпич", "isLocked": False},
    ])

    worker = BossWorker(
        account_id=acc_id,
        boss_api=boss_api,
        db_engine=engine,
        enable_jitter=False,
    )

    # Запускаем цикл выполнения пресета
    res = await worker.run_cycle()

    # Проверяем, что первый шаг (Лютый) был пропущен, и current_step_index продвинулся
    async with get_session(engine) as session:
        p = await session.get(BossPreset, preset_id)
        assert p.current_step_index >= 1

        # Проверяем запись в ActionLog
        stmt = select(ActionLog).where(
            ActionLog.account_id == acc_id,
            ActionLog.action_type == "boss_preset_step_skip"
        )
        skip_log = (await session.execute(stmt)).scalar_one_or_none()
        assert skip_log is not None
        assert "Лютый" in skip_log.details["boss"]
        assert "Кресты" in skip_log.details["reason"]


@pytest.mark.asyncio
async def test_boss_preset_pause_and_sleep(boss_setup):
    """Тест: планировщик пресетов не запускает пресеты при паузе или неактивности воркера."""
    from core.models import BossPreset
    from unittest.mock import MagicMock

    engine, acc_id = boss_setup
    async with get_session(engine) as session:
        p = BossPreset(
            account_id=acc_id,
            name="Тестовый",
            schedule_time_msk="09:00",
            daily_enabled=True,
            items=[{"boss_id": 1, "mode": "pacansky", "count": 1}],
            is_running=False,
        )
        session.add(p)
        await session.commit()

    boss_api = MagicMock()
    worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine, enable_jitter=False)

    # Ставим паузу
    worker.is_paused = True
    res = await worker.check_scheduled_presets(now_utc=datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc))
    assert res is None


@pytest.mark.asyncio
async def test_boss_worker_conveyor_claim_and_next_summon(boss_setup):
    """
    Конвейер: при сборе награды (state='reward') или убийстве босса ударом
    BossWorker немедленно призывает следующего босса в том же цикле run_cycle().
    """
    from core.models import BossPreset

    engine, acc_id = boss_setup
    summoned_ids = []
    claimed_ids = []

    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=acc_id,
            name="Конвейер",
            schedule_time_msk="09:00",
            daily_enabled=False,
            items=[
                {"boss_id": 1, "mode": "odin", "count": 1},
                {"boss_id": 1, "mode": "pacansky", "count": 1},
                {"boss_id": 1, "mode": "blotnoy", "count": 1},
            ],
            is_running=True,
            current_step_index=0,
        )
        session.add(preset)
        await session.commit()

    # Начинаем со старого state="reward" -> claim_reward -> сразу призыв #1 ->
    # смертельный удар -> claim_reward -> сразу призыв #2 в том же цикле!
    phase = "reward1"

    def mock_handler(request: httpx.Request):
        nonlocal phase
        import json as _json
        if request.url.path == "/api/boss/bootstrap":
            if phase == "reward1":
                return httpx.Response(200, json={
                    "success": True,
                    "state": "reward",
                    "hasReward": True,
                    "claimId": "claim_prev",
                    "currentBattle": {"sessionId": "s0", "bossId": 1, "currentHp": 0, "maxHp": 1000},
                })
            elif phase == "idle_for_1":
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None})
            elif phase == "battle_1":
                return httpx.Response(200, json={
                    "success": True,
                    "state": "active",
                    "currentBattle": {"sessionId": "s1", "bossId": 1, "currentHp": 500, "maxHp": 1000},
                })
            elif phase == "idle_for_2":
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None})
            else:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "active",
                    "currentBattle": {"sessionId": "s2", "bossId": 1, "mode": "blotnoy", "currentHp": 3000, "maxHp": 3000},
                })
        elif request.url.path == "/api/boss/claim":
            body = _json.loads(request.content) if request.content else {}
            claimed_ids.append(body.get("claimId"))
            if phase == "reward1":
                phase = "idle_for_1"
            return httpx.Response(200, json={"success": True, "rewards": {"cigarettes": 50}})
        elif request.url.path == "/api/boss/start-attack":
            body = _json.loads(request.content)
            summoned_ids.append((body.get("bossId"), body.get("mode")))
            if phase == "idle_for_1":
                phase = "battle_1"
            elif phase == "idle_for_2":
                phase = "battle_2"
            return httpx.Response(200, json={"success": True, "state": "active"})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": ["punchChest"], "lastPunchChestTime": None})
        elif request.url.path == "/api/boss/use-weapon":
            if phase == "battle_1":
                phase = "idle_for_2"
                return httpx.Response(200, json={"success": True, "currentHp": 0, "bossDefeated": True, "claimId": "claim_b1"})
            return httpx.Response(200, json={"success": True, "currentHp": 2500})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": [{"id": 1, "name": "Кирпич", "isLocked": False}]})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)

    worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 2
    assert claimed_ids == ["claim_prev", "claim_b1"]
    assert summoned_ids == [(1, "pacansky"), (1, "blotnoy")]
    assert res["boss_active"] is True


@pytest.mark.asyncio
async def test_boss_worker_manual_force_ignores_pause(boss_setup):
    """Ручной запуск run_cycle(force_manual=True) работает даже при is_paused=True в BotConfig."""
    engine, acc_id = boss_setup
    summoned = []

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.is_paused = True
        cfg.auto_boss_enabled = True
        cfg.boss_targets = [1]  # Проверяем также нормализацию raw int ID
        await session.commit()

    def mock_handler(request: httpx.Request):
        import json as _json
        if request.url.path == "/api/boss/bootstrap":
            if not summoned:
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None})
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "currentBattle": {"sessionId": "s_man", "bossId": 1, "currentHp": 1000, "maxHp": 1000},
            })
        elif request.url.path == "/api/boss/start-attack":
            summoned.append(_json.loads(request.content))
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": []})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": [{"id": 1, "name": "Кирпич"}]})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    worker = BossWorker(account_id=acc_id, boss_api=BossAPI(http_client=http_client), db_engine=engine, enable_jitter=False)

    # Авто-тик на паузе пропускает
    res_auto = await worker.run_cycle(force_manual=False)
    assert res_auto["status"] == "skipped"
    assert len(summoned) == 0

    # Ручной запуск с force_manual=True призывает босса даже на паузе
    res_manual = await worker.run_cycle(force_manual=True)
    assert res_manual["boss_active"] is True
    assert len(summoned) == 1 and summoned[0]["bossId"] == 1


@pytest.mark.asyncio
async def test_boss_worker_prisons_data_unlocks_boss(boss_setup):
    """Передача prison_api разблокирует боссов с requiredPrisonId (не маркирует их ложно isLocked=True)."""
    from client.api.prison import PrisonAPI

    engine, acc_id = boss_setup
    summoned = []

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.auto_boss_enabled = True
        # Сизый (id=2): требует прохождения Бутырки (id=1) и/или ключей
        # Лютый (id=4): требует ходки в Крестах (prison_id=2)
        cfg.boss_targets = [{"bossId": 4, "mode": "pacansky", "enabled": True}]
        await session.commit()

    def mock_handler(request: httpx.Request):
        import json as _json
        if request.url.path == "/api/prisons/all":
            return httpx.Response(200, json={
                "success": True,
                "prisons": [
                    {"id": 1, "name": "Бутырка", "dayRuns": 20, "nightRuns": 20, "isUnlocked": True},
                    {"id": 4, "name": "Кресты", "dayRuns": 5, "nightRuns": 0, "isUnlocked": True},
                ],
            })
        elif request.url.path == "/api/boss/bootstrap":
            if not summoned:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "idle",
                    "session": None,
                    "playerStats": {"keys": {"1": 10, "2": 10, "3": 10}, "wins": {"1": 5, "2": 5, "3": 5}, "dailyWins": {}},
                })
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "s4", "bossId": 4, "currentHp": 100000, "maxHp": 100000},
            })
        elif request.url.path == "/api/boss/start-attack":
            summoned.append(_json.loads(request.content))
            return httpx.Response(200, json={"success": True})
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={"equippedSlots": []})
        elif request.url.path.startswith("/api/boss/list"):
            return httpx.Response(200, json={"bosses": []})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    worker = BossWorker(
        account_id=acc_id,
        boss_api=BossAPI(http_client=http_client),
        prison_api=PrisonAPI(http_client=http_client),
        db_engine=engine,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(summoned) == 1
    assert summoned[0]["bossId"] == 4
    assert res["boss_active"] is True


@pytest.mark.asyncio
async def test_boss_worker_auto_melee_and_preset_defeat_reset(boss_setup):
    """Проверка авто-рукопашной (boss_auto_melee) и сброса пресета на поражении + очистки в state_hub."""
    from core.models import BossPreset, Notification
    from core.state_hub import LiveStateHub

    engine, acc_id = boss_setup
    hits = []
    hub = LiveStateHub()

    async with get_session(engine) as session:
        cfg = (await session.execute(select(BotConfig).where(BotConfig.account_id == acc_id))).scalar_one()
        cfg.boss_auto_melee = True
        cfg.auto_boss_hits = False
        preset = BossPreset(
            account_id=acc_id,
            name="Defeat Test",
            items=[{"bossId": 1, "bossName": "Кирпич", "mode": "pacansky", "count": 2}],
            is_running=True,
            current_step_index=0,
            last_status="В процессе",
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        preset_id = preset.id

    def mock_handler(request: httpx.Request):
        import json as _json
        if request.url.path == "/api/boss/bootstrap":
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {"sessionId": "s_melee", "bossId": 1, "bossName": "Кирпич", "mode": "pacansky", "currentHp": 5000, "maxHp": 10000},
                "weaponStatsEffective": {"punchChestCooldownSec": 28800},
            })
        elif request.url.path == "/api/boss/weapons":
            return httpx.Response(200, json={
                "equippedSlots": ["punchChest", "kickBalls"],
                "lastPunchChestTime": None,
                "lastKickBallsTime": "2020-01-01T00:00:00Z",
            })
        elif request.url.path == "/api/boss/use-weapon":
            body = _json.loads(request.content)
            hits.append(body.get("weapon"))
            return httpx.Response(200, json={"success": True, "currentHp": 4000})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    worker = BossWorker(
        account_id=acc_id,
        boss_api=BossAPI(http_client=http_client),
        db_engine=engine,
        enable_jitter=False,
        state_hub=hub,
    )

    hub.update_slice(acc_id, "boss", {"meleeTimestamps": {}, "session": {"currentHp": 5000}})
    melee_res = await worker.trigger_auto_melee()
    assert len(hits) == 2
    assert set(hits) == {"punchChest", "kickBalls"}
    assert melee_res["boss_hp_remaining"] == 4000

    # Проверяем сброс пресета и сохранение уведомления при поражении
    async with get_session(engine) as session:
        p_loaded = await session.get(BossPreset, preset_id)

    await worker.on_boss_fight_finished(
        {
            "outcome": "defeat",
            "bossName": "Кирпич",
            "mode": "pacansky",
            "remainingHp": 4000,
            "maxHp": 10000,
            "sessionId": "s_melee",
        },
        active_preset=p_loaded,
        preset_steps=[{"bossId": 1, "bossName": "Кирпич", "mode": "pacansky"}] * 2,
    )

    async with get_session(engine) as session:
        p_after = await session.get(BossPreset, preset_id)
        assert p_after.is_running is False
        assert "поражение" in (p_after.last_status or "").lower()
        defeat_notif = (
            await session.execute(select(Notification).where(Notification.title.like("%Поражение%")))
        ).scalar_one_or_none()
        assert defeat_notif is not None
        assert defeat_notif.meta_json["outcome"] == "defeat"
        assert defeat_notif.meta_json["remaining_hp"] == 4000
        assert defeat_notif.meta_json["max_hp"] == 10000
    presets_slice = hub.get_slice(acc_id, "presets")
    assert presets_slice is not None
    assert presets_slice.data["activeRun"] is None


@pytest.mark.asyncio
async def test_boss_claim_defeat_does_not_emit_false_victory(tmp_path):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    from core.database import get_engine, get_session, init_db
    from core.models import Account, Notification
    from core.state_hub import state_hub
    from sqlalchemy import select
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_defeat_claim.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    state_hub.clear(1)
    q = state_hub.subscribe(1)
    notifier = SimpleNamespace(notify=AsyncMock())
    boss_api = SimpleNamespace(
        claim_reward=AsyncMock(return_value={"result": "defeat", "isWin": False, "message": "Время боя вышло"}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    worker = BossWorker(account_id=1, boss_api=boss_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    bootstrap = {
        "state": "reward",
        "session": {"bossId": 39, "title": "Воркута", "mode": "pacansky", "currentHp": 120000, "maxHp": 400000000, "sessionId": "sess_vorkuta_loss"},
        "unclaimedRewards": [{"claimId": "cid_loss_1", "bossId": 39}],
    }
    results = {"rewards_claimed": 0, "hits_performed": [], "summoned_bosses": [], "boss_hp_remaining": 120000, "victories": [], "defeats": [], "errors": []}
    claimed = set()
    await worker._claim_pending_rewards(bootstrap, results, None, [], claimed)

    assert results["victories"] == []
    assert results["rewards_claimed"] == 0
    assert len(results["defeats"]) == 1
    assert results["defeats"][0]["boss_name"] == "Воркута"

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert "Босс повержен" not in notifs[0].title
        assert "Победа над боссом" not in notifs[0].title

    evts = []
    while not q.empty():
        evts.append(q.get_nowait())
    sync_evts = [e for e in evts if e.get("type") == "domain_sync"]
    assert any(set(e.get("domains", [])) >= {"boss", "profile", "talents", "notifications"} for e in sync_evts)
    state_hub.unsubscribe(1, q)
    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_vorkuta_0859_expired_defeat_not_classified_as_victory(tmp_path):
    """
    Воспроизведение инцидента 08:59 (Воркута Пацанский, 08:01:01):
    claim возвращает {"success": True, "status": "claimed", "rewards": {"result": "defeat", ...}},
    таймер истёк, last_hp > 0, дельта профиля 0 -> строго defeat, без ложной победы и без 'получены'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_vorkuta_defeat.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    vorkuta_claim = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b7d5b677e19377f0da45d4f52a",
        "rewards": {
            "mode": "pacansky",
            "time": "2026-11-26T05:58:42.0221039Z",
            "title": "Воркута",
            "bossId": 39,
            "result": "defeat",
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
        },
    }
    started_iso = (datetime.now(timezone.utc) - timedelta(hours=8, minutes=1, seconds=1)).isoformat()
    ends_iso = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 39,
            "title": "Воркута",
            "mode": "pacansky",
            "currentHp": 149444357,
            "maxHp": 400000000,
            "personalDamage": 67,
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
            "startedAt": started_iso,
            "endsAt": ends_iso,
        },
        "unclaimedRewards": [{"claimId": "01a214b7d5b677e19377f0da45d4f52a", "bossId": 39}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value=vorkuta_claim),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(
        init_player=AsyncMock(return_value={"currencies": {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 12}})
    )
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res.get("victories") or []) == 0
    assert len(res.get("defeats") or []) == 1
    df = res["defeats"][0]
    assert df["boss_name"] == "Воркута"
    assert df["remaining_hp"] == 149444357
    assert df["max_hp"] == 400000000
    assert df["personal_damage"] == 67

    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Поражение от босса: Воркута (Пацанский)" in tg_msg
    assert "Победа над боссом" not in tg_msg
    assert "получены" not in tg_msg

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert notifs[0].meta_json["outcome"] == "defeat"

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_victory_empty_claim_uses_fresh_profile_currencies_delta(tmp_path):
    """
    Победа с явным victory=True без массива rewards в ответе claim:
    свежий запрос player_api.init_player() возвращает currencies -> дельта дополняет награды в TG и Web.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_delta_currencies.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    notifier = SimpleNamespace(notify=AsyncMock())
    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"currencies": {"cigarettes": 1000, "sugar": 100, "authority": 500}, "authority": 500}
        return {"currencies": {"cigarettes": 1150, "sugar": 130, "authority": 1000}, "authority": 1000}

    bootstrap = {
        "state": "reward",
        "session": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_delta_cur"},
        "unclaimedRewards": [{"claimId": "cid_delta_cur", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value={"success": True, "victory": True}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res["victories"]) == 1
    cur_map = {r["currency"]: r["amount"] for r in res["victories"][0]["rewards"]}
    assert cur_map["cigarettes"] == 150
    assert cur_map["sugar"] == 30
    assert cur_map["authority"] == 500

    tg_msg = notifier.notify.call_args[0][0]
    assert "Папиросы +150" in tg_msg
    assert "Сахар +30" in tg_msg
    assert "Авторитет +500" in tg_msg
    assert "получены" not in tg_msg

    await engine.dispose()


def test_night_mode_windows_msk_and_worker_isolation():
    """Проверка окон Ночного режима по МСК и того, что is_worker_active не блокирует другие воркеры."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from core.database import is_night_mode_active, is_worker_active

    # 23:00-08:00 МСК: 02:30 МСК = 23:30 UTC предыдущего дня
    cfg_cross = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=23, sleep_end_hour=8)
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)) is False  # 12:00 МСК
    assert is_worker_active(cfg_cross) is True

    # 00:00-08:00 МСК: 03:00 МСК = 00:00 UTC
    cfg_same = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=0, sleep_end_hour=8)
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)) is False  # 08:00 МСК
    assert is_worker_active(cfg_same) is True

    # start == end -> не блокирует 24/7
    cfg_eq = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=5, sleep_end_hour=5)
    assert is_night_mode_active(cfg_eq, now_utc=datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_boss_worker_night_mode_allows_claim_blocks_summon_and_attack(tmp_path, monkeypatch):
    """В Ночной режим BossWorker забирает награды (claim), но не призывает и не атакует боссов."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_or_create_config, get_session
    from core.models import BotConfig
    import workers.boss_worker as bw_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'night_boss.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as s:
        db_cfg = await s.get(BotConfig, cfg.id)
        db_cfg.sleep_mode_enabled = True
        db_cfg.sleep_start_hour = 0
        db_cfg.sleep_end_hour = 8
        db_cfg.auto_boss_enabled = True
        db_cfg.auto_boss_summon = True
        db_cfg.auto_boss_hits = True
        db_cfg.boss_auto_melee = True
        db_cfg.boss_targets = [1]
        await s.commit()

    monkeypatch.setattr(bw_mod, "is_night_mode_active", lambda c: True)

    bootstraps = [
        # 1. Завершенный бой с наградой -> должен быть заклеймлен ночью!
        {
            "state": "reward",
            "battle": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_night_1"},
            "prisons": [],
        },
        # 2. После клейма слот свободен -> призывать нового ночью НЕЛЬЗЯ!
        {
            "state": "idle",
            "battle": None,
            "prisons": [],
        },
    ]
    claim_mock = AsyncMock(return_value={
        "success": True,
        "rewards": {"result": "victory", "globalReward": {"cigarettes": 100}},
    })
    summon_mock = AsyncMock()
    attack_mock = AsyncMock()
    notifier = SimpleNamespace(notify=AsyncMock())

    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(side_effect=lambda: bootstraps.pop(0) if len(bootstraps) > 1 else bootstraps[0]),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=claim_mock,
        start_boss=summon_mock,
        attack_boss=attack_mock,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=AsyncMock(return_value={"currencies": {"cigarettes": 500, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0, "authority": 0}}))

    worker = BossWorker(account_id=1, boss_api=boss_api, player_api=player_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 1
    assert res.get("night_mode_paused") is True
    assert claim_mock.await_count == 1
    assert summon_mock.await_count == 0
    assert attack_mock.await_count == 0
    assert notifier.notify.await_count == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_finalizing_retry_profile_delta_duration_and_tg_format(tmp_path):
    """
    Быстрая победа между опросами + 'Reward is being finalized' ->
    система НЕ шлет поражение, ретраит claim, дополняет награды из дельты профиля,
    считает длительность ЧЧ:ММ:СС и шлет строгий TG-формат победы без промежуточных атак/призывов.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_finalizing.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    claim_calls = 0

    async def _claim(cid=None):
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 1:
            return {"success": False, "status": "not_ready", "message": "Reward is being finalized", "retryAfterMs": 500}
        return {
            "success": True,
            "rewards": [{"type": "cigarettes", "amount": 200}],
            "tattoo": {"id": 12, "name": "Перстень", "set": "Мафия"},
        }

    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"player": {"resources": {"cigarettes": 1000, "authority": 500, "sugar": 10}}}
        return {"player": {"resources": {"cigarettes": 1200, "authority": 550, "sugar": 25}}}

    started_iso = (datetime.now(timezone.utc) - timedelta(seconds=95)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 1,
            "title": "Кирпич",
            "mode": "pacansky",
            "currentHp": 891,
            "maxHp": 1000,
            "sessionId": "sess_kirpich_fast",
            "startedAt": started_iso,
        },
        "unclaimedRewards": [{"claimId": "cid_fast_1", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=_claim,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert claim_calls == 2
    assert len(res.get("defeats") or []) == 0
    assert len(res["victories"]) == 1
    vic = res["victories"][0]
    assert vic["boss_name"] == "Кирпич"
    assert vic["duration_sec"] >= 90
    assert ":" in vic["duration_formatted"]

    # Проверяем, что дельта профиля добавила authority (+50) и sugar (+15) без дублирования cigarettes (+200)
    cur_map = {r["currency"]: r["amount"] for r in vic["rewards"]}
    assert cur_map["cigarettes"] == 200
    assert cur_map["authority"] == 50
    assert cur_map["sugar"] == 15

    # Проверяем строгий формат TG-уведомления
    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Победа над боссом: Кирпич (Пацанский)" in tg_msg
    assert "🔥 Награды:" in tg_msg
    assert "⏱️ Бой продлился:" in tg_msg
    assert "Битва с боссом:" not in tg_msg
    assert "Призвано боссов:" not in tg_msg

    # Проверяем сохранение в БД для Web
    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert "Победа над боссом: Кирпич (Пацанский)" in notifs[0].title
        assert notifs[0].meta_json.get("duration_formatted")
        assert len(notifs[0].meta_json.get("rewards") or []) >= 3

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_vorkuta_0859_expired_defeat_not_classified_as_victory(tmp_path):
    """
    Воспроизведение инцидента 08:59 (Воркута Пацанский, 08:01:01):
    claim возвращает {"success": True, "status": "claimed", "rewards": {"result": "defeat", ...}},
    таймер истёк, last_hp > 0, дельта профиля 0 -> строго defeat, без ложной победы и без 'получены'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_vorkuta_defeat.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    vorkuta_claim = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b7d5b677e19377f0da45d4f52a",
        "rewards": {
            "mode": "pacansky",
            "time": "2026-11-26T05:58:42.0221039Z",
            "title": "Воркута",
            "bossId": 39,
            "result": "defeat",
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
        },
    }
    started_iso = (datetime.now(timezone.utc) - timedelta(hours=8, minutes=1, seconds=1)).isoformat()
    ends_iso = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 39,
            "title": "Воркута",
            "mode": "pacansky",
            "currentHp": 149444357,
            "maxHp": 400000000,
            "personalDamage": 67,
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
            "startedAt": started_iso,
            "endsAt": ends_iso,
        },
        "unclaimedRewards": [{"claimId": "01a214b7d5b677e19377f0da45d4f52a", "bossId": 39}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value=vorkuta_claim),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(
        init_player=AsyncMock(return_value={"currencies": {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 12}})
    )
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res.get("victories") or []) == 0
    assert len(res.get("defeats") or []) == 1
    df = res["defeats"][0]
    assert df["boss_name"] == "Воркута"
    assert df["remaining_hp"] == 149444357
    assert df["max_hp"] == 400000000
    assert df["personal_damage"] == 67

    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Поражение от босса: Воркута (Пацанский)" in tg_msg
    assert "Победа над боссом" not in tg_msg
    assert "получены" not in tg_msg

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert notifs[0].meta_json["outcome"] == "defeat"

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_victory_empty_claim_uses_fresh_profile_currencies_delta(tmp_path):
    """
    Победа с явным victory=True без массива rewards в ответе claim:
    свежий запрос player_api.init_player() возвращает currencies -> дельта дополняет награды в TG и Web.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_delta_currencies.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    notifier = SimpleNamespace(notify=AsyncMock())
    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"currencies": {"cigarettes": 1000, "sugar": 100, "authority": 500}, "authority": 500}
        return {"currencies": {"cigarettes": 1150, "sugar": 130, "authority": 1000}, "authority": 1000}

    bootstrap = {
        "state": "reward",
        "session": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_delta_cur"},
        "unclaimedRewards": [{"claimId": "cid_delta_cur", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value={"success": True, "victory": True}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res["victories"]) == 1
    cur_map = {r["currency"]: r["amount"] for r in res["victories"][0]["rewards"]}
    assert cur_map["cigarettes"] == 150
    assert cur_map["sugar"] == 30
    assert cur_map["authority"] == 500

    tg_msg = notifier.notify.call_args[0][0]
    assert "Папиросы +150" in tg_msg
    assert "Сахар +30" in tg_msg
    assert "Авторитет +500" in tg_msg
    assert "получены" not in tg_msg

    await engine.dispose()


def test_night_mode_windows_msk_and_worker_isolation():
    """Проверка окон Ночного режима по МСК и того, что is_worker_active не блокирует другие воркеры."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from core.database import is_night_mode_active, is_worker_active

    # 23:00-08:00 МСК: 02:30 МСК = 23:30 UTC предыдущего дня
    cfg_cross = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=23, sleep_end_hour=8)
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)) is False  # 12:00 МСК
    assert is_worker_active(cfg_cross) is True

    # 00:00-08:00 МСК: 03:00 МСК = 00:00 UTC
    cfg_same = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=0, sleep_end_hour=8)
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)) is False  # 08:00 МСК
    assert is_worker_active(cfg_same) is True

    # start == end -> не блокирует 24/7
    cfg_eq = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=5, sleep_end_hour=5)
    assert is_night_mode_active(cfg_eq, now_utc=datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_boss_worker_night_mode_allows_claim_blocks_summon_and_attack(tmp_path, monkeypatch):
    """В Ночной режим BossWorker забирает награды (claim), но не призывает и не атакует боссов."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_or_create_config, get_session
    from core.models import BotConfig
    import workers.boss_worker as bw_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'night_boss.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as s:
        db_cfg = await s.get(BotConfig, cfg.id)
        db_cfg.sleep_mode_enabled = True
        db_cfg.sleep_start_hour = 0
        db_cfg.sleep_end_hour = 8
        db_cfg.auto_boss_enabled = True
        db_cfg.auto_boss_summon = True
        db_cfg.auto_boss_hits = True
        db_cfg.boss_auto_melee = True
        db_cfg.boss_targets = [1]
        await s.commit()

    monkeypatch.setattr(bw_mod, "is_night_mode_active", lambda c: True)

    bootstraps = [
        # 1. Завершенный бой с наградой -> должен быть заклеймлен ночью!
        {
            "state": "reward",
            "battle": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_night_1"},
            "prisons": [],
        },
        # 2. После клейма слот свободен -> призывать нового ночью НЕЛЬЗЯ!
        {
            "state": "idle",
            "battle": None,
            "prisons": [],
        },
    ]
    claim_mock = AsyncMock(return_value={
        "success": True,
        "rewards": {"result": "victory", "globalReward": {"cigarettes": 100}},
    })
    summon_mock = AsyncMock()
    attack_mock = AsyncMock()
    notifier = SimpleNamespace(notify=AsyncMock())

    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(side_effect=lambda: bootstraps.pop(0) if len(bootstraps) > 1 else bootstraps[0]),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=claim_mock,
        start_boss=summon_mock,
        attack_boss=attack_mock,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=AsyncMock(return_value={"currencies": {"cigarettes": 500, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0, "authority": 0}}))

    worker = BossWorker(account_id=1, boss_api=boss_api, player_api=player_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 1
    assert res.get("night_mode_paused") is True
    assert claim_mock.await_count == 1
    assert summon_mock.await_count == 0
    assert attack_mock.await_count == 0
    assert notifier.notify.await_count == 1
    await engine.dispose()



@pytest.mark.asyncio
async def test_boss_defeat_hp_cascade_all_cases(tmp_path):
    """
    Проверка каскада определения оставшегося HP при поражении от босса:
    1. Сервер вернул нули после таймаута, но есть живой снимок (18 500 / 50 000 -> 37%).
    2. Сервер вернул totalDamage без hp/maxHp -> max_hp из каталога, remaining_hp = max_hp - total_damage.
    3. Рестарт воркера -> живой снимок восстановлен из SQLite.
    4. Малый остаток HP (5 / 100 000) -> <0.1%, не 0%.
    5. Данных нет вообще -> hp_known=False, remaining_hp=None, 'нет данных'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from core.drop_parser import DropParser
    from workers.boss_worker import BossWorker, resolve_defeat_boss_hp

    db_path = tmp_path / "boss_defeat_cascade.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    # Кейс 1 + Кейс 3 (перезапуск воркера): сохраняем снимок первым инстансом, читаем вторым
    notifier = SimpleNamespace(notify=AsyncMock())
    boss_api = SimpleNamespace(
        claim_reward=AsyncMock(return_value={"result": "defeat", "isWin": False, "message": "Время боя вышло"}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    worker1 = BossWorker(account_id=1, boss_api=boss_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    await worker1._save_live_battle_snapshot(
        {"bossId": 3, "title": "Махно", "mode": "pacansky", "currentHp": 18500, "maxHp": 50000, "sessionId": "sess_makhno_1"},
        boss_name="Махно",
    )
    # Имитация перезапуска: новый BossWorker с пустой памятью
    worker2 = BossWorker(account_id=1, boss_api=boss_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    bootstrap_zeroed = {
        "state": "reward",
        "session": {"bossId": 3, "title": "Махно", "mode": "pacansky", "currentHp": 0, "maxHp": 0, "sessionId": "sess_makhno_1"},
        "unclaimedRewards": [{"claimId": "cid_makhno_1", "bossId": 3}],
    }
    results = {"rewards_claimed": 0, "hits_performed": [], "summoned_bosses": [], "boss_hp_remaining": None, "victories": [], "defeats": [], "errors": []}
    await worker2._claim_pending_rewards(bootstrap_zeroed, results, None, [], set())

    assert len(results["defeats"]) == 1
    df1 = results["defeats"][0]
    assert df1["remaining_hp"] == 18500
    assert df1["max_hp"] == 50000
    assert df1["hp_percent"] == 37.0
    assert df1["hp_known"] is True

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        meta = notifs[0].meta_json
        assert meta["remaining_hp"] == 18500
        assert meta["max_hp"] == 50000
        assert meta["hp_percent"] == 37.0
        assert meta["hp_known"] is True

    # Кейс 2: сервер вернул totalDamage без hp/maxHp -> max_hp из каталога (Воркута pacansky = 400_000_000)
    res2 = resolve_defeat_boss_hp(
        server_payload={"totalDamage": 125000000},
        battle=None,
        snapshot=None,
        boss_id=39,
        boss_name="Воркута",
        mode="pacansky",
    )
    assert res2["hp_known"] is True
    assert res2["max_hp"] == 400000000
    assert res2["remaining_hp"] == 275000000

    # Кейс 4: малый остаток HP (5 / 100 000) -> <0.1%, не 0%
    assert DropParser.format_hp_percent(5, 100000) == "<0.1%"
    assert DropParser.format_space_num(18500) == "18 500"

    # Кейс 5: данных нет вообще -> hp_known=False, remaining_hp=None
    res5 = resolve_defeat_boss_hp(server_payload={}, battle={"currentHp": 0, "maxHp": 0}, snapshot=None, boss_id=99999, boss_name="Неизвестный", mode="pacansky")
    assert res5["hp_known"] is False
    assert res5["remaining_hp"] is None
    parsed5 = DropParser.parse_boss_defeat(boss_name="Неизвестный", mode="pacansky", remaining_hp=res5["remaining_hp"], max_hp=res5["max_hp"], hp_known=res5["hp_known"])
    assert parsed5["meta_json"]["hp_known"] is False
    assert parsed5["meta_json"]["remaining_hp"] is None
    assert parsed5["meta_json"]["max_hp"] is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_vorkuta_0859_expired_defeat_not_classified_as_victory(tmp_path):
    """
    Воспроизведение инцидента 08:59 (Воркута Пацанский, 08:01:01):
    claim возвращает {"success": True, "status": "claimed", "rewards": {"result": "defeat", ...}},
    таймер истёк, last_hp > 0, дельта профиля 0 -> строго defeat, без ложной победы и без 'получены'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_vorkuta_defeat.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    vorkuta_claim = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b7d5b677e19377f0da45d4f52a",
        "rewards": {
            "mode": "pacansky",
            "time": "2026-11-26T05:58:42.0221039Z",
            "title": "Воркута",
            "bossId": 39,
            "result": "defeat",
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
        },
    }
    started_iso = (datetime.now(timezone.utc) - timedelta(hours=8, minutes=1, seconds=1)).isoformat()
    ends_iso = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 39,
            "title": "Воркута",
            "mode": "pacansky",
            "currentHp": 149444357,
            "maxHp": 400000000,
            "personalDamage": 67,
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
            "startedAt": started_iso,
            "endsAt": ends_iso,
        },
        "unclaimedRewards": [{"claimId": "01a214b7d5b677e19377f0da45d4f52a", "bossId": 39}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value=vorkuta_claim),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(
        init_player=AsyncMock(return_value={"currencies": {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 12}})
    )
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res.get("victories") or []) == 0
    assert len(res.get("defeats") or []) == 1
    df = res["defeats"][0]
    assert df["boss_name"] == "Воркута"
    assert df["remaining_hp"] == 149444357
    assert df["max_hp"] == 400000000
    assert df["personal_damage"] == 67

    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Поражение от босса: Воркута (Пацанский)" in tg_msg
    assert "Победа над боссом" not in tg_msg
    assert "получены" not in tg_msg

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert notifs[0].meta_json["outcome"] == "defeat"

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_victory_empty_claim_uses_fresh_profile_currencies_delta(tmp_path):
    """
    Победа с явным victory=True без массива rewards в ответе claim:
    свежий запрос player_api.init_player() возвращает currencies -> дельта дополняет награды в TG и Web.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_delta_currencies.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    notifier = SimpleNamespace(notify=AsyncMock())
    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"currencies": {"cigarettes": 1000, "sugar": 100, "authority": 500}, "authority": 500}
        return {"currencies": {"cigarettes": 1150, "sugar": 130, "authority": 1000}, "authority": 1000}

    bootstrap = {
        "state": "reward",
        "session": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_delta_cur"},
        "unclaimedRewards": [{"claimId": "cid_delta_cur", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value={"success": True, "victory": True}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res["victories"]) == 1
    cur_map = {r["currency"]: r["amount"] for r in res["victories"][0]["rewards"]}
    assert cur_map["cigarettes"] == 150
    assert cur_map["sugar"] == 30
    assert cur_map["authority"] == 500

    tg_msg = notifier.notify.call_args[0][0]
    assert "Папиросы +150" in tg_msg
    assert "Сахар +30" in tg_msg
    assert "Авторитет +500" in tg_msg
    assert "получены" not in tg_msg

    await engine.dispose()


def test_night_mode_windows_msk_and_worker_isolation():
    """Проверка окон Ночного режима по МСК и того, что is_worker_active не блокирует другие воркеры."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from core.database import is_night_mode_active, is_worker_active

    # 23:00-08:00 МСК: 02:30 МСК = 23:30 UTC предыдущего дня
    cfg_cross = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=23, sleep_end_hour=8)
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)) is False  # 12:00 МСК
    assert is_worker_active(cfg_cross) is True

    # 00:00-08:00 МСК: 03:00 МСК = 00:00 UTC
    cfg_same = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=0, sleep_end_hour=8)
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)) is False  # 08:00 МСК
    assert is_worker_active(cfg_same) is True

    # start == end -> не блокирует 24/7
    cfg_eq = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=5, sleep_end_hour=5)
    assert is_night_mode_active(cfg_eq, now_utc=datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_boss_worker_night_mode_allows_claim_blocks_summon_and_attack(tmp_path, monkeypatch):
    """В Ночной режим BossWorker забирает награды (claim), но не призывает и не атакует боссов."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_or_create_config, get_session
    from core.models import BotConfig
    import workers.boss_worker as bw_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'night_boss.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as s:
        db_cfg = await s.get(BotConfig, cfg.id)
        db_cfg.sleep_mode_enabled = True
        db_cfg.sleep_start_hour = 0
        db_cfg.sleep_end_hour = 8
        db_cfg.auto_boss_enabled = True
        db_cfg.auto_boss_summon = True
        db_cfg.auto_boss_hits = True
        db_cfg.boss_auto_melee = True
        db_cfg.boss_targets = [1]
        await s.commit()

    monkeypatch.setattr(bw_mod, "is_night_mode_active", lambda c: True)

    bootstraps = [
        # 1. Завершенный бой с наградой -> должен быть заклеймлен ночью!
        {
            "state": "reward",
            "battle": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_night_1"},
            "prisons": [],
        },
        # 2. После клейма слот свободен -> призывать нового ночью НЕЛЬЗЯ!
        {
            "state": "idle",
            "battle": None,
            "prisons": [],
        },
    ]
    claim_mock = AsyncMock(return_value={
        "success": True,
        "rewards": {"result": "victory", "globalReward": {"cigarettes": 100}},
    })
    summon_mock = AsyncMock()
    attack_mock = AsyncMock()
    notifier = SimpleNamespace(notify=AsyncMock())

    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(side_effect=lambda: bootstraps.pop(0) if len(bootstraps) > 1 else bootstraps[0]),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=claim_mock,
        start_boss=summon_mock,
        attack_boss=attack_mock,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=AsyncMock(return_value={"currencies": {"cigarettes": 500, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0, "authority": 0}}))

    worker = BossWorker(account_id=1, boss_api=boss_api, player_api=player_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 1
    assert res.get("night_mode_paused") is True
    assert claim_mock.await_count == 1
    assert summon_mock.await_count == 0
    assert attack_mock.await_count == 0
    assert notifier.notify.await_count == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_finalizing_retry_profile_delta_duration_and_tg_format(tmp_path):
    """
    Быстрая победа между опросами + 'Reward is being finalized' ->
    система НЕ шлет поражение, ретраит claim, дополняет награды из дельты профиля,
    считает длительность ЧЧ:ММ:СС и шлет строгий TG-формат победы без промежуточных атак/призывов.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_finalizing.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    claim_calls = 0

    async def _claim(cid=None):
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 1:
            return {"success": False, "status": "not_ready", "message": "Reward is being finalized", "retryAfterMs": 500}
        return {
            "success": True,
            "rewards": [{"type": "cigarettes", "amount": 200}],
            "tattoo": {"id": 12, "name": "Перстень", "set": "Мафия"},
        }

    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"player": {"resources": {"cigarettes": 1000, "authority": 500, "sugar": 10}}}
        return {"player": {"resources": {"cigarettes": 1200, "authority": 550, "sugar": 25}}}

    started_iso = (datetime.now(timezone.utc) - timedelta(seconds=95)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 1,
            "title": "Кирпич",
            "mode": "pacansky",
            "currentHp": 891,
            "maxHp": 1000,
            "sessionId": "sess_kirpich_fast",
            "startedAt": started_iso,
        },
        "unclaimedRewards": [{"claimId": "cid_fast_1", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=_claim,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert claim_calls == 2
    assert len(res.get("defeats") or []) == 0
    assert len(res["victories"]) == 1
    vic = res["victories"][0]
    assert vic["boss_name"] == "Кирпич"
    assert vic["duration_sec"] >= 90
    assert ":" in vic["duration_formatted"]

    # Проверяем, что дельта профиля добавила authority (+50) и sugar (+15) без дублирования cigarettes (+200)
    cur_map = {r["currency"]: r["amount"] for r in vic["rewards"]}
    assert cur_map["cigarettes"] == 200
    assert cur_map["authority"] == 50
    assert cur_map["sugar"] == 15

    # Проверяем строгий формат TG-уведомления
    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Победа над боссом: Кирпич (Пацанский)" in tg_msg
    assert "🔥 Награды:" in tg_msg
    assert "⏱️ Бой продлился:" in tg_msg
    assert "Битва с боссом:" not in tg_msg
    assert "Призвано боссов:" not in tg_msg

    # Проверяем сохранение в БД для Web
    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert "Победа над боссом: Кирпич (Пацанский)" in notifs[0].title
        assert notifs[0].meta_json.get("duration_formatted")
        assert len(notifs[0].meta_json.get("rewards") or []) >= 3

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_vorkuta_0859_expired_defeat_not_classified_as_victory(tmp_path):
    """
    Воспроизведение инцидента 08:59 (Воркута Пацанский, 08:01:01):
    claim возвращает {"success": True, "status": "claimed", "rewards": {"result": "defeat", ...}},
    таймер истёк, last_hp > 0, дельта профиля 0 -> строго defeat, без ложной победы и без 'получены'.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from datetime import datetime, timezone, timedelta
    from core.database import get_engine, init_db, get_session
    from core.models import Account, Notification
    from workers.boss_worker import BossWorker
    from sqlalchemy import select

    db_path = tmp_path / "boss_vorkuta_defeat.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)
    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79001112233", nickname="Test"))
        await session.commit()

    notifier = SimpleNamespace(notify=AsyncMock())
    vorkuta_claim = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b7d5b677e19377f0da45d4f52a",
        "rewards": {
            "mode": "pacansky",
            "time": "2026-11-26T05:58:42.0221039Z",
            "title": "Воркута",
            "bossId": 39,
            "result": "defeat",
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
        },
    }
    started_iso = (datetime.now(timezone.utc) - timedelta(hours=8, minutes=1, seconds=1)).isoformat()
    ends_iso = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    bootstrap = {
        "state": "reward",
        "session": {
            "bossId": 39,
            "title": "Воркута",
            "mode": "pacansky",
            "currentHp": 149444357,
            "maxHp": 400000000,
            "personalDamage": 67,
            "sessionId": "01a214b7d5b677e19377f0da45d4f52a",
            "startedAt": started_iso,
            "endsAt": ends_iso,
        },
        "unclaimedRewards": [{"claimId": "01a214b7d5b677e19377f0da45d4f52a", "bossId": 39}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value=vorkuta_claim),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(
        init_player=AsyncMock(return_value={"currencies": {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 12}})
    )
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res.get("victories") or []) == 0
    assert len(res.get("defeats") or []) == 1
    df = res["defeats"][0]
    assert df["boss_name"] == "Воркута"
    assert df["remaining_hp"] == 149444357
    assert df["max_hp"] == 400000000
    assert df["personal_damage"] == 67

    notifier.notify.assert_awaited_once()
    tg_msg = notifier.notify.call_args[0][0]
    assert "Поражение от босса: Воркута (Пацанский)" in tg_msg
    assert "Победа над боссом" not in tg_msg
    assert "получены" not in tg_msg

    async with get_session(engine) as session:
        notifs = (await session.execute(select(Notification))).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].title == "Поражение от босса: Воркута (Пацанский)"
        assert notifs[0].meta_json["outcome"] == "defeat"

    await engine.dispose()


@pytest.mark.asyncio
async def test_boss_victory_empty_claim_uses_fresh_profile_currencies_delta(tmp_path):
    """
    Победа с явным victory=True без массива rewards в ответе claim:
    свежий запрос player_api.init_player() возвращает currencies -> дельта дополняет награды в TG и Web.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db
    from workers.boss_worker import BossWorker

    db_path = tmp_path / "boss_delta_currencies.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    notifier = SimpleNamespace(notify=AsyncMock())
    init_calls = 0

    async def _init_player():
        nonlocal init_calls
        init_calls += 1
        if init_calls == 1:
            return {"currencies": {"cigarettes": 1000, "sugar": 100, "authority": 500}, "authority": 500}
        return {"currencies": {"cigarettes": 1150, "sugar": 130, "authority": 1000}, "authority": 1000}

    bootstrap = {
        "state": "reward",
        "session": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_delta_cur"},
        "unclaimedRewards": [{"claimId": "cid_delta_cur", "bossId": 1}],
    }
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value=bootstrap),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=AsyncMock(return_value={"success": True, "victory": True}),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=_init_player)
    worker = BossWorker(
        account_id=1,
        boss_api=boss_api,
        player_api=player_api,
        db_engine=engine,
        notifier=notifier,
        enable_jitter=False,
    )

    res = await worker.run_cycle()
    assert len(res["victories"]) == 1
    cur_map = {r["currency"]: r["amount"] for r in res["victories"][0]["rewards"]}
    assert cur_map["cigarettes"] == 150
    assert cur_map["sugar"] == 30
    assert cur_map["authority"] == 500

    tg_msg = notifier.notify.call_args[0][0]
    assert "Папиросы +150" in tg_msg
    assert "Сахар +30" in tg_msg
    assert "Авторитет +500" in tg_msg
    assert "получены" not in tg_msg

    await engine.dispose()


def test_night_mode_windows_msk_and_worker_isolation():
    """Проверка окон Ночного режима по МСК и того, что is_worker_active не блокирует другие воркеры."""
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from core.database import is_night_mode_active, is_worker_active

    # 23:00-08:00 МСК: 02:30 МСК = 23:30 UTC предыдущего дня
    cfg_cross = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=23, sleep_end_hour=8)
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 25, 23, 30, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_cross, now_utc=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)) is False  # 12:00 МСК
    assert is_worker_active(cfg_cross) is True

    # 00:00-08:00 МСК: 03:00 МСК = 00:00 UTC
    cfg_same = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=0, sleep_end_hour=8)
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)) is True
    assert is_night_mode_active(cfg_same, now_utc=datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)) is False  # 08:00 МСК
    assert is_worker_active(cfg_same) is True

    # start == end -> не блокирует 24/7
    cfg_eq = SimpleNamespace(is_paused=False, sleep_mode_enabled=True, sleep_start_hour=5, sleep_end_hour=5)
    assert is_night_mode_active(cfg_eq, now_utc=datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_boss_worker_night_mode_allows_claim_blocks_summon_and_attack(tmp_path, monkeypatch):
    """В Ночной режим BossWorker забирает награды (claim), но не призывает и не атакует боссов."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core.database import get_engine, init_db, get_or_create_config, get_session
    from core.models import BotConfig
    import workers.boss_worker as bw_mod

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'night_boss.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    cfg = await get_or_create_config(1, engine)
    async with get_session(engine) as s:
        db_cfg = await s.get(BotConfig, cfg.id)
        db_cfg.sleep_mode_enabled = True
        db_cfg.sleep_start_hour = 0
        db_cfg.sleep_end_hour = 8
        db_cfg.auto_boss_enabled = True
        db_cfg.auto_boss_summon = True
        db_cfg.auto_boss_hits = True
        db_cfg.boss_auto_melee = True
        db_cfg.boss_targets = [1]
        await s.commit()

    monkeypatch.setattr(bw_mod, "is_night_mode_active", lambda c: True)

    bootstraps = [
        # 1. Завершенный бой с наградой -> должен быть заклеймлен ночью!
        {
            "state": "reward",
            "battle": {"bossId": 1, "title": "Кирпич", "mode": "pacansky", "currentHp": 0, "maxHp": 1000, "sessionId": "s_night_1"},
            "prisons": [],
        },
        # 2. После клейма слот свободен -> призывать нового ночью НЕЛЬЗЯ!
        {
            "state": "idle",
            "battle": None,
            "prisons": [],
        },
    ]
    claim_mock = AsyncMock(return_value={
        "success": True,
        "rewards": {"result": "victory", "globalReward": {"cigarettes": 100}},
    })
    summon_mock = AsyncMock()
    attack_mock = AsyncMock()
    notifier = SimpleNamespace(notify=AsyncMock())

    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(side_effect=lambda: bootstraps.pop(0) if len(bootstraps) > 1 else bootstraps[0]),
        get_all_bosses=AsyncMock(return_value=[]),
        get_weapons=AsyncMock(return_value={}),
        claim_reward=claim_mock,
        start_boss=summon_mock,
        attack_boss=attack_mock,
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    player_api = SimpleNamespace(init_player=AsyncMock(return_value={"currencies": {"cigarettes": 500, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0, "authority": 0}}))

    worker = BossWorker(account_id=1, boss_api=boss_api, player_api=player_api, db_engine=engine, notifier=notifier, enable_jitter=False)
    res = await worker.run_cycle()

    assert res["rewards_claimed"] == 1
    assert res.get("night_mode_paused") is True
    assert claim_mock.await_count == 1
    assert summon_mock.await_count == 0
    assert attack_mock.await_count == 0
    assert notifier.notify.await_count == 1
    await engine.dispose()






@pytest.mark.asyncio
async def test_kresty_day_2_unlocks_lyutyy_for_catalog_and_boss_worker():
    """
    Регрессия бага: get_all_prisons() не содержит dayRuns/nightRuns,
    поэтому fetch_enriched_prisons_list + BossWorker._fetch_prisons_safe обязаны
    подтягивать dayRuns из get_prison_state(pid) и разблокировать Лютого при День: 2.
    """
    from unittest.mock import AsyncMock
    from client.api.boss import BossAPI, _load_bosses_catalog
    from client.api.prison import fetch_enriched_prisons_list
    from core.state_hub import state_hub

    state_hub.clear(1)
    prison_api = AsyncMock()
    prison_api.get_all_prisons.return_value = {
        "prisons": [
            {"id": 4, "name": "КРЕСТЫ", "isUnlocked": True},
        ]
    }
    # Кейс 1: Кресты День 2 -> Лютый (id=4, requiredPrisonId=4, requiredRuns=2) разблокирован!
    # Имитируем реальный ответ /api/player/prison/4 с обёрткой {"success": True, "data": {...}}
    prison_api.get_prison_state.return_value = {"success": True, "data": {"dayRuns": 2, "nightRuns": 0}}
    enriched_2 = await fetch_enriched_prisons_list(prison_api)
    assert enriched_2[0]["dayRuns"] == 2

    lyutyy = next(dict(b) for b in _load_bosses_catalog() if b["id"] == 4)
    boot = {"playerStats": {"keys": {"3": 8}, "wins": {}, "dailyWins": {}, "dailyBossBattleLimit": 7}}
    res_unlocked = BossAPI.evaluate_bosses_availability([dict(lyutyy)], bootstrap=boot, prisons_data=enriched_2)
    assert res_unlocked[0]["isLocked"] is False
    assert res_unlocked[0]["canAttack"] is True

    # Кейс 2: Обратный кейс (День 1 -> Лютый закрыт, 1 из 2)
    prison_api.get_prison_state.return_value = {"dayRuns": 1, "nightRuns": 0}
    enriched_1 = await fetch_enriched_prisons_list(prison_api)
    res_locked = BossAPI.evaluate_bosses_availability([dict(lyutyy)], bootstrap=boot, prisons_data=enriched_1)
    assert res_locked[0]["isLocked"] is True
    assert "1 из 2" in (res_locked[0].get("unlockReason") or "")

    # Кейс 3: BossWorker._fetch_prisons_safe после prison_completed (dirty=True)
    prison_api.get_prison_state.return_value = {"dayRuns": 2, "nightRuns": 0}
    state_hub.notify_mutation(1, "prison_completed", reason="test_2nd_run")
    bw = BossWorker(account_id=1, boss_api=AsyncMock(), prison_api=prison_api, enable_jitter=False)
    pr_for_worker = await bw._fetch_prisons_safe()
    assert pr_for_worker["prisons"][0]["dayRuns"] == 2



@pytest.mark.asyncio
async def test_boss_worker_live_mode_change_between_battles(boss_setup):
    """
    Live-смена режима атаки между боями без перезапуска воркера:
    бой 1 в pacansky -> обновление boss_targets на avtoritetny -> следующий бой в avtoritetny.
    """
    from core.database import get_or_create_config

    engine, acc_id = boss_setup
    async with get_session(engine) as session:
        cfg = await get_or_create_config(acc_id, engine)
        cfg.is_paused = False
        cfg.sleep_mode_enabled = False
        cfg.auto_boss_enabled = True
        cfg.auto_boss_summon = True
        cfg.auto_boss_hits = True
        cfg.boss_auto_melee = True
        cfg.boss_targets = [{"bossId": 1, "mode": "pacansky", "limit": 7, "enabled": True}]
        session.add(cfg)
        await session.commit()

    start_calls = []
    boot_state = {"phase": 0}

    def mock_handler(request: httpx.Request):
        path = request.url.path
        if path == "/api/boss/bootstrap":
            if boot_state["phase"] == 0:
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None, "playerStats": {"keys": {}, "dailyWins": {}}})
            if boot_state["phase"] == 1:
                return httpx.Response(200, json={
                    "success": True,
                    "state": "active",
                    "session": {
                        "sessionId": "s_live_1",
                        "bossId": 1,
                        "mode": "pacansky",
                        "currentHp": 100,
                        "maxHp": 500,
                        "weapons": {},
                    },
                    "weaponStats": {"punchChestCooldownSec": 28800, "kickBallsCooldownSec": 28800, "pokeEyesCooldownSec": 28800, "kneeEarCooldownSec": 28800},
                })
            if boot_state["phase"] == 2:
                return httpx.Response(200, json={"success": True, "state": "idle", "session": None, "playerStats": {"keys": {}, "dailyWins": {}}})
            return httpx.Response(200, json={
                "success": True,
                "state": "active",
                "session": {
                    "sessionId": "s_live_2",
                    "bossId": 1,
                    "mode": "avtoritetny",
                    "currentHp": 1000,
                    "maxHp": 1000,
                    "weapons": {},
                },
                "weaponStats": {"punchChestCooldownSec": 28800, "kickBallsCooldownSec": 28800, "pokeEyesCooldownSec": 28800, "kneeEarCooldownSec": 28800},
            })
        if path == "/api/boss/all":
            return httpx.Response(200, json={"bosses": [{"id": 1, "name": "Кирпич", "isLocked": False, "canAttack": True}]})
        if path == "/api/boss/start-attack":
            import json as _json
            body = _json.loads(request.content.decode("utf-8"))
            start_calls.append(body)
            boot_state["phase"] = 1 if len(start_calls) == 1 else 3
            return httpx.Response(200, json={"success": True})
        if path == "/api/boss/use-weapon":
            boot_state["phase"] = 2
            return httpx.Response(200, json={"success": True, "currentHp": 0, "bossDefeated": True, "state": "reward", "claimId": "c_live_1"})
        if path == "/api/boss/claim-reward":
            return httpx.Response(200, json={"success": True, "rewards": []})
        if path == "/api/player/bootstrap":
            return httpx.Response(200, json={"cigarettes": 100})
        if path == "/api/boss/friend-damage":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"success": True})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)
    worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine, enable_jitter=False)

    # Перехватываем _claim_reward_with_retry / окончание боя: меняем режим в БД между 1-й и 2-й атакой
    orig_load = worker._load_fresh_boss_config

    async def _switching_load():
        if len(start_calls) == 1 and boot_state["phase"] == 2:
            async with get_session(engine) as s:
                c = await get_or_create_config(acc_id, engine)
                c.boss_targets = [{"bossId": 1, "mode": "avtoritetny", "limit": 7, "enabled": True}]
                s.add(c)
                await s.commit()
        return await orig_load()

    worker._load_fresh_boss_config = _switching_load  # type: ignore[method-assign]

    res = await worker.run_cycle()
    assert len(start_calls) >= 2
    assert start_calls[0]["mode"] == "pacansky"
    assert start_calls[1]["mode"] == "avtoritetny"
    assert res["summoned_bosses"][0]["mode"] == "pacansky"
    assert res["summoned_bosses"][1]["mode"] == "avtoritetny"


@pytest.mark.asyncio
async def test_boss_worker_live_priority_reorder_and_removal(boss_setup):
    """
    Live-смена приоритета ротации и удаление босса из очереди:
    1) Кирпич -> Сизый меняем на Сизый -> Кирпич => воркер призывает Сизого.
    2) Удаляем Сизого из очереди => следующий призыв выбирает Кирпича.
    """
    from core.database import get_or_create_config

    engine, acc_id = boss_setup
    async with get_session(engine) as session:
        cfg = await get_or_create_config(acc_id, engine)
        cfg.is_paused = False
        cfg.sleep_mode_enabled = False
        cfg.auto_boss_enabled = True
        cfg.auto_boss_summon = True
        cfg.auto_boss_hits = False
        cfg.boss_auto_melee = False
        cfg.boss_targets = [
            {"bossId": 1, "mode": "pacansky", "limit": 7, "enabled": True},
            {"bossId": 2, "mode": "pacansky", "limit": 7, "enabled": True},
        ]
        session.add(cfg)
        await session.commit()

    start_calls = []

    def mock_handler(request: httpx.Request):
        path = request.url.path
        if path == "/api/boss/bootstrap":
            return httpx.Response(200, json={"success": True, "state": "idle", "session": None, "playerStats": {"keys": {"1": 10}, "dailyWins": {}}})
        if path == "/api/boss/all":
            return httpx.Response(200, json={
                "bosses": [
                    {"id": 1, "name": "Кирпич", "isLocked": False, "canAttack": True},
                    {"id": 2, "name": "Сизый", "isLocked": False, "canAttack": True},
                ]
            })
        if path == "/api/boss/start-attack":
            import json as _json
            body = _json.loads(request.content.decode("utf-8"))
            start_calls.append(body)
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json={"success": True})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    auth_provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)
    http_client = GameHttpClient(auth_provider=auth_provider, custom_client=mock_client)
    boss_api = BossAPI(http_client=http_client)
    worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine, enable_jitter=False)

    # 1. Меняем приоритет на Сизый (2) -> Кирпич (1)
    async with get_session(engine) as session:
        cfg = await get_or_create_config(acc_id, engine)
        cfg.boss_targets = [
            {"bossId": 2, "mode": "avtoritetny", "limit": 7, "enabled": True},
            {"bossId": 1, "mode": "pacansky", "limit": 7, "enabled": True},
        ]
        session.add(cfg)
        await session.commit()

    await worker.run_cycle()
    assert len(start_calls) == 1
    assert start_calls[0]["bossId"] == 2
    assert start_calls[0]["mode"] == "avtoritetny"

    # 2. Удаляем Сизого (2) из очереди -> остается только Кирпич (1)
    async with get_session(engine) as session:
        cfg = await get_or_create_config(acc_id, engine)
        cfg.boss_targets = [
            {"bossId": 1, "mode": "blotnoy", "limit": 7, "enabled": True},
        ]
        session.add(cfg)
        await session.commit()

    await worker.run_cycle()
    assert len(start_calls) == 2
    assert start_calls[1]["bossId"] == 1
    assert start_calls[1]["mode"] == "blotnoy"



@pytest.mark.asyncio
async def test_boss_availability_all_categories_and_no_false_lock_when_defeated():
    """
    1) Лютый с победами (dailyWins=3) никогда не помечается Закрыт даже при пустом prisons_data.
    2) Надзиратели (Циклоп, Раиса) и Рецидивисты (Отбой) имеют единую live-проверку доступности
       и структурированный объект availability.
    """
    from client.api.boss import BossAPI, _load_bosses_catalog

    catalog = [dict(b) for b in _load_bosses_catalog() if b["id"] in (4, 10, 11, 33)]
    # Кейс 1: prisons_data пуст, но у Лютого есть 3 дневные победы (и 0 в wins -> totalWins >= dailyWins)
    boot = {
        "playerStats": {
            "wins": {"4": 0},
            "dailyWins": {"4": 3},
            "keys": {"9": 3, "10": 0, "32": 0},
            "dailyBossBattleLimit": 7,
        }
    }
    res1 = BossAPI.evaluate_bosses_availability([dict(b) for b in catalog], bootstrap=boot, prisons_data=[])
    by_id1 = {b["id"]: b for b in res1}
    assert by_id1[4]["isLocked"] is False
    assert by_id1[4]["totalWins"] == 3
    assert by_id1[4]["dailyWins"] == 3
    assert by_id1[4]["availability"]["is_unlocked"] is True

    # Кейс 2: prisons_data с 0 ночных бунтов в Красной Пресне -> Циклоп (10) и Раиса (11) закрыты с требованиями
    prisons_0 = [
        {"id": 2, "name": "Красная Пресня", "dayRuns": 2, "nightRuns": 0},
        {"id": 3, "name": "Софийка", "dayRuns": 0, "nightRuns": 2},
    ]
    res2 = BossAPI.evaluate_bosses_availability([dict(b) for b in catalog], bootstrap=boot, prisons_data=prisons_0)
    by_id2 = {b["id"]: b for b in res2}
    assert by_id2[10]["isLocked"] is True
    assert "0 из 2" in (by_id2[10].get("unlockReason") or "")
    assert by_id2[10]["availability"]["requirements"][0]["type"] == "prison_runs"
    assert by_id2[11]["isLocked"] is True
    assert "0 из 2" in (by_id2[11].get("unlockReason") or "")
    # Отбой (Рецидивисты) имеет структурированное требование ключей
    assert any(r["type"] == "keys" for r in by_id2[33]["availability"]["requirements"])

    # Кейс 3: 2 ночных бунта в Красной Пресне -> Циклоп (10) открывается динамически
    prisons_ok = [
        {"id": 2, "name": "Красная Пресня", "dayRuns": 2, "nightRuns": 2},
        {"id": 3, "name": "Софийка", "dayRuns": 2, "nightRuns": 2},
    ]
    res3 = BossAPI.evaluate_bosses_availability([dict(b) for b in catalog], bootstrap=boot, prisons_data=prisons_ok)
    by_id3 = {b["id"]: b for b in res3}
    assert by_id3[10]["isLocked"] is False
    assert by_id3[10]["canAttack"] is True
    assert by_id3[11]["isLocked"] is False



@pytest.mark.asyncio
async def test_adaptive_battle_poll_interval_and_watcher_tick():
    """
    Проверка адаптивного интервала активного боя (fast/normal/heavy/degraded)
    и легковесного watch_active_battle_tick без тяжелых запросов и с обновлением StateHub.
    """
    from unittest.mock import AsyncMock
    from workers.boss_worker import compute_adaptive_battle_poll_interval
    from core.state_hub import state_hub

    assert compute_adaptive_battle_poll_interval(1000, 1000, False) == 2.0
    assert compute_adaptive_battle_poll_interval(150_000, 1_000_000, False) == 2.0
    assert compute_adaptive_battle_poll_interval(500_000, 1_000_000, False) == 4.0
    assert compute_adaptive_battle_poll_interval(5_000_000, 10_000_000, False) == 8.0
    assert compute_adaptive_battle_poll_interval(1000, 1000, True) == 5.0

    state_hub.clear(1)
    state_hub.update_slice(1, "boss", {"state": "active", "session": {"bossId": 1, "currentHp": 1000, "maxHp": 1000}})

    boss_api = AsyncMock()
    boss_api.get_bootstrap.return_value = {
        "state": "active",
        "session": {"bossId": 1, "currentHp": 450, "maxHp": 1000, "personalDamage": 550},
    }
    import time as _time
    bw = BossWorker(account_id=1, boss_api=boss_api, state_hub=state_hub, enable_jitter=False)
    bw.melee_ready_at = {"punchChest": _time.time() + 1000.0}
    tick = await bw.watch_active_battle_tick()
    assert tick["active"] is True
    assert tick["current_hp"] == 450
    assert tick["needs_action"] is False
    boss_api.get_all_bosses.assert_not_called()
    assert state_hub.get_slice(1, "boss").data["session"]["currentHp"] == 450

    boss_api.get_bootstrap.return_value = {"state": "reward", "session": {"bossId": 1, "currentHp": 0}}
    tick_done = await bw.watch_active_battle_tick()
    assert tick_done["needs_action"] is True
