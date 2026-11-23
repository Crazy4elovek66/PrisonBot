import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from client.http_client import GameHttpClient

logger = logging.getLogger(__name__)

CACHE_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "storage" / "tattoo_clothing_cache.json"


class PlayerAPI:
    """
    Методы взаимодействия с профилем игрока, рутинными активностями и гардеробом:
    - /api/player/init (синхронизация профиля и валют)
    - /api/player/me (краткая информация)
    - /api/beard/update (бритье/обновление бороды)
    - /api/daily/toilet-paper (ежедневная туалетная бумага)
    - /api/player/business/* (просмотр и сбор прибыли бизнесов)
    - /api/podogrev/* (сбор подогревов от друзей)
    - /api/talent/* (статус и прокачка талантов)
    - /api/collection/player/* (полные коллекции и обмен/впарить)
    - /api/stashgear/* (нычки и слоты)
    - /api/bauls/* (статистика и открытие баулов)
    - /api/clothing/* (инвентарь, надевание, покупка)
    - /api/tattoo/* (надевание, покупка татуировок)
    - /api/camera/* (список камер, выбор активной, покупка)
    - /api/kolsik/* (рулетка у кольщика)
    """

    def __init__(self, http_client: GameHttpClient):
        self.http = http_client
        self._tattoos_cache: Optional[List[Dict[str, Any]]] = None
        self._tattoos_cache_time: float = 0.0
        self._clothing_cache: Optional[List[Dict[str, Any]]] = None
        self._clothing_cache_time: float = 0.0
        self._cameras_cache: Optional[List[Dict[str, Any]]] = None
        self._cameras_cache_time: float = 0.0
        self._stashgear_cache: Optional[Dict[str, Any]] = None
        self._stashgear_cache_time: float = 0.0
        self._collections_cache: Dict[int, tuple[float, Dict[str, Any]]] = {}

    async def init_player(self) -> Dict[str, Any]:
        """Инициализация состояния игрока и получение балансов."""
        resp = await self.http.post("/api/player/init", json={})
        resp.raise_for_status()
        return resp.json()

    async def get_me(self) -> Dict[str, Any]:
        """Получение базовой информации о пользователе."""
        resp = await self.http.get("/api/player/me")
        resp.raise_for_status()
        return resp.json()

    async def update_beard(self) -> Dict[str, Any]:
        """Проверка и бритье бороды."""
        resp = await self.http.post("/api/beard/update", json={})
        resp.raise_for_status()
        return resp.json()

    async def claim_toilet_paper(self) -> Dict[str, Any]:
        """Сбор ежедневной туалетной бумаги."""
        resp = await self.http.post("/api/daily/toilet-paper", json={})
        resp.raise_for_status()
        return resp.json()

    async def get_businesses(self) -> Dict[str, Any]:
        """Получение списка и статуса всех бизнесов игрока."""
        resp = await self.http.get("/api/player/business/all")
        resp.raise_for_status()
        return resp.json()

    async def collect_business_rewards(self) -> Dict[str, Any]:
        """Сбор накопленной прибыли со всех бизнесов."""
        resp = await self.http.post("/api/player/business/collect", json={})
        resp.raise_for_status()
        return resp.json()

    async def get_podogrev_status(
        self,
        page: int = 1,
        page_size: int = 20,
        friends_page: int = 1,
        friends_page_size: int = 20,
    ) -> Dict[str, Any]:
        """Получение статуса подогревов и входящих подарков."""
        url = (
            f"/api/podogrev/status?page={page}&pageSize={page_size}"
            f"&friendsPage={friends_page}&friendsPageSize={friends_page_size}"
        )
        resp = await self.http.get(url)
        resp.raise_for_status()
        return resp.json()

    async def collect_all_podogrev(self) -> Dict[str, Any]:
        """Сбор всех доступных подогревов от друзей."""
        resp = await self.http.post("/api/podogrev/collect/all", json={})
        resp.raise_for_status()
        return resp.json()

    async def upgrade_business(self, business_id: int, prison_id: int) -> Dict[str, Any]:
        """Улучшение уровня бизнеса."""
        url = f"/api/player/business/upgrade?businessId={business_id}&prisonId={prison_id}"
        resp = await self.http.post(url, json={})
        resp.raise_for_status()
        return resp.json()

    async def get_talents_status(self) -> Dict[str, Any]:
        """Получение прогресса талантов."""
        resp = await self.http.get("/api/talent/status")
        resp.raise_for_status()
        return resp.json()

    async def upgrade_talent(self, talent_id: int) -> Dict[str, Any]:
        """Прокачка таланта."""
        resp = await self.http.post("/api/talent/upgrade", json={"talentId": talent_id})
        resp.raise_for_status()
        return resp.json()

    async def get_collections(self, user_id: int) -> Dict[str, Any]:
        """Получение списка коллекций игрока (реальный подтвержденный путь /api/collection/player/full) с кэшированием."""
        now = time.time()
        if user_id in self._collections_cache:
            ts, cached_data = self._collections_cache[user_id]
            if now - ts < 60.0:
                return cached_data

        resp = await self.http.get(f"/api/collection/player/full?userId={user_id}")
        resp.raise_for_status()
        data = resp.json()
        self._collections_cache[user_id] = (now, data)
        return data

    async def exchange_collection(
        self,
        collection_id: int,
        prison_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Обмен собранной коллекции (впарить) через /api/collection/player/vparit."""
        payload: Dict[str, Any] = {"collectionId": collection_id}
        if prison_id is not None:
            payload["prisonId"] = prison_id
        if user_id is not None:
            payload["userId"] = user_id

        # Пробуем актуальный путь /api/collection/player/vparit, при 404 делаем fallback
        try:
            resp = await self.http.post("/api/collection/player/vparit", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("Primary exchange endpoint failed, trying fallback /api/collection/vparit: %s", e)
            resp = await self.http.post("/api/collection/vparit", json={"collectionId": collection_id})
            resp.raise_for_status()
            return resp.json()

    async def get_bauls_stat(self) -> Dict[str, Any]:
        """Статистика баулов."""
        resp = await self.http.get("/api/bauls/stat")
        resp.raise_for_status()
        return resp.json()

    async def buy_baul(self, baul_id: int = 1) -> Dict[str, Any]:
        """Покупка/открытие баула."""
        resp = await self.http.post("/api/bauls/buy", json={"baulId": baul_id})
        resp.raise_for_status()
        return resp.json()

    async def get_player_view(self, user_id: int) -> Dict[str, Any]:
        """Получение детального внешнего профиля игрока по userId (GET /api/player/view/{userId})."""
        resp = await self.http.get(f"/api/player/view/{user_id}")
        resp.raise_for_status()
        return resp.json()

    async def roll_kolsik(self, currency: str = "paper") -> Dict[str, Any]:
        """Прокрутка у кольщика: покупка наколки за туалетную бумагу или за рубли."""
        c = str(currency).lower().strip()
        if c == "rubles":
            endpoint = "/api/kolsik/roll"
        elif c in ("paper", "toiletpaper"):
            endpoint = "/api/kolsik/roll-paper"
        else:
            raise ValueError(f"Недопустимая валюта для Кольщика: '{currency}'. Ожидается 'paper' или 'rubles'.")

        resp = await self.http.post(endpoint, json={})
        resp.raise_for_status()
        return resp.json()

    async def roll_paper(self) -> Dict[str, Any]:
        """Вращение рулона у кольщика (татуировки за туалетную бумагу)."""
        return await self.roll_kolsik("paper")

    async def get_wardrobe_inventory(self) -> Dict[str, Any]:
        """Получение инвентаря гардероба (ownedClothing, ownedTattoos, ownedCameras)."""
        resp = await self.http.get("/api/clothing/inventory")
        resp.raise_for_status()
        return resp.json()

    def _normalize_cameras(self, cameras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        room_static_overrides = {
            "27": "/static/assets/rooms/room_27.webp",
            "28": "/static/assets/rooms/room_28.webp",
            "29": "/static/assets/rooms/room_29.webp",
            "30": "/static/assets/rooms/room_30.webp",
            "31": "/static/assets/rooms/room_31.webp",
            "32": "/static/assets/rooms/room_32.webp",
            "33": "/static/assets/rooms/room_33.webp",
            "34": "/static/assets/rooms/room_34.webp",
            "35": "/static/assets/rooms/room_35.webp",
            "36": "/static/assets/rooms/room_36.webp",
            "37": "/static/assets/rooms/room_37.webp",
            "54": "/static/assets/rooms/room_54.webp",
        }
        for cam in cameras:
            if not isinstance(cam, dict):
                continue
            img_url = cam.get("imageUrl") or ""
            for folder, static_path in room_static_overrides.items():
                if f"RoomCameraUrl/{folder}/" in img_url or f"rooms/room_{folder}.webp" in img_url:
                    cam["imageUrl"] = static_path
                    break
        return cameras

    async def get_cameras(self) -> Dict[str, Any]:
        """Получение списка всех камер игры (Хаты)."""
        now = time.time()
        if self._cameras_cache is not None and (now - self._cameras_cache_time) < 600:
            return {"success": True, "cameras": self._cameras_cache}

        try:
            resp = await self.http.get("/api/camera/all")
            if resp.status_code == 200:
                data = resp.json()
                cameras = data.get("cameras", []) if isinstance(data, dict) else []
                if cameras:
                    self._cameras_cache = self._normalize_cameras(cameras)
                    self._cameras_cache_time = now
                    data["cameras"] = self._cameras_cache
                    return data
        except Exception as e:
            logger.debug("Failed to fetch /api/camera/all from server: %s", e)

        # Fallback to local cache file
        self._ensure_catalogs_loaded()
        if self._cameras_cache:
            self._cameras_cache = self._normalize_cameras(self._cameras_cache)
        return {"success": True, "cameras": self._cameras_cache or []}

    async def select_camera(self, camera_id: int) -> Dict[str, Any]:
        """Выбор активной камеры (Хаты)."""
        resp = await self.http.post("/api/camera/select", json={"cameraId": camera_id})
        resp.raise_for_status()
        return resp.json()

    async def buy_camera(self, camera_id: int) -> Dict[str, Any]:
        """Покупка камеры."""
        resp = await self.http.post("/api/camera/buy", json={"cameraId": camera_id})
        resp.raise_for_status()
        return resp.json()

    async def equip_tattoo(self, zone: int, tattoo_id: int, image_url: str = "") -> Dict[str, Any]:
        """Надевание татуировки."""
        payload = {"tattooZones": {str(zone): {"tattooId": tattoo_id, "imageUrl": image_url}}}
        resp = await self.http.post("/api/tattoo/apply", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def unequip_tattoo(self, zone: int) -> Dict[str, Any]:
        """Снятие татуировки с зоны."""
        payload = {"tattooZones": {str(zone): {"tattooId": 0, "imageUrl": ""}}}
        resp = await self.http.post("/api/tattoo/apply", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def equip_tattoo_set(self, zones_map: Dict[str, Any]) -> Dict[str, Any]:
        """Надевание целого комплекта татуировок."""
        payload = {"tattooZones": zones_map}
        resp = await self.http.post("/api/tattoo/apply", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def buy_tattoo(self, tattoo_id: int) -> Dict[str, Any]:
        """Покупка татуировки."""
        resp = await self.http.post("/api/tattoo/buy", json={"tattooId": tattoo_id})
        resp.raise_for_status()
        return resp.json()

    async def equip_clothing(self, zone: int, clothing_id: int, image_url: str = "") -> Dict[str, Any]:
        """Надевание предмета одежды."""
        payload = {"clothingZones": {str(zone): {"clothingId": clothing_id, "imageUrl": image_url}}}
        resp = await self.http.post("/api/clothing/apply", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def unequip_clothing(self, zone: int) -> Dict[str, Any]:
        """Снятие одежды с зоны."""
        payload = {"clothingZones": {str(zone): {"clothingId": 0, "imageUrl": ""}}}
        resp = await self.http.post("/api/clothing/apply", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def equip_clothing_set(self, zones_map: Dict[str, Any]) -> Dict[str, Any]:
        """Надевание комплекта одежды."""
        payload = {"clothingZones": zones_map}
        resp = await self.http.post("/api/clothing/apply", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def buy_clothing(self, clothing_id: int) -> Dict[str, Any]:
        """Покупка предмета одежды."""
        resp = await self.http.post("/api/clothing/buy", json={"clothingId": clothing_id})
        resp.raise_for_status()
        return resp.json()

    async def get_stashgear_all(self) -> Dict[str, Any]:
        """Получение списка нычек и предметов экипировки (/api/stashgear/all) с кэшированием (10 минут)."""
        now = time.time()
        if self._stashgear_cache is not None and now - self._stashgear_cache_time < 600.0:
            return self._stashgear_cache
        resp = await self.http.get("/api/stashgear/all")
        resp.raise_for_status()
        self._stashgear_cache = resp.json()
        self._stashgear_cache_time = now
        return self._stashgear_cache

    def _ensure_catalogs_loaded(self) -> None:
        """Загрузка каталогов татуировок, одежды и камер из локального файла кэша."""
        if (
            self._tattoos_cache is not None
            and self._clothing_cache is not None
            and self._cameras_cache is not None
        ):
            return

        if CACHE_FILE_PATH.exists():
            try:
                with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        now = time.time()
                        if self._tattoos_cache is None:
                            self._tattoos_cache = data.get("tattoos", [])
                            self._tattoos_cache_time = now
                        if self._clothing_cache is None:
                            self._clothing_cache = data.get("clothing", [])
                            self._clothing_cache_time = now
                        if self._cameras_cache is None:
                            self._cameras_cache = data.get("cameras", [])
                            self._cameras_cache_time = now
            except Exception as e:
                logger.error("Error reading tattoo/clothing cache file: %s", e)

        if self._tattoos_cache is None:
            self._tattoos_cache = []
        if self._clothing_cache is None:
            self._clothing_cache = []
        if self._cameras_cache is None:
            self._cameras_cache = []

    async def get_tattoos_catalog(self) -> List[Dict[str, Any]]:
        """Получение полного каталога татуировок с кэшированием в памяти на 10 минут."""
        now = time.time()
        if self._tattoos_cache is not None and (now - self._tattoos_cache_time) < 600:
            return self._tattoos_cache

        self._ensure_catalogs_loaded()
        return self._tattoos_cache or []

    async def get_clothing_catalog(self) -> List[Dict[str, Any]]:
        """Получение полного каталога одежды с кэшированием в памяти на 10 минут."""
        now = time.time()
        if self._clothing_cache is not None and (now - self._clothing_cache_time) < 600:
            return self._clothing_cache

        self._ensure_catalogs_loaded()
        return self._clothing_cache or []
