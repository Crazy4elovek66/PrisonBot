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
