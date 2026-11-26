import pytest
from client.api.katala import KatalaAPI, KatalaSolver, play_free_daily_game


def test_katala_hand_evaluation():
    # Проверка старшинства комбинаций
    eval_aa = KatalaSolver.evaluate_hand([{"rank": "A", "suit": 1}, {"rank": "A", "suit": 2}])
    assert eval_aa["rank_score"] == 1000
    assert eval_aa["reward"] == 1000
    assert eval_aa["has_tattoo"] is True

    eval_kk = KatalaSolver.evaluate_hand([{"rank": "K", "suit": 1}, {"rank": "K", "suit": 3}])
    assert eval_kk["rank_score"] == 700
    assert eval_kk["reward"] == 700
    assert eval_kk["has_tattoo"] is True

    eval_qq = KatalaSolver.evaluate_hand([{"rank": "Q", "suit": 2}, {"rank": "Q", "suit": 4}])
    assert eval_qq["rank_score"] == 500
    assert eval_qq["reward"] == 500

    eval_jj = KatalaSolver.evaluate_hand([{"rank": "J", "suit": 1}, {"rank": "J", "suit": 2}])
    assert eval_jj["rank_score"] == 200
    assert eval_jj["reward"] == 200

    eval_10 = KatalaSolver.evaluate_hand([{"rank": "10", "suit": 1}, {"rank": "10", "suit": 2}])
    assert eval_10["rank_score"] == 150
    assert eval_10["reward"] == 150

    eval_99 = KatalaSolver.evaluate_hand([{"rank": "9", "suit": 1}, {"rank": "9", "suit": 2}])
    assert eval_99["rank_score"] == 100
    assert eval_99["reward"] == 100

    eval_88 = KatalaSolver.evaluate_hand([{"rank": "8", "suit": 1}, {"rank": "8", "suit": 2}])
    assert eval_88["rank_score"] == 100
    assert eval_88["reward"] == 100

    eval_77 = KatalaSolver.evaluate_hand([{"rank": "7", "suit": 1}, {"rank": "7", "suit": 2}])
    assert eval_77["rank_score"] == 30
    assert eval_77["reward"] == 30

    eval_diff = KatalaSolver.evaluate_hand([{"rank": "A", "suit": 1}, {"rank": "7", "suit": 2}])
    assert eval_diff["rank_score"] == 10
    assert eval_diff["reward"] == 30
    assert eval_diff["pair"] is False


def test_katala_cheat_limits_by_level():
    assert KatalaSolver.get_max_cheats(1) == 0
    assert KatalaSolver.get_max_cheats(19) == 0
    assert KatalaSolver.get_max_cheats(20) == 1
    assert KatalaSolver.get_max_cheats(59) == 1
    assert KatalaSolver.get_max_cheats(60) == 2
    assert KatalaSolver.get_max_cheats(120) == 2


def test_katala_solver_decisions():
    cards_pair = [{"rank": "K", "suit": 1}, {"rank": "K", "suit": 2}]
    # При наличии пары - завершать игру
    action, idx = KatalaSolver.solve_step(cards_pair, cheats_used=0, max_cheats=2)
    assert action == "finish"

    cards_unpaired = [{"rank": "A", "suit": 1}, {"rank": "7", "suit": 2}]
    # При отсутствии пары и наличии бесплатных шульмовок - менять младшую (индекс 1)
    action, idx = KatalaSolver.solve_step(cards_unpaired, cheats_used=0, max_cheats=2)
    assert action == "reroll"
    assert idx == 1

    # При исчерпании шульмовок - завершать игру
    action, idx = KatalaSolver.solve_step(cards_unpaired, cheats_used=2, max_cheats=2)
    assert action == "finish"


@pytest.mark.asyncio
async def test_katala_play_free_daily_game_safety():
    # Мок API, запрещающий платные партии
    class MockKatalaAPI:
        def __init__(self):
            self.started = False
            self.finished = False

        async def get_state(self):
            return {"canPlayFree": True, "freeGamesLeft": 1}

        async def start_game(self, bet_type="free"):
            assert bet_type == "free"
            self.started = True
            return {
                "success": True,
                "cards": [{"rank": "Q", "suit": 1}, {"rank": "Q", "suit": 2}],
                "cheatsUsed": 0,
            }

        async def finish_game(self):
            self.finished = True
            return {"success": True, "reward": 500}

    class MockPlayerAPI:
        async def init_player(self):
            return {"player": {"level": 65}}

    k_api = MockKatalaAPI()
    p_api = MockPlayerAPI()

    res = await play_free_daily_game(katala_api=k_api, player_api=p_api, account_id=1)
    assert res["status"] == "success"
    assert k_api.started is True
    assert k_api.finished is True


@pytest.mark.asyncio
async def test_katala_last_free_play_time_24h_contract():
    """Проверка реального поля ответа /api/card/state: lastFreePlayTime (24ч кулдаун)."""
    from datetime import datetime, timedelta, timezone

    class _FakeKatala:
        def __init__(self, last_ts):
            self.last_ts = last_ts
            self.started = False

        async def get_state(self):
            return {"level": 5, "lastFreePlayTime": self.last_ts, "rerollsMax": 0}

        async def start_game(self):
            self.started = True
            return {"card1": "A_h", "card2": "A_d"}

        async def finish_game(self):
            return {"success": True, "result": {"cigarettes": 1000}}

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat().replace("+00:00", "Z")
    api_ready = _FakeKatala(old_ts)
    res_ok = await play_free_daily_game(api_ready)
    assert res_ok["success"] is True
    assert api_ready.started is True

    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    api_cd = _FakeKatala(recent_ts)
    res_cd = await play_free_daily_game(api_cd)
    assert res_cd["success"] is False
    assert res_cd["status"] == "already_played"
    assert res_cd["seconds_left"] > 70000
    assert api_cd.started is False
