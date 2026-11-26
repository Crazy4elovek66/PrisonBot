import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.state_hub import LiveStateHub


@pytest.mark.asyncio
async def test_live_state_hub_fingerprint_dedup_and_sse_publish():
    """
    LiveStateHub:
    - Идентичный payload (даже при изменении эфемерного updatedAt/generatedAt) НЕ инкрементирует version и НЕ шлёт событие в очередь;
    - Изменившийся payload инкрементирует version и публикует slice_update подписчикам.
    """
    hub = LiveStateHub()
    q = hub.subscribe(account_id=1)

    changed1, e1 = hub.update_slice(1, "profile", {"profile": {"energy": 40, "maxEnergy": 50}, "generatedAt": "t1"})
    assert changed1 is True
    assert e1.version == 1

    evt1 = await asyncio.wait_for(q.get(), timeout=1.0)
    assert evt1["type"] == "slice_update"
    assert evt1["slice"] == "profile"
    assert evt1["version"] == 1

    # Идентичный контент (другое generatedAt) -> дедупликация!
    changed2, e2 = hub.update_slice(1, "profile", {"profile": {"energy": 40, "maxEnergy": 50}, "generatedAt": "t2"})
    assert changed2 is False
    assert e2.version == 1
    assert q.empty() is True

    # Реальное изменение -> version=2 + событие
    changed3, e3 = hub.update_slice(1, "profile", {"profile": {"energy": 35, "maxEnergy": 50}, "generatedAt": "t3"})
    assert changed3 is True
    assert e3.version == 2
    evt2 = await asyncio.wait_for(q.get(), timeout=1.0)
    assert evt2["version"] == 2
    assert evt2["data"]["profile"]["energy"] == 35

    # Точечный патч ресурсов
    patched = hub.patch_profile_resources(1, energy=29)
    assert patched is True
    assert hub.get_slice(1, "profile").version == 3
    assert hub.get_slice(1, "profile").data["profile"]["energy"] == 29

    # Delta отдаёт только изменившиеся срезы
    hub.update_slice(1, "boss", {"state": "idle"})
    delta = hub.get_delta(1, client_versions={"profile": 3, "boss": 0})
    assert "profile" not in delta["changed"]
    assert "boss" in delta["changed"]
    assert delta["changed"]["boss"]["state"] == "idle"

    hub.unsubscribe(1, q)


@pytest.mark.asyncio
async def test_live_state_hub_single_flight():
    """Параллельные запросы под одним ключом run_single_flight выполняют корутину ровно 1 раз."""
    hub = LiveStateHub()
    calls = 0

    async def expensive():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return {"ok": True, "calls": calls}

    r1, r2, r3 = await asyncio.gather(
        hub.run_single_flight("k1", expensive),
        hub.run_single_flight("k1", expensive),
        hub.run_single_flight("k1", expensive),
    )
    assert calls == 1
    assert r1 == r2 == r3


def test_preset_run_state_sync_and_clear():
    """Проверка PresetRunState и трансляции среза presets в LiveStateHub."""
    from core.state_hub import LiveStateHub

    hub = LiveStateHub()
    st = hub.set_preset_state(
        1,
        7,
        current_step=1,
        total_steps=5,
        active_boss_id=3,
        status="running",
        presets_list=[{"id": 7, "is_running": True, "current_step_index": 1, "totalSteps": 5}],
    )
    assert st is not None
    assert st.preset_id == 7
    assert hub.get_preset_state(1).status == "running"

    sl = hub.get_slice(1, "presets")
    assert sl is not None
    assert sl.data["activeRun"]["isRunning"] is True

    hub.set_preset_state(1, None, status="stopped", presets_list=[{"id": 7, "is_running": False}])
    assert hub.get_preset_state(1) is None
    assert hub.get_slice(1, "presets").data["activeRun"] is None


@pytest.mark.asyncio
async def test_player_api_init_single_flight():
    """Одновременные вызовы PlayerAPI.init_player() схлопываются в 1 HTTP POST /api/player/init."""
    from types import SimpleNamespace
    from client.api.player import PlayerAPI

    calls = 0

    async def _post(url, json=None):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"userId": 1, "calls": calls})

    api = PlayerAPI(http_client=SimpleNamespace(post=_post))
    r1, r2 = await asyncio.gather(api.init_player(), api.init_player())
    assert calls == 1
    assert r1 == r2 == {"userId": 1, "calls": 1}


