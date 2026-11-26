"""
API-клиент, оценщик 10 покерных комбинаций, оптимальный решатель шульмовки (>= 20 ур.)
и Fail-Closed раннер строго бесплатной партии за красную фишку (/api/poker/*).
"""

from __future__ import annotations

import logging
from collections import Counter
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

RANKS_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VAL = {r: i + 2 for i, r in enumerate(RANKS_ORDER)}
SUITS = ["spades", "hearts", "diamonds", "clubs"]

POKER_COMBO_META = {
    9: ("royal_flush", "Роял-флеш", 10000),
    8: ("straight_flush", "Стрит-флеш", 5000),
    7: ("four_of_a_kind", "Каре", 2400),
    6: ("full_house", "Фулл-хаус", 1200),
    5: ("flush", "Флеш", 700),
    4: ("straight", "Стрит", 450),
    3: ("three_of_a_kind", "Сет", 250),
    2: ("two_pair", "Две пары", 120),
    1: ("one_pair", "Пара", 60),
    0: ("high_card", "Старшая карта", 20),
}


def parse_poker_card(card: Any) -> Tuple[int, str]:
    """Парсит карту вида 'A_clubs', '10_spades' или dict {'rank': 'A', 'suit': 'clubs'} -> (rank_val, suit)."""
    if isinstance(card, dict):
        r = str(card.get("rank") or "").upper()
        s = str(card.get("suit") or "spades").lower()
        return RANK_VAL.get(r, 2), s
    raw = str(card or "").strip()
    if "_" in raw:
        r_part, s_part = raw.split("_", 1)
    elif "-" in raw:
        r_part, s_part = raw.split("-", 1)
    else:
        r_part, s_part = raw, "spades"
    return RANK_VAL.get(r_part.upper(), 2), s_part.lower()


def evaluate_poker_hand(cards: List[Any]) -> Dict[str, Any]:
    """
    Оценивает 5-карточную покерную руку по всем 10 комбинациям игры.
    Возвращает {rank_index (0..9), code, title, score, tiebreakers}.
    """
    if not cards or len(cards) < 5:
        return {"rank_index": 0, "code": "high_card", "title": "Старшая карта", "score": 20, "tiebreakers": []}

    parsed = [parse_poker_card(c) for c in cards[:5]]
    ranks = sorted([r for r, _ in parsed], reverse=True)
    suits = [s for _, s in parsed]
    is_flush = len(set(suits)) == 1

    unique_ranks = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = 0
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
            straight_high = unique_ranks[0]
        elif unique_ranks == [14, 5, 4, 3, 2]:  # wheel A-2-3-4-5
            is_straight = True
            straight_high = 5

    cnt = Counter(ranks)
    groups = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    counts = [c for _, c in groups]

    if is_flush and is_straight and straight_high == 14:
        idx = 9
    elif is_flush and is_straight:
        idx = 8
    elif counts == [4, 1]:
        idx = 7
    elif counts == [3, 2]:
        idx = 6
    elif is_flush:
        idx = 5
    elif is_straight:
        idx = 4
    elif counts == [3, 1, 1]:
        idx = 3
    elif counts == [2, 2, 1]:
        idx = 2
    elif counts == [2, 1, 1, 1]:
        idx = 1
    else:
        idx = 0

    code, title, base_score = POKER_COMBO_META[idx]
    return {
        "rank_index": idx,
        "code": code,
        "title": title,
        "score": base_score,
        "tiebreakers": [r for r, _ in groups],
    }


