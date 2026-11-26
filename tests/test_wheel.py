from client.api.wheel import parse_wheel_state


def test_parse_wheel_state_extracts_tickets_matches_jackpot_and_winner():
    raw = {
        "tickets": 2,
        "blueMatches": 14,
        "jackpotBank": 6350,
        "wheelLevel": 3,
        "wheelXp": 45,
        "wheelXpToNext": 100,
        "lastJackpotWinner": {"name": "Пахан", "amount": 5000},
        "tattooSet": {"id": 12, "name": "Перстни"},
        "slots": [{"id": 1, "title": "Синие спички", "amount": 5}],
    }
    parsed = parse_wheel_state(raw)
    assert parsed["tickets"] == 2
    assert parsed["blue_matches"] == 14
    assert parsed["jackpot_rubles"] == 6350
    assert parsed["wheel_level"] == 3
    assert parsed["last_winner"]["name"] == "Пахан"
    assert len(parsed["slots"]) == 1
