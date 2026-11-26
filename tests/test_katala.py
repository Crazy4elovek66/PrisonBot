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


def test_katala_fail_closed_contract_and_7digit_iso():
    """Проверка fail-closed контракта is_free_game_available, включая 7-значные .NET ticks."""
    from datetime import datetime, timezone
    from client.api.katala import is_free_game_available

    now = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Реальный ответ сервера с 7-значными микросекундами (< 24ч назад) -> строго False
    ok, reason = is_free_game_available(
        {
            "level": 7,
            "progress": 3,
            "lastFreePlayTime": "2026-11-26T03:57:00.5039281Z",
            "totalPlays": 63,
            "rerollsMax": 0,
        },
        now_utc=now,
    )
    assert ok is False
    assert "cooldown_24h" in reason

    # 2. Прошло >= 24ч с 7-значным timestamp -> True
    ok2, reason2 = is_free_game_available(
        {
            "level": 7,
            "progress": 3,
            "lastFreePlayTime": "2026-11-25T03:57:00.5039281Z",
            "totalPlays": 63,
        },
        now_utc=now,
    )
    assert ok2 is True
    assert reason2 == "ok_24h_elapsed"

    # 3. Платная игра (cost > 0 / freeGameAvailable=False) -> False
    assert is_free_game_available({"cost": 1, "rubles": 1}, now_utc=now)[0] is False
    assert is_free_game_available({"freeGameAvailable": False}, now_utc=now)[0] is False
    assert is_free_game_available({"canPlayFree": False}, now_utc=now)[0] is False

    # 4. Битый/пустой/неизвестный ответ -> False (fail-closed)
    assert is_free_game_available(None, now_utc=now)[0] is False
    assert is_free_game_available({}, now_utc=now)[0] is False
    assert is_free_game_available({"unexpected": 123}, now_utc=now)[0] is False
    assert is_free_game_available({"lastFreePlayTime": "not-a-date"}, now_utc=now)[0] is False


@pytest.mark.asyncio
async def test_katala_api_start_game_blocks_paid_without_post():
    """KatalaAPI.start_game(allow_paid=False) не отправляет POST /api/card/start, если игра платная."""
    from datetime import datetime, timezone

    class _FakeResp:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    class _FakeHttp:
        def __init__(self):
            self.post_called = False
        async def get(self, url):
            recent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.1234567Z")
            return _FakeResp({"level": 7, "lastFreePlayTime": recent, "totalPlays": 10})
        async def post(self, url, json=None):
            self.post_called = True
            return _FakeResp({"success": True})

    http = _FakeHttp()
    api = KatalaAPI(http)
    res = await api.start_game(allow_paid=False)
    assert res["skipped"] is True
    assert res["reason"] == "paid_blocked"
    assert http.post_called is False


@pytest.mark.asyncio
async def test_katala_persistent_msk_limit_and_rubles_circuit_breaker(tmp_path):
    """Персистентный лимит 1 раз в день по МСК и Circuit Breaker при списании рублей."""
    from core.database import get_engine, init_db, get_katala_guard_state, reset_katala_rubles_guard
    from core.models import Account

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'katala_test.db'}"
    engine = get_engine(db_url)
    await init_db(engine)

    class _MockKatala:
        def __init__(self):
            self.starts = 0
        async def get_state(self):
            return {"canPlayFree": True, "freeGamesLeft": 1, "level": 10}
        async def start_game(self, allow_paid=False):
            self.starts += 1
            return {"card1": "A_h", "card2": "A_d"}
        async def finish_game(self):
            return {"success": True, "result": {"cigarettes": 1000}}

    class _MockPlayer:
        def __init__(self, rubles_seq):
            self.rubles_seq = list(rubles_seq)
        async def init_player(self):
            r = self.rubles_seq.pop(0) if len(self.rubles_seq) > 1 else self.rubles_seq[0]
            return {"player": {"level": 10}, "currencies": {"rubles": r}}

    # 1. Первый запуск проходит успешно и фиксирует day_msk в БД
    k1 = _MockKatala()
    p1 = _MockPlayer([100, 100, 100])
    r1 = await play_free_daily_game(k1, player_api=p1, account_id=1, allow_paid=False, db_engine=engine)
    assert r1["success"] is True
    assert k1.starts == 1

    # 2. Повторный запуск в те же сутки МСК блокируется БД даже при canPlayFree=True в моке
    r2 = await play_free_daily_game(k1, player_api=p1, account_id=1, allow_paid=False, db_engine=engine)
    assert r2["success"] is False
    assert r2["reason"] == "already_played_today_msk"
    assert k1.starts == 1

    # 3. Проверка Circuit Breaker при уменьшении рублей
    db_url2 = f"sqlite+aiosqlite:///{tmp_path / 'katala_cb.db'}"
    engine2 = get_engine(db_url2)
    await init_db(engine2)
    k2 = _MockKatala()
    p2 = _MockPlayer([200, 200, 199])  # списался 1 рубль!
    await play_free_daily_game(k2, player_api=p2, account_id=1, allow_paid=False, db_engine=engine2)
    guard = await get_katala_guard_state(account_id=1, engine=engine2)
    assert guard["rubles_guard_tripped"] is True

    # Следующий запуск блокируется Circuit Breaker до явного сброса
    r_blocked = await play_free_daily_game(k2, player_api=p2, account_id=1, allow_paid=False, db_engine=engine2)
    assert r_blocked["status"] == "guard_tripped"
    await reset_katala_rubles_guard(account_id=1, engine=engine2)
    assert (await get_katala_guard_state(account_id=1, engine=engine2))["rubles_guard_tripped"] is False
    await engine.dispose()
    await engine2.dispose()