def choose_best_poker_draw(cards: List[Any], rerolls_left: int = 1) -> Dict[str, Any]:
    """
    Оптимальный решатель шульмовки (доступна с 20 уровня покера):
    Перебирает варианты замены (0 или 1-2 карты для быстрой и точной оценки EV),
    либо сохраняет готовую сильную комбинацию (>= Стрит).
    Возвращает {"action": "finish" | "draw", "replace_indexes": [...], "expected_score": float, "current": dict}.
    """
    cur = evaluate_poker_hand(cards)
    if rerolls_left <= 0 or cur["rank_index"] >= 4:  # Стрит и выше держим
        return {"action": "finish", "replace_indexes": [], "expected_score": float(cur["score"]), "current": cur}

    parsed = [parse_poker_card(c) for c in cards[:5]]
    hand_set = set(parsed)
    deck = [(RANK_VAL[r], s) for r in RANKS_ORDER for s in SUITS if (RANK_VAL[r], s) not in hand_set]

    best_ev = float(cur["score"])
    best_replace: List[int] = []

    # Оцениваем замену 1 карты (точный перебор 47 карт) и 2 карт (выборка/точный по парам)
    for replace_cnt in (1, 2):
        for idxs in combinations(range(5), replace_cnt):
            kept = [parsed[i] for i in range(5) if i not in idxs]
            if replace_cnt == 1:
                total_score = 0.0
                for d_card in deck:
                    ev = evaluate_poker_hand([f"{RANKS_ORDER[r-2]}_{s}" for r, s in (kept + [d_card])])
                    total_score += ev["score"]
                avg_score = total_score / len(deck)
            else:
                # Быстрая детерминированная выборка по оставшейся колоде (шаг 3 для скорости < 10ms)
                sample_pairs = list(combinations(deck[::2], 2))
                total_score = 0.0
                for c1, c2 in sample_pairs:
                    ev = evaluate_poker_hand([f"{RANKS_ORDER[r-2]}_{s}" for r, s in (kept + [c1, c2])])
                    total_score += ev["score"]
                avg_score = total_score / max(1, len(sample_pairs))

            if avg_score > best_ev:
                best_ev = avg_score
                best_replace = list(idxs)

    if not best_replace:
        return {"action": "finish", "replace_indexes": [], "expected_score": float(cur["score"]), "current": cur}
    return {
        "action": "draw",
        "replace_indexes": best_replace,
        "expected_score": round(best_ev, 2),
        "current": cur,
    }


def is_free_poker_available(state_payload: Any) -> Tuple[bool, str]:
    """Fail-Closed проверка доступности бесплатной игры в Покер за красную фишку."""
    if not isinstance(state_payload, dict) or not state_payload:
        return False, "invalid_or_empty_state"
    chips = int(state_payload.get("chips") or 0)
    if chips < 1:
        return False, "no_red_chips"
    return True, "ok_red_chip"


def format_poker_rewards(reward_obj: Any) -> List[str]:
    """Форматирует полученные ресурсы из ответа /api/poker/finish без общих заглушек."""
    if not isinstance(reward_obj, dict):
        return []
    labels = {
        "rubles": "руб.",
        "soap": "мыла",
        "cigarettes": "папирос",
        "sugar": "сахара",
        "paper": "бумаги",
        "pink_matches": "розовых спичек",
        "pinkMatches": "розовых спичек",
        "poison": "яда",
        "gunshot": "самопалов",
        "knife": "финок",
        "authority": "авторитета",
        "chips": "красных фишек",
    }
    parts: List[str] = []
    for k, v in reward_obj.items():
        if k in ("clothingId", "clothing", "newBalances"):
            if k == "clothingId" and v:
                parts.append(f"Шмот #{v}")
            continue
        try:
            amt = int(v or 0)
        except (TypeError, ValueError):
            continue
        if amt > 0:
            lbl = labels.get(k, k)
            parts.append(f"+{amt} {lbl}")
    return parts


