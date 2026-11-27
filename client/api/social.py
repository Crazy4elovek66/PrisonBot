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
    cur_obj = p_data.get("currencies") if isinstance(p_data.get("currencies"), dict) else {}
    player_obj = p_data.get("player") if isinstance(p_data.get("player"), dict) else {}

    def _first_pos_int(*vals: Any) -> int:
        for v in vals:
            if v is not None and not isinstance(v, bool):
                try:
                    n = int(v)
                    if n > 0:
                        return n
                except (TypeError, ValueError):
                    pass
        return 0

    authority = _first_pos_int(
        res_obj.get("authority"),
        cur_obj.get("authority"),
        p_data.get("authority"),
        p_data.get("avtoritet"),
        stats_obj.get("authority"),
        prof_obj.get("authority"),
        user_obj.get("authority"),
        player_obj.get("authority"),
        p_data.get("respect"),
        stats_obj.get("respect"),
        p_data.get("rating"),
        p_data.get("reputation"),
    )

    level = _first_pos_int(
        p_data.get("level"),
        p_data.get("lvl"),
        p_data.get("playerLevel"),
        p_data.get("userLevel"),
        res_obj.get("level"),
        stats_obj.get("level"),
        prof_obj.get("level"),
        user_obj.get("level"),
        player_obj.get("level"),
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


_OBSHAK_PROFILE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_OBSHAK_CACHE_TTL_SEC = 1800.0
_OBSHAK_CACHE_MAX_SIZE = 1000

_OBSHAK_TIERS: Dict[str, Tuple[int, str, str]] = {
    "pacan": (1, "Пацанский", "assets/icons/obshak_pacan.webp"),
    "blat": (2, "Блатной", "assets/icons/obshak_blat.webp"),
    "avtoritet": (3, "Авторитетный", "assets/icons/obshak_avtoritet.webp"),
    "vor": (4, "Воровской", "assets/icons/obshak_vor.webp"),
}

_OBSHAK_ALIASES: Dict[str, str] = {
    "1": "pacan",
    "pacan": "pacan",
    "pacansky": "pacan",
    "пацанский": "pacan",
    "2": "blat",
    "blat": "blat",
    "blatnoy": "blat",
    "блатной": "blat",
    "3": "avtoritet",
    "avtoritet": "avtoritet",
    "avtoritetny": "avtoritet",
    "avtoritetnyy": "avtoritet",
    "авторитетный": "avtoritet",
    "4": "vor",
    "vor": "vor",
    "vorovskoy": "vor",
    "воровской": "vor",
}


def _empty_obshak_info() -> Dict[str, Any]:
    return {
        "has_obshak": False,
        "obshak_tier": "none",
        "obshak_rank": 0,
        "obshak_label": "",
        "obshak_icon": "",
        "obshak_expires_ts": None,
    }


def _parse_obshak_expires_ts(raw_val: Any) -> Optional[int]:
    if raw_val is None or raw_val == "" or isinstance(raw_val, bool):
        return None
    try:
        from client.api.menyala import _parse_iso_ts
        return _parse_iso_ts(raw_val)
    except Exception:
        return None


def parse_obshak_info(payload: Any, now_ts: Optional[float] = None) -> Dict[str, Any]:
    """
    Унифицированный парсер наличия и типа активного Общака (Пацанский, Блатной, Авторитетный, Воровской)
    из ответа /api/player/view/{uid} (vpiTier) или объекта заявки/профиля.
    """
    if not isinstance(payload, dict):
        return _empty_obshak_info()

    src = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(src, dict):
        src = payload

    # Если сервер уже вернул нормализованные поля
    if src.get("obshak_tier") in _OBSHAK_TIERS and src.get("has_obshak") is True:
        tier_key = str(src["obshak_tier"])
        rank, label, icon = _OBSHAK_TIERS[tier_key]
        exp_ts = _parse_obshak_expires_ts(src.get("obshak_expires_ts"))
        ref_now = float(now_ts) if now_ts is not None else __import__("time").time()
        if exp_ts is not None and exp_ts <= ref_now:
            return _empty_obshak_info()
        return {
            "has_obshak": True,
            "obshak_tier": tier_key,
            "obshak_rank": rank,
            "obshak_label": label,
            "obshak_icon": icon,
            "obshak_expires_ts": exp_ts,
        }

    vpi_obj = None
    for nested_key in ("vpi", "obshak", "obshchak", "subscription", "vip", "commonFund"):
        if isinstance(src.get(nested_key), dict):
            vpi_obj = src[nested_key]
            break

    raw_tier = None
    for k in ("vpiTier", "vpi_tier", "obshakTier", "obshak_tier", "subType", "subLevel", "fundTier", "tier", "vpi"):
        val = src.get(k)
        if val is not None and not isinstance(val, (dict, list, bool)):
            raw_tier = val
            break
    if raw_tier is None and isinstance(vpi_obj, dict):
        if vpi_obj.get("active") is False or vpi_obj.get("isActive") is False:
            return _empty_obshak_info()
        for k in ("tier", "vpiTier", "name", "level", "type"):
            val = vpi_obj.get(k)
            if val is not None and not isinstance(val, (dict, list, bool)):
                raw_tier = val
                break

    if raw_tier is None:
        return _empty_obshak_info()

    norm = _OBSHAK_ALIASES.get(str(raw_tier).strip().lower())
    if not norm or norm not in _OBSHAK_TIERS:
        return _empty_obshak_info()

    exp_raw = None
    for ek in ("vpiExpiresAt", "vpiEndUnix", "obshakExpiresAt", "expiresAt", "expires_at", "endUnix"):
        if src.get(ek) is not None:
            exp_raw = src.get(ek)
            break
    if exp_raw is None and isinstance(vpi_obj, dict):
        for ek in ("expiresAt", "expires_at", "endUnix", "endsAtUtc"):
            if vpi_obj.get(ek) is not None:
                exp_raw = vpi_obj.get(ek)
                break

    exp_ts = _parse_obshak_expires_ts(exp_raw)
    if exp_ts is not None:
        if now_ts is not None:
            ref_now = float(now_ts)
        else:
            try:
                from client.http_client import get_game_now_ts
                ref_now = get_game_now_ts()
            except Exception:
                ref_now = __import__("time").time()
        if exp_ts <= ref_now:
            return _empty_obshak_info()

    rank, label, icon = _OBSHAK_TIERS[norm]
    return {
        "has_obshak": True,
        "obshak_tier": norm,
        "obshak_rank": rank,
        "obshak_label": label,
        "obshak_icon": icon,
        "obshak_expires_ts": exp_ts,
    }


def _has_explicit_obshak_field(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    src = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return any(k in src for k in ("vpiTier", "vpi_tier", "obshakTier", "obshak_tier", "vpi", "obshak", "obshchak"))


async def enrich_friend_requests_with_obshak(
    requests_list: List[Dict[str, Any]],
    fetch_profile_fn: Optional[Any] = None,
    max_concurrency: int = 3,
    limit_fetch: int = 25,
    cache_ttl_sec: float = _OBSHAK_CACHE_TTL_SEC,
) -> List[Dict[str, Any]]:
    """
    Дообогащает список входящих заявок информацией об Общаке с TTL-кэшем по userId,
    ограничением параллелизма (Semaphore) и защитой от сбоев/rate-limit.
    """
    import time as _time
    from core.server_health import server_health_monitor

    if not isinstance(requests_list, list):
        return []

    sem = asyncio.Semaphore(max(1, int(max_concurrency)))
    fetch_budget = [max(0, int(limit_fetch))]

    async def _enrich_one(req_item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(req_item, dict):
            return req_item
        item = dict(req_item)
        if _has_explicit_obshak_field(item):
            item.update(parse_obshak_info(item))
            return item

        uid = item.get("userId") or item.get("fromUserId") or item.get("id")
        if uid is None:
            item.update(_empty_obshak_info())
            return item

        uid_key = str(uid)
        now_mono = _time.monotonic()
        cached = _OBSHAK_PROFILE_CACHE.get(uid_key)
        if cached and (now_mono - cached[0]) < cache_ttl_sec:
            item.update(dict(cached[1]))
            return item

        if fetch_profile_fn is None or server_health_monitor.is_maintenance or fetch_budget[0] <= 0:
            item.update(_empty_obshak_info())
            return item

        fetch_budget[0] -= 1
        try:
            async with sem:
                prof = await fetch_profile_fn(uid)
            info = parse_obshak_info(prof)
            if isinstance(prof, dict) and prof:
                if len(_OBSHAK_PROFILE_CACHE) >= _OBSHAK_CACHE_MAX_SIZE:
                    oldest_k = next(iter(_OBSHAK_PROFILE_CACHE))
                    _OBSHAK_PROFILE_CACHE.pop(oldest_k, None)
                _OBSHAK_PROFILE_CACHE[uid_key] = (_time.monotonic(), dict(info))
            item.update(info)
            return item
        except Exception as exc:
            logger.debug("Obshak profile enrich failed for %s: %s", uid, exc)
            item.update(_empty_obshak_info())
            return item

    enriched = await asyncio.gather(*(_enrich_one(r) for r in requests_list), return_exceptions=True)
    out: List[Dict[str, Any]] = []
    for orig, res in zip(requests_list, enriched):
        if isinstance(res, dict):
            out.append(res)
        elif isinstance(orig, dict):
            fallback = dict(orig)
            fallback.update(_empty_obshak_info())
            out.append(fallback)
    return out


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

        sem = asyncio.Semaphore(4)
        if not hasattr(self, "_player_view_cache"):
            self._player_view_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

        async def _fetch_player_view_safe(uid: Any) -> Dict[str, Any]:
            uid_key = str(uid)
            now_ts = asyncio.get_running_loop().time()
            cached = self._player_view_cache.get(uid_key)
            if cached and (now_ts - cached[0]) < 60.0:
                return cached[1]
            for attempt in range(3):
                try:
                    async with sem:
                        await asyncio.sleep(0.05 * (attempt + 1))
                        if player_api:
                            p_view = await player_api.get_player_view(uid)
                        else:
                            resp = await self.http.get(f"/api/player/view/{uid}")
                            if resp.status_code in (429, 502, 503, 504):
                                raise RuntimeError(f"HTTP {resp.status_code}")
                            p_view = resp.json() if resp.status_code == 200 else {}
                    if isinstance(p_view, dict) and p_view:
                        self._player_view_cache[uid_key] = (asyncio.get_running_loop().time(), p_view)
                        return p_view
                    return {}
                except Exception as exc:
                    err_s = str(exc).lower()
                    if any(k in err_s for k in ("429", "502", "503", "504", "too many", "timeout")) and attempt < 2:
                        await asyncio.sleep(0.8 * (attempt + 1))
                        continue
                    logger.debug(f"Не удалось обогатить профиль игрока {uid}: {exc}")
                    return {}
            return {}

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
            # дозагружаем через /api/player/view/{userId} с семафором и ретраем при 429
            obshak_info = parse_obshak_info(c) if _has_explicit_obshak_field(c) else None
            if uid and (level == 0 or authority == 0 or biceps is None or talents == 0 or tot_dmg == 0):
                p_view = await _fetch_player_view_safe(uid)
                if isinstance(p_view, dict) and p_view:
                    if obshak_info is None:
                        obshak_info = parse_obshak_info(p_view)
                        if _OBSHAK_PROFILE_CACHE is not None and len(_OBSHAK_PROFILE_CACHE) < _OBSHAK_CACHE_MAX_SIZE:
                            import time as _time
                            _OBSHAK_PROFILE_CACHE[str(uid)] = (_time.monotonic(), dict(obshak_info))
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

            if level == 0 and authority > 0:
                level = calculate_level_from_authority(authority)

            out_item = {
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
            if obshak_info is not None:
                out_item.update(obshak_info)
            return out_item

        tasks = [_enrich_candidate(c) for c in raw_list]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for item in enriched:
            if isinstance(item, dict) and item.get("userId") is not None:
                results.append(item)

        # Дообогащаем оставшиеся заявки (у которых не было vpiTier в заявке и не загружался p_view) через TTL-кэш
        need_obshak = [r for r in results if "obshak_tier" not in r]
        if need_obshak:
            enriched_obshak = await enrich_friend_requests_with_obshak(
                need_obshak,
                fetch_profile_fn=_fetch_player_view_safe,
                max_concurrency=3,
                limit_fetch=25,
            )
            by_uid = {str(x.get("userId")): x for x in enriched_obshak if isinstance(x, dict)}
            for r in results:
                if "obshak_tier" not in r:
                    upd = by_uid.get(str(r.get("userId")))
                    if upd:
                        for k in ("has_obshak", "obshak_tier", "obshak_rank", "obshak_label", "obshak_icon", "obshak_expires_ts"):
                            r[k] = upd.get(k)
                    else:
                        r.update(_empty_obshak_info())
        return results

    @staticmethod
    def classify_friendship_error(
        status_code: int,
        raw_text: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Классифицирует 4xx/5xx ошибку игрового API дружбы без показа сырых httpx-строк."""
        msg = ""
        if isinstance(data, dict):
            msg = str(data.get("message") or data.get("error") or data.get("detail") or "").strip()
        if not msg and raw_text:
            msg = raw_text.strip()[:300]
        low = msg.lower()

        if status_code == 429:
            return {
                "success": False,
                "code": "rate_limited",
                "message": msg or "Слишком много запросов к серверу игры. Повторите через пару секунд.",
                "remove_from_list": False,
                "status_code": status_code,
            }
        if status_code >= 500:
            return {
                "success": False,
                "code": "temporary_error",
                "message": "Временная ошибка сервера игры (5xx). Повторите попытку позже.",
                "remove_from_list": False,
                "status_code": status_code,
            }
        if "у этого игрока" in low or "он не может принять" in low or ("target" in low and "limit" in low):
            return {
                "success": False,
                "code": "target_friends_limit_reached",
                "message": msg or "У этого игрока уже максимальное количество друзей.",
                "remove_from_list": False,
                "status_code": status_code,
            }
        if "максимальное количество друзей" in low or "список друзей" in low or "friends limit" in low or "limit" in low:
            return {
                "success": False,
                "code": "friends_limit_reached",
                "message": msg or "Достигнут ваш лимит друзей.",
                "remove_from_list": False,
                "status_code": status_code,
            }
        if "уже в друзьях" in low or "already friends" in low or "уже друзья" in low:
            return {
                "success": False,
                "code": "already_friends",
                "message": msg or "Игрок уже в вашем списке друзей.",
                "remove_from_list": True,
                "status_code": status_code,
            }
        if status_code == 404 or any(w in low for w in ("не найдена", "не найден", "отозвана", "не существует", "not found", "already processed")):
            return {
                "success": False,
                "code": "request_not_found",
                "message": msg or "Заявка уже обработана или отозвана игроком.",
                "remove_from_list": True,
                "status_code": status_code,
            }
        return {
            "success": False,
            "code": "bad_request",
            "message": msg or f"Запрос отклонён сервером игры (HTTP {status_code}).",
            "remove_from_list": False,
            "status_code": status_code,
        }

    async def _post_friendship_action(self, url: str) -> Dict[str, Any]:
        """Устойчивый POST для действий с друзьями: ретраи на 429/5xx, классификация 4xx без падения."""
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = await self.http.post(url)
                status_code = int(getattr(resp, "status_code", 200))
                try:
                    data = resp.json()
                except Exception:
                    data = None
                raw_text = str(getattr(resp, "text", "") or "")

                if status_code in (200, 201, 204):
                    if isinstance(data, dict) and data.get("success") is False:
                        classified = self.classify_friendship_error(status_code, raw_text, data)
                        classified["raw"] = data
                        return classified
                    if isinstance(data, dict):
                        return data
                    return {"success": True}

                if status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue

                classified = self.classify_friendship_error(status_code, raw_text, data)
                classified["raw"] = data or raw_text
                logger.warning("Friendship API %s -> HTTP %s (%s): %s", url, status_code, classified["code"], classified["message"])
                return classified
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
        logger.warning("Friendship API %s failed after retries: %s", url, last_exc)
        return {
            "success": False,
            "code": "temporary_error",
            "message": "Сервер игры временно недоступен. Повторите попытку позже.",
            "remove_from_list": False,
            "status_code": 503,
        }

    async def accept_friend(self, from_user_id: int) -> Dict[str, Any]:
        """Принятие заявки в друзья (POST /api/friendship/accept-request?fromUserId={from_user_id})."""
        return await self._post_friendship_action(f"/api/friendship/accept-request?fromUserId={from_user_id}")

    async def decline_friend(self, from_user_id: int) -> Dict[str, Any]:
        """Отклонение заявки в друзья (POST /api/friendship/decline-request?fromUserId={from_user_id})."""
        return await self._post_friendship_action(f"/api/friendship/decline-request?fromUserId={from_user_id}")

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
            res = None
            for attempt in range(3):
                try:
                    if page > 0 or attempt > 0:
                        await asyncio.sleep(0.25 if attempt == 0 else 1.0 * attempt)
                    res = await self.get_friend_profiles(page=page, page_size=page_size)
                    break
                except Exception as e:
                    if ("429" in str(e).lower() or "too many" in str(e).lower()) and attempt < 2:
                        continue
                    logger.warning(f"Ошибка пагинации профилей друзей на странице {page}: {e}")
                    res = None
                    break
            if res is None:
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
        return await self._post_friendship_action(f"/api/friendship/remove-friend?friendUserId={friend_user_id}")

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

    async def get_friend_top100(self) -> Dict[str, Any]:
        """Получение топ-100 игроков (GET /api/friend/top100)."""
        resp = await self.http.get("/api/friend/top100")
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

    async def perform_interaction(
        self,
        from_user_id: int,
        to_user_id: int,
        action_type: str,
    ) -> Dict[str, Any]:
        """
        Выполняет взаимодействие в камере друга (POST /api/interaction/perform).
        action_type: 'Fight' | 'Harknut' | 'TossDroj' | 'UpgradeBiceps'.
        """
        payload = {
            "fromUserId": int(from_user_id),
            "toUserId": int(to_user_id),
            "type": str(action_type),
        }
        resp = await self.http.post("/api/interaction/perform", json=payload)
        resp.raise_for_status()
        return resp.json()
