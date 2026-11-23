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
