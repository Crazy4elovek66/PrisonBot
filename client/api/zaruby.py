"""
API-клиент, парсер 4 тиров / 8 задач / Топ-5 и безопасный классификатор задач «Зарубов» (/api/zaruba/*).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ZARUBA_TIERS: Dict[str, Dict[str, Any]] = {
    "pacan": {"mode": 1, "title": "Пацанская", "reward_signet": 10},
    "blat": {"mode": 2, "title": "Блатная", "reward_signet": 20},
    "avtoritet": {"mode": 3, "title": "Авторитетная", "reward_signet": 35},
    "vor": {"mode": 4, "title": "Воровская", "reward_signet": 54},
}

MODE_TO_TIER = {v["mode"]: k for k, v in ZARUBA_TIERS.items()}

ZARUBA_TASK_ICONS: Dict[int, str] = {
    1: "zaruba_i_nits.webp",
    2: "zaruba_i_avtoritet.webp",
    3: "zaruba_i_podogrev.webp",
    4: "zaruba_i_zone.webp",
    5: "zaruba_i_winboss.webp",
    6: "zaruba_i_winboss.webp",
    7: "zaruba_i_winboss.webp",
    8: "zaruba_i_harknyt.webp",
    9: "zaruba_i_winPlayer.webp",
    10: "zaruba_i_papiros.webp",
    11: "talents.webp",
    12: "poker_icon.webp",
    13: "fartovy_icon.webp",
}


def _zaruba_task_icon(task_type: Any) -> str:
    try:
        t = int(task_type or 0)
    except (TypeError, ValueError):
        t = 0
    return ZARUBA_TASK_ICONS.get(t, "zaruba_i_avtoritet.webp")


def _det_rand(seed_val: int, lo: float, hi: float) -> float:
    x = ((seed_val * 1103515245 + 12345) & 0x7FFFFFFF) / 2147483647.0
    return lo + (hi - lo) * x


def classify_zarub_task(task: Dict[str, Any], config: Any = None) -> Tuple[str, str]:
    """
    Классифицирует задачу Заруба:
    - skip_damage: любая задача на урон боссам (ВСЕГДА пропускать!)
    - skip_paid: платный пропуск / покупка за рубли/мыло/сахар
    - skip_energy_conflict: задачи на энергию, если в «Ходках и мастерах» выбрана зона или мастер
    - safe_auto: безопасные бесплатные задачи (терпила, харчок, дрожжи, бесплатный Фартовый, папиросы и др.)
    """
    t_type = int(task.get("type") or 0)
    title = str(task.get("title") or "").lower()

    # 1. Задачи на урон боссам (type=6 или ключевые слова) -> ВСЕГДА skip_damage
    if t_type == 6 or task.get("bossId") is not None or any(
        w in title for w in ("урон", "босс", "яд", "финк", "самопал")
    ):
        return "skip_damage", "Пропуск: задачи на урон боссам отключены"

    # 2. Платные задачи
    if any(w in title for w in ("рубл", "мыл", "купи", "потрать", "пропуск")):
        return "skip_paid", "Пропуск: требует платных ресурсов"

    # 3. Задачи с затратой энергии (type=4 уважение в зоне, type=11 очки знаний у мастеров)
    if t_type in (4, 11) or task.get("prisonId") is not None or any(
        w in title for w in ("уважен", "мастер", "знан", "ходк", "энерг")
    ):
        prison_busy = bool(
            getattr(config, "auto_prison", False)
            or getattr(config, "auto_masters", False)
            or int(getattr(config, "prison_target_id", 0) or 0) > 0
        )
        if prison_busy:
            return "skip_energy_conflict", "Пропуск: энергия занята «Ходками и мастерами»"
        return "skip_energy_conflict", "Пропуск: требует расхода энергии"

    # 4. Безопасные бесплатные задачи:
    # type 9: Напряги терпилу, type 13: Сыграй фартового, type 10: Заработай папирос, харчки, дрожжи, подогревы
    if t_type in (9, 10, 13) or any(
        w in title for w in ("терпил", "фартов", "папирос", "харч", "дрожж", "подогрев", "балан")
    ):
        return "safe_auto", "Авто: безопасная бесплатная задача"

    return "skip_paid_or_unsupported", "Пропуск: требует ручного выполнения"


def parse_zaruby_state(
    raw_payload: Any,
    config: Any = None,
    now_unix: Optional[int] = None,
    current_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    active = raw.get("active") if isinstance(raw.get("active"), dict) else None
    progress = raw.get("progress") if isinstance(raw.get("progress"), dict) else {}
    balances = raw.get("balances") if isinstance(raw.get("balances"), dict) else {}
    modes_list = raw.get("modes") if isinstance(raw.get("modes"), list) else []

    if now_unix is not None:
        cur_unix = int(now_unix)
    else:
        try:
            from client.http_client import get_game_now_ts
            cur_unix = int(get_game_now_ts())
        except Exception:
            cur_unix = int(datetime.now(timezone.utc).timestamp())
    tasks_out: List[Dict[str, Any]] = []
    completed_count = 0
    ratio_sum = 0.0
    skip_soap_cost = int(raw.get("skipSoapCost") or 0)

    if active:
        raw_tasks = active.get("tasks") or active.get("Tasks") or []
        for t in raw_tasks:
            if not isinstance(t, dict):
                continue
            req = max(1, int(t.get("requiredAmount") or t.get("target") or 1))
            cur = max(0, int(t.get("currentAmount") or t.get("current") or 0))
            done = bool(int(t.get("status") or 0) >= 1 or cur >= req)
            if done:
                completed_count += 1
            ratio = min(1.0, cur / req)
            ratio_sum += ratio
            pct = min(100.0, round(ratio * 100.0, 1))
            cls_code, cls_reason = classify_zarub_task(t, config=config)
            tasks_out.append({
                "taskId": t.get("taskId"),
                "type": t.get("type"),
                "title": t.get("title") or "Задача",
                "subtitle": t.get("subtitle"),
                "current": cur,
                "target": req,
                "completed": done,
                "progress_pct": pct,
                "icon": _zaruba_task_icon(t.get("type")),
                "skip_soap_cost": skip_soap_cost if not done else 0,
                "classification": cls_code,
                "classification_reason": cls_reason,
            })

    total_count = len(tasks_out) or 8
    overall_pct_exact = round((ratio_sum / total_count) * 100.0, 2) if tasks_out else 0.0
    overall_pct = round(overall_pct_exact)
    mode_int = int(active.get("mode") or 1) if active else 1
    tier_key = MODE_TO_TIER.get(mode_int, "pacan")

    reward_signet = int(ZARUBA_TIERS.get(tier_key, {}).get("reward_signet") or 10)
    for m_item in modes_list:
        if isinstance(m_item, dict) and int(m_item.get("mode") or 0) == mode_int:
            if m_item.get("rewardSignet") is not None:
                reward_signet = int(m_item.get("rewardSignet") or reward_signet)
            break

    def _norm_unix(val: Any) -> int:
        try:
            v = int(val or 0)
            if v > 10_000_000_000:
                v //= 1000
            return v
        except (TypeError, ValueError):
            return 0

    start_unix = _norm_unix(active.get("startUnix") if active else 0)
    end_unix = _norm_unix(active.get("endUnix") if active else 0)
    seconds_left = max(0, end_unix - cur_unix) if end_unix > 0 else 0

    time_ratio = 0.0
    if start_unix > 0 and end_unix > start_unix:
        time_ratio = max(0.0, min(1.0, (cur_unix - start_unix) / float(end_unix - start_unix)))

    participants_raw = (active.get("participants") or []) if active else []
    max_auth = max((int(p.get("authority") or 0) for p in participants_raw if isinstance(p, dict)), default=1) or 1
    leaderboard = []
    for idx, p in enumerate(participants_raw[:5], 1):
        if not isinstance(p, dict):
            continue
        uid = p.get("userId")
        try:
            uid_int = int(uid) if uid is not None else idx
        except (TypeError, ValueError):
            uid_int = idx
        is_self = bool(current_user_id is not None and uid_int == int(current_user_id))
        explicit_pct = p.get("progressPct") if p.get("progressPct") is not None else p.get("progress")
        if explicit_pct is not None:
            p_pct = min(100.0, max(0.0, round(float(explicit_pct), 2)))
        elif is_self or (current_user_id is None and idx == 1 and overall_pct_exact > 0):
            p_pct = overall_pct_exact
        else:
            auth_w = min(1.0, max(0.0, int(p.get("authority") or 0) / float(max_auth)))
            est = time_ratio * (0.55 + 0.45 * auth_w) * _det_rand(uid_int, 0.9, 1.1) + _det_rand(uid_int + 33, -0.03, 0.04)
            p_pct = round(max(0.0, min(1.0, est)) * 100.0, 2)
        leaderboard.append({
            "rank": idx,
            "userId": uid,
            "nickname": p.get("nickname") or f"Игрок {uid}",
            "photoUrl": p.get("photoUrl"),
            "authority": int(p.get("authority") or 0),
            "progress_pct": p_pct,
            "is_self": is_self,
        })

    leaderboard.sort(key=lambda item: (-float(item["progress_pct"]), -int(item["authority"])))
    for new_rank, item in enumerate(leaderboard, 1):
        item["rank"] = new_rank

    finished_success = bool(active.get("finishedSuccess")) if active else False
    finished_fail = bool(active.get("finishedFail")) if active else False
    can_claim = bool(raw.get("pendingReward") or (active and (finished_success or finished_fail or (end_unix > 0 and seconds_left == 0))))

    return {
        "active": bool(active),
        "server_now_ts": cur_unix,
        "tier": tier_key,
        "tier_title": ZARUBA_TIERS.get(tier_key, {}).get("title", "Пацанская"),
        "mode": mode_int,
        "start_unix": start_unix,
        "end_unix": end_unix,
        "seconds_left": seconds_left,
        "finished_success": finished_success,
        "finished_fail": finished_fail,
        "can_claim": can_claim,
        "reward_signet": reward_signet,
        "skip_soap_cost": skip_soap_cost,
        "tasks": tasks_out,
        "completed_count": completed_count,
        "total_count": total_count,
        "overall_pct": overall_pct,
        "overall_pct_exact": overall_pct_exact,
        "summary_label": f"{completed_count}/{total_count} ({overall_pct}%)" if active else "Не активен",
        "leaderboard": leaderboard,
        "level": int(progress.get("level") or 0),
        "xp": int(progress.get("xp") or 0),
        "need_xp": int(progress.get("need") or 100),
        "signets": int(balances.get("signet") or 0),
        "ore_signet": int(balances.get("ore_signet") or 0),
        "pending_reward": raw.get("pendingReward"),
        "limits": raw.get("limits") or {},
        "modes": modes_list,
    }


class ZarubyAPI:
    """Клиент эндпоинтов Зарубов (/api/zaruba/*)."""

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client

    async def get_state(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/zaruba/state")
        resp.raise_for_status()
        return resp.json()

    async def get_well_state(self) -> Dict[str, Any]:
        resp = await self.http.get("/api/zaruba/well/state")
        resp.raise_for_status()
        return resp.json()

    async def start_zarub(self, tier: str = "pacan") -> Dict[str, Any]:
        mode = ZARUBA_TIERS.get(str(tier).lower(), ZARUBA_TIERS["pacan"])["mode"]
        resp = await self.http.post("/api/zaruba/start", json={"Mode": mode})
        resp.raise_for_status()
        return resp.json()

    async def claim_reward(self) -> Dict[str, Any]:
        resp = await self.http.post("/api/zaruba/claim", json={})
        resp.raise_for_status()
        return resp.json()

    async def exchange_ore(self) -> Dict[str, Any]:
        resp = await self.http.post("/api/zaruba/exchange-ore", json={})
        resp.raise_for_status()
        return resp.json()

    async def open_bag(self, bag_id: str) -> Dict[str, Any]:
        resp = await self.http.post("/api/zaruba/open-bag", json={"bagId": bag_id})
        resp.raise_for_status()
        return resp.json()
