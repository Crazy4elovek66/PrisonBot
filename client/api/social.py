import asyncio
import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from client.http_client import GameHttpClient

logger = logging.getLogger(__name__)

# Базовый урон 3 оружий персонажа в игре (bundle.js, module 607)
_BASE_WEAPON_DAMAGE: Dict[str, int] = {"poison": 250, "gunshot": 60, "knife": 30}

# Порядок прокачки дерева талантов (/api/talent/status: id, maxLevel, advanceGate, weapon, flatBonusPerLevel)
# Талант id=6 (бицепс, max=200) открывает переход к id=7 после 10 очков (advanceGate=10).
# Узлы [35, 36, 37] открываются одновременно после id=34.
_TALENT_LINEAR_SPECS: Tuple[Tuple[int, int, int, Optional[str], int], ...] = (
    (0, 10, 10, "knife", 1),
    (1, 20, 20, "gunshot", 1),
    (2, 10, 10, "poison", 10),
    (3, 10, 10, None, 0),
    (4, 10, 10, None, 0),
    (5, 10, 10, None, 0),
    (6, 200, 10, None, 0),
    (7, 10, 10, None, 0),
    (8, 10, 10, None, 0),
    (9, 10, 10, None, 0),
    (10, 2, 2, None, 0),
    (11, 6, 6, None, 0),
    (12, 4, 4, None, 0),
    (13, 10, 10, None, 0),
    (14, 10, 10, None, 0),
    (15, 10, 10, None, 0),
    (16, 1, 1, None, 0),
    (17, 10, 10, None, 0),
    (18, 20, 20, None, 0),
    (19, 32, 32, None, 0),
    (20, 45, 45, None, 0),
    (21, 40, 40, None, 0),
    (22, 5, 5, "poison", 10),
    (23, 10, 10, None, 0),
    (24, 102, 102, "knife", 1),
    (25, 20, 20, None, 0),
    (26, 150, 150, "gunshot", 1),
    (27, 10, 10, None, 0),
    (28, 10, 10, "poison", 10),
    (29, 70, 70, None, 0),
    (30, 10, 10, "poison", 10),
    (31, 6, 6, None, 0),
    (32, 10, 10, "gunshot", 10),
    (33, 48, 48, None, 0),
    (34, 2, 2, None, 0),
)
_TALENT_BRANCH_35_37: Tuple[Tuple[int, int, str, int], ...] = (
    (35, 10, "gunshot", 30),
    (36, 10, "poison", 50),
    (37, 10, "knife", 50),
)


def _normalize_asset_key(raw: Any) -> str:
    return str(raw or "").strip().lower().lstrip("/")


