"""
API-клиент и парсер «Колеса фортуны» (/api/wheel/*).
Строгий запрет на автоматическую покупку билетов за рубли.
"""

from __future__ import annotations

from typing import Any, Dict


def parse_wheel_state(raw_payload: Any) -> Dict[str, Any]:
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    return {
        "tickets": int(raw.get("tickets") or 0),
        "blue_matches": int(raw.get("blueMatches") or 0),
        "jackpot_rubles": int(raw.get("jackpotBank") or 0),
        "ticket_price_rubles": 10,
        "wheel_level": int(raw.get("wheelLevel") or 1),
        "wheel_xp": int(raw.get("wheelXp") or 0),
        "wheel_xp_to_next": int(raw.get("wheelXpToNext") or 100),
        "rubles": int(raw.get("rubles") or 0),
        "has_pending_prize": bool(raw.get("hasPendingPrize")),
        "pending": raw.get("pending"),
        "last_winner": raw.get("lastJackpotWinner"),
        "tattoo_set": raw.get("tattooSet"),
        "slots": raw.get("slots") or [],
    }


class WheelAPI:
    """Клиент эндпоинтов Колеса фортуны (/api/wheel/*)."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/wheel/state")
        resp.raise_for_status()
        return resp.json()

    async def spin(self, allow_buy: bool = False) -> Dict[str, Any]:
        if not allow_buy:
            st = parse_wheel_state(await self.get_state())
            if st["tickets"] < 1:
                return {"skipped": True, "reason": "no_tickets"}
        resp = await self.http.post("/api/wheel/spin", json={})
        resp.raise_for_status()
        return resp.json()

    async def open_case(self, case_id: int) -> Dict[str, Any]:
        resp = await self.http.post("/api/wheel/open-case", json={"caseId": int(case_id)})
        resp.raise_for_status()
        return resp.json()
