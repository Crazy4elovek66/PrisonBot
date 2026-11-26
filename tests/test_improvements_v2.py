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


@pytest.mark.asyncio
async def test_boss_melee_dict_equipped_slots_hits_3_ready_and_skips_cooldown():
    now = datetime.now(timezone.utc)
    weapons_data = {
        "equippedSlots": [
            {"slot": 0, "type": "kickBalls", "count": 1},
            {"slot": 1, "type": "punchChest", "count": 1},
            {"slot": 2, "type": "pokeEyes", "count": 1},
            {"slot": 3, "type": "kneeEar", "count": 1},
            {"slot": 5, "type": "poison", "count": 1},
        ],
        "lastKickBallsTime": (now - timedelta(seconds=100)).isoformat(),  # on cooldown (7100s left)
        "lastPunchChestTime": None,  # ready
        "lastPokeEyesTime": None,    # ready
        "lastKneeEarTime": None,     # ready
    }
    bootstrap = {
        "state": "active",
        "session": {"currentHp": 100000, "maxHp": 100000, "bossId": 39, "mode": "pacansky"},
        "weaponStatsEffective": {
            "kickBallsCooldownSec": 7200,
            "punchChestCooldownSec": 7200,
            "pokeEyesCooldownSec": 7200,
            "kneeEarCooldownSec": 7200,
        },
    }
    boss_api = SimpleNamespace(
        get_weapons=AsyncMock(return_value=weapons_data),
        hit_boss=AsyncMock(return_value={"currentHp": 99900, "state": "active"}),
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

    hit_weapons = [h["weapon"] for h in res["hits_performed"]]
    assert set(hit_weapons) == {"punchChest", "pokeEyes", "kneeEar"}
    assert len(rescheduled) == 1
    assert 7000.0 <= res["next_melee_wait_sec"] <= 7205.0


def test_cold_start_collections_catalog_resolves_real_name():
    from pathlib import Path
    catalog_path = Path(__file__).resolve().parent.parent / "storage" / "collections_catalog.json"
    assert catalog_path.exists(), "storage/collections_catalog.json must exist"

    DropParser._collection_item_map = {}
    DropParser._collection_image_map = {}
    DropParser._collection_catalog_loaded = False

    parsed = DropParser.parse_prison_work(
        {"collectionDrop": {"itemId": 1, "imageUrl": "assets/PrisonV3/collections/1/1/1.webp"}},
        prison_name="КРЕСТЫ",
    )
    assert len(parsed["drops"]) == 1
    title = parsed["drops"][0]["title"]
    assert "Коллекционный предмет" not in title
    assert "Предмет коллекции" not in title
    assert "Коллекция «" in title


def test_wardrobe_headwear_zones_and_cache_busting():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert "styles.css?v=20261126_04" in index_html
    assert "app.js?v=20261126_04" in index_html
    assert "spine_room_player.js?v=20261126_04" in index_html
    assert 'overEyes: (z === "1" || z === "2")' in app_js
    assert 'for (const z of ["7", "5"])' in app_js
    assert "scale: 1.192" in app_js


def test_boss_talents_widget_present_between_active_and_melee():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    index_html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    pos_active = index_html.index('id="boss-active-card"')
    pos_talents = index_html.index('id="boss-talents-widget"')
    pos_idle_talents = index_html.index('id="boss-talents-idle-card"')
    pos_top_slot = index_html.index('id="boss-attack-slot-top"')
    pos_melee = index_html.index('id="cfg-boss_auto_melee"')
    assert pos_active < pos_talents < pos_idle_talents < pos_top_slot < pos_melee
    assert "function renderBossTalentsWidget(state)" in app_js


def test_room_folder_id_mapping_for_all_boss_rooms():
    import json, re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    cache = json.loads((root / "storage" / "tattoo_clothing_cache.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cache.get("cameras", [])}

    def _extract(raw_c_img, cid):
        m = re.search(r"RoomCameraUrl/([^/]+)/|room_(\d+)\.(?:webp|png)", str(raw_c_img))
        return (m.group(1) or m.group(2)) if m else str(cid)

    assert _extract(by_id[32]["imageUrl"], 32) == "31"  # Феня
    assert _extract(by_id[33]["imageUrl"], 33) == "32"  # Воркута
    assert _extract(by_id[34]["imageUrl"], 34) == "33"  # Север
    assert _extract(by_id[35]["imageUrl"], 35) == "34"  # Бульдозер
    assert _extract(by_id[36]["imageUrl"], 36) == "35"  # Змей
    assert _extract(by_id[37]["imageUrl"], 37) == "36"  # Шнифер
    assert _extract(by_id[38]["imageUrl"], 38) == "37"  # Взлом (Spine-animated)


@pytest.mark.asyncio
async def test_katala_exact_reschedule_and_smart_cheat():
    from client.api.katala import KatalaSolver

    # Smart cheat keeps higher card and rerolls lower card
    act = KatalaSolver.choose_best_action("7", "A", shulmovki_left=1)
    assert act["action"] == "reroll"
    assert act["card_index"] == 0
    assert act["keep_card"] == "A"

    act_pair = KatalaSolver.choose_best_action("K", "K", shulmovki_left=2)
    assert act_pair["action"] == "finish"

    rescheduled = []
    katala_api = SimpleNamespace(
        get_state=AsyncMock(return_value={"freeGameAvailable": False, "cooldownSec": 1200}),
    )
    player_api = SimpleNamespace(http=None)
    rw = RoutineWorker(
        account_id=1,
        player_api=player_api,
        enable_jitter=False,
        on_katala_reschedule=lambda sec: rescheduled.append(sec),
    )
    # Monkeypatch KatalaAPI inside play_katala_if_ready via client.api.katala
    import client.api.katala as k_mod
    orig_cls = k_mod.KatalaAPI
    k_mod.KatalaAPI = lambda _http: katala_api
    try:
        res = await rw.play_katala_if_ready(config=SimpleNamespace(auto_katala=True, is_paused=False))
    finally:
        k_mod.KatalaAPI = orig_cls

    assert res["status"] == "already_played"
    assert len(rescheduled) == 1
    assert 1200.0 <= rescheduled[0] <= 1205.0


@pytest.mark.asyncio
async def test_podogrev_send_includes_type_1_and_respects_toggle():
    from client.api.player import PlayerAPI

    posted = []

    async def _post(url, json=None):
        posted.append((url, json))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"success": True})

    async def _get(url):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"friends": [{"userId": 101}, {"userId": 102}]})

    p_api = PlayerAPI(http_client=SimpleNamespace(post=_post, get=_get))
    rw = RoutineWorker(account_id=1, player_api=p_api, enable_jitter=False)

    # Disabled toggle -> skipped
    r_off = await rw.send_podogrev_if_ready(config=SimpleNamespace(auto_podogrev_send=False, is_paused=False))
    assert r_off["skipped"] is True
    assert posted == []

    # Enabled toggle -> sends with type=1 and sendToAll=True
    r_on = await rw.send_podogrev_if_ready(config=SimpleNamespace(auto_podogrev_send=True, is_paused=False))
    assert r_on["sent"] == 2
    assert posted == [("/api/podogrev/send", {"type": 1, "sendToAll": True})]


