"""
Модуль для работы с мини-игрой «Катала» (карточная игра у Каталы).
Содержит API-клиент, интеллектуальный солвер комбинаций и шульмовок,
а также безопасный раннер строго бесплатной суточной партии.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# Старшинство рангов карт от старшей к младшей (1-в-1 как в bundle.js)
CARD_RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]

# Веса и награды комбинаций
COMBO_SCORES = {
    "AA": 1000,     # 1000 папирос + Наколка + CartWinAA (Джекпот)
    "KK": 700,      # 700 папирос + Наколка + CartWinKK
    "QQ": 500,      # 500 папирос + CartWinQQ
    "JJ": 200,      # 200 папирос
    "1010": 150,    # 150 папирос
    "99": 100,      # 100 авторитета
    "88": 100,      # 100 папирос
    "77": 30,       # 30 авторитета
    "default": 10,  # Разнобой (30 папирос)
}


class KatalaAPI:
    """Клиент эндпоинтов мини-игры «Катала»."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        """Получение текущего состояния Каталы (GET /api/card/state)."""
        resp = await self.http.get("/api/card/state")
        resp.raise_for_status()
        return resp.json()

    async def start_game(self) -> Dict[str, Any]:
        """Старт игры (POST /api/card/start)."""
        resp = await self.http.post("/api/card/start", json={})
        resp.raise_for_status()
        return resp.json()

    async def reroll_card(self, card_index: int) -> Dict[str, Any]:
        """
        Шульмовка / переворот выбранной карты (POST /api/card/reroll).
        card_index: 0 для card1, 1 для card2.
        """
        resp = await self.http.post("/api/card/reroll", json={"cardIndex": card_index})
        resp.raise_for_status()
        return resp.json()

    async def finish_game(self) -> Dict[str, Any]:
        """Завершение игры и сбор выигрыша (POST /api/card/finish)."""
        resp = await self.http.post("/api/card/finish", json={})
        resp.raise_for_status()
        return resp.json()

    async def get_jackpot(self) -> Dict[str, Any]:
        """Получение инфо о текущем победителе джекпота AA (GET /api/card/jackpot/aa)."""
        resp = await self.http.get("/api/card/jackpot/aa")
        resp.raise_for_status()
        return resp.json()


class KatalaSolver:
    """Интеллектуальный солвер комбинаций и шульмовок Каталы."""

    @staticmethod
    def extract_rank(card_str: str) -> str:
        """Извлечение ранга из названия карты (например, 'A_h' -> 'A', '10_d' -> '10')."""
        if not card_str:
            return ""
        clean = card_str.replace("katala_card_", "")
        parts = clean.split("_")
        return parts[0] if parts else clean

    @classmethod
    def evaluate_combination(cls, card1: str, card2: str) -> str:
        """
        Определение комбинации двух карт 1-в-1 по формуле bundle.js.
        Возвращает: 'AA', 'KK', 'QQ', 'JJ', '1010', '99', '88', '77', или 'AK', 'default' и т.д.
        """
        r1 = cls.extract_rank(card1)
        r2 = cls.extract_rank(card2)
        if not r1 or not r2:
            return "default"

        if r1 == r2:
            return "1010" if r1 == "10" else f"{r1}{r1}"

        if r1 not in CARD_RANKS or r2 not in CARD_RANKS:
            return "default"

        idx1 = CARD_RANKS.index(r1)
        idx2 = CARD_RANKS.index(r2)
        return f"{r1}{r2}" if idx1 <= idx2 else f"{r2}{r1}"

    @classmethod
    def get_combo_score(cls, combo_name: str) -> int:
        """Возвращает математический вес комбинации."""
        return COMBO_SCORES.get(combo_name, COMBO_SCORES["default"])

    @staticmethod
    def shulmovki_for_level(level: int) -> int:
        """
        Лимит бесплатных шульмовок от уровня Каталы (из bundle.js):
        < 20 -> 0
        20..59 -> 1
        >= 60 -> 2
        """
        lvl = int(level or 0)
        if lvl >= 60:
            return 2
        if lvl >= 20:
            return 1
        return 0

    @classmethod
    def get_max_cheats(cls, level: int) -> int:
        """Алиас для shulmovki_for_level."""
        return cls.shulmovki_for_level(level)

    @classmethod
    def evaluate_hand(cls, cards: List[Any]) -> Dict[str, Any]:
        """Оценка руки из двух карт: возвращает ранг, награду, признак пары и тату."""
        if not cards or len(cards) < 2:
            return {"combo": "default", "rank_score": 100, "reward": 30, "pair": False, "has_tattoo": False}
        c1 = cards[0].get("rank") if isinstance(cards[0], dict) else str(cards[0])
        c2 = cards[1].get("rank") if isinstance(cards[1], dict) else str(cards[1])
        combo = cls.evaluate_combination(c1, c2)
        score = cls.get_combo_score(combo)
        is_pair = (cls.extract_rank(c1) == cls.extract_rank(c2))
        has_tattoo = combo in ("AA", "KK")
        reward_map = {
            "AA": 1000, "KK": 700, "QQ": 500, "JJ": 200, "1010": 150,
            "99": 100, "88": 100, "77": 30, "default": 30
        }
        reward = reward_map.get(combo, 30)
        return {
            "combo": combo,
            "rank_score": score,
            "reward": reward,
            "pair": is_pair,
            "has_tattoo": has_tattoo
        }

    @classmethod
    def solve_step(cls, cards: List[Any], cheats_used: int, max_cheats: int) -> Tuple[str, Optional[int]]:
        """Определение шага солвера: 'finish' или ('reroll', card_index)."""
        c1 = cards[0].get("rank") if isinstance(cards[0], dict) else str(cards[0])
        c2 = cards[1].get("rank") if isinstance(cards[1], dict) else str(cards[1])
        shulmovki_left = max(0, max_cheats - cheats_used)
        act = cls.choose_best_action(c1, c2, shulmovki_left)
        return act["action"], act.get("card_index")

    @classmethod
    def choose_best_action(
        cls,
        card1: str,
        card2: str,
        shulmovki_left: int
    ) -> Dict[str, Any]:
        """
        Принятие оптимального решения на текущем шаге.
        Возвращает словарь:
        - {"action": "finish", "combo": combo_name} — завершить партию и забрать награду.
        - {"action": "reroll", "card_index": int, "keep_card": str} — шульмануть карту с индексом 0 или 1.
        """
        r1 = cls.extract_rank(card1)
        r2 = cls.extract_rank(card2)
        combo = cls.evaluate_combination(card1, card2)

        # 1. Если уже собрана пара (AA, KK, QQ, JJ, 1010, 99, 88, 77)
        if r1 and r2 and r1 == r2:
            return {
                "action": "finish",
                "combo": combo,
                "score": cls.get_combo_score(combo),
                "reason": f"Пара {combo} уже собрана — забираем выигрыш",
            }

        # 2. Если бесплатных шульмовок больше нет
        if shulmovki_left <= 0:
            return {
                "action": "finish",
                "combo": combo,
                "score": cls.get_combo_score("default"),
                "reason": "Шульмовки закончились — забираем выигрыш",
            }

        # 3. Разные карты и есть шульмовки:
        # Удерживаем более старшую карту, шульмуем более младшую.
        idx1 = CARD_RANKS.index(r1) if r1 in CARD_RANKS else 999
        idx2 = CARD_RANKS.index(r2) if r2 in CARD_RANKS else 999

        if idx1 <= idx2:
            # card1 старше (меньший индекс в CARD_RANKS) или равна -> держим card1 (0), крутим card2 (1)
            target_reroll = 1
            keep_card = card1
        else:
            # card2 старше -> держим card2 (1), крутим card1 (0)
            target_reroll = 0
            keep_card = card2

        return {
            "action": "reroll",
            "card_index": target_reroll,
            "keep_card": keep_card,
            "shulmovki_left": shulmovki_left,
            "reason": f"Держим старшую {keep_card}, шульмуем младшую карту (индекс {target_reroll})",
        }


async def play_free_daily_game(
    katala_api: KatalaAPI,
    force: bool = False,
    player_api: Optional[Any] = None,
    account_id: int = 1
) -> Dict[str, Any]:
    """
    Выполняет строго 1 бесплатную суточную партию у Каталы.
    Строгий запрет на любые платные ставки за рубли/сахар/мыло.
    Использует бесплатные шульмовки по уровню и забирает выигрыш.
    """
    try:
        state = await katala_api.get_state()
    except Exception as e:
        logger.warning(f"Катала: ошибка получения состояния: {e}")
        return {"success": False, "status": "error", "error": f"state_error: {e}"}

    # Проверка бесплатной попытки и точного серверного таймера отката
    from datetime import timezone as _tz
    free_available = (
        state.get("freeGameAvailable", False)
        or state.get("canPlayFree", False)
        or state.get("freeGamesLeft", 0) > 0
    )
    now_utc = datetime.now(_tz.utc)
    seconds_left: Optional[float] = None
    for cd_key in ("cooldownSec", "secondsLeft", "remainingSec", "nextFreeInSec"):
        if state.get(cd_key) is not None:
            try:
                seconds_left = max(0.0, float(state[cd_key]))
                break
            except (TypeError, ValueError):
                pass
    if seconds_left is None:
        for ts_key in ("nextFreeGameAt", "nextFreeAt", "nextGameAt", "availableAt"):
            raw_ts = state.get(ts_key)
            if raw_ts:
                try:
                    dt = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=_tz.utc)
                    seconds_left = max(0.0, (dt - now_utc).total_seconds())
                    break
                except Exception:
                    pass

    last_game_str = state.get("lastGameTime")
    if not free_available and last_game_str and not force:
        try:
            # Проверка 24ч
            last_dt = datetime.fromisoformat(str(last_game_str).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=_tz.utc)
            diff = (now_utc - last_dt).total_seconds()
            if diff < 86400:
                rem = seconds_left if seconds_left is not None else max(1.0, 86400.0 - diff)
                logger.info(f"Катала: бесплатная суточная игра еще на кулдауне (осталось {int(rem)}с)")
                return {
                    "success": False,
                    "status": "already_played",
                    "seconds_left": int(rem),
                    "message": "Бесплатная попытка у Каталы сегодня уже использована",
                }
        except Exception:
            pass

    if not free_available and not force:
        return {
            "success": False,
            "status": "already_played",
            "seconds_left": int(seconds_left) if seconds_left is not None else None,
            "message": "Бесплатная суточная игра у Каталы недоступна",
        }

    # Старт игры (строго free)
    try:
        import inspect
        if "bet_type" in inspect.signature(katala_api.start_game).parameters:
            start_res = await katala_api.start_game(bet_type="free")
        else:
            start_res = await katala_api.start_game()
    except Exception as e:
        logger.error(f"Катала: ошибка старта игры: {e}")
        return {"success": False, "status": "error", "error": f"start_error: {e}"}

    card1 = ""
    card2 = ""
    if "cards" in start_res and isinstance(start_res["cards"], list) and len(start_res["cards"]) >= 2:
        c1_item = start_res["cards"][0]
        c2_item = start_res["cards"][1]
        card1 = c1_item.get("rank") if isinstance(c1_item, dict) else str(c1_item)
        card2 = c2_item.get("rank") if isinstance(c2_item, dict) else str(c2_item)
    else:
        card1 = start_res.get("card1") or ""
        card2 = start_res.get("card2") or ""

    level = state.get("level", 0)
    if player_api:
        try:
            init_d = await player_api.init_player()
            p_inf = init_d.get("player") or init_d
            level = p_inf.get("level", level)
        except Exception:
            pass

    shulmovki_left = KatalaSolver.shulmovki_for_level(level)
    shulmovki_used = 0

    logger.info(f"Катала: старт партии, уровень={level}, карты=[{card1}, {card2}], доступно шульмовок={shulmovki_left}")

    # Цикл принятия решений
    while shulmovki_left > 0:
        decision = KatalaSolver.choose_best_action(card1, card2, shulmovki_left)
        if decision["action"] == "finish":
            break

        idx = decision["card_index"]
        try:
            reroll_res = await katala_api.reroll_card(idx)
            if "cards" in reroll_res and isinstance(reroll_res["cards"], list) and len(reroll_res["cards"]) >= 2:
                r_c1 = reroll_res["cards"][0]
                r_c2 = reroll_res["cards"][1]
                card1 = (r_c1.get("rank") if isinstance(r_c1, dict) else str(r_c1)) or card1
                card2 = (r_c2.get("rank") if isinstance(r_c2, dict) else str(r_c2)) or card2
            else:
                card1 = reroll_res.get("card1") or card1
                card2 = reroll_res.get("card2") or card2
            shulmovki_left -= 1
            shulmovki_used += 1
            logger.info(f"Катала: шульмовка карты {idx} успешна, новая рука=[{card1}, {card2}], осталось={shulmovki_left}")
        except Exception as e:
            logger.warning(f"Катала: ошибка при шульмовке карты {idx}: {e}")
            break

    # Завершение партии
    try:
        finish_res = await katala_api.finish_game()
        final_combo = KatalaSolver.evaluate_combination(card1, card2)
        reward = finish_res.get("result") or finish_res.get("reward") or finish_res
        logger.info(f"Катала: партия завершена! Итог: комбо={final_combo}, награда={reward}")
        return {
            "success": True,
            "status": "success",
            "final_hand": [card1, card2],
            "combo": final_combo,
            "hand_name": final_combo,
            "shulmovki_used": shulmovki_used,
            "reward": reward,
            "finish_result": finish_res,
            "next_cooldown_sec": int(finish_res.get("cooldownSec") or 86400),
        }
    except Exception as e:
        logger.error(f"Катала: ошибка при завершении игры: {e}")
        return {
            "success": False,
            "status": "error",
            "error": f"finish_error: {e}",
            "final_hand": [card1, card2],
        }