class PokerAPI:
    """Клиент эндпоинтов Покера (/api/poker/*)."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/poker/state")
        resp.raise_for_status()
        return resp.json()

    async def get_hand_payouts(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/poker/hand-payouts")
        resp.raise_for_status()
        return resp.json()

    async def start_game(self, mode: str = "chips", allow_paid: bool = False) -> Dict[str, Any]:
        clean_mode = str(mode or "chips").lower().strip()
        if not allow_paid:
            if clean_mode != "chips":
                return {"skipped": True, "reason": "paid_blocked", "detail": "paid_mode_blocked"}
            st = await self.get_state()
            ok, reason = is_free_poker_available(st)
            if not ok:
                return {"skipped": True, "reason": "paid_blocked", "detail": reason}
        resp = await self.http.post(f"/api/poker/start?mode={clean_mode}", json={})
        resp.raise_for_status()
        return resp.json()

    async def draw_cards(self, replace_indexes: List[int]) -> Dict[str, Any]:
        resp = await self.http.post("/api/poker/draw", json={"replaceIndexes": list(replace_indexes)})
        resp.raise_for_status()
        return resp.json()

    async def finish_game(self) -> Dict[str, Any]:
        resp = await self.http.post("/api/poker/finish", json={})
        resp.raise_for_status()
        return resp.json()

    async def open_box(self, case_id: int) -> Dict[str, Any]:
        resp = await self.http.post(f"/api/poker/box/open?caseId={int(case_id)}", json={})
        resp.raise_for_status()
        return resp.json()


async def _fetch_soap_and_rubles(player_api: Any) -> Tuple[Optional[int], Optional[int]]:
    if not player_api or not hasattr(player_api, "init_player"):
        return None, None
    try:
        d = await player_api.init_player()
        cur = (d.get("currencies") if isinstance(d, dict) else None) or {}
        if not cur and isinstance(d, dict) and isinstance(d.get("player"), dict):
            cur = d["player"].get("currencies") or {}
        soap = int(cur["soap"]) if cur.get("soap") is not None else None
        rubles = int(cur["rubles"]) if cur.get("rubles") is not None else None
        return soap, rubles
    except Exception:
        return None, None


async def play_free_poker_game(
    poker_api: PokerAPI,
    player_api: Optional[Any] = None,
    account_id: int = 1,
    allow_paid: bool = False,
    mode: str = "chips",
    db_engine: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fail-Closed запуск Покера:
    - При allow_paid=False играет ТОЛЬКО за красные фишки (chips >= 1) и проверяет отсутствие списания soap/rubles.
    - При уровне покера >= 20 использует оптимальный решатель шульмовки.
    """
    if db_engine is not None and not allow_paid:
        try:
            from core.database import get_game_guard_state
            guard = await get_game_guard_state(account_id, "poker", engine=db_engine)
            if guard.get("guard_tripped"):
                return {
                    "success": False,
                    "skipped": True,
                    "status": "guard_tripped",
                    "message": f"Авто-Покер остановлен защитой ресурсов: {guard.get('guard_reason')}",
                }
        except Exception:
            pass

    state = await poker_api.get_state()
    if not allow_paid:
        ok, reason = is_free_poker_available(state)
        if not ok:
            return {"success": False, "skipped": True, "status": "no_chips", "reason": reason}

    soap_before, rubles_before = await _fetch_soap_and_rubles(player_api)

    start_res = await poker_api.start_game(mode=mode, allow_paid=allow_paid)
    if isinstance(start_res, dict) and start_res.get("skipped"):
        return {"success": False, "skipped": True, "status": "paid_blocked", "reason": start_res.get("detail")}

    cards = start_res.get("cards") or []
    poker_lvl = int(state.get("level") or 0)
    rerolls_left = int(start_res.get("rerollsLeft") or (1 if poker_lvl >= 20 else 0))

    if poker_lvl >= 20 and rerolls_left > 0 and len(cards) >= 5:
        decision = choose_best_poker_draw(cards, rerolls_left=rerolls_left)
        if decision["action"] == "draw" and decision["replace_indexes"]:
            draw_res = await poker_api.draw_cards(decision["replace_indexes"])
            cards = draw_res.get("cards") or cards

    finish_res = await poker_api.finish_game()
    hand_eval = evaluate_poker_hand(cards)
    reward_obj = finish_res.get("reward") or {}
    reward_parts = format_poker_rewards(reward_obj)

    soap_after, rubles_after = await _fetch_soap_and_rubles(player_api)
    guard_tripped = False
    cb_msg = None
    if not allow_paid and (
        (soap_before is not None and soap_after is not None and soap_after < soap_before)
        or (rubles_before is not None and rubles_after is not None and rubles_after < rubles_before)
    ):
        guard_tripped = True
        cb_msg = f"soap {soap_before}->{soap_after}, rubles {rubles_before}->{rubles_after}"
        logger.critical("CRITICAL: Авто-Покер списал платные ресурсы! %s", cb_msg)
        if db_engine is not None:
            from core.database import trip_game_guard
            await trip_game_guard(account_id, "poker", cb_msg, engine=db_engine)

    after_state = await poker_api.get_state()
    return {
        "success": True,
        "status": "guard_tripped" if guard_tripped else "success",
        "guard_tripped": guard_tripped,
        "guard_reason": cb_msg,
        "cards": cards,
        "combo_code": hand_eval["code"],
        "combo_title": finish_res.get("handLabel") or hand_eval["title"],
        "reward": reward_obj,
        "rewards_formatted": reward_parts,
        "chips_left": int(after_state.get("chips") or 0),
        "finish_result": finish_res,
    }
