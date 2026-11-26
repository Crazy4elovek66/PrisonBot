"""
Модуль для работы с мини-игрой «Катала» (карточная игра у Каталы).
Содержит API-клиент, интеллектуальный солвер комбинаций и шульмовок,
а также безопасный раннер строго бесплатной суточной партии.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import re
from datetime import datetime, timezone
import httpx

from core.config import MSK_TZ

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


def _parse_iso_utc_safe(raw: Any) -> Optional[datetime]:
    """
    Безопасный парсинг ISO-8601 даты (в т.ч. .NET ticks с 7 цифрами дробных секунд на Python 3.10).
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # Нормализуем дробную часть секунд до 6 цифр для совместимости с Python <= 3.10
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _extract_paid_cost(payload: Dict[str, Any]) -> float:
    """Извлекает стоимость игры в рублях/валюте, если сервер передал цену."""
    for key in ("price", "cost", "rublesCost", "betRubles", "entryCost", "rubles"):
        val = payload.get(key)
        if val is not None and not isinstance(val, bool):
            try:
                num = float(val)
                if num > 0:
                    return num
            except (TypeError, ValueError):
                return 1.0
    return 0.0


def is_free_game_available(
    status_payload: Any,
    now_utc: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    Fail-Closed проверка доступности бесплатной игры у Каталы.
    Возвращает (True, reason) ТОЛЬКО при явном подтверждении бесплатности и цене 0.
    """
    if not isinstance(status_payload, dict) or not status_payload:
        return False, "invalid_or_empty_state"

    if status_payload.get("freeGameAvailable") is False or status_payload.get("canPlayFree") is False:
        return False, "explicit_free_disabled"

    free_games_left = status_payload.get("freeGamesLeft")
    if free_games_left is not None:
        try:
            if int(free_games_left) <= 0 and status_payload.get("freeGameAvailable") is not True:
                return False, "no_free_games_left"
        except (TypeError, ValueError):
            return False, "invalid_free_games_left"

    explicit_free = (
        status_payload.get("freeGameAvailable") is True
        or status_payload.get("canPlayFree") is True
        or (isinstance(free_games_left, (int, float)) and free_games_left > 0)
    )

    paid_cost = _extract_paid_cost(status_payload)
    if paid_cost > 0 and not explicit_free:
        return False, f"non_zero_cost_{paid_cost}"

    ref_now = now_utc or datetime.now(timezone.utc)
    if ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=timezone.utc)

    for cd_key in ("cooldownSec", "secondsLeft", "remainingSec", "nextFreeInSec"):
        if status_payload.get(cd_key) is not None:
            try:
                cd_val = float(status_payload[cd_key])
                if cd_val > 0:
                    return False, f"cooldown_{int(cd_val)}s"
            except (TypeError, ValueError):
                return False, f"invalid_{cd_key}"

    for ts_key in ("nextFreeGameAt", "nextFreeAt", "nextGameAt", "availableAt"):
        raw_ts = status_payload.get(ts_key)
        if raw_ts:
            dt = _parse_iso_utc_safe(str(raw_ts))
            if dt is None:
                return False, f"unparseable_{ts_key}"
            rem = (dt - ref_now).total_seconds()
            if rem > 0:
                return False, f"next_free_in_future_{int(rem)}s"

    last_game_str = (
        status_payload.get("lastFreePlayTime")
        or status_payload.get("lastGameTime")
        or status_payload.get("lastFreeGameAt")
        or status_payload.get("lastPlayTime")
    )
    if last_game_str:
        last_dt = _parse_iso_utc_safe(str(last_game_str))
        if last_dt is None:
            return False, "unparseable_last_free_play_time"
        diff = (ref_now - last_dt).total_seconds()
        if diff < 86400:
            rem = max(1, int(86400.0 - diff))
            return False, f"cooldown_24h_{rem}s"
        if paid_cost > 0:
            return False, f"non_zero_cost_{paid_cost}"
        return True, "ok_24h_elapsed"

    if explicit_free and paid_cost == 0:
        return True, "ok_explicit_free"

    # Первый запуск на аккаунте: lastFreePlayTime еще null, но ответ /api/card/state валиден и totalPlays == 0
    if (
        "lastFreePlayTime" in status_payload
        and status_payload.get("lastFreePlayTime") in (None, "")
        and status_payload.get("totalPlays") == 0
        and status_payload.get("level") is not None
        and paid_cost == 0
    ):
        return True, "ok_first_ever_game"

    return False, "missing_free_confirmation"


class KatalaAPI:
    """Клиент эндпоинтов мини-игры «Катала»."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        """Получение текущего состояния Каталы (GET /api/card/state)."""
        resp = await self.http.get("/api/card/state")
        resp.raise_for_status()
        return resp.json()

    async def start_game(self, allow_paid: bool = False) -> Dict[str, Any]:
        """
        Старт игры (POST /api/card/start).
        При allow_paid=False обязательно проверяет /api/card/state и блокирует любой платный старт.
        """
        if not allow_paid:
            state = await self.get_state()
            ok, reason = is_free_game_available(state)
            if not ok:
                logger.warning(f"Катала: старт заблокирован (allow_paid=False, reason={reason})")
                return {"skipped": True, "reason": "paid_blocked", "detail": reason}
        resp = await self.http.post("/api/card/start", json={})
        resp.raise_for_status()
        return resp.json()

    async def reroll_card(self, card_index: int, allow_paid: bool = False) -> Dict[str, Any]:
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


async def _fetch_rubles_safe(player_api: Any) -> Optional[int]:
    """Безопасно получает текущий баланс рублей игрока."""
    if not player_api or not hasattr(player_api, "init_player"):
        return None
    try:
        init_d = await player_api.init_player()
        if not isinstance(init_d, dict):
            return None
        cur = init_d.get("currencies")
        if isinstance(cur, dict) and cur.get("rubles") is not None:
            return int(cur["rubles"])
        p_inf = init_d.get("player")
        if isinstance(p_inf, dict):
            p_cur = p_inf.get("currencies")
            if isinstance(p_cur, dict) and p_cur.get("rubles") is not None:
                return int(p_cur["rubles"])
            if p_inf.get("rubles") is not None:
                return int(p_inf["rubles"])
        if init_d.get("rubles") is not None:
            return int(init_d["rubles"])
    except Exception:
        return None
    return None


async def play_free_daily_game(
    katala_api: KatalaAPI,
    force: bool = False,
    player_api: Optional[Any] = None,
    account_id: int = 1,
    allow_paid: bool = False,
    db_engine: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Выполняет строго 1 бесплатную суточную партию у Каталы (Fail-Closed).
    Строгий запрет на любые платные ставки за рубли/сахар/мыло.
    """
    now_utc = datetime.now(timezone.utc)
    today_msk = now_utc.astimezone(MSK_TZ).strftime("%Y-%m-%d")

    # 1. Персистентный лимит МСК + Circuit Breaker в SQLite
    if db_engine is not None:
        try:
            from core.database import get_katala_guard_state
            guard = await get_katala_guard_state(account_id=account_id, engine=db_engine)
            if guard.get("rubles_guard_tripped"):
                logger.warning("Катала: заблокирована сработавшим Circuit Breaker по рублям (%s)", guard.get("guard_reason"))
                return {
                    "success": False,
                    "skipped": True,
                    "status": "guard_tripped",
                    "reason": "rubles_guard_tripped",
                    "message": f"Авто-Катала остановлена защитой рублей: {guard.get('guard_reason') or 'обнаружено списание'}",
                }
            if guard.get("last_free_day_msk") == today_msk and not allow_paid:
                logger.info(f"Катала: суточный лимит МСК ({today_msk}) уже использован в БД")
                return {
                    "success": False,
                    "skipped": True,
                    "status": "already_played",
                    "reason": "already_played_today_msk",
                    "message": "Бесплатная суточная игра у Каталы уже сыграна сегодня (МСК)",
                }
        except Exception as db_err:
            logger.warning(f"Катала: ошибка чтения guard_state из БД: {db_err}")

    try:
        state = await katala_api.get_state()
    except Exception as e:
        logger.warning(f"Катала: ошибка получения состояния: {e}")
        return {"success": False, "skipped": True, "status": "error", "error": f"state_error: {e}"}

    ok, reason = is_free_game_available(state, now_utc=now_utc)
    seconds_left: Optional[int] = None
    if not ok:
        m_cd = re.search(r"_(\d+)s$", reason)
        if m_cd:
            seconds_left = int(m_cd.group(1))
        elif isinstance(state, dict):
            for cd_key in ("cooldownSec", "secondsLeft", "remainingSec", "nextFreeInSec"):
                if state.get(cd_key) is not None:
                    try:
                        val = int(float(state[cd_key]))
                        if val > 0:
                            seconds_left = val
                            break
                    except (TypeError, ValueError):
                        pass
        if not allow_paid:
            logger.info(f"Катала пропущена (fail-closed): reason={reason}, seconds_left={seconds_left}")
            return {
                "success": False,
                "skipped": True,
                "status": "already_played" if ("cooldown" in reason or "future" in reason or "disabled" in reason or "no_free" in reason) else "paid_blocked",
                "reason": reason,
                "seconds_left": seconds_left,
                "message": "Бесплатная суточная попытка у Каталы недоступна или уже использована",
            }

    rubles_before = await _fetch_rubles_safe(player_api)

    # Старт игры (строго allow_paid=False по умолчанию)
    try:
        import inspect
        sig_params = inspect.signature(katala_api.start_game).parameters
        if "allow_paid" in sig_params:
            start_res = await katala_api.start_game(allow_paid=allow_paid)
        elif "bet_type" in sig_params:
            start_res = await katala_api.start_game(bet_type="free")
        else:
            start_res = await katala_api.start_game()
    except Exception as e:
        logger.error(f"Катала: ошибка старта игры: {e}")
        return {"success": False, "status": "error", "error": f"start_error: {e}"}

    if isinstance(start_res, dict) and start_res.get("skipped"):
        return {
            "success": False,
            "skipped": True,
            "status": "paid_blocked",
            "reason": start_res.get("detail") or start_res.get("reason") or "paid_blocked",
            "message": "Старт Каталы заблокирован защитой от траты рублей",
        }

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

    # Цикл принятия решений (только бесплатные шульмовки)
    while shulmovki_left > 0:
        decision = KatalaSolver.choose_best_action(card1, card2, shulmovki_left)
        if decision["action"] == "finish":
            break

        idx = decision["card_index"]
        try:
            reroll_res = await katala_api.reroll_card(idx)
            if isinstance(reroll_res, dict) and reroll_res.get("skipped"):
                break
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

        rubles_after = await _fetch_rubles_safe(player_api)
        logger.info(
            f"Katala free check -> status={reason}, rubles_before={rubles_before} -> rubles_after={rubles_after}"
        )

        # Circuit Breaker: неожиданное списание рублей
        if rubles_before is not None and rubles_after is not None and rubles_after < rubles_before:
            lost = rubles_before - rubles_after
            cb_reason = f"rubles decreased {rubles_before} -> {rubles_after} (-{lost})"
            logger.critical(f"CRITICAL: Катала списала рубли! {cb_reason}; raw_finish={finish_res}")
            if db_engine is not None:
                try:
                    from core.database import trip_katala_rubles_guard
                    from core.drop_parser import DropParser
                    await trip_katala_rubles_guard(account_id=account_id, reason=cb_reason, engine=db_engine)
                    await DropParser.save_notification(
                        account_id,
                        {
                            "category": "other",
                            "event_type": "katala_rubles_guard",
                            "title": "🚨 Катала заблокирована: списание рублей",
                            "body": f"Зафиксировано списание {lost} руб. ({rubles_before} → {rubles_after}). Авто-Катала остановлена.",
                            "meta_json": {"rubles_before": rubles_before, "rubles_after": rubles_after},
                        },
                        db_engine,
                    )
                except Exception as cb_err:
                    logger.error(f"Не удалось записать trip_katala_rubles_guard: {cb_err}")
        elif db_engine is not None:
            try:
                from core.database import mark_katala_free_played_today
                await mark_katala_free_played_today(
                    account_id=account_id,
                    day_msk=today_msk,
                    last_play_at=now_utc.isoformat(),
                    engine=db_engine,
                )
            except Exception as mk_err:
                logger.warning(f"Не удалось сохранить отметку дня Каталы: {mk_err}")

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
            "rubles_before": rubles_before,
            "rubles_after": rubles_after,
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
