"""
API-клиент, парсер 4 тиров / 8 задач / Топ-5 и безопасный классификатор задач «Зарубов» (/api/zaruba/*).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ZARUBA_TIERS: Dict[str, Dict[str, Any]] = {
    "pacan": {"mode": 1, "title": "Пацанские"},
    "blat": {"mode": 2, "title": "Блатные"},
    "avtoritet": {"mode": 3, "title": "Авторитетные"},
    "vor": {"mode": 4, "title": "Воровские"},
}

MODE_TO_TIER = {v["mode"]: k for k, v in ZARUBA_TIERS.items()}


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


def parse_zaruby_state(raw_payload: Any, config: Any = None, now_unix: Optional[int] = None) -> Dict[str, Any]:
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    active = raw.get("active") if isinstance(raw.get("active"), dict) else None
    progress = raw.get("progress") if isinstance(raw.get("progress"), dict) else {}
    balances = raw.get("balances") if isinstance(raw.get("balances"), dict) else {}

    cur_unix = now_unix if now_unix is not None else int(datetime.now(timezone.utc).timestamp())
    tasks_out: List[Dict[str, Any]] = []
    completed_count = 0
    total_pct_sum = 0.0

    if active:
        raw_tasks = active.get("tasks") or []
        for t in raw_tasks:
            if not isinstance(t, dict):
                continue
            req = max(1, int(t.get("requiredAmount") or 1))
            cur = max(0, int(t.get("currentAmount") or 0))
            done = bool(t.get("status") == 1 or cur >= req)
            if done:
                completed_count += 1
            pct = min(100.0, round((cur / req) * 100.0, 1))
            total_pct_sum += pct
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
                "classification": cls_code,
                "classification_reason": cls_reason,
            })

    total_count = len(tasks_out) or 8
    overall_pct = round(total_pct_sum / len(tasks_out)) if tasks_out else 0
    mode_int = int(active.get("mode") or 1) if active else 1
    tier_key = MODE_TO_TIER.get(mode_int, "pacan")
    raw_end = active.get("endUnix") if active else 0
    try:
        end_unix = int(raw_end or 0)
        if end_unix > 10_000_000_000:
            end_unix //= 1000
    except (TypeError, ValueError):
        end_unix = 0
    seconds_left = max(0, end_unix - cur_unix) if end_unix > 0 else 0

    participants_raw = (active.get("participants") or []) if active else []
    leaderboard = []
    for idx, p in enumerate(participants_raw[:5], 1):
        if not isinstance(p, dict):
            continue
        leaderboard.append({
            "rank": idx,
            "userId": p.get("userId"),
            "nickname": p.get("nickname") or f"Игрок {p.get('userId')}",
            "authority": int(p.get("authority") or 0),
            "progress_pct": round(float(p.get("progressPct") or p.get("progress") or 0), 1),
        })

    return {
        "active": bool(active),
        "tier": tier_key,
        "tier_title": ZARUBA_TIERS.get(tier_key, {}).get("title", "Пацанские"),
        "mode": mode_int,
        "end_unix": end_unix,
        "seconds_left": seconds_left,
        "finished_success": bool(active.get("finishedSuccess")) if active else False,
        "finished_fail": bool(active.get("finishedFail")) if active else False,
        "tasks": tasks_out,
        "completed_count": completed_count,
        "total_count": total_count,
        "overall_pct": overall_pct,
        "summary_label": f"{completed_count}/{total_count} ({overall_pct}%)" if active else "Не активен",
        "leaderboard": leaderboard,
        "level": int(progress.get("level") or 1),
        "xp": int(progress.get("xp") or 0),
        "need_xp": int(progress.get("need") or 100),
        "signets": int(balances.get("signet") or 0),
        "ore_signet": int(balances.get("ore_signet") or 0),
        "pending_reward": raw.get("pendingReward"),
        "limits": raw.get("limits") or {},
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