@lru_cache(maxsize=1)
def _load_wardrobe_bonus_catalog() -> Dict[str, Dict[Any, Tuple[int, Dict[str, int]]]]:
    """Ленивая загрузка справочника наколок и шмота для точного расчета боевых бонусов."""
    cache_path = Path(__file__).resolve().parent.parent.parent / "storage" / "tattoo_clothing_cache.json"
    empty = {
        "tattoo_by_id": {},
        "tattoo_by_url": {},
        "clothing_by_id": {},
        "clothing_by_url": {},
    }
    if not cache_path.exists():
        return empty
    try:
        with open(cache_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        logger.debug(f"Не удалось прочитать каталог tattoo_clothing_cache.json: {exc}")
        return empty

    def _index_items(items: List[Dict[str, Any]]) -> Tuple[Dict[int, Tuple[int, Dict[str, int]]], Dict[str, Tuple[int, Dict[str, int]]]]:
        by_id: Dict[int, Tuple[int, Dict[str, int]]] = {}
        by_url: Dict[str, Tuple[int, Dict[str, int]]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            iid = item.get("id")
            if iid is None:
                continue
            try:
                iid_int = int(iid)
            except (TypeError, ValueError):
                continue
            raw_bonus = item.get("combat_stats_bonus") or {}
            if not isinstance(raw_bonus, dict):
                raw_bonus = {}
            clean_bonus = {
                w: int(raw_bonus.get(w) or 0)
                for w in ("poison", "gunshot", "knife")
                if int(raw_bonus.get(w) or 0) > 0
            }
            entry = (iid_int, clean_bonus)
            by_id[iid_int] = entry
            for url_field in ("imageUrl", "imageBackUrl", "backImageUrl"):
                norm_u = _normalize_asset_key(item.get(url_field))
                if norm_u:
                    by_url.setdefault(norm_u, entry)
        return by_id, by_url

    t_id, t_url = _index_items(data.get("tattoos") or [])
    c_id, c_url = _index_items(data.get("clothing") or [])
    return {
        "tattoo_by_id": t_id,
        "tattoo_by_url": t_url,
        "clothing_by_id": c_id,
        "clothing_by_url": c_url,
    }


def calculate_talent_weapon_floor(talent_points: int) -> Dict[str, int]:
    """
    Вычисляет гарантированный нижний бонус урона от дерева талантов (/api/talent/status)
    по общему числу вложенных очков талантов с учетом необязательного добора id=6 (200 ур.)
    и параллельной ветки [35, 36, 37].
    """
    pts = max(0, int(talent_points or 0))
    bonuses = {"poison": 0, "gunshot": 0, "knife": 0}
    if pts <= 0:
        return bonuses

    # Обязательные последовательные очки от 0 до 34 (с порогом перехода gate=10 для id=6)
    optional_pool = 0
    for tid, max_lvl, gate, weapon, flat in _TALENT_LINEAR_SPECS:
        if pts <= 0:
            break
        if tid == 6:
            gate_spent = min(pts, gate)
            pts -= gate_spent
            optional_pool = max_lvl - gate
            if pts <= 0:
                break
            # Выделяем худший случай (игрок мог потратить до 190 лишних очков в id=6 до перехода далее)
            reserved = min(pts, optional_pool)
            pts -= reserved
            continue
        spent = min(pts, gate)
        pts -= spent
        if weapon and flat > 0 and spent > 0:
            bonuses[weapon] += spent * flat

    # Параллельные таланты [35, 36, 37]: в худшем случае сначала вкачиваются два других (20 очков)
    if pts > 0:
        other_branch_max = 20
        for _tid, max_lvl, weapon, flat in _TALENT_BRANCH_35_37:
            guaranteed = min(max_lvl, max(0, pts - other_branch_max))
            if guaranteed > 0:
                bonuses[weapon] += guaranteed * flat

    return bonuses


def _collect_zone_bonuses(
    zones_obj: Any,
    by_id: Dict[int, Tuple[int, Dict[str, int]]],
    by_url: Dict[str, Tuple[int, Dict[str, int]]],
    seen_ids: Set[int],
    totals: Dict[str, int],
) -> None:
    if not isinstance(zones_obj, dict):
        return
    for val in zones_obj.values():
        match: Optional[Tuple[int, Dict[str, int]]] = None
        if isinstance(val, int) and val > 0:
            match = by_id.get(val)
        elif isinstance(val, dict):
            raw_id = val.get("tattooId") or val.get("clothingId") or val.get("id")
            if raw_id is not None:
                try:
                    match = by_id.get(int(raw_id))
                except (TypeError, ValueError):
                    match = None
            if not match:
                norm_u = _normalize_asset_key(val.get("imageUrl") or val.get("url"))
                if norm_u:
                    match = by_url.get(norm_u)
        elif isinstance(val, str):
            norm_u = _normalize_asset_key(val)
            if norm_u:
                match = by_url.get(norm_u)

        if match:
            item_id, item_bonus = match
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            for w in ("poison", "gunshot", "knife"):
                totals[w] += item_bonus.get(w, 0)


def compute_player_weapon_damage_floor(
    player_view_data: Dict[str, Any],
    talents_total: int = 0,
) -> Dict[str, int]:
    """
    Рассчитывает реальный гарантированный урон 3 оружий по экипированным вещам, наколкам и талантам:
    base (250/60/30) + clothing combat_stats_bonus + tattoo combat_stats_bonus + talent weapon_bonus.
    Совпадает с /api/boss/check-session -> weaponStatsEffective для профиля с точностью 100%.
    """
    catalog = _load_wardrobe_bonus_catalog()
    totals = dict(_BASE_WEAPON_DAMAGE)

    seen_clothing: Set[int] = set()
    _collect_zone_bonuses(
        player_view_data.get("clothingFrontIds"),
        catalog["clothing_by_id"],
        catalog["clothing_by_url"],
        seen_clothing,
        totals,
    )
    _collect_zone_bonuses(
        player_view_data.get("clothingZones"),
        catalog["clothing_by_id"],
        catalog["clothing_by_url"],
        seen_clothing,
        totals,
    )
    _collect_zone_bonuses(
        player_view_data.get("clothingBackZones"),
        catalog["clothing_by_id"],
        catalog["clothing_by_url"],
        seen_clothing,
        totals,
    )

    seen_tattoos: Set[int] = set()
    _collect_zone_bonuses(
        player_view_data.get("tattooZones"),
        catalog["tattoo_by_id"],
        catalog["tattoo_by_url"],
        seen_tattoos,
        totals,
    )

    t_bonuses = calculate_talent_weapon_floor(talents_total)
    for w in ("poison", "gunshot", "knife"):
        totals[w] += t_bonuses[w]

    return totals


def calculate_level_from_authority(authority: int) -> int:
    """
    Расчет игрового уровня арестанта по формуле оригинальной игры (Module 415 bundle.js):
    D = 1600 + 80 * max(0, authority)
    level = max(1, floor((-40 + sqrt(D)) / 40))
    """
    auth = max(0, int(authority or 0))
    disc = 1600 + 80 * auth
    if disc < 0:
        return 1
    lvl = int((-40 + math.sqrt(disc)) / 40)
    return max(1, lvl)


def extract_player_combat_stats(
    payload: Optional[Dict[str, Any]],
    summary_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Универсальное извлечение боевых и профильных характеристик игрока из ответов API
    (/api/friendship/requests, /api/player/view/{uid}, /api/summary/{uid} и др.).
    Если сервер не отдает weaponDamage напрямую (входная заявка), рассчитывает реальный урон
    по надетому шмоту, наколкам и талантам игрока (только при наличии данных профиля/summary; иначе 0).
    """
    raw = payload if isinstance(payload, dict) else {}
    p_data = raw.get("data") if isinstance(raw.get("data"), dict) else raw

    res_obj = p_data.get("resources") if isinstance(p_data.get("resources"), dict) else {}
    stats_obj = p_data.get("stats") if isinstance(p_data.get("stats"), dict) else {}
    combat_obj = p_data.get("combatStats") if isinstance(p_data.get("combatStats"), dict) else {}
    prof_obj = p_data.get("profile") if isinstance(p_data.get("profile"), dict) else {}
    user_obj = p_data.get("user") if isinstance(p_data.get("user"), dict) else {}

    authority = int(
        res_obj.get("authority")
        or p_data.get("authority")
        or stats_obj.get("authority")
        or 0
    )

    level = int(
        p_data.get("level")
        or p_data.get("lvl")
        or res_obj.get("level")
        or stats_obj.get("level")
        or 0
    )
    if (level <= 1 or level == 0) and authority > 0:
        level = calculate_level_from_authority(authority)

    raw_b = (
        p_data.get("biceps")
        or stats_obj.get("biceps")
        or res_obj.get("biceps")
        or prof_obj.get("biceps")
        or user_obj.get("biceps")
    )
    biceps: Optional[int] = int(raw_b) if (raw_b is not None and int(raw_b) > 0) else None

    talents = int(
        p_data.get("talents")
        or p_data.get("talentsCount")
        or p_data.get("TalentsCount")
        or p_data.get("talentPointsTotal")
        or stats_obj.get("talents")
        or stats_obj.get("talentsCount")
        or 0
    )
    if talents == 0 and isinstance(summary_payload, dict):
        s_data = summary_payload.get("data") if isinstance(summary_payload.get("data"), dict) else summary_payload
        ov = s_data.get("overview") or s_data.get("Overview") or {}
        if isinstance(ov, dict):
            talents = int(ov.get("talentPointsTotal") or ov.get("talentsCount") or ov.get("talents") or 0)

    wep_dmg = (
        p_data.get("weaponDamage")
        or p_data.get("WeaponDamage")
        or p_data.get("weaponStatsEffective")
        or stats_obj.get("weaponDamage")
        or stats_obj.get("WeaponDamage")
        or combat_obj.get("weaponDamage")
        or {}
    )
    if not isinstance(wep_dmg, dict):
        wep_dmg = {}

    poison_dmg = int(
        wep_dmg.get("poison")
        or wep_dmg.get("Poison")
        or combat_obj.get("poison")
        or p_data.get("poisonDamage")
        or p_data.get("PoisonDamage")
        or 0
    )
    gunshot_dmg = int(
        wep_dmg.get("gunshot")
        or wep_dmg.get("Gunshot")
        or combat_obj.get("gunshot")
        or p_data.get("gunshotDamage")
        or p_data.get("GunshotDamage")
        or 0
    )
    knife_dmg = int(
        wep_dmg.get("knife")
        or wep_dmg.get("Knife")
        or combat_obj.get("knife")
        or p_data.get("knifeDamage")
        or p_data.get("KnifeDamage")
        or 0
    )

    weapon_estimated = False
    has_profile_build = bool(
        isinstance(p_data.get("tattooZones"), dict)
        or isinstance(p_data.get("clothingZones"), dict)
        or isinstance(p_data.get("clothingFrontIds"), dict)
        or talents > 0
    )
    if poison_dmg == 0 and gunshot_dmg == 0 and knife_dmg == 0 and has_profile_build:
        calc = compute_player_weapon_damage_floor(p_data, talents_total=talents)
        poison_dmg = calc["poison"]
        gunshot_dmg = calc["gunshot"]
        knife_dmg = calc["knife"]
        weapon_estimated = True

    total_dmg = int(
        p_data.get("totalDamage")
        or p_data.get("TotalDamage")
        or p_data.get("bossDamage")
        or p_data.get("damage")
        or (knife_dmg + poison_dmg + gunshot_dmg)
        or 0
    )

    return {
        "authority": authority,
        "level": level,
        "biceps": biceps,
        "talents": talents,
        "poisonDamage": poison_dmg,
        "gunshotDamage": gunshot_dmg,
        "knifeDamage": knife_dmg,
        "totalDamage": total_dmg,
        "weaponDamageEstimated": weapon_estimated,
    }


class SocialAPI:
    """
    Методы взаимодействия с социальными функциями и регулярными событиями:
    - Подарки (GET /api/gifts/inbox, POST /api/gifts/claim, POST /api/gifts/send)
    - Друзья (GET /api/friendship/requests, GET /api/friendship/accept-request, GET /api/friendship/list)
    - Ежемесячный календарь (GET /api/monthly/state, POST /api/monthly/claim)
    - Дворовые игры (GET /api/yard/games, POST /api/kolsik/roll-paper)
    """

    def __init__(self, http_client: GameHttpClient):
        self.http = http_client

    async def get_gifts_inbox(self) -> Dict[str, Any]:
        """Получение списка входящих подарков."""
        resp = await self.http.get("/api/gifts/inbox")
        resp.raise_for_status()
        return resp.json()

    # Псевдоним для совместимости
    get_inbox_gifts = get_gifts_inbox

    async def claim_gift(self, gift_id: Any) -> Dict[str, Any]:
        """Сбор входящего подарка."""
        resp = await self.http.post("/api/gifts/claim", json={"giftId": gift_id})
        resp.raise_for_status()
        return resp.json()

    async def get_gifts_stats(self) -> Dict[str, Any]:
        """Получение статистики подарков."""
        resp = await self.http.get("/api/gifts/stats")
        resp.raise_for_status()
        return resp.json()

    async def send_gift(
        self,
        to_user_id: int,
        tier: int = 1,
        kind: str = "chips",
        message: str = "",
    ) -> Dict[str, Any]:
        """Отправка подарка другу."""
        payload = {
            "toUserId": to_user_id,
            "tier": tier,
            "kind": kind,
            "message": message,
        }
        resp = await self.http.post("/api/gifts/send", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_friend_requests(self, page: int = 0, page_size: int = 50) -> Any:
        """Получение списка входящих заявок в друзья."""
        url = f"/api/friendship/requests?page={page}&pageSize={page_size}"
        resp = await self.http.get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_enriched_friend_requests(
        self,
        page: int = 0,
        page_size: int = 50,
        player_api: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Запрашивает список входящих заявок в друзья (GET /api/friendship/requests)
        и обогащает профили кандидатов ключевыми характеристиками:
        level, authority, biceps, talents, knifeDamage, poisonDamage, gunshotDamage, totalDamage.
        """
        raw_res = await self.get_friend_requests(page=page, page_size=page_size)
        raw_list = (
            raw_res
            if isinstance(raw_res, list)
            else raw_res.get("requests", [])
            if isinstance(raw_res, dict)
            else []
        )

        sem = asyncio.Semaphore(5)

        async def _enrich_candidate(c: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(c, dict):
                return {}

            uid = c.get("userId") or c.get("fromUserId") or c.get("id")
            nick = c.get("nickname") or c.get("name") or (f"Игрок {uid}" if uid else "Арестант")
            photo = c.get("photoUrl") or c.get("avatarUrl") or c.get("photo")

            base_stats = extract_player_combat_stats(c)
            poi_dmg = base_stats["poisonDamage"]
            gun_dmg = base_stats["gunshotDamage"]
            kni_dmg = base_stats["knifeDamage"]
            tot_dmg = base_stats["totalDamage"]
            talents = base_stats["talents"]
            level = base_stats["level"]
            authority = base_stats["authority"]
            biceps = base_stats["biceps"]

            # Если базовые характеристики (уровень, авторитет, бицуха, таланты или урон) не заданы в заявке,
            # дозагружаем через /api/player/view/{userId}
            if uid and (level == 0 or authority == 0 or biceps is None or talents == 0 or tot_dmg == 0):
                try:
                    async with sem:
                        if player_api:
                            p_view = await player_api.get_player_view(uid)
                        else:
                            resp = await self.http.get(f"/api/player/view/{uid}")
                            p_view = resp.json() if resp.status_code == 200 else {}

                        ext_stats = extract_player_combat_stats(p_view)
                        p_data = p_view.get("data") if isinstance(p_view.get("data"), dict) else p_view
                        if isinstance(p_data, dict):
                            if not authority:
                                authority = ext_stats["authority"]
                            if not level:
                                level = ext_stats["level"]
                            if biceps is None:
                                biceps = ext_stats["biceps"]
                            if not talents:
                                talents = ext_stats["talents"]
                            if not poi_dmg:
                                poi_dmg = ext_stats["poisonDamage"]
                            if not gun_dmg:
                                gun_dmg = ext_stats["gunshotDamage"]
                            if not kni_dmg:
                                kni_dmg = ext_stats["knifeDamage"]
                            if not tot_dmg:
                                tot_dmg = ext_stats["totalDamage"]
                            if not nick or nick.startswith("Игрок"):
                                ext_nick = p_data.get("nickname") or p_data.get("name")
                                if ext_nick:
                                    nick = ext_nick
                            if not photo:
                                photo = p_data.get("photoUrl") or p_data.get("avatarUrl") or p_data.get("photo")
                except Exception as e:
                    logger.debug(f"Не удалось обогатить профиль игрока {uid}: {e}")

            if level == 0 and authority > 0:
                level = calculate_level_from_authority(authority)

            return {
                "userId": uid,
                "nickname": nick,
                "photoUrl": photo,
                "level": level,
                "authority": authority,
                "biceps": biceps,
                "talents": talents,
                "knifeDamage": kni_dmg,
                "poisonDamage": poi_dmg,
                "gunshotDamage": gun_dmg,
                "totalDamage": tot_dmg if tot_dmg > 0 else (kni_dmg + poi_dmg + gun_dmg),
            }

        tasks = [_enrich_candidate(c) for c in raw_list]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for item in enriched:
            if isinstance(item, dict) and item.get("userId") is not None:
                results.append(item)
        return results

    async def accept_friend(self, from_user_id: int) -> Dict[str, Any]:
        """Принятие заявки в друзья (POST /api/friendship/accept-request?fromUserId={from_user_id})."""
        url = f"/api/friendship/accept-request?fromUserId={from_user_id}"
        resp = await self.http.post(url)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"success": True}

    async def decline_friend(self, from_user_id: int) -> Dict[str, Any]:
        """Отклонение заявки в друзья (POST /api/friendship/decline-request?fromUserId={from_user_id})."""
        url = f"/api/friendship/decline-request?fromUserId={from_user_id}"
        resp = await self.http.post(url)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"success": True}

    async def get_friend_profiles(self, page: int = 0, page_size: int = 50) -> Any:
        """Получение профилей друзей."""
        url = f"/api/friendship/profiles?page={page}&pageSize={page_size}"
        resp = await self.http.get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_friends_list(self) -> Any:
        """Получение списка друзей."""
        resp = await self.http.get("/api/friendship/list")
        resp.raise_for_status()
        return resp.json()

    async def get_all_friend_ids(self) -> Set[int]:
        """
        Корректно разбирает все возможные форматы ответа GET /api/friendship/list:
        - массив int: [9000000000147562, ...]
        - массив dict: [{"userId": ...}, {"id": ...}]
        - объект: {"friends": [...], "total": N} или {"items": [...]}
        Возвращает множество int ID друзей.
        """
        try:
            raw = await self.get_friends_list()
        except Exception as e:
            logger.warning(f"Ошибка получения списка друзей: {e}")
            return set()

        items = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("friends") or raw.get("items") or raw.get("userIds") or []

        friend_ids: Set[int] = set()
        for item in items:
            if isinstance(item, (int, str)):
                try:
                    friend_ids.add(int(item))
                except (ValueError, TypeError):
                    pass
            elif isinstance(item, dict):
                uid = item.get("userId") or item.get("id") or item.get("friendUserId")
                if uid is not None:
                    try:
                        friend_ids.add(int(uid))
                    except (ValueError, TypeError):
                        pass
        return friend_ids

    async def get_all_friend_profiles(self, page_size: int = 100, max_pages: int = 50) -> List[Dict[str, Any]]:
        """
        Итерируется по page = 0, 1, ... через GET /api/friendship/profiles?page={page}&pageSize={page_size}
        до получения пустой страницы или < page_size элементов (с паузой 0.15-0.3с между страницами),
        возвращая полный список всех профилей друзей.
        """
        all_profiles: List[Dict[str, Any]] = []
        for page in range(max_pages):
            try:
                res = await self.get_friend_profiles(page=page, page_size=page_size)
            except Exception as e:
                logger.warning(f"Ошибка пагинации профилей друзей на странице {page}: {e}")
                break

            items = (
                res
                if isinstance(res, list)
                else res.get("profiles") or res.get("items") or []
                if isinstance(res, dict)
                else []
            )

            if not items:
                break

            for p in items:
                if isinstance(p, dict) and p.get("userId") is not None:
                    all_profiles.append(p)

            if len(items) < page_size:
                break

            await asyncio.sleep(0.15)

        return all_profiles

    async def send_friend_request(self, to_user_id: int) -> Dict[str, Any]:
        """Отправка заявки в друзья (POST /api/friendship/send-request?toUserId={to_user_id})."""
        url = f"/api/friendship/send-request?toUserId={to_user_id}"
        resp = await self.http.post(url)
        if resp.status_code in (200, 204):
            try:
                return resp.json()
            except Exception:
                return {"success": True}
        resp.raise_for_status()
        return resp.json()

    async def remove_friend(self, friend_user_id: int) -> Dict[str, Any]:
        """Удаление из друзей (POST /api/friendship/remove-friend?friendUserId={friend_user_id})."""
        url = f"/api/friendship/remove-friend?friendUserId={friend_user_id}"
        resp = await self.http.post(url)
        if resp.status_code in (200, 204):
            try:
                return resp.json()
            except Exception:
                return {"success": True}
        resp.raise_for_status()
        return resp.json()

    async def get_weekly_top(self, limit: int = 100) -> Dict[str, Any]:
        """Получение еженедельного топа игроков по урону (GET /api/weekly-top/top?limit={limit})."""
        resp = await self.http.get(f"/api/weekly-top/top?limit={limit}")
        resp.raise_for_status()
        return resp.json()

    async def get_top_achievements(self, limit: int = 100) -> Dict[str, Any]:
        """Получение топа игроков по достижениям (GET /api/weekly-top/achievements?limit={limit})."""
        resp = await self.http.get(f"/api/weekly-top/achievements?limit={limit}")
        resp.raise_for_status()
        return resp.json()

    async def get_guild_members(self, guild_id: int) -> Dict[str, Any]:
        """Получение состава бригады (GET /api/guild/{guild_id}/members)."""
        resp = await self.http.get(f"/api/guild/{guild_id}/members")
        resp.raise_for_status()
        return resp.json()

    async def get_recruitment_list(self, limit: int = 100) -> Dict[str, Any]:
        """Получение объявлений о наборе в бригады (GET /api/guild/recruitment/list?limit={limit})."""
        resp = await self.http.get(f"/api/guild/recruitment/list?limit={limit}")
        resp.raise_for_status()
        return resp.json()

    async def get_monthly_state(self) -> Dict[str, Any]:
        """Получение состояния ежемесячного календаря наград."""
        resp = await self.http.get("/api/monthly/state")
        resp.raise_for_status()
        return resp.json()

    async def claim_monthly_reward(self, tier: int) -> Dict[str, Any]:
        """Сбор награды ежемесячного календаря."""
        resp = await self.http.post("/api/monthly/claim", json={"Tier": tier})
        resp.raise_for_status()
        return resp.json()

    async def get_yard_games(self) -> Dict[str, Any]:
        """Получение состояния дворовых игр."""
        resp = await self.http.get("/api/yard/games")
        resp.raise_for_status()
        return resp.json()

    async def roll_paper_kolsik(self) -> Dict[str, Any]:
        """Бесплатное вращение кольщика за туалетную бумагу (если доступно)."""
        resp = await self.http.post("/api/kolsik/roll-paper", json={})
        resp.raise_for_status()
        return resp.json()
