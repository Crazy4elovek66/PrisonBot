from types import SimpleNamespace
from client.api.zaruby import ZARUBA_TIERS, classify_zarub_task, parse_zaruby_state


def test_classify_zarub_task_respects_safety_and_energy_conflicts():
    assert classify_zarub_task({"type": 6, "title": "Нанести урон"}, SimpleNamespace())[0] == "skip_damage"
    assert classify_zarub_task({"type": 4, "title": "Сделать ходки"}, SimpleNamespace(auto_prison=True))[0] == "skip_energy_conflict"
    assert classify_zarub_task({"type": 13, "title": "Потратить рубли"}, SimpleNamespace())[0] == "skip_paid"
    assert classify_zarub_task({"type": 9, "title": "Напряги терпилу"}, SimpleNamespace())[0] == "safe_auto"


def test_parse_zaruby_state_extracts_tasks_and_leaderboard():
    assert ZARUBA_TIERS["pacan"]["mode"] == 1
    assert ZARUBA_TIERS["vor"]["mode"] == 4
    raw = {
        "active": {
            "mode": 2,
            "startUnix": 1000,
            "endUnix": 2000,
            "completedCount": 1,
            "tasks": [{"taskId": 1, "type": 9, "title": "Терпила", "currentAmount": 1, "requiredAmount": 1, "status": 1}],
            "participants": [{"userId": 1, "nickname": "A", "authority": 100}, {"userId": 2, "nickname": "B", "authority": 90}],
        },
        "progress": {"level": 4, "xp": 20, "need": 80},
        "balances": {"ore_signet": 10, "signet": 12},
    }
    parsed = parse_zaruby_state(raw, config=SimpleNamespace())
    assert parsed["completed_count"] == 1
    assert parsed["total_count"] == 1
    assert parsed["tasks"][0]["classification"] == "safe_auto"
    assert len(parsed["leaderboard"]) == 2
