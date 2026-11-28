import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import parse_qs, urlsplit
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

    def __init__(self, http_client: Any = None, client: Any = None):
        self.http = http_client or client
        self._tattoos_cache: Optional[List[Dict[str, Any]]] = None
        self._tattoos_cache_time: float = 0.0
        self._clothing_cache: Optional[List[Dict[str, Any]]] = None
        self._clothing_cache_time: float = 0.0
        self._cameras_cache: Optional[List[Dict[str, Any]]] = None
        self._cameras_cache_time: float = 0.0
        self._stashgear_cache: Optional[Dict[str, Any]] = None
        self._stashgear_cache_time: float = 0.0
        self._collections_cache: Dict[int, tuple[float, Dict[str, Any]]] = {}
        self._init_inflight: Optional[asyncio.Task] = None

    async def init_player(self) -> Dict[str, Any]:
        """Инициализация состояния игрока и получение балансов (single-flight)."""
        if self._init_inflight is not None and not self._init_inflight.done():
            return await self._init_inflight

        async def _do_init() -> Dict[str, Any]:
            resp = await self.http.post("/api/player/init", json={})
            resp.raise_for_status()
            return resp.json()

        task = asyncio.create_task(_do_init())
        self._init_inflight = task
        try:
            return await task
        finally:
            if self._init_inflight is task:
                self._init_inflight = None

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

    async def get_stew_status(self, rebuild: bool = False) -> Dict[str, Any]:
        """Получение баланса тушенки, прогресса достижений и гаранта посылок."""
        flag = "true" if rebuild else "false"
        resp = await self.http.get(f"/api/achievement/stew/status?rebuild={flag}")
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def parse_parcels_progress(raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, int]]:
        """Нормализует ответ /api/achievement/stew/status в единый объект parcels_progress."""
        if not isinstance(raw, dict):
            return None
        prog = raw.get("progress") if isinstance(raw.get("progress"), dict) else {}
        cp = raw.get("clothingProgress") if isinstance(raw.get("clothingProgress"), dict) else {}
        stew_val = raw.get("stewBalance") if raw.get("stewBalance") is not None else raw.get("stew")
        if stew_val is None and not prog and not cp:
            return None
        return {
            "stew_count": max(0, int(stew_val or 0)),
            "achievements_current": max(0, int(prog.get("current") or 0)),
            "achievements_target": max(1, int(prog.get("step") or 50)),
            "guaranteed_item_current": max(0, int(cp.get("opensSinceClothing") or 0)),
            "guaranteed_item_target": max(1, int(cp.get("pityOpenings") or 20)),
        }

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

    async def get_player_summary(self, user_id: int) -> Dict[str, Any]:
        """Получение сводки достижений, талантов и побед над боссами игрока (GET /api/summary/{userId})."""
        resp = await self.http.get(f"/api/summary/{user_id}")
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

    async def claim_toilet_paper(self) -> Dict[str, Any]:
        """Ежедневное действие: «Щипануть туалетку» у барыги (POST /api/daily/toilet-paper)."""
        resp = await self.http.post("/api/daily/toilet-paper", json={})
        resp.raise_for_status()
        return resp.json()

    async def get_podogrev_friends(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Получение списка друзей, которым можно отправить подогрев (GET /api/podogrev/friends)."""
        resp = await self.http.get(f"/api/podogrev/friends?page={page}&pageSize={page_size}")
        resp.raise_for_status()
        return resp.json()

    async def send_podogrev(self, recipient_ids: List[int], send_to_all: bool = False, gift_type: int = 1) -> Dict[str, Any]:
        """
        Отправка бесплатных подогревов друзьям (POST /api/podogrev/send).
        Категорический запрет на платные подарки /api/gifts/send.
        """
        if send_to_all:
            payload: Dict[str, Any] = {
                "type": int(gift_type),
                "sendToAll": True,
            }
        else:
            payload = {
                "type": int(gift_type),
                "sendToAll": False,
                "recipientIds": [int(uid) for uid in recipient_ids],
            }
        resp = await self.http.post("/api/podogrev/send", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def send_all_podogrev(self) -> Dict[str, Any]:
        """
        Получает список друзей, готовых к приему подогрева (GET /api/podogrev/friends)
        и отправляет им подогревы (POST /api/podogrev/send).
        Категорический запрет на /api/gifts/send.
        """
        try:
            friends_data = await self.get_podogrev_friends(page=1, page_size=50)
            friends_list = (
                friends_data.get("friends")
                or friends_data.get("items")
                or friends_data.get("list")
                or []
            )
            recipient_ids = []
            for f in friends_list:
                if isinstance(f, dict):
                    fid = f.get("id") or f.get("userId")
                    can_send = f.get("canSend", True)
                    if fid and can_send:
                        recipient_ids.append(int(fid))

            if not recipient_ids:
                return {"success": True, "sent": 0, "message": "Нет доступных друзей для отправки подогревов"}

            res = await self.send_podogrev(recipient_ids=recipient_ids, send_to_all=True)
            return {"success": True, "sent": len(recipient_ids), "result": res}
        except Exception as e:
            logger.error("Ошибка в send_all_podogrev: %s", e)
            return {"success": False, "error": str(e), "sent": 0}

    async def get_monthly_state(self, track_open: bool = True) -> Dict[str, Any]:
        """Получение состояния Месячных Делюг (GET /api/monthly/state)."""
        resp = await self.http.get(f"/api/monthly/state?trackOpen={'true' if track_open else 'false'}")
        resp.raise_for_status()
        return resp.json()

    async def claim_monthly_tier(self, tier: int) -> Dict[str, Any]:
        """Получение награды за выполненный тир Месячных Делюг (POST /api/monthly/claim)."""
        resp = await self.http.post("/api/monthly/claim", json={"Tier": int(tier)})
        resp.raise_for_status()
        return resp.json()

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

    @staticmethod
    def _unwrap_game_asset_url(image_url: str) -> str:
        """Преобразует проксированный URL (/api/v1/assets/proxy?path=...) или CDN URL в чистый путь игры (assets/...)."""
        raw = str(image_url or "").strip()
        if not raw:
            return ""
        if "assets/proxy" in raw:
            parsed = urlsplit(raw)
            qs = parse_qs(parsed.query)
            path_vals = qs.get("path") or []
            if path_vals and path_vals[0]:
                raw = str(path_vals[0]).strip()
        cdn_prefix = "https://oldprison-prod-assets-cdn-yandex.luckygem.online/"
        if raw.startswith(cdn_prefix):
            raw = raw[len(cdn_prefix):]
        if raw.startswith("/assets/"):
            raw = raw.lstrip("/")
        return raw

    def _resolve_catalog_item(self, kind: str, item_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает элемент каталога по ID для татуировок или одежды."""
        if item_id <= 0:
            return None
        self._ensure_catalogs_loaded()
        catalog = self._tattoos_cache if kind == "tattoo" else self._clothing_cache
        for item in catalog or []:
            if isinstance(item, dict) and item.get("id") == item_id:
                return item
        return None

    def _normalize_zones_payload(
        self,
        kind: str,
        zones_map: Dict[str, Any],
        *,
        require_positive_id: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Приводит zonesMap к строгому контракту игрового API:
        - tattoo:   {"<zone>": {"tattooId": int, "imageUrl": str}}
        - clothing: {"<zone>": {"clothingId": int, "imageUrl": str}}
        При надевании сета (require_positive_id=True) никогда не включает зоны с id <= 0,
        чтобы исключить случайное снятие наколок/одежды на сервере игры.
        """
        if not isinstance(zones_map, dict):
            return {}
        id_key = "tattooId" if kind == "tattoo" else "clothingId"
        normalized: Dict[str, Dict[str, Any]] = {}
        for zone_key, info in zones_map.items():
            try:
                zone_int = int(zone_key)
            except (TypeError, ValueError):
                continue
            if zone_int <= 0:
                continue

            if isinstance(info, dict):
                raw_id = info.get(id_key)
                if raw_id is None:
                    raw_id = info.get("id")
                if raw_id is None:
                    raw_id = info.get("item_id")
                try:
                    item_id = int(raw_id or 0)
                except (TypeError, ValueError):
                    item_id = 0
                raw_url = str(
                    info.get("rawImageUrl")
                    or info.get("imageUrl")
                    or info.get("image_url")
                    or ""
                )
            else:
                try:
                    item_id = int(info or 0)
                except (TypeError, ValueError):
                    item_id = 0
                raw_url = ""

            if require_positive_id and item_id <= 0:
                continue

            clean_url = self._unwrap_game_asset_url(raw_url)
            if item_id > 0 and (not clean_url or clean_url.startswith("/static/")):
                cat_item = self._resolve_catalog_item(kind, item_id)
                if cat_item:
                    clean_url = self._unwrap_game_asset_url(cat_item.get("imageUrl") or "")

            if require_positive_id and not clean_url:
                logger.warning("Wardrobe %s zone=%s id=%s skipped: empty imageUrl", kind, zone_int, item_id)
                continue

            normalized[str(zone_int)] = {
                id_key: item_id,
                "imageUrl": clean_url,
            }
        return normalized

    async def select_camera(self, camera_id: int) -> Dict[str, Any]:
        """Выбор активной камеры (Хаты)."""
        cid = int(camera_id)
        logger.info("Wardrobe select_camera: cameraId=%s", cid)
        resp = await self.http.post("/api/camera/select", json={"cameraId": cid})
        resp.raise_for_status()
        data = resp.json()
        logger.info("Wardrobe select_camera response: status=%s ok=%s", resp.status_code, data.get("success"))
        return data

    async def buy_camera(self, camera_id: int) -> Dict[str, Any]:
        """Покупка камеры."""
        resp = await self.http.post("/api/camera/buy", json={"cameraId": int(camera_id)})
        resp.raise_for_status()
        return resp.json()

    async def equip_tattoo(self, zone: int, tattoo_id: int, image_url: str = "") -> Dict[str, Any]:
        """Надевание татуировки."""
        tid = int(tattoo_id)
        if tid <= 0:
            raise ValueError("tattoo_id должен быть > 0 для надевания; для снятия используйте unequip_tattoo")
        clean_url = self._unwrap_game_asset_url(image_url)
        if not clean_url or clean_url.startswith("/static/"):
            cat_item = self._resolve_catalog_item("tattoo", tid)
            if cat_item:
                clean_url = self._unwrap_game_asset_url(cat_item.get("imageUrl") or "")
        payload = {"tattooZones": {str(int(zone)): {"tattooId": tid, "imageUrl": clean_url}}}
        logger.info("Wardrobe equip_tattoo: zone=%s tattooId=%s imageUrl=%s", zone, tid, clean_url)
        resp = await self.http.post("/api/tattoo/apply", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Wardrobe equip_tattoo response: status=%s ok=%s", resp.status_code, data.get("success"))
        return data

    async def unequip_tattoo(self, zone: int) -> Dict[str, Any]:
        """Снятие татуировки с зоны."""
        payload = {"tattooZones": {str(int(zone)): {"tattooId": 0, "imageUrl": ""}}}
        logger.info("Wardrobe unequip_tattoo: zone=%s", zone)
        resp = await self.http.post("/api/tattoo/apply", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Wardrobe unequip_tattoo response: status=%s ok=%s", resp.status_code, data.get("success"))
        return data

    async def equip_tattoo_set(self, zones_map: Dict[str, Any]) -> Dict[str, Any]:
        """Надевание целого комплекта татуировок по контракту POST /api/tattoo/apply."""
        normalized = self._normalize_zones_payload("tattoo", zones_map, require_positive_id=True)
        if not normalized:
            raise ValueError("Нет валидных частей комплекта татуировок для надевания")
        payload = {"tattooZones": normalized}
        logger.info(
            "Wardrobe equip_tattoo_set: zones_count=%d zones=%s",
            len(normalized),
            list(normalized.keys()),
        )
        resp = await self.http.post("/api/tattoo/apply", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "Wardrobe equip_tattoo_set response: status=%s ok=%s body=%s",
            resp.status_code,
            data.get("success") if isinstance(data, dict) else None,
            str(data)[:240],
        )
        return data

    async def buy_tattoo(self, tattoo_id: int) -> Dict[str, Any]:
        """Покупка татуировки."""
        resp = await self.http.post("/api/tattoo/buy", json={"tattooId": int(tattoo_id)})
        resp.raise_for_status()
        return resp.json()

    async def equip_clothing(self, zone: int, clothing_id: int, image_url: str = "") -> Dict[str, Any]:
        """Надевание предмета одежды."""
        cid = int(clothing_id)
        if cid <= 0:
            raise ValueError("clothing_id должен быть > 0 для надевания; для снятия используйте unequip_clothing")
        clean_url = self._unwrap_game_asset_url(image_url)
        if not clean_url or clean_url.startswith("/static/"):
            cat_item = self._resolve_catalog_item("clothing", cid)
            if cat_item:
                clean_url = self._unwrap_game_asset_url(cat_item.get("imageUrl") or "")
        payload = {"clothingZones": {str(int(zone)): {"clothingId": cid, "imageUrl": clean_url}}}
        logger.info("Wardrobe equip_clothing: zone=%s clothingId=%s imageUrl=%s", zone, cid, clean_url)
        resp = await self.http.post("/api/clothing/apply", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Wardrobe equip_clothing response: status=%s ok=%s", resp.status_code, data.get("success"))
        return data

    async def unequip_clothing(self, zone: int) -> Dict[str, Any]:
        """Снятие одежды с зоны."""
        payload = {"clothingZones": {str(int(zone)): {"clothingId": 0, "imageUrl": ""}}}
        logger.info("Wardrobe unequip_clothing: zone=%s", zone)
        resp = await self.http.post("/api/clothing/apply", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Wardrobe unequip_clothing response: status=%s ok=%s", resp.status_code, data.get("success"))
        return data

    async def equip_clothing_set(self, zones_map: Dict[str, Any]) -> Dict[str, Any]:
        """Надевание комплекта одежды по контракту POST /api/clothing/apply."""
        normalized = self._normalize_zones_payload("clothing", zones_map, require_positive_id=True)
        if not normalized:
            raise ValueError("Нет валидных частей комплекта одежды для надевания")
        payload = {"clothingZones": normalized}
        logger.info(
            "Wardrobe equip_clothing_set: zones_count=%d zones=%s",
            len(normalized),
            list(normalized.keys()),
        )
        resp = await self.http.post("/api/clothing/apply", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "Wardrobe equip_clothing_set response: status=%s ok=%s body=%s",
            resp.status_code,
            data.get("success") if isinstance(data, dict) else None,
            str(data)[:240],
        )
        return data

    async def buy_clothing(self, clothing_id: int) -> Dict[str, Any]:
        """Покупка предмета одежды."""
        resp = await self.http.post("/api/clothing/buy", json={"clothingId": int(clothing_id)})
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


_FULL_PROFILE_MARKERS = (
    "vpiTier",
    "vpi_tier",
    "obshakTier",
    "obshak_tier",
    "subType",
    "subLevel",
    "fundTier",
    "vpi",
    "obshak",
    "obshchak",
    "commonFund",
    "subscription",
    "vip",
    "weaponDamage",
    "weaponStats",
    "talentsCount",
    "talents",
    "resources",
    "camera",
    "tattoos",
    "clothing",
    "activeTattoos",
    "activeClothing",
    "isFriend",
    "friendStatus",
)


def extract_obshak_from_payload(
    payload: Any,
    now_ts: Optional[float] = None,
) -> tuple[Optional[bool], str]:
    """
    Канонический парсер наличия и типа общака из payload профиля/лидерборда.
    Возвращает `(has_obshak, obshak_type)`:
      - `(True, "pacan" | "blat" | "vor" | "avtoritet")` — активный общак найден
      - `(False, "none")` — полный профиль получен и общака в нём явно нет
      - `(None, "unknown")` — сокращённый объект без полей профиля/общака
    """
    if not isinstance(payload, dict):
        return (None, "unknown")

    src = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(src, dict):
        return (None, "unknown")

    from client.api.social import parse_obshak_info

    info = parse_obshak_info(src, now_ts=now_ts)
    if info.get("has_obshak") and info.get("obshak_tier") in ("pacan", "blat", "avtoritet", "vor"):
        return (True, str(info["obshak_tier"]))

    # Если это полный ответ профиля или в нём явно переданы поля общака (даже null/истёкший) -> 'none'
    if any(k in src for k in _FULL_PROFILE_MARKERS):
        return (False, "none")

    return (None, "unknown")
