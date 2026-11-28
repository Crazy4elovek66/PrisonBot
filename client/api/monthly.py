"""
Парсер полного календаря «Месячных делюг» («От звонка до звонка» /api/monthly/state)
по датам месяца (1..30/31) и всех этапных наград месяца с порогами получения.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

MSK_TZ = timezone(timedelta(hours=3))

_MONTH_NAMES_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

_WEEKDAYS_RU = ("ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС")

_REWARD_RESOURCE_META: Dict[str, tuple[str, str]] = {
    "rubles": ("Рубли", "assets/icons/rubles.webp"),
    "sugar": ("Сахар", "assets/icons/sugar.webp"),
    "cigarettes": ("Папиросы", "assets/icons/cigarettes.webp"),
    "soap": ("Мыло", "assets/icons/soap.webp"),
    "paper": ("Бумага", "assets/icons/paper.webp"),
    "stew": ("Тушенка", "assets/icons/stew.webp"),
    "chefir": ("Чифир", "assets/icons/energy.webp"),
    "energy": ("Энергия", "assets/icons/energy.webp"),
    "gunshot": ("Самопал", "assets/icons/gunshot.webp"),
    "poison": ("Яд", "assets/icons/poison.webp"),
    "knife": ("Финка", "assets/icons/knife.webp"),
    "chips": ("Фишки", "assets/icons/poker_chip_red.webp"),
    "keys": ("Ключи", "assets/icons/keys.webp"),
    "signet": ("Перстни", "assets/icons/signet.webp"),
}


def _extract_reward_items(tier_data: Any) -> List[Dict[str, Any]]:
    if not isinstance(tier_data, dict):
        return []
    items: List[Dict[str, Any]] = []
    currencies = tier_data.get("currencies") if isinstance(tier_data.get("currencies"), dict) else {}
    for k, v in currencies.items():
        try:
            amt = int(v or 0)
        except (TypeError, ValueError):
            amt = 0
        if amt <= 0:
            continue
        title, icon = _REWARD_RESOURCE_META.get(str(k), (str(k), "assets/icons/stash.webp"))
        items.append({"key": str(k), "title": title, "amount": amt, "icon": icon})

    for direct_key in ("gunshot", "poison", "knife", "rubles", "sugar", "cigarettes", "stew", "chefir", "soap", "paper"):
        if direct_key in tier_data and direct_key not in currencies:
            try:
                amt = int(tier_data.get(direct_key) or 0)
            except (TypeError, ValueError):
                amt = 0
            if amt > 0:
                title, icon = _REWARD_RESOURCE_META.get(direct_key, (direct_key, "assets/icons/stash.webp"))
                items.append({"key": direct_key, "title": title, "amount": amt, "icon": icon})

    clothing_ids = tier_data.get("clothingIds")
    if isinstance(clothing_ids, list) and len(clothing_ids) > 0:
        items.append({
            "key": "clothing",
            "title": "Одежда",
            "amount": len(clothing_ids),
            "icon": "assets/icons/parcel_cloth.webp",
        })
    return items


def parse_monthly_state(
    raw_payload: Any,
    history_rows: Optional[List[Dict[str, Any]]] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
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
    now_msk = ref_utc.astimezone(MSK_TZ)

    global_m = raw.get("global") if isinstance(raw.get("global"), dict) else {}
    user_m = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    summary_m = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    today_m = raw.get("today") if isinstance(raw.get("today"), dict) else {}

    year = int(global_m.get("year") or now_msk.year)
    month = int(global_m.get("month") or now_msk.month)
    if not (1 <= month <= 12):
        month = now_msk.month
    days_in_month = int(global_m.get("daysInMonth") or summary_m.get("totalDays") or calendar.monthrange(year, month)[1])
    year_month = f"{year:04d}-{month:02d}"
    month_label = f"{_MONTH_NAMES_RU.get(month, str(month))} {year}"

    today_day = int(user_m.get("activeDayId") or today_m.get("dayId") or now_msk.day)
    completed_count = int(user_m.get("completedCount") or summary_m.get("completedCount") or 0)

    # Индексируем определения дней из global.days, прогресс из user.days и историю из БД
    defs_by_day: Dict[int, Dict[str, Any]] = {}
    for d in (global_m.get("days") or []):
        if isinstance(d, dict) and d.get("dayId") is not None:
            try:
                defs_by_day[int(d["dayId"])] = d
            except (TypeError, ValueError):
                pass

    user_days = user_m.get("days") if isinstance(user_m.get("days"), dict) else {}
    hist_by_day: Dict[int, Dict[str, Any]] = {}
    for hr in (history_rows or []):
        if isinstance(hr, dict) and hr.get("day_num") is not None:
            hist_by_day[int(hr["day_num"])] = hr

    schedule: List[Dict[str, Any]] = []
    future_tasks_available = False
    today_task_out: Optional[Dict[str, Any]] = None

    for day_num in range(1, days_in_month + 1):
        try:
            d_obj = date(year, month, day_num)
            date_iso = d_obj.isoformat()
            weekday = _WEEKDAYS_RU[d_obj.weekday()]
        except ValueError:
            date_iso = f"{year_month}-{day_num:02d}"
            weekday = ""
        date_label = f"{day_num:02d}.{month:02d}"

        d_def = defs_by_day.get(day_num) or {}
        u_prog = user_days.get(str(day_num)) or user_days.get(day_num) or {}
        h_row = hist_by_day.get(day_num) or {}

        title = str(d_def.get("title") or "").strip()
        if not title and day_num == today_day:
            title = str(today_m.get("title") or "").strip()
        if not title:
            title = str(h_row.get("task_title") or "").strip()

        task_key = str(d_def.get("action") or h_row.get("task_key") or "").strip()
        target = int(d_def.get("target") or (today_m.get("target") if day_num == today_day else 0) or h_row.get("target_value") or 0)
        progress = int(u_prog.get("progress") or (today_m.get("progress") if day_num == today_day else 0) or h_row.get("progress_value") or 0)
        completed = bool(u_prog.get("completed")) or (day_num == today_day and bool(today_m.get("completed")))
        expired = bool(u_prog.get("expired"))

        is_today = day_num == today_day
        if completed:
            status = "completed"
        elif is_today:
            status = "today"
        elif day_num < today_day or expired:
            status = "missed"
        else:
            status = "upcoming"

        if day_num > today_day and title:
            future_tasks_available = True

        entry = {
            "day_num": day_num,
            "date_iso": date_iso,
            "date_label": date_label,
            "weekday": weekday,
            "task_key": task_key,
            "title": title,
            "progress": progress,
            "target": target,
            "completed": completed,
            "status": status,
            "is_today": is_today,
        }
        schedule.append(entry)

        if is_today:
            today_task_out = {
                "day_num": day_num,
                "date_label": date_label,
                "title": title,
                "action": task_key,
                "progress": progress,
                "target": target,
                "completed": completed,
            }

    # Парсинг всех этапных наград месяца из global.tierRewards
    raw_tiers = global_m.get("tierRewards") if isinstance(global_m.get("tierRewards"), dict) else {}
    claimed_set = {int(x) for x in (user_m.get("claimedTiers") or []) if str(x).isdigit()}
    claimable_set = {int(x) for x in (user_m.get("claimableTiers") or []) if str(x).isdigit()}

    sorted_tiers: List[tuple[int, str, Any]] = []
    for k, v in raw_tiers.items():
        try:
            req_cnt = int(k)
        except (TypeError, ValueError):
            continue
        sorted_tiers.append((req_cnt, str(k), v))
    sorted_tiers.sort(key=lambda x: x[0])

    rewards_out: List[Dict[str, Any]] = []
    for idx, (req_cnt, tier_key, tier_val) in enumerate(sorted_tiers):
        items = _extract_reward_items(tier_val)
        first_item = items[0] if items else {"title": "Награда", "amount": 1, "icon": "assets/icons/stash.webp"}
        is_claimed = req_cnt in claimed_set
        is_claimable = (not is_claimed) and (req_cnt in claimable_set or completed_count >= req_cnt)
        status = "claimed" if is_claimed else ("claimable" if is_claimable else "locked")
        rewards_out.append({
            "index": idx,
            "reward_id": tier_key,
            "tier": req_cnt,
            "required_count": req_cnt,
            "current_count": completed_count,
            "remaining_count": max(0, req_cnt - completed_count),
            "title": first_item["title"],
            "amount": first_item["amount"],
            "icon": first_item["icon"],
            "items": items,
            "status": status,
            "claimable": is_claimable,
        })

    return {
        "active": bool(raw.get("active", True)),
        "year_month": year_month,
        "month_label": month_label,
        "completed_count": completed_count,
        "total_days": days_in_month,
        "today_day": today_day,
        "future_tasks_available": future_tasks_available,
        "today_task": today_task_out,
        "schedule": schedule,
        "rewards": rewards_out,
        "server_now_ts": server_now_ts,
    }
