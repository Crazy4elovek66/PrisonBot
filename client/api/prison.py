import logging
from typing import Dict, Any, List, Optional
from client.http_client import GameHttpClient

logger = logging.getLogger(__name__)


class PrisonAPI:
    """
    Методы взаимодействия с тюрьмами, ходками, чекпоинтами и мастерами:
    - /api/prisons/all (список всех тюрем игры)
    - /api/player/prison/{prison_id} (состояние прогресса игрока в тюрьме)
    - /api/player/prison/{prison_id}/checkpoints?isDay={is_day} (список чекпоинтов с требованиями и наградами)
    - /api/player/prison/{prison_id}/work?isDay={is_day} (выполнение одной ходки/задания)
    - /api/masters (список мастеров)
    - /api/player/masters/{master_id}/enter (состояние и каталог мастера)
    - /api/player/masters/{master_id}/work (тренировка/работа у мастера)
    """

    def __init__(self, http_client: GameHttpClient):
        self.http = http_client

    async def get_all_prisons(self) -> Dict[str, Any]:
        """Получение списка всех тюрем игры."""
        resp = await self.http.get("/api/prisons/all")
        resp.raise_for_status()
        return resp.json()

    async def get_prison_state(self, prison_id: int) -> Dict[str, Any]:
        """Получение детального прогресса игрока в конкретной тюрьме."""
        resp = await self.http.get(f"/api/player/prison/{prison_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_checkpoints(self, prison_id: int, is_day: bool = True) -> Dict[str, Any]:
        """Получение списка чекпоинтов для тюрьмы в дневном/ночном режиме."""
        day_str = "true" if is_day else "false"
        resp = await self.http.get(f"/api/player/prison/{prison_id}/checkpoints?isDay={day_str}")
        resp.raise_for_status()
        return resp.json()

    async def do_prison_work(self, prison_id: int, is_day: bool = True) -> Dict[str, Any]:
        """Выполнение одной ходки (задания) в тюрьме."""
        day_str = "true" if is_day else "false"
        resp = await self.http.post(f"/api/player/prison/{prison_id}/work?isDay={day_str}", json={})
        resp.raise_for_status()
        return resp.json()

    async def claim_checkpoints(self, prison_id: int, is_day: bool = True) -> Dict[str, Any]:
        """
        Сбор / проверка наград чекпоинтов.
        В API Old Prison награды за чекпоинты начисляются сервером автоматически при выполнении ходки,
        а данный метод проверяет и актуализирует состояние чекпоинтов.
        """
        return await self.get_checkpoints(prison_id=prison_id, is_day=is_day)

    async def get_masters(self) -> Dict[str, Any]:
        """Получение списка мастеров."""
        resp = await self.http.get("/api/masters")
        resp.raise_for_status()
        return resp.json()

    async def enter_master(self, master_id: int) -> Dict[str, Any]:
        """Вход к мастеру и получение его каталога и чекпоинтов."""
        resp = await self.http.get(f"/api/player/masters/{master_id}/enter")
        resp.raise_for_status()
        return resp.json()

    async def do_master_work(self, master_id: int) -> Dict[str, Any]:
        """Выполнение тренировки/работы у мастера."""
        resp = await self.http.post(f"/api/player/masters/{master_id}/work", json={})
        resp.raise_for_status()
        return resp.json()


async def fetch_enriched_prisons_list(prison_api: Any) -> List[Dict[str, Any]]:
    """
    Загружает список всех тюрем (/api/prisons/all) и обогащает каждую открытую тюрьму
    реальными счетчиками dayRuns / nightRuns из /api/player/prison/{pid}.
    """
    import asyncio

    p_res = await prison_api.get_all_prisons()
    raw_prisons = p_res.get("prisons", []) if isinstance(p_res, dict) else p_res
    if not isinstance(raw_prisons, list):
        return []

    unlocked_ids = [
        int(p["id"])
        for p in raw_prisons
        if isinstance(p, dict) and p.get("id") is not None and p.get("isUnlocked", True)
    ]

    states_by_id: Dict[int, Dict[str, Any]] = {}
    if unlocked_ids and hasattr(prison_api, "get_prison_state"):
        sem = asyncio.Semaphore(6)

        async def _fetch_one(pid: int):
            async with sem:
                try:
                    st = await prison_api.get_prison_state(pid)
                    if isinstance(st, dict):
                        if isinstance(st.get("data"), dict):
                            st = st["data"]
                        elif isinstance(st.get("state"), dict):
                            st = st["state"]
                        return pid, st
                    return pid, {}
                except Exception:
                    return pid, {}

        pairs = await asyncio.gather(*(_fetch_one(pid) for pid in unlocked_ids))
        states_by_id = {pid: st for pid, st in pairs}

    enriched: List[Dict[str, Any]] = []
    for p in raw_prisons:
        if not isinstance(p, dict):
            continue
        p_copy = dict(p)
        pid = p_copy.get("id") or p_copy.get("prisonId")
        try:
            pid_int = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            pid_int = None
        st = states_by_id.get(pid_int, {}) if pid_int is not None else {}
        day_runs = int(
            st.get("dayRuns")
            if st.get("dayRuns") is not None
            else (p_copy.get("dayRuns") or p_copy.get("dayCount") or p_copy.get("dayCompletions") or 0)
        )
        night_runs = int(
            st.get("nightRuns")
            if st.get("nightRuns") is not None
            else (p_copy.get("nightRuns") or p_copy.get("nightCount") or p_copy.get("nightCompletions") or 0)
        )
        p_copy["dayRuns"] = day_runs
        p_copy["nightRuns"] = night_runs
        enriched.append(p_copy)
    return enriched



def compute_prison_shift_energy(
    checkpoints: Any,
    completed_cps: int = 0,
    current_clicks: int = 0,
) -> tuple[int, int]:
    """
    Вычисляет (full_energy, remaining_energy) для смены тюрьмы (День/Ночь)
    по списку чекпоинтов (clicksRequired * energyCost).
    """
    if not isinstance(checkpoints, list) or not checkpoints:
        return 0, 0
    full_energy = 0
    remaining_energy = 0
    comp = max(0, int(completed_cps or 0))
    clicks_done = max(0, int(current_clicks or 0))
    total_cps = len(checkpoints)

    for idx, cp in enumerate(checkpoints):
        if not isinstance(cp, dict):
            continue
        req = max(1, int(cp.get("clicksRequired") or cp.get("clicks") or 1))
        cost = max(0, int(cp.get("energyCost") or cp.get("energy") or 0))
        cp_energy = req * cost
        full_energy += cp_energy
        if comp >= total_cps:
            continue
        if idx > comp:
            remaining_energy += cp_energy
        elif idx == comp:
            rem_clicks = max(0, req - clicks_done)
            remaining_energy += rem_clicks * cost

    return full_energy, remaining_energy


def compute_master_cycle_energy(master: Any) -> tuple[int, int]:
    """
    Вычисляет (full_cycle_energy, remaining_cycle_energy) для мастера.
    Поддерживает структуру `/api/player/masters/{id}/enter` (`checkpoints` + `data.progress`),
    а также скалярные поля (`energyCost`/`maxProgress`/`progress`).
    """
    if not isinstance(master, dict):
        return 0, 0
    steps = master.get("checkpoints") or master.get("steps")
    progress_obj = master.get("progress")
    if not isinstance(progress_obj, dict) and isinstance(master.get("data"), dict):
        progress_obj = master["data"].get("progress")

    if isinstance(steps, list) and steps:
        if isinstance(progress_obj, dict):
            comp = int(progress_obj.get("currentCheckpoint") or progress_obj.get("currentStep") or 0)
            cur_clicks = int(progress_obj.get("clicksInCheckpoint") or progress_obj.get("currentClicks") or 0)
        else:
            comp = int(master.get("currentCheckpoint") or master.get("currentStep") or master.get("completedSteps") or 0)
            cur_clicks = int(master.get("clicksInCheckpoint") or master.get("currentClicks") or master.get("progress") or 0)
        return compute_prison_shift_energy(steps, completed_cps=comp, current_clicks=cur_clicks)

    step_cost = int(master.get("energyCost") or master.get("stepEnergy") or master.get("energy") or 0)
    total_steps = int(
        master.get("maxProgress")
        or master.get("totalSteps")
        or master.get("stepsRequired")
        or master.get("clicksRequired")
        or master.get("need")
        or 0
    )
    if step_cost <= 0 or total_steps <= 0:
        return 0, 0
    cur_raw = progress_obj.get("clicksInCheckpoint") if isinstance(progress_obj, dict) else (master.get("progress") or master.get("currentProgress") or 0)
    full = step_cost * total_steps
    cur = max(0, int(cur_raw or 0))
    rem = max(0, (total_steps - min(total_steps, cur)) * step_cost)
    return full, rem