@pytest.mark.asyncio
async def test_boss_victory_notification_web_and_telegram_formatting():
    claim_payload = {
        "bossId": 39,
        "mode": "pacansky",
        "globalReward": {
            "authority": 1000,
            "keys": 2,
            "currencies": [{"type": "sugar", "amount": 500}, {"type": "cigarettes", "amount": 1000}],
        },
    }
    parsed = DropParser.parse_boss_claim(claim_payload, boss_name=None, mode="pacansky")
    assert "Воркута" in parsed["title"]
    assert "Босс повержен: Босс" != parsed["title"]
    curs = {r["currency"]: r["amount"] for r in parsed["rewards"]}
    assert curs["authority"] == 1000
    assert curs["sugar"] == 500
    assert curs["cigarettes"] == 1000
    assert curs["keys"] == 2

    sent_msgs = []
    notifier = SimpleNamespace(notify=AsyncMock(side_effect=lambda msg: sent_msgs.append(msg)))
    boss_api = SimpleNamespace(
        get_bootstrap=AsyncMock(return_value={
            "state": "reward",
            "session": {"bossId": 39, "title": "Воркута", "mode": "pacansky", "currentHp": 0, "maxHp": 400000000, "sessionId": "sess_39"},
            "unclaimedRewards": [{"claimId": "c39", "bossId": 39}],
        }),
        claim_reward=AsyncMock(return_value=claim_payload),
        get_friend_damage=AsyncMock(return_value={"friends": []}),
    )
    prison_api = SimpleNamespace(get_prisons=AsyncMock(return_value={"prisons": []}))
    worker = BossWorker(account_id=1, boss_api=boss_api, notifier=notifier, prison_api=prison_api, enable_jitter=False)
    cfg = SimpleNamespace(is_paused=False, sleep_mode_enabled=False, auto_boss_enabled=False, auto_boss_summon=False, boss_auto_melee=False)
    await worker._claim_pending_rewards(
        bootstrap=await boss_api.get_bootstrap(),
        results={"rewards_claimed": 0, "hits_performed": [], "summoned_bosses": [], "boss_hp_remaining": 0, "victories": [], "errors": []},
        active_preset=None,
        preset_steps=[],
        claimed_keys_in_cycle=set(),
    )
    assert "boss_claim_sess_39" in worker._notified_victory_keys


