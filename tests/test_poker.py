import pytest
from unittest.mock import AsyncMock

from client.api.poker import (
    evaluate_poker_hand,
    choose_best_poker_draw,
    is_free_poker_available,
    format_poker_rewards,
    play_free_poker_game,
)


def test_evaluate_poker_hand_rankings():
    pair = [{"rank": "10", "suit": "spades"}, {"rank": "10", "suit": "hearts"}, {"rank": "2", "suit": "diamonds"}, {"rank": "5", "suit": "clubs"}, {"rank": "9", "suit": "spades"}]
    two_pair = [{"rank": "10", "suit": "spades"}, {"rank": "10", "suit": "hearts"}, {"rank": "5", "suit": "diamonds"}, {"rank": "5", "suit": "clubs"}, {"rank": "9", "suit": "spades"}]
    flush = [{"rank": "2", "suit": "hearts"}, {"rank": "6", "suit": "hearts"}, {"rank": "9", "suit": "hearts"}, {"rank": "J", "suit": "hearts"}, {"rank": "A", "suit": "hearts"}]
    assert evaluate_poker_hand(pair)["rank_index"] < evaluate_poker_hand(two_pair)["rank_index"] < evaluate_poker_hand(flush)["rank_index"]


def test_choose_best_poker_draw_keeps_pair_or_flush():
    hand = [
        {"rank": "A", "suit": "spades"},
        {"rank": "A", "suit": "hearts"},
        {"rank": "3", "suit": "diamonds"},
        {"rank": "7", "suit": "clubs"},
        {"rank": "9", "suit": "spades"},
    ]
    plan = choose_best_poker_draw(hand)
    assert plan["action"] == "draw"
    # Must keep the pair of Aces (indices 0 and 1)
    assert 0 not in plan["replace_indexes"] and 1 not in plan["replace_indexes"]
    assert len(plan["replace_indexes"]) >= 2


def test_is_free_poker_available():
    assert is_free_poker_available({"chips": 1}) == (True, "ok_red_chip")
    assert is_free_poker_available({"chips": 0, "soapPlaysUsedToday": 0}) == (False, "no_red_chips")
    assert is_free_poker_available({}) == (False, "invalid_or_empty_state")


def test_format_poker_rewards():
    txt = format_poker_rewards({"pink_matches": 25})
    assert any("25" in item for item in txt)


@pytest.mark.asyncio
async def test_play_free_poker_game_blocks_when_no_chips_and_trips_guard_on_rubles_decrease():
    api = AsyncMock()
    api.get_state.return_value = {"chips": 0, "level": 5, "handActive": False}
    res_no_chip = await play_free_poker_game(poker_api=api, player_api=AsyncMock(), allow_paid=False)
    assert res_no_chip["success"] is False
    api.start_game.assert_not_called()

    # Guard trips when rubles decrease unexpectedly
    api.get_state.return_value = {"chips": 1, "level": 25, "handActive": False}
    api.start_game.return_value = {"cards": [{"rank": "A", "suit": "spades"}, {"rank": "A", "suit": "hearts"}, {"rank": "2", "suit": "diamonds"}, {"rank": "4", "suit": "clubs"}, {"rank": "9", "suit": "spades"}]}
    api.draw_cards.return_value = {"cards": [{"rank": "A", "suit": "spades"}, {"rank": "A", "suit": "hearts"}, {"rank": "A", "suit": "diamonds"}, {"rank": "4", "suit": "clubs"}, {"rank": "9", "suit": "spades"}]}
    api.finish_game.return_value = {"combination": "Сет", "rewards": {"pink_matches": 10}}

    player_api = AsyncMock()
    player_api.init_player.side_effect = [
        {"success": True, "currencies": {"rubles": 100, "soap": 10}},
        {"success": True, "currencies": {"rubles": 90, "soap": 10}},
    ]
    res_guard = await play_free_poker_game(poker_api=api, player_api=player_api, allow_paid=False)
    assert res_guard.get("status") == "guard_tripped" or res_guard.get("guard_tripped") is True
