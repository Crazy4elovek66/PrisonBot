from datetime import datetime, timezone
from client.api.fartovy import FARTOVY_REGEN_INTERVAL_SEC, parse_fartovy_state, analyze_spin_bonuses


def test_parse_fartovy_state_calculates_exact_regen_interval():
    assert FARTOVY_REGEN_INTERVAL_SEC == 5760  # 1h 36m
    now = datetime(2026, 11, 26, 21, 0, 0, tzinfo=timezone.utc)
    payload = {
        "success": True,
        "data": {
            "state": {
                "bet": 1,
                "level": 2,
                "slotsRed": 4,
                "slotsGrass": 10,
                "energyRegenCap": 15,
                "energyTsUtc": "2026-11-26T20:34:17Z",
                "freeSpins": 2,
                "bonusActive": False,
                "bonusBoxesRemaining": 0,
            }
        },
    }
    parsed = parse_fartovy_state(payload, now_utc=now)
    assert parsed["green_matches"] == 10
    assert parsed["max_green_matches"] == 15
    assert parsed["red_matches"] == 4
    assert parsed["free_spins_left"] == 2
    assert parsed["next_green_match_at"] == "2026-11-26T22:10:17+00:00"
    assert parsed["seconds_to_next_green_match"] == 4217


def test_parse_fartovy_state_at_cap_has_no_timer():
    payload = {
        "success": True,
        "data": {
            "state": {
                "slotsGrass": 15,
                "energyRegenCap": 15,
                "energyTsUtc": "2026-11-26T20:34:17Z",
                "freeSpins": 0,
            }
        },
    }
    parsed = parse_fartovy_state(payload)
    assert parsed["next_green_match_at"] is None
    assert parsed["seconds_to_next_green_match"] == 0


def test_analyze_spin_bonuses_detects_all_4_features():
    spin_resp = {
        "data": {
            "reels": ["stalin", "top", "bell", "goat", "matches"],
            "freeSpins": 3,
            "multiplier": 2,
            "bonusActive": True,
            "bonusBoxesRemaining": 2,
            "comboId": 6,
            "hasWild": True,
        }
    }
    res = analyze_spin_bonuses(spin_resp)
    assert res["is_stalin_jackpot"] is True
    assert res["has_wild_top"] is True
    assert res["is_bell_freespins"] is True
    assert res["is_goat_bonus"] is True