def test_state_hub_talents_protection_and_idle_zeroing():
    hub = LiveStateHub()
    valid = {"currentDamage": 67, "requiredDamage": 90, "spentPoints": 10, "unspentPoints": 2, "totalPoints": 12}
    res1 = hub.merge_talents_state(1, valid)
    assert res1["currentDamage"] == 67
    assert res1["totalPoints"] == 12

    # Пустой или нулевой пакет не должен затирать валидные таланты
    res_empty = hub.merge_talents_state(1, {})
    assert res_empty["currentDamage"] == 67
    assert res_empty["requiredDamage"] == 90
    res_zero = hub.merge_talents_state(1, {"currentDamage": 0, "requiredDamage": 0, "totalPoints": 0, "unspentPoints": 0})
    assert res_zero["currentDamage"] == 67
    assert res_zero["totalPoints"] == 12

    # При отсутствии активного боя обнуляется только currentDamage, очки и порог сохраняются
    res_idle = hub.merge_talents_state(1, None, allow_damage_zero=True)
    assert res_idle["currentDamage"] == 0
    assert res_idle["requiredDamage"] == 90
    assert res_idle["totalPoints"] == 12
    assert res_idle["unspentPoints"] == 2


@pytest.mark.asyncio
async def test_state_hub_emit_change_revisions_and_domain_sync():
    hub = LiveStateHub()
    q = hub.subscribe(1)
    cb_calls = []
    hub.register_invalidation_callback(lambda acc, doms, patch, reason: cb_calls.append((acc, doms, reason)))

    hub.update_slice(1, "boss", {"active": True, "hp": 500})
    evt1 = hub.emit_change(1, ["boss", "talents"], patch={"boss": {"hp": 400}, "talents": {"currentDamage": 100, "requiredDamage": 200, "totalPoints": 5}}, reason="boss_hit")
    assert evt1["revisions"]["boss"] == 1
    assert evt1["revisions"]["talents"] == 1
    assert hub.get_slice(1, "boss").data["active"] is True
    assert hub.get_slice(1, "boss").data["hp"] == 400
    assert cb_calls == [(1, ["boss", "talents"], "boss_hit")]

    evt2 = hub.emit_change(1, ["social"], patch={"social": {"incoming_count": 4, "accepted_ids": [11, 22]}}, reason="accept")
    assert evt2["revisions"]["social"] == 1

    # Очищаем первые 2 slice_update (от update_slice("boss") и merge_talents_state) и проверяем domain_sync + social_updated
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    types = [e["type"] for e in events]
    assert "domain_sync" in types
    assert "social_updated" in types
    hub.unsubscribe(1, q)


def test_state_hub_collections_slice_preserves_icons():
    hub = LiveStateHub()
    payload = {
        "success": True,
        "collections": [
            {
                "prisonId": 1,
                "collectionId": 1,
                "name": "Мастера закатки",
                "items": [{"id": 1, "count": 2, "icon": "/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp"}],
            }
        ],
        "stashes": [],
    }
    hub.update_slice(1, "collections", payload)
    sl = hub.get_slice(1, "collections")
    assert sl is not None
    assert sl.data["collections"][0]["items"][0]["icon"].startswith("/api/v1/assets/proxy?path=")

    # Пустой срез collections не должен затирать уже загруженные коллекции с иконками
    changed, _ = hub.update_slice(1, "collections", {"success": True, "collections": [], "stashes": []})
    assert changed is False
    assert len(hub.get_slice(1, "collections").data["collections"]) == 1


