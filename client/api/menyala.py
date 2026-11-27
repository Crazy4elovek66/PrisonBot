"""
Модуль «Меняла и Акции» (/api/smuggling/*):
приезд каждую пятницу, 4 акционных набора (Бесплатный, Пацанский, Блатной, Авторитетный),
обмен ресурсов (сахар/папиросы -> рубли/бумага) и однократное оповещение о приезде в Web + TG.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MSK_TZ = timezone(timedelta(hours=3))

PROMO_CATALOG: Tuple[Tuple[str, str, str, str], ...] = (
    ("F", "free", "free", "Бесплатный"),
    ("P", "pacan", "pacan", "Пацанский"),
    ("B", "blat", "blat", "Блатной"),
    ("A", "avtoritet", "avtoritet", "Авторитетный"),
)

PROMO_ID_TO_CODE: Dict[str, str] = {}
for _code, _pid, _tier, _ in PROMO_CATALOG:
    PROMO_ID_TO_CODE[_code] = _code
    PROMO_ID_TO_CODE[_code.lower()] = _code
    PROMO_ID_TO_CODE[_pid] = _code

LOOT_KEY_MAP: Dict[str, Tuple[str, str, str]] = {
    "rubles": ("rubles", "Рубли", "assets/icons/rubles.webp"),
    "sugar": ("sugar", "Сахар", "assets/icons/sugar.webp"),
    "cigarettes": ("cigarettes", "Папиросы", "assets/icons/cigarettes.webp"),
    "soap": ("soap", "Мыло", "assets/icons/soap.webp"),
    "paper": ("paper", "Бумага", "assets/icons/paper.webp"),
    "chips": ("chips", "Фишки покера", "assets/icons/poker_chip_red.webp"),
    "pokerChips": ("chips", "Фишки покера", "assets/icons/poker_chip_red.webp"),
    "stew": ("stew", "Тушенка", "assets/icons/stew.webp"),
    "stewBalance": ("stew", "Тушенка", "assets/icons/stew.webp"),
    "poisonCount": ("poison", "Яд", "assets/icons/poison.webp"),
    "poison": ("poison", "Яд", "assets/icons/poison.webp"),
    "gunshotCount": ("gunshot", "Самопал", "assets/icons/gunshot.webp"),
    "gunshot": ("gunshot", "Самопал", "assets/icons/gunshot.webp"),
    "knifeCount": ("knife", "Финка", "assets/icons/knife.webp"),
    "knife": ("knife", "Финка", "assets/icons/knife.webp"),
    "chefir": ("chefir", "Чифир", "assets/icons/energy.webp"),
}


def _parse_iso_ts(raw_ts: Any) -> Optional[int]:
    if raw_ts is None or raw_ts == "" or isinstance(raw_ts, bool):
        return None
    if isinstance(raw_ts, (int, float)):
        v = int(raw_ts)
        return v // 1000 if v > 10_000_000_000 else v
    s = str(raw_ts).strip()
    if s.isdigit():
        v = int(s)
        return v // 1000 if v > 10_000_000_000 else v
    try:
        import re
        s = re.sub(r"\.(\d{6})\d+", r".\1", s)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.astimezone(timezone.utc).timestamp())
    except Exception:
        return None


def _format_msk_label(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(MSK_TZ)
        return dt.strftime("%d.%m %H:%M МСК")
    except Exception:
        return None


def _next_friday_arrival_ts(now_utc: datetime) -> int:
    """Ближайшая пятница 00:00 МСК (четверг 21:00 UTC)."""
    now_msk = now_utc.astimezone(MSK_TZ)
    days_ahead = (4 - now_msk.weekday()) % 7
    target_msk = (now_msk + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    if target_msk <= now_msk:
        target_msk += timedelta(days=7)
    return int(target_msk.astimezone(timezone.utc).timestamp())


def parse_menyala_state(raw_payload: Any, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    if now_utc is not None:
        ref_utc = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
    else:
        try:
            from client.http_client import get_game_now_ts
            ref_utc = datetime.fromtimestamp(get_game_now_ts(), tz=timezone.utc)
        except Exception:
            ref_utc = datetime.now(timezone.utc)
    server_now_ts = int(ref_utc.timestamp())

    is_active = bool(raw.get("active"))
    event = raw.get("event") if isinstance(raw.get("event"), dict) else {}
    offers_claimed = raw.get("offers") if isinstance(raw.get("offers"), list) else []
    prices = raw.get("prices") if isinstance(raw.get("prices"), dict) else {}
    offers_loot = event.get("offersLoot") if isinstance(event.get("offersLoot"), dict) else {}
    user_obj = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    balances = user_obj.get("balances") if isinstance(user_obj.get("balances"), dict) else {}

    cycle_id = str(event.get("eventId") or "")
    if not cycle_id and event.get("startedAtUtc"):
        cycle_id = str(event.get("startedAtUtc"))[:10]
    if not cycle_id and is_active:
        cycle_id = ref_utc.astimezone(MSK_TZ).strftime("%Y-%m-%d")

    departure_ts = _parse_iso_ts(event.get("endsAtUtc")) if is_active else None
    next_arrival_ts = _parse_iso_ts(raw.get("nextStartAtUtc"))
    if not is_active and next_arrival_ts is None:
        next_arrival_ts = _next_friday_arrival_ts(ref_utc)

    promos: List[Dict[str, Any]] = []
    if is_active:
        for idx, (code, pid, tier, title) in enumerate(PROMO_CATALOG):
            raw_price = prices.get(code)
            price_rubles = int(raw_price or 0) if raw_price is not None else (0 if code == "F" else 0)
            claimed = bool(offers_claimed[idx]) if idx < len(offers_claimed) else False
            loot_dict = offers_loot.get(code) if isinstance(offers_loot.get(code), dict) else {}
            items: List[Dict[str, Any]] = []
            for lk, lv in loot_dict.items():
                try:
                    amt = int(lv or 0)
                except (TypeError, ValueError):
                    amt = 0
                if amt <= 0:
                    continue
                mapped = LOOT_KEY_MAP.get(lk, (lk, lk, "assets/icons/stash.webp"))
                items.append({
                    "key": mapped[0],
                    "label": mapped[1],
                    "amount": amt,
                    "icon": mapped[2],
                })
            promos.append({
                "id": pid,
                "code": code,
                "tier": tier,
                "title": title,
                "price_rubles": price_rubles,
                "is_free": price_rubles <= 0,
                "claimed": claimed,
                "items": items,
            })

    variant = str(event.get("variant") or "Sugar")
    rates = event.get("rates") if isinstance(event.get("rates"), dict) else {}
    exchanges: List[Dict[str, Any]] = []
    if is_active:
        from_res = "cigarettes" if variant.lower().startswith("cig") else "sugar"
        if from_res == "sugar":
            r_rub = int(rates.get("sugarPerRuble") or 7600)
            r_pap = int(rates.get("sugarPerPaper") or 1500)
        else:
            r_rub = int(rates.get("cigsPerRuble") or 10000)
            r_pap = int(rates.get("cigsPerPaper") or 2000)
        from_bal = int(balances.get(from_res) or 0)
        exchanges = [
            {
                "id": f"{from_res}_to_rubles",
                "from_resource": from_res,
                "to_resource": "rubles",
                "rate_from": r_rub,
                "rate_to": 1,
                "available": from_bal >= r_rub,
                "max_to": from_bal // max(1, r_rub),
                "from_balance": from_bal,
            },
            {
                "id": f"{from_res}_to_paper",
                "from_resource": from_res,
                "to_resource": "paper",
                "rate_from": r_pap,
                "rate_to": 1,
                "available": from_bal >= r_pap,
                "max_to": from_bal // max(1, r_pap),
                "from_balance": from_bal,
            },
        ]

    remaining_sec = 0
    if is_active and departure_ts:
        remaining_sec = max(0, int(departure_ts) - server_now_ts)
    elif not is_active and next_arrival_ts:
        remaining_sec = max(0, int(next_arrival_ts) - server_now_ts)

    return {
        "is_active": is_active,
        "cycle_id": cycle_id,
        "variant": variant,
        "server_now_ts": server_now_ts,
        "next_arrival_ts": next_arrival_ts,
        "departure_ts": departure_ts,
        "next_arrival_msk": _format_msk_label(next_arrival_ts),
        "departure_msk": _format_msk_label(departure_ts),
        "remaining_sec": remaining_sec,
        "promos": promos,
        "exchanges": exchanges,
        "balances": balances,
    }


class MenyalaAPI:
    """Клиент игровых эндпоинтов Менялы (/api/smuggling/*)."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/smuggling/state")
        resp.raise_for_status()
        return resp.json()

    async def get_menyala_state(self) -> Dict[str, Any]:
        raw = await self.get_state()
        return parse_menyala_state(raw)

    async def claim_or_buy_promo(self, promo_id: str) -> Dict[str, Any]:
        code = PROMO_ID_TO_CODE.get(str(promo_id or "").strip(), "")
        if not code:
            raise ValueError(f"Unknown promo_id: {promo_id}")
        if code == "F":
            resp = await self.http.post("/api/smuggling/claim", json={})
        else:
            resp = await self.http.post("/api/smuggling/buy", json={"code": code})
        resp.raise_for_status()
        return resp.json()

    async def exchange_resource(self, exchange_id: str, amount: int, rate_from: Optional[int] = None) -> Dict[str, Any]:
        ex_str = str(exchange_id or "").lower()
        if "paper" in ex_str:
            to_key = "paper"
        elif "ruble" in ex_str:
            to_key = "rubles"
        else:
            raise ValueError(f"Unsupported exchange_id: {exchange_id}")

        desired_to = max(1, int(amount or 1))
        if rate_from is None:
            st = await self.get_menyala_state()
            matched = next((e for e in st.get("exchanges", []) if e["to_resource"] == to_key), None)
            rate_from = int(matched["rate_from"]) if matched else (7600 if to_key == "rubles" else 1500)
        amount_from = desired_to * max(1, int(rate_from))
        resp = await self.http.post("/api/smuggling/exchange", json={"to": to_key, "amountFrom": amount_from})
        resp.raise_for_status()
        return resp.json()


async def check_and_notify_menyala_arrival(
    account_id: int,
    menyala_api: MenyalaAPI,
    db_engine: Optional[Any] = None,
    notifier: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Проверяет состояние Менялы, обновляет StateHub и отправляет ровно 1 оповещение (Web + TG)
    при переходе в активный статус нового цикла (с персистентной защитой last_notified_menyala_cycle в БД).
    """
    raw = await menyala_api.get_state()
    parsed = parse_menyala_state(raw)

    try:
        from core.state_hub import state_hub
        state_hub.set_domain_data(account_id, "menyala", parsed)
        state_hub.update_slice(account_id, "menyala", parsed)
    except Exception:
        pass

    if not parsed["is_active"] or not parsed.get("cycle_id"):
        return {"is_active": parsed["is_active"], "notified": False, "state": parsed}

    cycle_id = str(parsed["cycle_id"])
    notified = False
    if db_engine is not None:
        from core.database import get_or_create_config, get_session
        from core.models import BotConfig
        from sqlalchemy import update

        cfg = await get_or_create_config(account_id, db_engine)
        last_cycle = str(getattr(cfg, "last_notified_menyala_cycle", "") or "")
        if last_cycle != cycle_id:
            async with get_session(db_engine) as session:
                await session.execute(
                    update(BotConfig)
                    .where(BotConfig.account_id == account_id)
                    .values(last_notified_menyala_cycle=cycle_id)
                )
                await session.commit()

            promo_lines = [
                f"• {p['title']}: {'Бесплатно' if p['is_free'] else str(p['price_rubles']) + ' руб.'}"
                for p in parsed.get("promos", [])
            ]
            dep_str = ""
            if parsed.get("departure_ts"):
                dep_dt = datetime.fromtimestamp(int(parsed["departure_ts"]), tz=timezone.utc).astimezone(MSK_TZ)
                dep_str = f"До отъезда: {dep_dt.strftime('%d.%m %H:%M')} МСК"

            try:
                from core.drop_parser import DropParser
                await DropParser.save_notification(
                    account_id,
                    {
                        "category": "business",
                        "title": "🚚 Меняла приехал!",
                        "subtitle": (dep_str + ("\n" if dep_str and promo_lines else "") + ", ".join(promo_lines)).strip(),
                        "event_key": f"menyala_arrival:{cycle_id}",
                        "meta_json": {
                            "type": "menyala_arrival",
                            "cycle_id": cycle_id,
                            "departure_ts": parsed.get("departure_ts"),
                        },
                    },
                    db_engine,
                )
            except Exception as ne:
                logger.warning("Failed to save Web notification for Menyala arrival: %s", ne)

            if notifier is not None:
                try:
                    tg_msg = "🚚 <b>Меняла приехал!</b>\n" + "\n".join(promo_lines)
                    if dep_str:
                        tg_msg += f"\n\n⏳ {dep_str}"
                    await notifier.notify(tg_msg)
                except Exception as te:
                    logger.warning("Failed to send TG notification for Menyala arrival: %s", te)
            notified = True

    return {"is_active": True, "notified": notified, "cycle_id": cycle_id, "state": parsed}