@pytest.mark.asyncio
async def test_auto_interactions_targets_pool_and_limit_stop(tmp_path):
    from pathlib import Path
    from core.models import BotConfig, SentFriendRequest, TrackedCandidate

    db_path = tmp_path / "test_interactions.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    async with get_session(engine) as session:
        acc = Account(id=1, phone="79000000000", game_user_id=1000, nickname="Test")
        session.add(acc)
        cfg = BotConfig(account_id=1, auto_biceps=True, auto_spit_balanda=False, auto_throw_yeast=True)
        session.add(cfg)
        session.add(TrackedCandidate(account_id=1, user_id=202))
        session.add(TrackedCandidate(account_id=1, user_id=1000))  # self -> excluded
        session.add(SentFriendRequest(account_id=1, target_user_id=303))
        session.add(SentFriendRequest(account_id=1, target_user_id=202))  # duplicate -> deduplicated
        await session.commit()

    calls = []

    async def _perform_interaction(from_uid, to_uid, action_type):
        calls.append((from_uid, to_uid, action_type))
        if action_type == "UpgradeBiceps" and to_uid == 202:
            return {"success": False, "message": "Дневной лимит исчерпан"}
        return {"success": True}

    social_api = SimpleNamespace(
        get_all_friend_profiles=AsyncMock(return_value=[{"userId": 101}, {"userId": 1000}]),
        perform_interaction=AsyncMock(side_effect=_perform_interaction),
    )
    rw = RoutineWorker(
        account_id=1,
        player_api=SimpleNamespace(),
        db_engine=engine,
        social_api=social_api,
        enable_jitter=False,
    )
    res1 = await rw.process_auto_interactions(player_data={"userId": 1000})
    assert res1["targets_pool"] == 3  # 101, 202, 303
    assert "Harknut" not in res1["actions"]
    assert res1["actions"]["UpgradeBiceps"]["done"] == 1
    assert res1["actions"]["UpgradeBiceps"]["limit_reached"] is True
    assert res1["actions"]["TossDroj"]["done"] == 3
    assert (1000, 303, "UpgradeBiceps") not in calls  # stopped at 202 limit

    # Mark TossDroj limit too and verify next call short-circuits
    res_off = await rw.process_auto_interactions(
        config=SimpleNamespace(is_paused=False, sleep_mode_enabled=False, auto_biceps=True, auto_spit_balanda=False, auto_throw_yeast=False),
        player_data={"userId": 1000},
    )
    assert res_off["status"] == "limit_reached"

    await engine.dispose()


def test_auto_interactions_and_boss_talents_ui_and_config_flags():
    from pathlib import Path
    from core.models import BotConfig

    for col in ("auto_biceps", "auto_spit_balanda", "auto_throw_yeast"):
        assert hasattr(BotConfig, col)

    root = Path(__file__).resolve().parent.parent
    html = (root / "web" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    for cid in ("cfg-auto_biceps", "cfg-auto_spit_balanda", "cfg-auto_throw_yeast"):
        assert cid in html

    for key in ('"auto_biceps"', '"auto_spit_balanda"', '"auto_throw_yeast"'):
        assert js.count(key) >= 2

    boss_fn_start = js.index("async function loadBoss()")
    boss_fn_end = js.index("async function ", boss_fn_start + 10)
    assert "loadTalents()" in js[boss_fn_start:boss_fn_end]
    assert "mergeTalentsState" in js
    assert "domain_sync" in js
    assert "social_updated" in js


@pytest.mark.asyncio
async def test_auto_interactions_negative_disjoint_and_extended_pool(tmp_path):
    from core.models import BotConfig, DailyInteractionTarget

    db_path = tmp_path / "test_neg_disjoint.db"
    engine = get_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_db(engine)

    async with get_session(engine) as session:
        session.add(Account(id=1, phone="79000000001", game_user_id=1000, nickname="Test"))
        session.add(BotConfig(account_id=1, auto_biceps=False, auto_spit_balanda=True, auto_throw_yeast=True))
        await session.commit()

    calls = []

    async def _perform_interaction(from_uid, to_uid, action_type):
        calls.append((to_uid, action_type))
        if to_uid == 202:
            return {"success": False, "message": "Негативное действие уже применено сегодня"}
        return {"success": True}

    social_api = SimpleNamespace(
        get_all_friend_profiles=AsyncMock(return_value=[{"userId": 101}, {"userId": 202}]),
        get_weekly_top=AsyncMock(return_value={"top": [{"userId": 303}, {"userId": 404}, {"userId": 505}]}),
        perform_interaction=AsyncMock(side_effect=_perform_interaction),
    )
    rw = RoutineWorker(
        account_id=1,
        player_api=SimpleNamespace(),
        db_engine=engine,
        social_api=social_api,
        enable_jitter=False,
    )

    res = await rw.process_auto_interactions(player_data={"userId": 1000})
    assert res["targets_pool"] == 5  # 101, 202 (друзья) + 303, 404, 505 (weekly top)

    harknut_targets = {uid for uid, act in calls if act == "Harknut"}
    droj_targets = {uid for uid, act in calls if act == "TossDroj"}
    # Цели для плевка и дрожжей не пересекаются в одни сутки МСК!
    assert harknut_targets.isdisjoint(droj_targets)
    assert res["actions"]["Harknut"]["done"] >= 2
    assert res["actions"]["TossDroj"]["done"] >= 1

    # Повторный вызов в те же сутки не трогает уже обработанные негативные цели (включая 202)
    calls.clear()
    res2 = await rw.process_auto_interactions(player_data={"userId": 1000})
    assert calls == []
    assert res2["actions"]["Harknut"]["done"] == 0
    assert res2["actions"]["TossDroj"]["done"] == 0

    await engine.dispose()