@pytest.mark.asyncio
async def test_daily_resource_snapshots_persistence_msk_rollover_and_validation(tmp_path):
    """
    Проверка суточных дельт ресурсов (МСК):
    1) фиксация базы и расчёт дельт;
    2) персистентность после перезапуска БД (нового engine);
    3) смена суток строго по МСК (23:55 МСК vs 00:05 МСК, когда в UTC еще прежний день);
    4) защита от битых/пустых данных;
    5) пересчёт resource_deltas в LiveStateHub.patch_profile_resources.
    """
    from datetime import datetime, timezone
    from core.config import MSK_TZ
    from core.database import (
        get_engine,
        init_db,
        compute_daily_resource_deltas,
        ensure_daily_resource_baseline,
        get_daily_resource_baseline,
    )
    from core.state_hub import LiveStateHub

    db_path = tmp_path / "daily_deltas.db"
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    engine1 = get_engine(db_url)
    await init_db(engine1)

    t_2355_msk = datetime(2026, 11, 26, 23, 55, 0, tzinfo=MSK_TZ)
    base_res = {"cigarettes": 5000, "sugar": 30000, "rubles": 200, "paper": 100, "soap": 10}
    d1 = await compute_daily_resource_deltas(base_res, now_msk=t_2355_msk, engine=engine1)
    assert d1 is not None
    assert d1["day_msk"] == "2026-11-26"
    assert d1["deltas"] == {"cigarettes": 0, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0}

    # Последующее обновление в те же сутки МСК
    upd_res = {"cigarettes": 5225, "sugar": 29800, "rubles": 208, "paper": 100, "soap": 12}
    d2 = await compute_daily_resource_deltas(upd_res, now_msk=t_2355_msk, engine=engine1)
    assert d2["deltas"] == {"cigarettes": 225, "sugar": -200, "rubles": 8, "paper": 0, "soap": 2}
    await engine1.dispose()

    # Имитация перезапуска сервиса (новый engine на том же файле БД)
    engine2 = get_engine(db_url)
    d2_after_restart = await compute_daily_resource_deltas(upd_res, now_msk=t_2355_msk, engine=engine2)
    assert d2_after_restart["baseline"] == base_res
    assert d2_after_restart["deltas"] == {"cigarettes": 225, "sugar": -200, "rubles": 8, "paper": 0, "soap": 2}

    # Смена суток по МСК: 2026-11-26 21:05 UTC == 2026-11-27 00:05 MSK!
    t_0005_msk_from_utc = datetime(2026, 11, 26, 21, 5, 0, tzinfo=timezone.utc)
    d_next = await compute_daily_resource_deltas(upd_res, now_msk=t_0005_msk_from_utc, engine=engine2)
    assert d_next["day_msk"] == "2026-11-27"
    assert d_next["baseline"] == upd_res
    assert d_next["deltas"] == {"cigarettes": 0, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0}

    # Защита от битых/пустых данных
    assert await ensure_daily_resource_baseline("2026-11-28", {}, engine=engine2) is None
    assert await ensure_daily_resource_baseline("2026-11-28", {"cigarettes": -5, "sugar": 0, "rubles": 0, "paper": 0, "soap": 0}, engine=engine2) is None
    assert await get_daily_resource_baseline("2026-11-28", engine=engine2) is None
    await engine2.dispose()

    # Проверка patch_profile_resources в LiveStateHub
    hub = LiveStateHub()
    hub.update_slice(1, "profile", {
        "profile": {"id": 1, "level": 10},
        "currencies": dict(base_res),
        "resource_deltas": d1,
    })
    hub.patch_profile_resources(1, cigarettes=5500, rubles=250)
    patched = hub.get_slice(1, "profile").data
    assert patched["resource_deltas"]["deltas"]["cigarettes"] == 500
    assert patched["resource_deltas"]["deltas"]["rubles"] == 50


@pytest.mark.asyncio
async def test_state_hub_domain_freshness_single_flight_and_cross_invalidation():
    from core.state_hub import LiveStateHub

    hub = LiveStateHub()
    fetch_calls = 0

    async def fetch_prisons():
        nonlocal fetch_calls
        fetch_calls += 1
        await asyncio.sleep(0.02)
        return {"success": True, "prisons": [{"id": 4, "name": "КРЕСТЫ", "dayRuns": 2, "nightRuns": 0}]}

    # 1. Single-flight: 5 concurrent calls -> 1 network request
    results = await asyncio.gather(*[
        hub.ensure_domain_fresh(1, "prisons", fetcher=fetch_prisons)
        for _ in range(5)
    ])
    assert fetch_calls == 1
    assert all(r["prisons"][0]["dayRuns"] == 2 for r in results)

    # 2. Failure preservation: error during forced refresh preserves last valid cached data
    async def fail_fetch():
        raise RuntimeError("maintenance_503")

    preserved = await hub.ensure_domain_fresh(1, "prisons", force=True, fetcher=fail_fetch)
    assert preserved["prisons"][0]["dayRuns"] == 2
    assert hub.get_domain_state(1, "prisons").last_error == "maintenance_503"

    # 3. Cross-invalidation matrix + wakeup callback
    woken = []
    hub.register_wakeup_callback(lambda name, dt: woken.append(name))
    hub.notify_mutation(1, "prison_completed", reason="test_kresty_2")
    assert hub.get_domain_state(1, "prisons").dirty is True
    assert hub.get_domain_state(1, "boss").dirty is True
    assert hub.get_domain_state(1, "player").dirty is True
    assert hub.get_domain_state(1, "zaruby").dirty is True
    assert "boss" in woken and "zaruby" in woken

    telemetry = hub.get_domains_telemetry(1)
    assert telemetry["state_revision"] > 0
    assert telemetry["domain_revisions"]["boss"] >= 1
    assert "prisons" in telemetry["domains"]
