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
