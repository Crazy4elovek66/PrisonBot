"""
API-клиент и парсер игрового автомата «Фартовый» 5x3 (/api/slots-game/*).
Поддерживает точный таймер зеленых спичек (5760с = 1ч 36м), защиту от траты рублей
и обработку всех 4 бонусов: «Отец народов», «Топ» (Wild), «Колокол воли» (фриспины) и «Козёл».
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Точный интервал восстановления 1 зеленой спички из bundle.js: s + 576e4 - Date.now()
FARTOVY_REGEN_INTERVAL_SEC = 5760


def _parse_iso_utc(raw: Any) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_fartovy_state(raw_payload: Any, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """Точный парсер состояния Фартового из GET /api/slots-game/info."""
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    st = data.get("state") if isinstance(data.get("state"), dict) else data

    green = int(st.get("slotsGrass") or 0)
    cap = int(st.get("energyRegenCap") or 15)
    red = int(st.get("slotsRed") or 0)
    orange = int(st.get("slotsOrenge") or st.get("slotsOrange") or 0)
    free_spins = int(st.get("freeSpins") or 0)
    bonus_active = bool(st.get("bonusActive"))
    bonus_boxes_rem = int(st.get("bonusBoxesRemaining") or 0)

    ref_now = now_utc or datetime.now(timezone.utc)
    if ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=timezone.utc)

    next_regen_iso: Optional[str] = None
    sec_to_next: int = 0
    if green < cap:
        ts_dt = _parse_iso_utc(st.get("energyTsUtc"))
        if ts_dt is not None:
            next_dt = ts_dt + timedelta(seconds=FARTOVY_REGEN_INTERVAL_SEC)
            # Если прошло больше 1 интервала, сдвигаем до ближайшего будущего тика
            while next_dt <= ref_now and green < cap:
                next_dt += timedelta(seconds=FARTOVY_REGEN_INTERVAL_SEC)
            next_regen_iso = next_dt.isoformat()
            sec_to_next = max(0, int((next_dt - ref_now).total_seconds()))

    return {
        "level": int(st.get("level") or 1),
        "exp": int(st.get("exp") or 0),
        "exp_in_level": int(st.get("expInLevel") or 0),
        "exp_to_next": int(st.get("expToNextLevel") or 0),
        "bet": int(st.get("bet") or 1),
        "green_matches": green,
        "max_green_matches": cap,
        "regen_interval_sec": FARTOVY_REGEN_INTERVAL_SEC,
        "energy_ts_utc": st.get("energyTsUtc"),
        "next_green_match_at": next_regen_iso,
        "seconds_to_next_green_match": sec_to_next,
        "red_matches": red,
        "orange_matches": orange,
        "last_red_win": int(st.get("lastRedWin") or 0),
        "free_spins_left": free_spins,
        "bonus_active": bonus_active,
        "bonus_boxes_remaining": bonus_boxes_rem,
        "bonus_boxes": st.get("bonusBoxes"),
        "rubles": int(st.get("rubles") or 0),
        "combo_top": data.get("comboTop") or [],
    }


def analyze_spin_bonuses(spin_res: Any) -> Dict[str, Any]:
    """Определяет выпавшие бонусы (Отец народов, Топ/Wild, Колокол воли, Козёл) из ответа спина."""
    raw = spin_res if isinstance(spin_res, dict) else {}
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    st = data.get("state") if isinstance(data.get("state"), dict) else {}

    win_red = int(data.get("win") or data.get("redWin") or data.get("winRed") or 0)
    free_spins = int(st.get("freeSpins") or data.get("freeSpins") or 0)
    bonus_active = bool(st.get("bonusActive") or data.get("bonusActive"))
    combo_id = data.get("comboId")
    lines = data.get("winningLines") or data.get("lines") or []
    reels = data.get("reels") or data.get("grid") or data.get("matrix") or []

    has_wild = bool(data.get("hasWild") or any(isinstance(ln, dict) and ln.get("hasWild") for ln in lines))
    is_stalin = bool(
        data.get("isStalinJackpot")
        or combo_id == 6
        or win_red >= 1000
    )

    return {
        "win_red": win_red,
        "free_spins_left": free_spins,
        "bonus_active": bonus_active,
        "has_wild_top": has_wild,
        "is_bell_freespins": free_spins > 0,
        "is_goat_bonus": bonus_active,
        "is_stalin_jackpot": is_stalin,
        "reels": reels,
        "winning_lines": lines,
    }


class FartovyAPI:
    """Клиент эндпоинтов Фартового (/api/slots-game/*)."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/slots-game/info")
        resp.raise_for_status()
        return resp.json()

    async def spin(self, bet: int = 1, allow_paid: bool = False) -> Dict[str, Any]:
        if not allow_paid:
            info = await self.get_state()
            parsed = parse_fartovy_state(info)
            if parsed["green_matches"] < 1 and parsed["free_spins_left"] < 1:
                return {"skipped": True, "reason": "no_green_matches"}
        resp = await self.http.post("/api/slots-game/spin", json={})
        resp.raise_for_status()
        return resp.json()

    async def open_bonus_box(self, side: str = "left", super_game: bool = True) -> Dict[str, Any]:
        resp = await self.http.post(
            "/api/slots-game/bonus/open-box",
            json={"superGame": bool(super_game), "side": side},
        )
        resp.raise_for_status()
        return resp.json()

    async def open_chest(self, chest_id: int) -> Dict[str, Any]:
        resp = await self.http.post("/api/slots-game/open-chest", json={"chestId": int(chest_id)})
        resp.raise_for_status()
        return resp.json()
