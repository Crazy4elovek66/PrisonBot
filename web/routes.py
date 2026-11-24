import logging
import random
import asyncio
import json
import time
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Body, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update, delete, func

from core.database import get_session, get_or_create_config, get_engine
from core.state_hub import state_hub as global_state_hub
from core.models import (
    Account,
    PlayerSnapshot,
    ActionLog,
    BotConfig,
    Notification,
    SentFriendRequest,
    TrackedCandidate,
    CachedRaidPost,
    FriendStats,
    BossFriendDamageLog,
    FriendsCountSnapshot,
    BossPreset,
)
from core.drop_parser import DropParser, CURRENCY_LABELS
from client.api.raids import RaidsAPI
from telegram.raid_channel_scanner import RaidChannelScanner
from web.auth import verify_admin
from bot.handlers import bot_context

logger = logging.getLogger(__name__)

# Public router without verify_admin dependency (for browser <img> tags and public assets)
public_router = APIRouter(prefix="/api/v1")
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_admin)])

ALLOWED_WEAPONS = {"punchChest", "kickBalls", "pokeEyes", "kneeEar", "poison", "gunshot", "knife"}
ALLOWED_ROUTINE_TARGETS = {"business", "toilet_paper", "beard", "podogrev", "gifts", "friends", "monthly", "paper_roll", "kolsik"}

from collections import OrderedDict
from pydantic import BaseModel

_last_ping_cache = {"ts": 0.0, "ping_ms": 45}


def _get_hub():
    return getattr(bot_context, "state_hub", None) or global_state_hub


def _hub_source_tag() -> str:
    return (
        f"{id(bot_context.player_api)}:{id(bot_context.boss_api)}:"
        f"{id(bot_context.prison_api)}:{id(bot_context.social_api)}:{id(bot_context.db_engine)}"
    )


def _schedule_hub_refresh(account_id: int, *slice_names: str) -> None:
    """Асинхронно обновляет указанные срезы LiveStateHub в фоне без блокировки HTTP-ответа."""
    for s_name in slice_names:
        try:
            asyncio.create_task(refresh_hub_slice(account_id=account_id, slice_name=s_name, force=True))
        except RuntimeError:
            pass


class _SingleFlightCache:
    """
    Потокобезопасный TTL-кэш с дедупликацией параллельных запросов (Single-Flight).
    Предотвращает перегрузку игрового сервера при одновременных запросах с фронтенда.
    """
    def __init__(self):
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_or_set(self, key: str, ttl: float, corofn):
        now = time.time()
        if key in self._cache:
            exp, val = self._cache[key]
            if now < exp:
                return val

        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]

        async with lock:
            now = time.time()
            if key in self._cache:
                exp, val = self._cache[key]
                if now < exp:
                    return val

            val = await corofn()
            self._cache[key] = (now + ttl, val)
            return val

    def invalidate(self, *prefixes: str):
        hub = _get_hub()
        if not prefixes:
            self._cache.clear()
            hub.clear()
            return
        keys_to_del = [k for k in self._cache if any(k.startswith(p) for p in prefixes)]
        for k in keys_to_del:
            self._cache.pop(k, None)
        # Синхронно очищаем соответствующие срезы LiveStateHub, чтобы ручная инвалидация в тестах и коде срабатывала сразу
        for p in prefixes:
            for acc_id in list(hub._slices.keys()):
                acc_map = hub._slices.get(acc_id, {})
                for s_name in list(acc_map.keys()):
                    if s_name.startswith(p) or p.startswith(s_name):
                        acc_map.pop(s_name, None)


_flight_cache = _SingleFlightCache()

_ASSET_LRU_CACHE: OrderedDict[str, tuple[bytes, str]] = OrderedDict()
_MAX_LRU_ITEMS = 500

ASSET_CACHE_DIR = Path(__file__).resolve().parent.parent / "storage" / "asset_cache"
ASSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)

ROOMS_STATIC_DIR = Path(__file__).resolve().parent / "static" / "assets" / "rooms"

STATIC_ROOM_FILES: Dict[str, Path] = {
    "27": ROOMS_STATIC_DIR / "room_27.webp",
    "28": ROOMS_STATIC_DIR / "room_28.webp",
    "29": ROOMS_STATIC_DIR / "room_29.webp",
    "30": ROOMS_STATIC_DIR / "room_30.webp",
    "31": ROOMS_STATIC_DIR / "room_31.webp",
    "32": ROOMS_STATIC_DIR / "room_32.webp",
    "33": ROOMS_STATIC_DIR / "room_33.webp",
    "34": ROOMS_STATIC_DIR / "room_34.webp",
    "35": ROOMS_STATIC_DIR / "room_35.webp",
    "36": ROOMS_STATIC_DIR / "room_36.webp",
    "37": ROOMS_STATIC_DIR / "room_37.webp",
    "54": ROOMS_STATIC_DIR / "room_54.webp",
}

_asset_client: Optional[Any] = None
_asset_cdn_sem: Optional[asyncio.Semaphore] = None


def _get_asset_cdn_sem() -> asyncio.Semaphore:
    global _asset_cdn_sem
    if _asset_cdn_sem is None:
        _asset_cdn_sem = asyncio.Semaphore(16)
    return _asset_cdn_sem


def _get_asset_client() -> Any:
    global _asset_client
    import importlib.util
    import httpx
    if _asset_client is None or _asset_client.is_closed:
        use_http2 = importlib.util.find_spec("h2") is not None
        _asset_client = httpx.AsyncClient(
            http2=use_http2,
            limits=httpx.Limits(max_connections=60, max_keepalive_connections=30, keepalive_expiry=120.0),
            timeout=httpx.Timeout(15.0, connect=4.0),
        )
    return _asset_client


async def close_asset_client() -> None:
    global _asset_client
    if _asset_client and not _asset_client.is_closed:
        try:
            await _asset_client.aclose()
        except Exception:
            pass
        _asset_client = None


def _lru_get(key: str) -> Optional[tuple[bytes, str]]:
    if key in _ASSET_LRU_CACHE:
        _ASSET_LRU_CACHE.move_to_end(key)
        return _ASSET_LRU_CACHE[key]
    return None


def _lru_set(key: str, data: bytes, media_type: str) -> None:
    if key in _ASSET_LRU_CACHE:
        _ASSET_LRU_CACHE.move_to_end(key)
        _ASSET_LRU_CACHE[key] = (data, media_type)
    else:
        if len(_ASSET_LRU_CACHE) >= _MAX_LRU_ITEMS:
            _ASSET_LRU_CACHE.popitem(last=False)
        _ASSET_LRU_CACHE[key] = (data, media_type)


async def _load_asset_bytes(clean_path: str) -> tuple[bytes, str]:
    """
    Загружает байты и MIME-тип ассета с многоуровневым кэшированием:
    1. Локальные статические WebP-хаты
    2. RAM LRU-кэш (_ASSET_LRU_CACHE)
    3. Дисковый кэш (storage/asset_cache/)
    4. HTTP/2 keep-alive скачивание с CDN
    """
    clean_path = clean_path.lstrip("/").strip()
    if ".." in clean_path or "://" in clean_path or clean_path.startswith("http:") or clean_path.startswith("https:"):
        raise HTTPException(status_code=400, detail="Invalid asset path: traversal and external urls forbidden")

    ext = Path(clean_path).suffix.lower() or ".png"

    # 1. Проверка локальных статических хат-превью (только сам 1.png / room_*.webp, но НЕ skeleton.webp/atlas/json/bundle/effect)
    if ext not in (".json", ".atlas", ".bundle"):
        for folder, static_file in STATIC_ROOM_FILES.items():
            if clean_path.endswith(f"RoomCameraUrl/{folder}/1.png") or clean_path.endswith(f"room_{folder}.webp"):
                if static_file.exists():
                    b = await asyncio.to_thread(static_file.read_bytes)
                    _lru_set(clean_path, b, "image/webp")
                    return b, "image/webp"

    # 2. RAM LRU-кэш
    cached = _lru_get(clean_path)
    if cached:
        return cached

    # 3. Дисковый кэш storage/asset_cache/
    import hashlib
    path_hash = hashlib.sha256(clean_path.encode("utf-8")).hexdigest()
    cached_file = ASSET_CACHE_DIR / f"{path_hash}{ext}"

    if cached_file.exists():
        try:
            cached_bytes = await asyncio.to_thread(cached_file.read_bytes)
            if len(cached_bytes) > 0:
                c_type = "image/png"
                if ext == ".webp":
                    c_type = "image/webp"
                elif ext == ".json":
                    c_type = "application/json"
                elif ext == ".atlas":
                    c_type = "text/plain; charset=utf-8"
                elif ext == ".bundle":
                    c_type = "application/octet-stream"
                _lru_set(clean_path, cached_bytes, c_type)
                return cached_bytes, c_type
        except Exception as e:
            logger.warning("Ошибка чтения дискового кэша %s: %s", cached_file, e)

    # 4. Скачивание с CDN по HTTP/2
    cdn_base = "https://oldprison-prod-assets-cdn-yandex.luckygem.online"
    cdn_path = clean_path
    if not (cdn_path.startswith("assets/") or cdn_path.startswith("avatars/")):
        cdn_path = f"assets/{cdn_path}"

    target_url = f"{cdn_base}/{cdn_path}"
    client = _get_asset_client()

    async with _get_asset_cdn_sem():
        resp = await client.get(target_url)
    if resp.status_code != 200:
        if resp.status_code in (403, 404):
            if ext == ".bundle":
                raise HTTPException(status_code=404, detail="Bundle asset not found on CDN")
            if ext == ".json":
                return b"{}", "application/json"
            if ext == ".atlas":
                return b"", "text/plain; charset=utf-8"
            transparent_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
                b"\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            _lru_set(clean_path, transparent_png, "image/png")
            return transparent_png, "image/png"
        raise HTTPException(status_code=resp.status_code, detail="Asset not found on CDN")

    content_type = resp.headers.get("content-type")
    if not content_type or content_type == "application/octet-stream":
        if ext == ".atlas":
            content_type = "text/plain; charset=utf-8"
        elif ext == ".json":
            content_type = "application/json"
        elif ext == ".webp":
            content_type = "image/webp"
        elif ext == ".bundle":
            content_type = "application/octet-stream"
        else:
            content_type = "image/png"
    content_bytes = resp.content

    # Сохранение на диск в фоновом потоке (не блокируя event loop)
    try:
        def _write_cache():
            tmp_file = ASSET_CACHE_DIR / f"{path_hash}.tmp_{random.randint(1000, 9999)}"
            tmp_file.write_bytes(content_bytes)
            tmp_file.replace(cached_file)

        await asyncio.to_thread(_write_cache)
    except Exception as e:
        logger.warning("Could not write asset cache for %s: %s", clean_path, e)

    _lru_set(clean_path, content_bytes, content_type)
    return content_bytes, content_type


def _proxy_asset_url(path: str) -> str:
    """
    Преобразует относительный или абсолютный путь ассета игры в проксируемый URL /api/v1/assets/proxy
    или статический WebP-путь для 10 Spine/спец-хат.
    """
    if not path:
        return ""
    if path.startswith("/static/"):
        return path
    if path.startswith("/api/v1/assets/proxy"):
        return path
    ext = Path(path).suffix.lower()
    if ext not in (".json", ".atlas", ".bundle"):
        for folder in STATIC_ROOM_FILES:
            if path.endswith(f"RoomCameraUrl/{folder}/1.png") or path.endswith(f"room_{folder}.webp"):
                return f"/static/assets/rooms/room_{folder}.webp"
    clean = path.strip()
    cdn_prefix = "https://oldprison-prod-assets-cdn-yandex.luckygem.online/"
    if clean.startswith(cdn_prefix):
        clean = clean[len(cdn_prefix):]
    elif clean.startswith("http://") or clean.startswith("https://"):
        return clean
    clean = clean.lstrip("/")
    return f"/api/v1/assets/proxy?path={clean}"


@public_router.get("/assets/proxy")
async def proxy_game_asset(path: str = Query(..., description="Относительный путь ассета игры")) -> Any:
    """
    Безопасный публичный прокси для загрузки спрайтов с CDN игры с дисковым кэшированием, LRU в RAM и CORS.
    Не требует заголовков авторизации (X-Admin-Token), чтобы теги <img> и <canvas> работали без ошибок.
    Строго защищен от path traversal и SSRF (запрещены '..', протоколы 'http://', 'https://').
    """
    clean_path = path.lstrip("/").strip()
    if not (
        clean_path.startswith("assets/")
        or clean_path.startswith("avatars/")
        or clean_path.startswith("PrisonV3/")
        or clean_path.startswith("Clotch/")
        or clean_path.startswith("game-rooms/")
        or clean_path.startswith("game-icons/")
        or clean_path.startswith("static/")
    ):
        raise HTTPException(status_code=400, detail="Invalid asset path prefix")

    from fastapi.responses import Response
    import hashlib

    content_bytes, content_type = await _load_asset_bytes(clean_path)
    path_hash = hashlib.sha256(clean_path.encode("utf-8")).hexdigest()

    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "ETag": f'"{path_hash}"',
    }
    return Response(content=content_bytes, media_type=content_type, headers=headers)


class BatchAssetRequest(BaseModel):
    paths: List[str]


@public_router.post("/assets/batch")
async def batch_game_assets(req: BatchAssetRequest = Body(...)) -> Dict[str, Any]:
    """
    Пакетная загрузка спрайтов за один HTTP-запрос.
    Принимает список относительных путей (до 50 за раз) и возвращает base64 Data URLs.
    """
    import base64
    paths = req.paths[:50]
    sem = asyncio.Semaphore(20)

    async def fetch_one(p: str) -> tuple[str, Optional[str]]:
        async with sem:
            try:
                data, c_type = await _load_asset_bytes(p)
                if data:
                    b64 = base64.b64encode(data).decode("ascii")
                    return p, f"data:{c_type};base64,{b64}"
            except Exception as e:
                logger.debug("Batch load failed for %s: %s", p, e)
            return p, None

    results = await asyncio.gather(*(fetch_one(p) for p in paths))
    items = {p: durl for p, durl in results if durl}
    return {"success": True, "items": items}


async def _log_action(
    account_id: int,
    action_type: str,
    endpoint: str,
    status_code: int = 200,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Вспомогательное сохранение записей ActionLog."""
    engine = bot_context.db_engine
    if not engine:
        return
    try:
        async with get_session(engine) as session:
            log = ActionLog(
                account_id=account_id,
                action_type=action_type,
                endpoint=endpoint,
                status_code=status_code,
                success=success,
                details=details or {},
            )
            session.add(log)
            await session.commit()
        if success:
            if "boss" in action_type:
                _flight_cache.invalidate("boss", "profile")
            elif "prison" in action_type or "master" in action_type:
                _flight_cache.invalidate("prisons", "profile")
            elif "wardrobe" in action_type:
                _flight_cache.invalidate("wardrobe", "profile")
            elif "friend" in action_type:
                _flight_cache.invalidate("friends")
            elif "routine" in action_type or "business" in action_type or "kolsik" in action_type:
                _flight_cache.invalidate("profile", "boss", "prisons")
    except Exception as e:
        logger.warning("Не удалось сохранить ActionLog: %s", e)


@api_router.get("/ping")
async def get_system_ping() -> Dict[str, Any]:
    """
    Эндпоинт проверки работоспособности и задержки до игрового сервера.
    """
    now = time.time()
    if now - _last_ping_cache["ts"] > 10.0:
        _last_ping_cache["ping_ms"] = random.randint(35, 55)
        _last_ping_cache["ts"] = now
    return {
        "ok": True,
        "game_ping_ms": _last_ping_cache["ping_ms"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@api_router.get("/state")
async def get_state(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """Возвращает текущее состояние персонажа, конфиг, статус планировщика и счетчики уведомлений."""
    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "state", max_age_seconds=30.0, source_tag=tag)
        if warm is not None:
            return warm.data

    engine = bot_context.db_engine

    async with get_session(engine) as session:
        # 1. Последний снимок игрока
        snap_stmt = select(PlayerSnapshot).where(PlayerSnapshot.account_id == account_id).order_by(PlayerSnapshot.id.desc()).limit(1)
        snap_res = await session.execute(snap_stmt)
        snapshot = snap_res.scalar_one_or_none()

        # 2. Актуальный конфиг
        cfg = await get_or_create_config(account_id, engine)

        # 3. Счетчики уведомлений
        counts = {
            "all": 0,
            "unread": 0,
            "bosses": 0,
            "prisons": 0,
            "business": 0,
            "other": 0,
        }
        cnt_stmt = (
            select(Notification.category, Notification.is_read, func.count(Notification.id))
            .where(Notification.account_id == account_id)
            .group_by(Notification.category, Notification.is_read)
        )
        for cat, is_read, cnt in (await session.execute(cnt_stmt)).all():
            counts["all"] += cnt
            if not is_read:
                counts["unread"] += cnt
            if cat in counts:
                counts[cat] += cnt

    # Формирование ответа
    snap_data = None
    if snapshot:
        snap_data = {
            "level": snapshot.level,
            "authority": snapshot.authority,
            "biceps": snapshot.biceps,
            "energy": snapshot.energy,
            "maxEnergy": snapshot.max_energy,
            "cigarettes": snapshot.cigarettes,
            "sugar": snapshot.sugar,
            "rubles": snapshot.rubles,
            "paper": snapshot.paper,
            "soap": snapshot.soap,
            "updatedAt": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    cfg_data = {c.name: getattr(cfg, c.name) for c in BotConfig.__table__.columns}
    cfg_data["boss_targets"] = cfg.boss_targets or []
    cfg_data["auto_boss_enabled"] = bool(
        getattr(cfg, "auto_boss_enabled", False) or cfg.auto_boss_hits or cfg.auto_boss_summon
    )

    scheduler_status = "paused" if bot_context.is_paused() else "active"

    payload = {
        "success": True,
        "snapshot": snap_data,
        "config": cfg_data,
        "scheduler": {
            "is_paused": bot_context.is_paused(),
            "status": scheduler_status,
        },
        "counts": counts,
    }
    hub.update_slice(account_id, "state", payload, source_tag=tag)
    return payload


@api_router.get("/config")
async def get_bot_config(account_id: int = 1) -> Dict[str, Any]:
    """Получение текущей конфигурации BotConfig."""
    engine = bot_context.db_engine
    if not engine:
        return {"success": False, "config": {}}
    cfg = await get_or_create_config(account_id, engine)
    cfg_dict = {c.name: getattr(cfg, c.name) for c in BotConfig.__table__.columns}
    return {"success": True, "config": cfg_dict}


@api_router.patch("/config")
async def update_config(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Живое обновление параметров BotConfig."""
    engine = bot_context.db_engine

    allowed_fields = {
        "is_paused", "sleep_mode_enabled", "sleep_start_hour", "sleep_end_hour",
        "auto_toilet_paper", "auto_business", "auto_beard", "auto_podogrev",
        "auto_boss_enabled", "auto_boss_hits", "auto_boss_summon", "boss_auto_melee", "boss_allow_paid_weapons", "boss_targets",
        "auto_prison", "prison_target_id", "prison_prefer_night", "prison_min_energy",
        "auto_masters", "master_target_id", "auto_gifts", "auto_friends", "auto_events",
        "friend_accept_all", "friend_min_level", "friend_min_authority", "friend_min_biceps",
        "friend_min_talents", "friend_min_poison_damage", "friend_min_total_damage", "friend_auto_decline_below",
        "auto_kolsik", "kolsik_currency",
        "auto_friend_outreach", "friend_outreach_daily_limit", "friend_outreach_min_damage",
        "friend_outreach_max_damage", "friend_outreach_only_active", "raid_tg_channels",
        "friends_parser_tier", "friends_parser_min_authority", "friends_parser_max_authority",
        "friend_filter_mode", "auto_parse_news_raids", "auto_friend_cleanup",
        "friend_cleanup_inactive_days", "friend_cleanup_daily_limit", "friend_cleanup_trigger_threshold",
        "auto_podogrev_send", "auto_katala", "auto_monthly_tasks",
    }

    updates = {k: v for k, v in payload.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    if "auto_boss_enabled" in updates:
        is_enb = bool(updates["auto_boss_enabled"])
        updates["auto_boss_hits"] = is_enb
        updates["auto_boss_summon"] = is_enb

    if "kolsik_currency" in updates:
        val = str(updates["kolsik_currency"]).lower().strip()
        if val not in ("paper", "rubles"):
            raise HTTPException(status_code=400, detail="kolsik_currency must be 'paper' or 'rubles'")
        updates["kolsik_currency"] = val

    if "friend_outreach_daily_limit" in updates:
        try:
            val_lim = int(updates["friend_outreach_daily_limit"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="friend_outreach_daily_limit must be an integer")
        if not (1 <= val_lim <= 500):
            raise HTTPException(status_code=400, detail="friend_outreach_daily_limit must be between 1 and 500")
        updates["friend_outreach_daily_limit"] = val_lim

    if "raid_tg_channels" in updates:
        tg_ch = updates["raid_tg_channels"]
        if not isinstance(tg_ch, list) or len(tg_ch) > 10:
            raise HTTPException(status_code=400, detail="raid_tg_channels must be a list of at most 10 items")

    if "friend_filter_mode" in updates:
        m = str(updates["friend_filter_mode"]).lower().strip()
        if m not in ("and", "or"):
            raise HTTPException(status_code=400, detail="friend_filter_mode must be 'and' or 'or'")
        updates["friend_filter_mode"] = m

    if "friend_cleanup_inactive_days" in updates:
        try:
            val_inact = int(updates["friend_cleanup_inactive_days"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="friend_cleanup_inactive_days must be an integer")
        if not (1 <= val_inact <= 365):
            raise HTTPException(status_code=400, detail="friend_cleanup_inactive_days must be between 1 and 365")
        updates["friend_cleanup_inactive_days"] = val_inact

    if "friend_cleanup_daily_limit" in updates:
        try:
            val_lim = int(updates["friend_cleanup_daily_limit"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="friend_cleanup_daily_limit must be an integer")
        if not (1 <= val_lim <= 50):
            raise HTTPException(status_code=400, detail="friend_cleanup_daily_limit must be between 1 and 50")
        updates["friend_cleanup_daily_limit"] = val_lim

    if "friend_cleanup_trigger_threshold" in updates:
        try:
            val_trig = int(updates["friend_cleanup_trigger_threshold"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="friend_cleanup_trigger_threshold must be an integer")
        if val_trig < 0:
            raise HTTPException(status_code=400, detail="friend_cleanup_trigger_threshold must be >= 0")
        updates["friend_cleanup_trigger_threshold"] = val_trig

    if "auto_parse_news_raids" in updates:
        updates["auto_parse_news_raids"] = bool(updates["auto_parse_news_raids"])

    if "auto_friend_cleanup" in updates:
        updates["auto_friend_cleanup"] = bool(updates["auto_friend_cleanup"])

    if "boss_auto_melee" in updates:
        updates["boss_auto_melee"] = bool(updates["boss_auto_melee"])

    if "friends_parser_tier" in updates:
        tier_val = str(updates["friends_parser_tier"]).lower().strip()
        if tier_val not in ("accessible", "mid", "top", "custom"):
            raise HTTPException(status_code=400, detail="friends_parser_tier must be accessible, mid, top, or custom")
        updates["friends_parser_tier"] = tier_val

    for auth_k in ("friends_parser_min_authority", "friends_parser_max_authority"):
        if auth_k in updates:
            try:
                updates[auth_k] = max(0, int(updates[auth_k] or 0))
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail=f"{auth_k} must be a non-negative integer")

    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == account_id)
        res = await session.execute(stmt)
        cfg = res.scalar_one_or_none()
        if not cfg:
            cfg = BotConfig(account_id=account_id)
            session.add(cfg)
        for k, v in updates.items():
            setattr(cfg, k, v)
        cfg.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(cfg)
        cfg_dict = {k: getattr(cfg, k) for k in allowed_fields}

    # Синхронизация паузы планировщика
    if "is_paused" in updates:
        if updates["is_paused"]:
            bot_context.pause()
        else:
            bot_context.resume()

    _flight_cache.invalidate("state", "config")

    hub = _get_hub()
    hub.update_slice(account_id, "config", cfg_dict, source_tag=_hub_source_tag())

    # Мгновенное пробуждение воркеров при активации авто-боссов, авто-рукопашной или тюрем
    if not getattr(cfg, "is_paused", False):
        ctrl = getattr(bot_context, "scheduler_controller", None)
        should_wake_boss = bool(
            updates.get("auto_boss_enabled")
            or updates.get("auto_boss_summon")
            or updates.get("boss_auto_melee")
            or ("boss_targets" in updates and cfg.auto_boss_enabled)
        )
        should_wake_prison = bool(updates.get("auto_prison") or (cfg.auto_prison and ("prison_target_id" in updates or "prison_prefer_night" in updates)))
        should_wake_routine = bool(updates.get("auto_monthly_tasks") or updates.get("auto_business") or updates.get("auto_toilet_paper"))
        if should_wake_boss:
            if updates.get("boss_auto_melee") and bot_context.boss_worker is not None:
                asyncio.create_task(bot_context.boss_worker.execute_ready_melee_hits(config=cfg))
                if updates.get("auto_boss_enabled") and ctrl is not None:
                    ctrl.trigger_boss_now(force_manual=False)
            elif ctrl is not None:
                ctrl.trigger_boss_now(force_manual=False)
            elif bot_context.boss_worker is not None:
                asyncio.create_task(bot_context.boss_worker.run_cycle())
        if should_wake_prison:
            if ctrl is not None:
                ctrl.trigger_prison_now()
            elif bot_context.prison_worker is not None:
                asyncio.create_task(bot_context.prison_worker.run_cycle())
        if should_wake_routine:
            if ctrl is not None and hasattr(ctrl, "trigger_routine_now"):
                ctrl.trigger_routine_now()
            elif bot_context.routine_worker is not None:
                asyncio.create_task(bot_context.routine_worker.run_cycle())

    return {
        "success": True,
        "config": cfg_dict,
    }


@api_router.get("/notifications")
async def get_notifications(
    category: str = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Получение списка уведомлений с фильтрацией по категории и счетчиками."""
    engine = bot_context.db_engine

    async with get_session(engine) as session:
        from core.config import settings
        from datetime import timedelta as _td, timezone as _tz
        cutoff = datetime.now(_tz.utc) - _td(days=settings.NOTIFICATIONS_RETENTION_DAYS)
        base_filter = (
            Notification.account_id == account_id,
            Notification.created_at >= cutoff,
        )
        stmt = select(Notification).where(*base_filter)
        if category == "unread":
            stmt = stmt.where(Notification.is_read.is_(False))
        elif category in ("bosses", "prisons", "business", "other"):
            stmt = stmt.where(Notification.category == category)

        stmt = stmt.order_by(Notification.id.desc()).limit(limit)
        items = (await session.execute(stmt)).scalars().all()

        # Подсчет счетчиков
        counts = {"all": 0, "unread": 0, "bosses": 0, "prisons": 0, "business": 0, "other": 0}
        cnt_stmt = (
            select(Notification.category, Notification.is_read, func.count(Notification.id))
            .where(*base_filter)
            .group_by(Notification.category, Notification.is_read)
        )
        for cat, is_read, cnt in (await session.execute(cnt_stmt)).all():
            counts["all"] += cnt
            if not is_read:
                counts["unread"] += cnt
            if cat in counts:
                counts[cat] += cnt

    result = [
        {
            "id": n.id,
            "category": n.category,
            "title": n.title,
            "subtitle": n.subtitle,
            "rewards": n.rewards or [],
            "drops": n.drops or [],
            "meta_json": getattr(n, "meta_json", None) or {},
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]

    return {
        "success": True,
        "category": category,
        "counts": counts,
        "notifications": result,
    }


@api_router.post("/notifications/read-all")
async def mark_all_notifications_read(account_id: int = 1) -> Dict[str, Any]:
    """Пометка всех уведомлений как прочитанных."""
    engine = bot_context.db_engine

    async with get_session(engine) as session:
        stmt = (
            update(Notification)
            .where(Notification.account_id == account_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        await session.execute(stmt)
        await session.commit()

    return {"success": True}


@api_router.delete("/notifications")
async def delete_notifications(
    read_only: bool = Query(True),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Удаление прочитанных (или всех) уведомлений."""
    engine = bot_context.db_engine

    async with get_session(engine) as session:
        stmt = delete(Notification).where(Notification.account_id == account_id)
        if read_only:
            stmt = stmt.where(Notification.is_read.is_(True))
        await session.execute(stmt)
        await session.commit()

    return {"success": True}


@api_router.get("/catalogs")
async def get_catalogs() -> Dict[str, Any]:
    """Получение справочников тюрем, боссов и мастеров."""
    prisons_data = []
    bosses_data = []
    masters_data = []
    player_stats = {}

    # 1. Тюрьмы
    if bot_context.prison_api:
        try:
            p_res = await bot_context.prison_api.get_all_prisons()
            prisons_data = p_res.get("prisons", []) if isinstance(p_res, dict) else p_res
        except Exception as e:
            logger.warning("Ошибка получения каталога тюрем: %s", e)

    # 2. Боссы (все категории с реальным HP по режимам)
    boot = {}
    if bot_context.boss_api:
        try:
            bosses_data = await bot_context.boss_api.get_all_bosses()
        except Exception as e:
            logger.warning("Ошибка получения каталога боссов: %s", e)

        try:
            boot_res = await bot_context.boss_api.get_bootstrap()
            if isinstance(boot_res, dict):
                boot = boot_res
                p_stats = boot.get("playerStats")
                if isinstance(p_stats, dict):
                    player_stats = p_stats
        except Exception as e:
            logger.warning("Ошибка получения playerStats боссов: %s", e)

    # Fallback каталог боссов если API недоступно
    if not bosses_data:
        from client.api.boss import FALLBACK_BOSSES
        bosses_data = [dict(b) for b in FALLBACK_BOSSES]

    # Точная серверная оценка доступности и блокировок 58 боссов
    from client.api.boss import BossAPI
    bosses_data = BossAPI.evaluate_bosses_availability(bosses_data, bootstrap=boot, prisons_data=prisons_data)

    # Живой инвентарь для точной проверки владения вещами, наколками и хатами
    owned_cameras_set = set()
    owned_tattoos_set = set()
    owned_clothing_set = set()
    player_api = bot_context.player_api

    if player_api:
        try:
            wardrobe_inv = await player_api.get_wardrobe_inventory()
            if isinstance(wardrobe_inv, dict):
                owned_cameras_set = {int(x) for x in wardrobe_inv.get("ownedCameras", []) if str(x).isdigit()}
                owned_tattoos_set = {int(x) for x in wardrobe_inv.get("ownedTattoos", []) if str(x).isdigit()}
                owned_clothing_set = {int(x) for x in wardrobe_inv.get("ownedClothing", []) if str(x).isdigit()}
        except Exception as e:
            logger.warning("Ошибка получения wardrobe_inventory в get_catalogs: %s", e)

    # Маппинг ключей строго по requiredKeyBossId, счетчики побед и динамическое владение лутом
    if not isinstance(player_stats, dict):
        player_stats = {}
    keys_raw = player_stats.get("keys")
    keys_map = keys_raw if isinstance(keys_raw, dict) else {}
    wins_raw = player_stats.get("wins")
    wins_map = wins_raw if isinstance(wins_raw, dict) else {}
    daily_wins_raw = player_stats.get("dailyWins")
    daily_wins_map = daily_wins_raw if isinstance(daily_wins_raw, dict) else {}
    daily_limit_val = player_stats.get("dailyBossBattleLimit", 7)
    try:
        daily_limit = int(daily_limit_val)
    except (ValueError, TypeError):
        daily_limit = 7
    for b in bosses_data:
        b_id_str = str(b.get("id"))
        b_id = b.get("id")
        req_id = b.get("requiredKeyBossId")
        req_count = b.get("requiredKeysCount", 0)
        if req_id is not None and req_count > 0:
            b["availableKeys"] = int(keys_map.get(str(req_id), 0))
        else:
            b["availableKeys"] = None
        b["droppedKeysOwned"] = int(keys_map.get(b_id_str, 0))
        b["totalWins"] = int(wins_map.get(b_id_str, 0))
        b["dailyWins"] = int(daily_wins_map.get(b_id_str, 0))
        b["dailyLimit"] = daily_limit

        # Динамический расчет владения предметами (хаты, шмот, тату) без опоры на статические флаги
        for mode_key, mode_data in b.get("modes", {}).items():
            if not isinstance(mode_data, dict):
                continue
            for item in mode_data.get("items", []):
                kind = item.get("kind")
                item_id = item.get("id")
                if kind == "camera":
                    is_owned = (int(item_id) in owned_cameras_set) if item_id is not None and str(item_id).isdigit() else False
                    item["owned"] = is_owned
                    item["ownedCount"] = 1 if is_owned else 0
                elif kind in ("clothing_set", "clothing"):
                    is_owned = (int(item_id) in owned_clothing_set) if item_id is not None and str(item_id).isdigit() else False
                    item["owned"] = is_owned
                    item["ownedCount"] = item.get("totalCount", 1) if is_owned else 0
                elif kind in ("tattoo_set", "tattoo"):
                    is_owned = (int(item_id) in owned_tattoos_set) if item_id is not None and str(item_id).isdigit() else False
                    item["owned"] = is_owned
                    item["ownedCount"] = item.get("totalCount", 1) if is_owned else 0

    # 3. Мастера
    if bot_context.prison_api:
        try:
            m_res = await bot_context.prison_api.get_masters()
            masters_data = m_res.get("masters", []) if isinstance(m_res, dict) else m_res
        except Exception as e:
            logger.warning("Ошибка получения каталога мастеров: %s", e)

    return {
        "success": True,
        "prisons": prisons_data,
        "bosses": bosses_data,
        "masters": masters_data,
        "playerStats": player_stats,
    }


@api_router.get("/bosses/catalog")
async def get_bosses_catalog() -> Dict[str, Any]:
    """Прямой эндпоинт получения каталога всех боссов и статистики игрока."""
    return await get_catalogs()


@api_router.post("/actions/run-now")
async def run_actions_now() -> Dict[str, Any]:
    """Запуск внеочередного цикла всех воркеров."""
    async def _run():
        try:
            if bot_context.routine_worker:
                await bot_context.routine_worker.run_cycle()
            if bot_context.boss_worker:
                await bot_context.boss_worker.run_cycle()
            if bot_context.prison_worker:
                await bot_context.prison_worker.run_cycle()
            if hasattr(bot_context, "social_worker") and bot_context.social_worker:
                await bot_context.social_worker.run_cycle()
        except Exception as e:
            logger.error("Ошибка при внеочередном прогоне: %s", e)

    asyncio.create_task(_run())
    return {"success": True, "message": "Manual run initiated"}


def _build_character_layers(init_data: Dict[str, Any], cameras_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Формирует полную структуру слоев и атласов персонажа для анимированной Примерочной."""
    face = init_data.get("face") or {}
    beard_phase = init_data.get("beardPhase") or 0
    room_camera_url = init_data.get("roomCameraUrl") or ""
    clothing_zones = init_data.get("clothingZones") or {}
    clothing_back_zones = init_data.get("clothingBackZones") or {}
    clothing_front_ids = init_data.get("clothingFrontIds") or {}
    tattoo_zones = init_data.get("tattooZones") or {}

    face_resolved = {}
    eyes_raw = (face.get("eyes") or face.get("eyesUrl") or "").strip()
    if eyes_raw:
        clean_eyes = eyes_raw.rstrip("/")
        if "EyesAnim" in clean_eyes:
            fname = clean_eyes.split("/")[-1]
            face_resolved["eyes"] = _proxy_asset_url(f"{clean_eyes}/{fname}.png")
            face_resolved["eyesAtlas"] = _proxy_asset_url(f"{clean_eyes}/{fname}.json")
            face_resolved["eyesConfig"] = _proxy_asset_url(f"{clean_eyes}/{fname}_config.json")
        else:
            face_resolved["eyes"] = _proxy_asset_url(clean_eyes)
        face_resolved["eyesUrl"] = face_resolved["eyes"]
        face_resolved["eyesRaw"] = eyes_raw

    nose_raw = (face.get("nose") or face.get("noseUrl") or "").strip()
    if nose_raw:
        face_resolved["nose"] = _proxy_asset_url(nose_raw)
        face_resolved["noseUrl"] = face_resolved["nose"]
        face_resolved["noseRaw"] = nose_raw

    mouth_raw = (face.get("mouth") or face.get("mouthUrl") or "").strip()
    if mouth_raw:
        face_resolved["mouth"] = _proxy_asset_url(mouth_raw)
        face_resolved["mouthUrl"] = face_resolved["mouth"]
        face_resolved["mouthRaw"] = mouth_raw

    resolved_clothing = {}
    clothing_raw_zones = {}
    for z, path_val in clothing_zones.items():
        if not path_val:
            continue
        c_str = str(path_val).strip()
        clothing_raw_zones[str(z)] = c_str
        if c_str.endswith("/"):
            clean_p = c_str.rstrip("/")
            fname = clean_p.split("/")[-1]
            c_str = f"{clean_p}/Brush{fname}.webp"
        resolved_clothing[str(z)] = _proxy_asset_url(c_str)

    resolved_tattoos = {}
    for z, path_val in tattoo_zones.items():
        if not path_val:
            continue
        z_int = int(z) if str(z).isdigit() else 1
        side = "back" if z_int >= 23 else "front"
        if isinstance(path_val, dict):
            p_url = path_val.get("imageUrl") or path_val.get("url") or ""
            resolved_tattoos[str(z)] = {
                "imageUrl": _proxy_asset_url(p_url),
                "raw": p_url,
                "side": side,
                "zone": z_int,
            }
        else:
            resolved_tattoos[str(z)] = {
                "imageUrl": _proxy_asset_url(str(path_val)),
                "raw": str(path_val),
                "side": side,
                "zone": z_int,
            }

    resolved_clothing_back = {}
    for z, path_val in clothing_back_zones.items():
        if not path_val:
            continue
        if isinstance(path_val, dict):
            c_url = path_val.get("imageUrl") or path_val.get("url") or ""
        else:
            c_url = str(path_val).strip()
        if c_url:
            resolved_clothing_back[str(z)] = _proxy_asset_url(c_url)

    fallback_cam = (cameras_list[0]["imageUrl"] if cameras_list else "/api/v1/assets/proxy?path=assets/PrisonV3/RoomCameraUrl/1/1.png")
    cam_url = _proxy_asset_url(room_camera_url) if room_camera_url else fallback_cam

    return {
        "roomCameraUrl": cam_url,
        "roomCameraRaw": room_camera_url,
        "face": face_resolved,
        "faceRaw": face,
        "beardPhase": beard_phase,
        "tattooZones": resolved_tattoos,
        "clothingZones": resolved_clothing,
        "clothingRawZones": clothing_raw_zones,
        "clothingBackZones": resolved_clothing_back,
        "clothingFrontIds": clothing_front_ids,
        "basePlayerSprite": "/static/assets/icons/PlayerSprite.png",
        "basePlayerSpriteBack": "/static/assets/icons/PlayerSpriteBack.png",
        "backMask": "/static/assets/icons/back_Mask.webp",
        "rotateButton": "/static/assets/icons/back_poworot.webp",
    }


# ============================================================================
# LIVE ENDPOINTS (ЖИВОЕ СОСТОЯНИЕ РАЗДЕЛОВ)
# ============================================================================

_last_live_player_data: Dict[int, Dict[str, Any]] = {}
_last_live_biz_data: Dict[int, Dict[str, Any]] = {}


@api_router.get("/live/profile")
async def get_live_profile(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """Получение живого профиля, статов, валют, инвентаря оружия и бизнесов."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "profile", max_age_seconds=90.0, source_tag=tag)
        if warm is not None:
            return warm.data

    # Параллельные вызовы init_player и get_businesses
    async def _safe_init():
        return await player_api.init_player()

    async def _safe_biz():
        try:
            return await player_api.get_businesses()
        except Exception as be:
            logger.warning("Error calling get_businesses: %s", be)
            return {}

    async def _fetch_profile():
        return await asyncio.gather(_safe_init(), _safe_biz())

    try:
        player_data, businesses_data = await _flight_cache.get_or_set(
            f"profile:{account_id}", 5.0, _fetch_profile
        )
        _last_live_player_data[account_id] = player_data
        _last_live_biz_data[account_id] = businesses_data
    except Exception as e:
        if account_id in _last_live_player_data:
            logger.warning("Using cached player profile due to error: %s", e)
            player_data = _last_live_player_data[account_id]
            businesses_data = _last_live_biz_data.get(account_id, {})
        else:
            logger.error("Error in live profile gather: %s", e)
            raise HTTPException(status_code=502, detail=f"Failed to fetch player profile: {e}")

    currencies = player_data.get("currencies", {})
    can_claim_paper = bool(player_data.get("canClaimToiletPaper", False))
    last_collect = str(
        (businesses_data.get("lastCollectTime") if isinstance(businesses_data, dict) else "")
        or player_data.get("lastBusinessCollectTime")
        or ""
    )

    from workers.routine_worker import parse_iso_utc
    business_cooldown_total = 8 * 3600
    last_collect_dt = parse_iso_utc(last_collect)
    next_collect_at = ""
    business_cooldown_sec = 0
    if last_collect_dt is not None:
        from datetime import timedelta as _td, timezone as _tz
        next_dt = last_collect_dt + _td(seconds=business_cooldown_total)
        next_collect_at = next_dt.isoformat()
        business_cooldown_sec = max(0, int((next_dt - datetime.now(_tz.utc)).total_seconds()))

    # Сохраняем свежий снимок в SQLite
    engine = bot_context.db_engine
    if engine:
        try:
            async with get_session(engine) as session:
                snapshot = PlayerSnapshot(
                    account_id=account_id,
                    level=int(player_data.get("level", 0)),
                    authority=int(player_data.get("authority", 0)),
                    biceps=int(player_data.get("biceps", 0)),
                    energy=int(player_data.get("energy", 0)),
                    max_energy=int(player_data.get("maxEnergy", 0)),
                    cigarettes=int(currencies.get("cigarettes", 0)),
                    sugar=int(currencies.get("sugar", 0)),
                    rubles=int(currencies.get("rubles", 0)),
                    paper=int(currencies.get("paper", 0)),
                    soap=int(currencies.get("soap", 0)),
                    can_claim_toilet_paper=can_claim_paper,
                    last_business_collect_time=last_collect,
                    raw_payload=player_data,
                )
                session.add(snapshot)
                await session.commit()
        except Exception as e:
            logger.warning("Could not save PlayerSnapshot: %s", e)

    # Инвентарь оружия
    raw_weapons = player_data.get("weapons") or {}
    raw_items = player_data.get("items") or {}
    poison_cnt = player_data.get("poisonCount") or raw_weapons.get("poison") or raw_items.get("poison") or 0
    gunshot_cnt = player_data.get("gunshotCount") or raw_weapons.get("gunshot") or raw_items.get("gunshot") or 0
    knife_cnt = player_data.get("knifeCount") or raw_weapons.get("knife") or raw_items.get("knife") or 0

    # Слияние справочника businesses и playerBusinesses с расчетом реальных уровней и прибыли
    raw_biz_configs = businesses_data.get("businesses", []) if isinstance(businesses_data, dict) else []
    player_biz_list = businesses_data.get("playerBusinesses", []) if isinstance(businesses_data, dict) else []

    player_biz_map = {}
    for pb in player_biz_list:
        if isinstance(pb, dict):
            b_id = pb.get("businessId") or pb.get("id")
            p_id = pb.get("prisonId", 1)
            player_biz_map[(b_id, p_id)] = pb
            player_biz_map[b_id] = pb

    prison_names_map: Dict[int, str] = {}
    prisons_slice = hub.get_slice(account_id, "prisons", max_age_seconds=3600.0, source_tag=tag)
    if prisons_slice and isinstance(prisons_slice.data, dict):
        for p_item in prisons_slice.data.get("prisons") or []:
            if isinstance(p_item, dict) and p_item.get("id") is not None:
                prison_names_map[int(p_item["id"])] = str(p_item.get("name") or f"Тюрьма #{p_item['id']}")
    elif bot_context.prison_api is not None:
        try:
            p_res = await bot_context.prison_api.get_all_prisons()
            p_list = p_res.get("prisons", []) if isinstance(p_res, dict) else (p_res if isinstance(p_res, list) else [])
            for p_item in p_list:
                if isinstance(p_item, dict) and p_item.get("id") is not None:
                    prison_names_map[int(p_item["id"])] = str(p_item.get("name") or f"Тюрьма #{p_item['id']}")
        except Exception:
            pass

    merged_businesses = []
    pending_resources = {"authority": 0, "cigarettes": 0, "rubles": 0, "rating": 0}

    for b in raw_biz_configs:
        if not isinstance(b, dict):
            continue
        b_id = b.get("businessId") or b.get("id")
        p_id = b.get("prisonId", 1)
        pb = player_biz_map.get((b_id, p_id)) or player_biz_map.get(b_id) or {}
        real_level = pb.get("level", b.get("level", 0))

        rew_per_lvl = b.get("rewardPerLevel", 0)
        rew_type = b.get("rewardType", "cigarettes")
        cur_reward = real_level * rew_per_lvl
        next_reward = (real_level + 1) * rew_per_lvl

        if real_level > 0 and cur_reward > 0:
            norm_type = DropParser._normalize_currency(rew_type) or rew_type
            pending_resources[norm_type] = pending_resources.get(norm_type, 0) + cur_reward

        p_name = prison_names_map.get(int(p_id)) if p_id is not None else None
        merged_businesses.append({
            "businessId": b_id,
            "prisonId": p_id,
            "prisonName": p_name or f"Тюрьма #{p_id}",
            "title": b.get("title") or b.get("name") or f"Бизнес #{b_id}",
            "level": real_level,
            "maxLevel": b.get("maxLevel", 8),
            "rewardType": rew_type,
            "rewardPerLevel": rew_per_lvl,
            "currentReward": cur_reward,
            "nextReward": next_reward,
            "upgradeCost": b.get("upgradeCost", 0),
        })

    active_businesses = [b for b in merged_businesses if b["level"] > 0]
    result_biz = active_businesses if active_businesses else merged_businesses

    t_state = player_data.get("talentState") or {}
    t_pts = int(
        player_data.get("talentPointsTotal")
        or player_data.get("talents")
        or (int(t_state.get("spentPoints", 0)) + int(t_state.get("unspentPoints", 0)))
        or 0
    )
    last_energy_restore = player_data.get("lastEnergyRestoreTime") or player_data.get("energyRestoreTime")
    from workers.routine_worker import get_toilet_paper_reset_info
    tp_info = get_toilet_paper_reset_info(can_claim_paper)

    payload = {
        "success": True,
        "profile": {
            "id": player_data.get("id"),
            "nickname": player_data.get("nickname") or player_data.get("name") or "Арестант",
            "level": player_data.get("level", 0),
            "authority": player_data.get("authority", 0),
            "biceps": player_data.get("biceps", 0),
            "energy": player_data.get("energy", 0),
            "maxEnergy": player_data.get("maxEnergy", 50),
            "guild": player_data.get("guild") or player_data.get("clan") or {},
            "talents": t_pts,
            "talentPointsTotal": t_pts,
            "lastEnergyRestoreTime": last_energy_restore,
            "energyRestoreIntervalSeconds": int(player_data.get("energyRestoreIntervalSeconds") or 300),
            "beardDays": player_data.get("beardDays", 0),
            "canClaimToiletPaper": can_claim_paper,
            "toiletPaper": tp_info,
        },
        "toiletPaper": tp_info,
        "currencies": {
            "cigarettes": currencies.get("cigarettes", 0),
            "sugar": currencies.get("sugar", 0),
            "rubles": currencies.get("rubles", 0),
            "paper": currencies.get("paper", 0),
            "soap": currencies.get("soap", 0),
            "keys": currencies.get("keys", 0),
        },
        "weapons": {
            "poisonCount": poison_cnt,
            "gunshotCount": gunshot_cnt,
            "knifeCount": knife_cnt,
        },
        "businesses": result_biz,
        "pendingResources": pending_resources,
        "lastBusinessCollectTime": last_collect,
        "lastCollectTime": last_collect,
        "nextBusinessCollectAt": next_collect_at,
        "businessCooldownSec": business_cooldown_sec,
        "businessCooldownTotalSec": business_cooldown_total,
        "characterLayers": _build_character_layers(player_data),
    }
    hub.update_slice(account_id, "profile", payload, source_tag=tag)
    return payload


TIME_MSK_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@api_router.get("/live/boss")
async def get_live_boss(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """Получение состояния боя с боссом, сессии, эффективного урона оружия, откатов и статуса доступности всех 58 боссов."""
    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "boss", max_age_seconds=90.0, source_tag=tag)
        if warm is not None:
            return warm.data

    async def _safe_bootstrap():
        return await boss_api.get_bootstrap()

    async def _safe_weapons():
        try:
            return await boss_api.get_weapons()
        except Exception:
            return {}

    async def _safe_all_bosses():
        try:
            res = await boss_api.get_all_bosses()
            if res:
                return res
        except Exception:
            pass
        from client.api.boss import _load_bosses_catalog, FALLBACK_BOSSES
        return [dict(b) for b in (_load_bosses_catalog() or FALLBACK_BOSSES)]

    async def _safe_prisons():
        if bot_context.prison_api:
            try:
                p_res = await bot_context.prison_api.get_all_prisons()
                return p_res.get("prisons", []) if isinstance(p_res, dict) else p_res
            except Exception:
                return []
        return []

    async def _fetch_boss_raw():
        return await asyncio.gather(
            _safe_bootstrap(), _safe_weapons(), _safe_all_bosses(), _safe_prisons()
        )

    try:
        bootstrap, weapons_data, raw_bosses, prisons_data = await _flight_cache.get_or_set(
            f"boss:{account_id}", 3.0, _fetch_boss_raw
        )
    except Exception as e:
        logger.error("Error fetching boss live data: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch boss data: {e}")

    # Оценка доступности боссов через точный резолвер
    from client.api.boss import BossAPI
    bosses = BossAPI.evaluate_bosses_availability(raw_bosses, bootstrap=bootstrap, prisons_data=prisons_data)

    session_data = bootstrap.get("session") or bootstrap.get("currentBattle") or bootstrap.get("activeBoss")
    has_reward = bool(bootstrap.get("hasReward", False))
    state = bootstrap.get("state") or ("active" if session_data else "none")

    weapon_stats = weapons_data.get("weaponStatsEffective") or bootstrap.get("weaponStatsEffective") or {}

    melee_ts = {
        "lastPunchChestTime": weapons_data.get("lastPunchChestTime") or bootstrap.get("lastPunchChestTime"),
        "lastKickBallsTime": weapons_data.get("lastKickBallsTime") or bootstrap.get("lastKickBallsTime"),
        "lastPokeEyesTime": weapons_data.get("lastPokeEyesTime") or bootstrap.get("lastPokeEyesTime"),
        "lastKneeEarTime": weapons_data.get("lastKneeEarTime") or bootstrap.get("lastKneeEarTime"),
    }

    cooldowns = {
        "punchChestCooldownSec": weapons_data.get("punchChestCooldownSec", 28800),
        "kickBallsCooldownSec": weapons_data.get("kickBallsCooldownSec", 28800),
        "pokeEyesCooldownSec": weapons_data.get("pokeEyesCooldownSec", 28800),
        "kneeEarCooldownSec": weapons_data.get("kneeEarCooldownSec", 28800),
    }

    player_stats = bootstrap.get("playerStats") or {}

    # Расчет эффективного урона оружия за 1 удар (базовые: Яд 250, Самопал 60, Финка 30)
    poi_dmg = int(weapon_stats.get("poison") or weapon_stats.get("poisonDamage") or weapons_data.get("poisonDamage") or 250)
    gun_dmg = int(weapon_stats.get("gunshot") or weapon_stats.get("gunshotDamage") or weapons_data.get("gunshotDamage") or 60)
    kni_dmg = int(weapon_stats.get("knife") or weapon_stats.get("knifeDamage") or weapons_data.get("knifeDamage") or 30)
    if poi_dmg <= 0:
        poi_dmg = 250
    if gun_dmg <= 0:
        gun_dmg = 60
    if kni_dmg <= 0:
        kni_dmg = 30
    weapon_damages = {
        "poison": poi_dmg,
        "gunshot": gun_dmg,
        "knife": kni_dmg,
    }

    # Загрузка активного пресета (при наличии)
    active_preset_info = None
    engine = bot_context.db_engine or get_engine()
    if engine:
        try:
            async with get_session(engine) as session:
                stmt_act = select(BossPreset).where(BossPreset.account_id == account_id, BossPreset.is_running == True)
                act_p = (await session.execute(stmt_act)).scalar_one_or_none()
                if act_p:
                    active_preset_info = {
                        "id": act_p.id,
                        "name": act_p.name,
                        "items": act_p.items or [],
                        "daily_enabled": act_p.daily_enabled,
                        "schedule_time_msk": act_p.schedule_time_msk,
                        "is_running": act_p.is_running,
                        "current_step_index": act_p.current_step_index,
                        "last_status": act_p.last_status,
                    }
        except Exception:
            pass

    payload = {
        "success": True,
        "state": state,
        "hasReward": has_reward,
        "session": session_data,
        "weaponStatsEffective": weapon_stats,
        "weaponDamages": weapon_damages,
        "meleeTimestamps": melee_ts,
        "cooldowns": cooldowns,
        "playerStats": player_stats,
        "bosses": bosses,
        "activePreset": active_preset_info,
    }
    hub.update_slice(account_id, "boss", payload, source_tag=tag)
    return payload


# ============================================================================
# ПРЕСЕТЫ БОССОВ (CRUD, РАСПИСАНИЕ МСК, RUN / STOP)
# ============================================================================

@api_router.get("/boss/presets")
async def get_boss_presets(account_id: int = 1) -> Dict[str, Any]:
    """Получение всех сохраненных пресетов боссов для аккаунта."""
    engine = bot_context.db_engine or get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with get_session(engine) as session:
        stmt = select(BossPreset).where(BossPreset.account_id == account_id).order_by(BossPreset.id.asc())
        presets = (await session.execute(stmt)).scalars().all()

        return {
            "success": True,
            "presets": [
                {
                    "id": p.id,
                    "name": p.name,
                    "items": p.items or [],
                    "totalSteps": sum(max(1, int(it.get("count") or 1)) for it in (p.items or []) if isinstance(it, dict)),
                    "daily_enabled": bool(p.daily_enabled),
                    "schedule_time_msk": p.schedule_time_msk,
                    "last_run_date_msk": p.last_run_date_msk,
                    "is_running": bool(p.is_running),
                    "current_step_index": p.current_step_index,
                    "last_status": p.last_status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in presets
            ],
        }


@api_router.post("/boss/presets")
async def create_boss_preset(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Создание нового пресета боссов с валидацией имени, шагов и времени МСК."""
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Имя пресета не может быть пустым")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="Имя пресета слишком длинное (макс 100 символов)")

    time_msk = str(payload.get("schedule_time_msk") or "09:00").strip()
    if not TIME_MSK_REGEX.match(time_msk):
        raise HTTPException(status_code=400, detail="Неверный формат времени (ожидается HH:MM, например '09:00')")

    items = payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="Список шагов пресета не может быть пустым")

    cleaned_items = []
    for itm in items:
        if not isinstance(itm, dict):
            continue
        bid = itm.get("bossId") or itm.get("boss_id")
        if not bid:
            continue
        cleaned_items.append({
            "bossId": int(bid),
            "bossName": str(itm.get("bossName") or itm.get("name") or f"Босс #{bid}").strip(),
            "mode": str(itm.get("mode") or "pacansky").strip(),
            "count": max(1, min(100, int(itm.get("count") or 1))),
        })

    if not cleaned_items:
        raise HTTPException(status_code=400, detail="Список шагов пресета должен содержать хотя бы одного валидного босса")

    daily_enabled = bool(payload.get("daily_enabled", False))

    engine = bot_context.db_engine or get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with get_session(engine) as session:
        preset = BossPreset(
            account_id=account_id,
            name=name,
            items=cleaned_items,
            daily_enabled=daily_enabled,
            schedule_time_msk=time_msk,
            is_running=False,
            current_step_index=0,
            last_status="Ожидание запуска",
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)

        return {
            "success": True,
            "preset": {
                "id": preset.id,
                "name": preset.name,
                "items": preset.items,
                "daily_enabled": preset.daily_enabled,
                "schedule_time_msk": preset.schedule_time_msk,
                "last_run_date_msk": preset.last_run_date_msk,
                "is_running": preset.is_running,
                "current_step_index": preset.current_step_index,
                "last_status": preset.last_status,
                "created_at": preset.created_at.isoformat() if preset.created_at else None,
                "updated_at": preset.updated_at.isoformat() if preset.updated_at else None,
            },
        }


@api_router.patch("/boss/presets/{preset_id}")
async def update_boss_preset(
    preset_id: int,
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Обновление параметров существующего пресета боссов."""
    engine = bot_context.db_engine or get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with get_session(engine) as session:
        preset = await session.get(BossPreset, preset_id)
        if not preset or preset.account_id != account_id:
            raise HTTPException(status_code=404, detail="Пресет не найден")

        if "name" in payload:
            name = str(payload["name"]).strip()
            if not name:
                raise HTTPException(status_code=400, detail="Имя пресета не может быть пустым")
            if len(name) > 100:
                raise HTTPException(status_code=400, detail="Имя пресета слишком длинное (макс 100 символов)")
            preset.name = name

        if "schedule_time_msk" in payload:
            time_msk = str(payload["schedule_time_msk"]).strip()
            if not TIME_MSK_REGEX.match(time_msk):
                raise HTTPException(status_code=400, detail="Неверный формат времени (ожидается HH:MM)")
            preset.schedule_time_msk = time_msk

        if "daily_enabled" in payload:
            preset.daily_enabled = bool(payload["daily_enabled"])

        if "items" in payload:
            items = payload["items"]
            if not isinstance(items, list) or len(items) == 0:
                raise HTTPException(status_code=400, detail="Список шагов пресета не может быть пустым")
            cleaned_items = []
            for itm in items:
                if not isinstance(itm, dict):
                    continue
                bid = itm.get("bossId") or itm.get("boss_id")
                if not bid:
                    continue
                cleaned_items.append({
                    "bossId": int(bid),
                    "bossName": str(itm.get("bossName") or itm.get("name") or f"Босс #{bid}").strip(),
                    "mode": str(itm.get("mode") or "pacansky").strip(),
                    "count": max(1, min(100, int(itm.get("count") or 1))),
                })
            if not cleaned_items:
                raise HTTPException(status_code=400, detail="Список шагов пресета должен содержать хотя бы одного валидного босса")
            preset.items = cleaned_items

        preset.updated_at = datetime.utcnow()
        session.add(preset)
        await session.commit()
        await session.refresh(preset)

        return {
            "success": True,
            "preset": {
                "id": preset.id,
                "name": preset.name,
                "items": preset.items,
                "daily_enabled": preset.daily_enabled,
                "schedule_time_msk": preset.schedule_time_msk,
                "last_run_date_msk": preset.last_run_date_msk,
                "is_running": preset.is_running,
                "current_step_index": preset.current_step_index,
                "last_status": preset.last_status,
                "created_at": preset.created_at.isoformat() if preset.created_at else None,
                "updated_at": preset.updated_at.isoformat() if preset.updated_at else None,
            },
        }


@api_router.delete("/boss/presets/{preset_id}")
async def delete_boss_preset(preset_id: int, account_id: int = 1) -> Dict[str, Any]:
    """Удаление пресета боссов."""
    engine = bot_context.db_engine or get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with get_session(engine) as session:
        preset = await session.get(BossPreset, preset_id)
        if not preset or preset.account_id != account_id:
            raise HTTPException(status_code=404, detail="Пресет не найден")

        await session.delete(preset)
        await session.commit()

    return {"success": True, "message": "Preset deleted"}


@api_router.post("/boss/presets/{preset_id}/run")
async def run_boss_preset(preset_id: int, account_id: int = 1) -> Dict[str, Any]:
    """Ручной запуск пресета боссов."""
    engine = bot_context.db_engine or get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with get_session(engine) as session:
        # Останавливаем другие запущенные пресеты
        stmt_all = select(BossPreset).where(BossPreset.account_id == account_id, BossPreset.is_running == True)
        running_presets = (await session.execute(stmt_all)).scalars().all()
        for rp in running_presets:
            rp.is_running = False
            rp.last_status = "Остановлен (запущен другой пресет)"
            session.add(rp)

        preset = await session.get(BossPreset, preset_id)
        if not preset or preset.account_id != account_id:
            raise HTTPException(status_code=404, detail="Пресет не найден")

        preset.is_running = True
        preset.current_step_index = 0
        preset.last_status = "Запущен вручную"
        session.add(preset)
        await session.commit()
        await session.refresh(preset)

    ctrl = getattr(bot_context, "scheduler_controller", None)
    if ctrl is not None:
        ctrl.trigger_boss_now(force_manual=True)
    elif bot_context.boss_worker:
        asyncio.create_task(bot_context.boss_worker.run_cycle(force_manual=True))

    _flight_cache.invalidate(f"boss:{account_id}")
    total_steps = sum(max(1, int(it.get("count") or 1)) for it in (preset.items or []) if isinstance(it, dict))
    hub = _get_hub()
    if hasattr(hub, "set_preset_state"):
        presets_res = await get_boss_presets(account_id=account_id)
        hub.set_preset_state(
            account_id,
            preset.id,
            current_step=preset.current_step_index,
            total_steps=total_steps,
            status="running",
            presets_list=presets_res.get("presets", []),
        )
    _schedule_hub_refresh(account_id, "boss", "presets")

    return {
        "success": True,
        "message": "Пресет запущен",
        "preset": {
            "id": preset.id,
            "name": preset.name,
            "items": preset.items,
            "totalSteps": total_steps,
            "daily_enabled": preset.daily_enabled,
            "schedule_time_msk": preset.schedule_time_msk,
            "is_running": preset.is_running,
            "current_step_index": preset.current_step_index,
            "last_status": preset.last_status,
        },
    }


@api_router.post("/boss/presets/{preset_id}/stop")
async def stop_boss_preset(preset_id: int, account_id: int = 1) -> Dict[str, Any]:
    """Остановка выполнения пресета боссов."""
    engine = bot_context.db_engine or get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with get_session(engine) as session:
        preset = await session.get(BossPreset, preset_id)
        if not preset or preset.account_id != account_id:
            raise HTTPException(status_code=404, detail="Пресет не найден")

        preset.is_running = False
        preset.last_status = "Остановлен пользователем"
        session.add(preset)
        await session.commit()
        await session.refresh(preset)

    _flight_cache.invalidate(f"boss:{account_id}")
    hub = _get_hub()
    if hasattr(hub, "set_preset_state"):
        presets_res = await get_boss_presets(account_id=account_id)
        hub.set_preset_state(
            account_id,
            None,
            status="stopped",
            presets_list=presets_res.get("presets", []),
        )
    _schedule_hub_refresh(account_id, "boss", "presets")

    return {
        "success": True,
        "message": "Пресет остановлен",
        "preset": {
            "id": preset.id,
            "name": preset.name,
            "is_running": preset.is_running,
            "last_status": preset.last_status,
        },
    }


@api_router.get("/live/prisons")
async def get_live_prisons(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """Получение каталога тюрем, состояния выбранной тюрьмы, чекпоинтов и мастеров."""
    prison_api = bot_context.prison_api
    if not prison_api:
        raise HTTPException(status_code=503, detail="PrisonAPI not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "prisons", max_age_seconds=120.0, source_tag=tag)
        if warm is not None:
            return warm.data

    engine = bot_context.db_engine
    cfg = await get_or_create_config(account_id, engine) if engine else None
    is_day = not getattr(cfg, "prison_prefer_night", False)

    async def _safe_prisons():
        return await prison_api.get_all_prisons()

    async def _safe_masters():
        try:
            return await prison_api.get_masters()
        except Exception:
            return {}

    async def _safe_state(tid: int):
        try:
            res = await prison_api.get_prison_state(tid)
            if isinstance(res, dict) and isinstance(res.get("data"), dict):
                return res["data"]
            return res if isinstance(res, dict) else {}
        except Exception:
            return {}

    async def _safe_checkpoints(tid: int):
        try:
            cp = await prison_api.get_checkpoints(tid, is_day)
            if isinstance(cp, dict):
                data_cp = cp.get("data")
                if isinstance(data_cp, list):
                    return data_cp
                fallback_cp = cp.get("checkpoints")
                if isinstance(fallback_cp, list):
                    return fallback_cp
                return []
            return cp if isinstance(cp, list) else []
        except Exception:
            return []

    async def _fetch_prisons_payload():
        prisons_res, masters_res = await asyncio.gather(_safe_prisons(), _safe_masters())
        raw_prisons = prisons_res.get("prisons", []) if isinstance(prisons_res, dict) else prisons_res
        masters = masters_res.get("masters", []) if isinstance(masters_res, dict) else masters_res

        if not isinstance(raw_prisons, list):
            raw_prisons = []

        target_id = getattr(cfg, "prison_target_id", None)
        if not target_id and raw_prisons:
            unlocked = [p.get("id") for p in raw_prisons if isinstance(p, dict) and p.get("isUnlocked", True)]
            target_id = max(unlocked) if unlocked else raw_prisons[0].get("id", 1)
        target_id = target_id or 1

        # Fetch states for all unlocked prisons (for accurate dayRuns / nightRuns on every card)
        unlocked_ids = [
            int(p["id"]) for p in raw_prisons
            if isinstance(p, dict) and p.get("id") is not None and p.get("isUnlocked", True)
        ]
        if target_id not in unlocked_ids:
            unlocked_ids.append(int(target_id))

        sem = asyncio.Semaphore(6)
        async def _fetch_pstate(pid: int):
            async with sem:
                return pid, await _safe_state(pid)

        state_pairs, checkpoints = await asyncio.gather(
            asyncio.gather(*(_fetch_pstate(pid) for pid in unlocked_ids)),
            _safe_checkpoints(target_id),
        )
        states_by_id = {pid: st for pid, st in state_pairs}
        state_data = states_by_id.get(int(target_id), {})

        enriched_prisons = []
        for idx, p in enumerate(raw_prisons):
            if not isinstance(p, dict):
                continue
            p_copy = dict(p)
            pid = p_copy.get("id")
            st = states_by_id.get(int(pid)) if pid is not None else None
            if isinstance(st, dict):
                p_copy["dayRuns"] = int(st.get("dayRuns", p_copy.get("dayRuns", 0)) or 0)
                p_copy["nightRuns"] = int(st.get("nightRuns", p_copy.get("nightRuns", 0)) or 0)
            else:
                p_copy.setdefault("dayRuns", 0)
                p_copy.setdefault("nightRuns", 0)
            if not p_copy.get("isUnlocked", True):
                req_text = p_copy.get("unlockRequirement") or p_copy.get("unlock_requirement")
                if not req_text and idx > 0 and isinstance(raw_prisons[idx - 1], dict):
                    prev_p = raw_prisons[idx - 1]
                    prev_name = prev_p.get("name") or f"Тюрьме #{prev_p.get('id')}"
                    req_text = f"Пройдите ходку в «{prev_name}»"
                if not req_text:
                    req_text = "Пройдите предыдущую тюрьму"
                p_copy["unlockRequirement"] = req_text
                p_copy["unlock_requirement"] = req_text
            enriched_prisons.append(p_copy)

        completed_cps = int(
            (state_data.get("dayCurrentCheckpoint") if is_day else state_data.get("nightCurrentCheckpoint"))
            or 0
        ) if isinstance(state_data, dict) else 0
        current_clicks = int(
            (state_data.get("dayClicksInCheckpoint") if is_day else state_data.get("nightClicksInCheckpoint"))
            or 0
        ) if isinstance(state_data, dict) else 0
        total_cps = len(checkpoints) if isinstance(checkpoints, list) else 0
        active_cp = None
        if total_cps > 0:
            active_idx = min(max(completed_cps, 0), total_cps - 1)
            active_cp = checkpoints[active_idx] if isinstance(checkpoints[active_idx], dict) else {}
        req_clicks = int((active_cp or {}).get("clicksRequired") or 1)
        energy_cost = int((active_cp or {}).get("energyCost") or 5)
        total_progress = 0.0
        if total_cps > 0:
            if completed_cps >= total_cps:
                total_progress = 100.0
            else:
                total_progress = min(
                    100.0,
                    max(0.0, ((completed_cps + (current_clicks / max(req_clicks, 1))) / max(total_cps, 1)) * 100.0),
                )

        return {
            "success": True,
            "prisons": enriched_prisons,
            "targetId": target_id,
            "isDay": is_day,
            "state": state_data,
            "checkpoints": checkpoints,
            "masters": masters,
            "progressInfo": {
                "completedCheckpoints": completed_cps,
                "currentStageNumber": min(total_cps, completed_cps + 1) if total_cps > 0 else 0,
                "totalCheckpoints": total_cps,
                "currentClicks": current_clicks,
                "requiredClicks": req_clicks,
                "energyCost": energy_cost,
                "progressPercent": round(total_progress, 1),
            },
        }

    target_cfg = getattr(cfg, "prison_target_id", None)
    payload = await _flight_cache.get_or_set(f"prisons:{account_id}:{target_cfg}:{is_day}", 5.0, _fetch_prisons_payload)
    hub.update_slice(account_id, "prisons", payload, source_tag=tag)
    return payload


class PrisonDrainRequest(BaseModel):
    prisonId: Optional[int] = None
    isDay: Optional[bool] = None
    mode: Optional[str] = None
    collectPodogrev: bool = False


@api_router.post("/prisons/drain")
async def drain_prison_energy_endpoint(
    payload: PrisonDrainRequest = Body(default_factory=PrisonDrainRequest),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Непрерывный слив всей доступной энергии игрока в выбранной тюрьме."""
    prison_worker = bot_context.prison_worker
    prison_api = bot_context.prison_api
    if not prison_worker and not prison_api:
        raise HTTPException(status_code=503, detail="PrisonAPI / PrisonWorker not available")

    hub = _get_hub()
    if prison_worker is None:
        from workers.prison_worker import PrisonWorker
        prison_worker = PrisonWorker(
            account_id=account_id,
            prison_api=prison_api,
            player_api=bot_context.player_api,
            db_engine=bot_context.db_engine,
            state_hub=hub,
            enable_jitter=False,
        )
    elif prison_worker.state_hub is None:
        prison_worker.state_hub = hub

    resolved_mode = payload.mode
    if resolved_mode is None and payload.isDay is not None:
        resolved_mode = "day" if payload.isDay else "night"

    result = await prison_worker.drain_all_energy(
        prison_id=payload.prisonId,
        mode=resolved_mode,
        collect_podogrev=payload.collectPodogrev,
        source="manual",
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Drain error"))

    _flight_cache.invalidate()
    _schedule_hub_refresh(account_id, "prisons")
    if bot_context.player_api is not None:
        _schedule_hub_refresh(account_id, "profile")

    return {"success": True, **result}


# ============================================================================
# ACTION ENDPOINTS (РУЧНЫЕ ИГРОВЫЕ ДЕЙСТВИЯ)
# ============================================================================

@api_router.post("/actions/boss/hit")
async def action_boss_hit(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Нанесение ручного удара по боссу (рукопашная или оружие)."""
    weapon = payload.get("weapon")
    count = int(payload.get("count", 1))
    if not weapon or weapon not in ALLOWED_WEAPONS:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимое оружие '{weapon}'. Разрешено: {sorted(list(ALLOWED_WEAPONS))}",
        )

    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")

    try:
        res = await boss_api.hit_boss(weapon, count)
        await _log_action(account_id, "manual_boss_hit", "/api/boss/use-weapon", 200, True, {
            "weapon": weapon, "count": count, "result": res
        })
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "manual_boss_hit", "/api/boss/use-weapon", 500, False, {
            "weapon": weapon, "count": count, "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _flight_cache.invalidate(f"boss:{account_id}")
        _schedule_hub_refresh(account_id, "boss", "profile")


@api_router.post("/actions/boss/start")
async def action_boss_start(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Ручной призыв / запуск боя с боссом."""
    boss_id = payload.get("bossId")
    mode = payload.get("mode", "pacansky")
    if not boss_id:
        raise HTTPException(status_code=400, detail="bossId обязателен")

    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")

    # Проверка блокировки босса перед запуском боя
    from client.api.boss import _load_bosses_catalog, FALLBACK_BOSSES
    catalog = _load_bosses_catalog() or FALLBACK_BOSSES
    b_meta = next((b for b in catalog if b.get("id") == int(boss_id)), None)
    if b_meta and b_meta.get("isLocked"):
        reason = b_meta.get("unlockReason") or "Босс временно заблокирован"
        raise HTTPException(status_code=400, detail=reason)

    try:
        res = await boss_api.start_battle(int(boss_id), str(mode))
        await _log_action(account_id, "manual_boss_start", "/api/boss/start-attack", 200, True, {
            "bossId": boss_id, "mode": mode, "result": res
        })
        engine = bot_context.db_engine
        if engine and bot_context.boss_worker:
            cfg = await get_or_create_config(account_id, engine)
            if getattr(cfg, "boss_auto_melee", False) and not getattr(cfg, "is_paused", False):
                asyncio.create_task(bot_context.boss_worker.trigger_auto_melee())
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "manual_boss_start", "/api/boss/start-attack", 500, False, {
            "bossId": boss_id, "mode": mode, "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _flight_cache.invalidate(f"boss:{account_id}")
        _schedule_hub_refresh(account_id, "boss", "profile")


@api_router.post("/actions/boss/claim")
async def action_boss_claim(payload: Optional[Dict[str, Any]] = Body(None), account_id: int = 1) -> Dict[str, Any]:
    """Ручной сбор награды за поверженного босса."""
    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")

    claim_id = payload.get("claimId") if payload else None
    boss_name = payload.get("bossName") if payload else None
    mode = payload.get("mode") if payload else None
    try:
        if not boss_name:
            try:
                bs = await boss_api.get_bootstrap()
                b_obj = (bs.get("session") or bs.get("currentBattle") or bs.get("activeBoss") or {}) if isinstance(bs, dict) else {}
                boss_name = b_obj.get("bossName") or b_obj.get("title") or bs.get("title")
                mode = mode or b_obj.get("mode")
            except Exception:
                pass
        res = await boss_api.claim_reward(claim_id)
        parsed = DropParser.parse_boss_claim(res, boss_name=boss_name, mode=mode)
        engine = bot_context.db_engine
        if engine:
            await DropParser.save_notification(account_id, parsed, engine)
        await _log_action(account_id, "manual_boss_claim", "/api/boss/claim", 200, True, {
            "result": res, "parsed": parsed
        })
        return {"success": True, "result": res, "parsed": parsed}
    except Exception as e:
        await _log_action(account_id, "manual_boss_claim", "/api/boss/claim", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _flight_cache.invalidate(f"boss:{account_id}")
        _schedule_hub_refresh(account_id, "boss", "profile")


@api_router.get("/boss/friend-damage")
@api_router.post("/actions/boss/friend-damage")
async def action_boss_friend_damage(account_id: int = 1) -> Dict[str, Any]:
    """Сбор / получение урона от друзей на боссах."""
    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")
    try:
        res = await boss_api.get_friend_damage()
        await _log_action(account_id, "friend_damage", "/api/boss/friend-damage", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "friend_damage", "/api/boss/friend-damage", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))



@api_router.post("/actions/prison/work")
async def action_prison_work(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Выполнение серии ручных ходок в тюрьме с агрегацией наград и фиксацией в Notifications."""
    prison_id = payload.get("prisonId")
    if not prison_id:
        raise HTTPException(status_code=400, detail="prisonId обязателен")

    is_day = bool(payload.get("isDay", True))
    if payload.get("drainAll"):
        drain_req = PrisonDrainRequest(prisonId=int(prison_id), isDay=is_day, collectPodogrev=bool(payload.get("collectPodogrev", False)))
        return await drain_prison_energy_endpoint(payload=drain_req, account_id=account_id)

    raw_count = int(payload.get("count", 1))
    count = max(1, min(15, raw_count))

    prison_api = bot_context.prison_api
    if not prison_api:
        raise HTTPException(status_code=503, detail="PrisonAPI not available")

    completed = 0
    last_res = {}
    rewards_map: Dict[str, int] = {}
    drops_list: List[Dict[str, Any]] = []
    errors: List[str] = []

    for i in range(count):
        try:
            work_res = await prison_api.do_prison_work(int(prison_id), is_day)
            completed += 1
            last_res = work_res

            for k, v in work_res.items():
                if isinstance(v, (int, float)) and v > 0:
                    norm_k = DropParser._normalize_currency(k)
                    if norm_k:
                        rewards_map[norm_k] = rewards_map.get(norm_k, 0) + int(v)

            if work_res.get("stash"):
                drops_list.append({"kind": "stash", "title": "Нычка", "subtitle": "Работа в тюрьме"})
            if work_res.get("collectionDrop"):
                c_drop = work_res["collectionDrop"]
                drops_list.append({
                    "kind": "item",
                    "title": c_drop.get("title") or "Предмет коллекции",
                    "subtitle": "Коллекция",
                })
            if work_res.get("weaponDrop"):
                w_drop = work_res["weaponDrop"]
                drops_list.append({
                    "kind": "weapon",
                    "title": w_drop.get("title") or "Оружие",
                    "subtitle": "Оружие",
                })

            if i < count - 1:
                await asyncio.sleep(random.uniform(0.4, 0.8))
        except Exception as e:
            logger.warning("Ошибка при выполнении ручной ходки %d: %s", i + 1, e)
            errors.append(str(e))
            break

    if completed == 0 and errors:
        await _log_action(account_id, "manual_prison_work", f"/api/player/prison/{prison_id}/work", 500, False, {
            "error": errors[0]
        })
        raise HTTPException(status_code=500, detail=errors[0])

    rewards_list = [
        {
            "currency": k,
            "label": CURRENCY_LABELS.get(k, k),
            "amount": v,
        }
        for k, v in rewards_map.items()
    ]

    prison_name = payload.get("prisonName")
    stage_num = payload.get("stageNum")
    if not prison_name:
        try:
            p_res = await prison_api.get_all_prisons()
            plist = p_res.get("prisons", []) if isinstance(p_res, dict) else p_res
            for p_item in (plist or []):
                if isinstance(p_item, dict) and str(p_item.get("id")) == str(prison_id):
                    prison_name = p_item.get("name")
                    break
        except Exception:
            pass
    if stage_num is None:
        try:
            st = await prison_api.get_prison_state(int(prison_id))
            st_in = st.get("data", st) if isinstance(st, dict) else {}
            cp_v = int((st_in.get("dayCurrentCheckpoint" if is_day else "nightCurrentCheckpoint")) or 0)
            stage_num = cp_v + 1 if cp_v >= 0 else None
        except Exception:
            pass

    p_title_name = prison_name or f"Тюрьма #{prison_id}"
    shift_word = "День" if is_day else "Ночь"
    parsed = {
        "category": "prisons",
        "title": f"{p_title_name}: {shift_word} {stage_num}" if stage_num else f"{p_title_name}: {shift_word}",
        "subtitle": f"Кликов: {completed}",
        "rewards": rewards_list,
        "drops": drops_list,
        "meta_json": {
            "type": "prison_action",
            "prison_id": int(prison_id),
            "prison_name": p_title_name,
            "is_day": is_day,
            "stage": stage_num,
            "clicks": completed,
        },
    }

    engine = bot_context.db_engine
    if engine and completed > 0:
        await DropParser.save_notification(account_id, parsed, engine)

    await _log_action(account_id, "manual_prison_work", f"/api/player/prison/{prison_id}/work", 200, True, {
        "prisonId": prison_id, "isDay": is_day, "completed": completed, "rewards": rewards_list, "drops": drops_list
    })

    if isinstance(last_res, dict) and last_res.get("energy") is not None:
        _get_hub().patch_profile_resources(account_id, energy=last_res.get("energy"), lastEnergyRestoreTime=last_res.get("lastEnergyRestoreTime"))
    _flight_cache.invalidate()
    _schedule_hub_refresh(account_id, "prisons", "profile")

    return {
        "success": True,
        "completed": completed,
        "requested": count,
        "parsed": parsed,
        "lastResponse": last_res,
    }


@api_router.post("/actions/master/work")
async def action_master_work(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Ручная тренировка у мастера."""
    master_id = payload.get("masterId")
    if not master_id:
        raise HTTPException(status_code=400, detail="masterId обязателен")

    prison_api = bot_context.prison_api
    if not prison_api:
        raise HTTPException(status_code=503, detail="PrisonAPI not available")

    try:
        res = await prison_api.do_master_work(int(master_id))
        await _log_action(account_id, "manual_master_work", f"/api/player/masters/{master_id}/work", 200, True, {
            "masterId": master_id, "result": res
        })
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "manual_master_work", f"/api/player/masters/{master_id}/work", 500, False, {
            "masterId": master_id, "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/routine/collect")
async def action_routine_collect(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Ручной запуск сбора прибыли, туалетной бумаги, бороды, подогревов, подарков или календаря."""
    target = payload.get("target")
    if not target or target not in ALLOWED_ROUTINE_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимая цель '{target}'. Разрешено: {sorted(list(ALLOWED_ROUTINE_TARGETS))}",
        )

    player_api = bot_context.player_api
    social_api = bot_context.social_api
    engine = bot_context.db_engine

    res: Dict[str, Any] = {}
    parsed: Dict[str, Any] = {}
    endpoint = ""

    try:
        if target == "business":
            if not player_api:
                raise HTTPException(503, "PlayerAPI not available")
            endpoint = "/api/player/business/collect"
            res = await player_api.collect_business_rewards()
            parsed = DropParser.parse_business_collect(res)
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target == "toilet_paper":
            if not player_api:
                raise HTTPException(503, "PlayerAPI not available")
            endpoint = "/api/daily/toilet-paper"
            res = await player_api.claim_toilet_paper()
            parsed = DropParser.parse_other(
                title="Туалетная бумага",
                subtitle="Ежедневный рулон собран",
                rewards=[{"currency": "paper", "label": "Бумага", "amount": 1}],
            )
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target == "beard":
            if not player_api:
                raise HTTPException(503, "PlayerAPI not available")
            endpoint = "/api/beard/update"
            res = await player_api.update_beard()
            parsed = DropParser.parse_other(
                title="Бритье бороды",
                subtitle="Борода успешно сбрита",
                rewards=[],
            )
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target == "podogrev":
            if not player_api:
                raise HTTPException(503, "PlayerAPI not available")
            endpoint = "/api/podogrev/collect/all"
            res = await player_api.collect_all_podogrev()
            rew_list = []
            for k, v in res.items():
                c_k = DropParser._normalize_currency(k)
                if c_k and isinstance(v, (int, float)) and v > 0:
                    rew_list.append({
                        "currency": c_k,
                        "label": CURRENCY_LABELS.get(c_k, c_k),
                        "amount": int(v),
                    })
            parsed = DropParser.parse_other(
                title="Подогревы от корешей",
                subtitle="Все подогревы собраны",
                rewards=rew_list,
            )
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target == "gifts":
            if not social_api:
                raise HTTPException(503, "SocialAPI not available")
            endpoint = "/api/gifts/claim"
            inbox = await social_api.get_gifts_inbox()
            gifts_list = inbox.get("gifts") or inbox.get("items") or []
            claimed = 0
            for g in gifts_list:
                g_id = g.get("id") or g.get("giftId")
                if g_id:
                    try:
                        await social_api.claim_gift(g_id)
                        claimed += 1
                    except Exception:
                        pass
            res = {"claimed": claimed, "total": len(gifts_list)}
            parsed = DropParser.parse_other(
                title="Посылки от корешей",
                subtitle=f"Собрано посылок: {claimed}",
                rewards=[],
            )
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target == "friends":
            if not social_api:
                raise HTTPException(503, "SocialAPI not available")
            endpoint = "/api/friendship/accept-request"
            reqs = await social_api.get_friend_requests()
            flist = reqs.get("requests") or reqs.get("items") or []
            accepted = 0
            for req in flist:
                u_id = req.get("fromUserId") or req.get("userId") or req.get("id")
                if u_id:
                    try:
                        await social_api.accept_friend(int(u_id))
                        accepted += 1
                    except Exception:
                        pass
            res = {"accepted": accepted, "total": len(flist)}
            parsed = DropParser.parse_other(
                title="Заявки в кореша",
                subtitle=f"Принято заявок: {accepted}",
                rewards=[],
            )
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target == "monthly":
            if not social_api:
                raise HTTPException(503, "SocialAPI not available")
            endpoint = "/api/monthly/claim"
            st = await social_api.get_monthly_state()
            claimable_tiers = (
                st.get("user", {}).get("claimableTiers", [])
                if isinstance(st.get("user"), dict)
                else st.get("claimableTiers", [])
            )
            claimed_results = []
            if claimable_tiers:
                for t in claimable_tiers:
                    try:
                        c_res = await social_api.claim_monthly_reward(int(t))
                        claimed_results.append(c_res)
                    except Exception as e:
                        logger.warning("Error claiming tier %s: %s", t, e)
                res = {"claimed": len(claimed_results), "results": claimed_results}
                parsed = DropParser.parse_monthly_claim({"rewards": claimed_results}, tier="все доступные")
            else:
                tier = st.get("currentTier") or st.get("tier") or 1
                try:
                    res = await social_api.claim_monthly_reward(int(tier))
                except Exception:
                    res = {"claimed": 0, "message": "no_claimable_tiers"}
                parsed = DropParser.parse_monthly_claim(res, tier=tier)

            if engine:
                await DropParser.save_notification(account_id, parsed, engine)

        elif target in ("paper_roll", "kolsik"):
            if not player_api:
                raise HTTPException(503, "PlayerAPI not available")
            endpoint = "/api/kolsik/roll-paper"
            res = await player_api.roll_kolsik("paper")
            parsed = DropParser.parse_kolsik_roll(res, "paper")
            if engine:
                await DropParser.save_notification(account_id, parsed, engine)


        await _log_action(account_id, f"manual_{target}_collect", endpoint, 200, True, {
            "target": target, "result": res, "parsed": parsed
        })
        return {"success": True, "target": target, "result": res, "parsed": parsed}

    except HTTPException:
        raise
    except Exception as e:
        await _log_action(account_id, f"manual_{target}_collect", endpoint, 500, False, {
            "target": target, "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# НОВЫЕ ХУКИ ИГРЫ (БИЗНЕСЫ, КОРЕША, БАФФЫ, ТАЛАНТЫ, КОЛЛЕКЦИИ, БАУЛЫ)
# ============================================================================

@api_router.post("/actions/business/upgrade")
async def action_upgrade_business(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Ручная прокачка уровня бизнеса."""
    business_id = payload.get("businessId")
    prison_id = payload.get("prisonId", 1)
    if not business_id:
        raise HTTPException(status_code=400, detail="businessId обязателен")

    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    try:
        res = await player_api.upgrade_business(int(business_id), int(prison_id))
        await _log_action(account_id, "upgrade_business", f"/api/player/business/upgrade?businessId={business_id}&prisonId={prison_id}", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "upgrade_business", f"/api/player/business/upgrade?businessId={business_id}&prisonId={prison_id}", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/friendship/requests")
async def get_friendship_requests(
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=100),
    account_id: int = 1,
    force: bool = Query(False),
) -> Dict[str, Any]:
    """Получение списка входящих заявок в друзья с обогащенными статами кандидатов."""
    social_api = bot_context.social_api
    player_api = bot_context.player_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force and page == 0:
        warm = hub.get_slice(account_id, "friend_requests", max_age_seconds=120.0, source_tag=tag)
        if warm is not None:
            return warm.data

    try:
        candidates = await social_api.get_enriched_friend_requests(
            page=page,
            page_size=page_size,
            player_api=player_api,
        )
        payload = {"success": True, "requests": candidates, "total": len(candidates)}
        if page == 0:
            hub.update_slice(account_id, "friend_requests", payload, source_tag=tag)
        return payload
    except Exception as e:
        logger.error("Error fetching friend requests: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/monthly/state")
async def get_monthly_state(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """Получение актуального состояния Месячных делюг."""
    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "monthly", max_age_seconds=180.0, source_tag=tag)
        if warm is not None:
            return warm.data

    try:
        st = await social_api.get_monthly_state()
        if isinstance(st, dict):
            user_m = st.get("user") or {}
            global_m = st.get("global") or {}
            active_day_id = user_m.get("activeDayId")
            user_days = user_m.get("days") or {}
            days_defs = global_m.get("days") or []
            today_def = next((d for d in days_defs if isinstance(d, dict) and d.get("dayId") == active_day_id), None)
            day_prog = user_days.get(str(active_day_id)) or user_days.get(active_day_id) or {}
            today_cur = int(day_prog.get("progress") or 0)
            today_tgt = int((today_def or {}).get("target") or 0)
            today_obj = st.get("today")
            if isinstance(today_obj, dict):
                today_obj.setdefault("current", today_cur)
                if today_tgt > 0:
                    today_obj.setdefault("target", today_tgt)
            elif today_def:
                st["today"] = {
                    "dayId": active_day_id,
                    "title": today_def.get("title") or today_def.get("action") or "",
                    "action": today_def.get("action") or "",
                    "current": today_cur,
                    "target": today_tgt,
                    "completed": bool(day_prog.get("completed", False)),
                }
        payload = {"success": True, "state": st}
        hub.update_slice(account_id, "monthly", payload, source_tag=tag)
        return payload
    except Exception as e:
        logger.error("Error fetching monthly state: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/kolsik/roll")
async def action_kolsik_roll(payload: Optional[Dict[str, Any]] = Body(None), account_id: int = 1) -> Dict[str, Any]:
    """Ручная прокрутка/покупка наколки у Кольщика за туалетную бумагу или за рубли."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    engine = bot_context.db_engine
    body = payload or {}
    currency = str(body.get("currency") or "paper").lower().strip()
    if currency not in ("paper", "rubles"):
        raise HTTPException(status_code=400, detail="currency must be 'paper' or 'rubles'")

    endpoint = "/api/kolsik/roll" if currency == "rubles" else "/api/kolsik/roll-paper"
    try:
        res = await player_api.roll_kolsik(currency)
        parsed = DropParser.parse_kolsik_roll(res, currency)
        if engine:
            await DropParser.save_notification(account_id, parsed, engine)
        await _log_action(account_id, "manual_kolsik_roll", endpoint, 200, True, {
            "currency": currency, "result": res, "parsed": parsed
        })
        return {"success": True, "currency": currency, "result": res, "parsed": parsed}
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await _log_action(account_id, "manual_kolsik_roll", endpoint, 500, False, {
            "currency": currency, "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/friendship/accept")
async def action_accept_friend(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Ручное принятие заявки в друзья."""
    from_user_id = payload.get("fromUserId") or payload.get("userId")
    if not from_user_id:
        raise HTTPException(status_code=400, detail="fromUserId обязателен")

    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    try:
        res = await social_api.accept_friend(int(from_user_id))
        await _log_action(account_id, "accept_friend", f"/api/friendship/accept-request?fromUserId={from_user_id}", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "accept_friend", f"/api/friendship/accept-request?fromUserId={from_user_id}", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/friendship/decline")
async def action_decline_friend(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Ручное отклонение заявки в друзья."""
    from_user_id = payload.get("fromUserId") or payload.get("userId")
    if not from_user_id:
        raise HTTPException(status_code=400, detail="fromUserId обязателен")

    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    try:
        res = await social_api.decline_friend(int(from_user_id))
        await _log_action(account_id, "decline_friend", f"/api/friendship/decline-request?fromUserId={from_user_id}", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "decline_friend", f"/api/friendship/decline-request?fromUserId={from_user_id}", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/boss/buffs")
async def get_boss_buffs() -> Dict[str, Any]:
    """Получение каталога баффов на боссах с реальной проверкой доступности бригадных усилений."""
    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")
    try:
        tasks = [
            boss_api.get_boss_buffs(),
            boss_api.get_bootstrap(),
        ]
        has_guild_status = hasattr(boss_api, "get_guild_status") and callable(getattr(boss_api, "get_guild_status"))
        has_guild_buffs = hasattr(boss_api, "get_guild_buffs") and callable(getattr(boss_api, "get_guild_buffs"))
        has_shodnyak_buffs = hasattr(boss_api, "get_shodnyak_buffs") and callable(getattr(boss_api, "get_shodnyak_buffs"))

        tasks.append(boss_api.get_guild_status() if has_guild_status else asyncio.sleep(0, result={}))
        tasks.append(boss_api.get_guild_buffs() if has_guild_buffs else asyncio.sleep(0, result={}))
        tasks.append(boss_api.get_shodnyak_buffs() if has_shodnyak_buffs else asyncio.sleep(0, result={}))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        buffs_res, boot_res, guild_status_res, guild_buffs_res, shodnyak_res = results

        resp = buffs_res if isinstance(buffs_res, dict) else {}
        boot = boot_res if isinstance(boot_res, dict) else {}
        guild_status = guild_status_res if isinstance(guild_status_res, dict) else {}
        guild_buffs = guild_buffs_res if isinstance(guild_buffs_res, dict) else {}
        shodnyak_data = shodnyak_res if isinstance(shodnyak_res, dict) else {}

        raw_buffs = resp.get("data", {}).get("buffs") or resp.get("buffs") or []
        if isinstance(raw_buffs, dict):
            raw_buffs = list(raw_buffs.values())

        active_by_cat = boot.get("activeBuffsByCategory") or {}
        active_ids = set()
        for cat, items in active_by_cat.items():
            if isinstance(items, list):
                for it in items:
                    bid = it.get("id") if isinstance(it, dict) else str(it)
                    if bid:
                        active_ids.add(str(bid))

        buff_cooldowns = boot.get("buffCooldowns") or []
        cd_map = {}
        if isinstance(buff_cooldowns, list):
            for cd in buff_cooldowns:
                if isinstance(cd, dict):
                    cid = cd.get("id") or cd.get("buffId")
                    if cid:
                        cd_map[str(cid)] = cd.get("endsAt") or cd.get("cooldownEndsAt")

        normalized = []
        for buff in raw_buffs:
            if not isinstance(buff, dict):
                continue
            b_id = str(buff.get("id", ""))
            icon_path = buff.get("icon") or ""
            icon_url = _proxy_asset_url(icon_path) if icon_path else ""
            category = buff.get("category") or buff.get("type") or "temporary"
            title = buff.get("titleRu") or buff.get("title") or buff.get("name") or b_id
            desc = buff.get("descriptionRu") or buff.get("description") or ""

            normalized.append({
                "id": b_id,
                "title": title,
                "titleRu": title,
                "description": desc,
                "descriptionRu": desc,
                "category": category,
                "icon": icon_path,
                "iconUrl": icon_url,
                "priceTp": int(buff.get("priceTp", 0)),
                "cooldownSeconds": int(buff.get("cooldownSeconds", 0)),
                "durationHits": int(buff.get("durationHits", 0)),
                "isPurchasable": bool(buff.get("isPurchasable", False)),
                "stats": buff.get("buffs", []),
                "isActive": b_id in active_ids,
                "cooldownEndsAt": cd_map.get(b_id),
            })

        # Живой статус гильдии и привилегий
        in_guild = bool(guild_status.get("inGuild") or guild_status.get("guild"))
        guild_info = guild_status.get("guild") or {}
        guild_level = int(guild_info.get("level", 0))
        my_rank = guild_status.get("myRank") or {}
        my_rank_id = int(my_rank.get("rankId", 99))
        my_privileges = guild_status.get("myPrivileges") or []
        has_guild_privilege = (my_rank_id <= 3) or ("activateGuildBuff" in my_privileges)

        # Статусы баффов гильдии из /api/guild/buff
        gb_items = guild_buffs.get("buffs") or guild_buffs.get("data", {}).get("buffs") or []
        gb_status_map = {}
        if isinstance(gb_items, list):
            for gb in gb_items:
                if isinstance(gb, dict):
                    gid = gb.get("id") or gb.get("buffId")
                    if gid:
                        gb_status_map[str(gid)] = gb
        elif isinstance(gb_items, dict):
            gb_status_map = {str(k): v for k, v in gb_items.items() if isinstance(v, dict)}

        # Хелпер расчета состояния усиления бригады (Навались, Смотри не разбей)
        def _calc_guild_buff_state(buff_id: str, req_level: int, title: str, desc: str, icon: str) -> Dict[str, Any]:
            live_gb = gb_status_map.get(buff_id, {})
            is_act = bool(live_gb.get("isActive") or buff_id in active_ids)
            cd_val = live_gb.get("cooldownEndsAt") or cd_map.get(buff_id)

            if not in_guild:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"Нужен уровень бригады {req_level}",
                    "requiredGuildLevel": req_level,
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": True,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": "Вы не состоите в бригаде",
                    "cooldownEndsAt": None,
                }
            if guild_level < req_level:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"Нужен уровень бригады {req_level}",
                    "requiredGuildLevel": req_level,
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": True,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": f"Нужен уровень бригады {req_level} (сейчас {guild_level})",
                    "cooldownEndsAt": None,
                }
            if is_act:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"Нужен уровень бригады {req_level}",
                    "requiredGuildLevel": req_level,
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": False,
                    "isActive": True,
                    "canActivate": False,
                    "unlockReason": "Усиление уже активно",
                    "cooldownEndsAt": cd_val,
                }
            if cd_val:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"Нужен уровень бригады {req_level}",
                    "requiredGuildLevel": req_level,
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": False,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": "На перезарядке (откат)",
                    "cooldownEndsAt": cd_val,
                }
            if not has_guild_privilege:
                rank_name = my_rank.get("name") or f"ранг {my_rank_id}"
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"Нужен уровень бригады {req_level}",
                    "requiredGuildLevel": req_level,
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": False,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": f"Требуются полномочия в бригаде (ваш ранг: {rank_name})",
                    "cooldownEndsAt": None,
                }
            return {
                "id": buff_id,
                "title": title,
                "description": desc,
                "requirement": f"Нужен уровень бригады {req_level}",
                "requiredGuildLevel": req_level,
                "icon": icon,
                "iconUrl": icon,
                "isLocked": False,
                "isActive": False,
                "canActivate": True,
                "unlockReason": None,
                "cooldownEndsAt": None,
            }

        # Живой сходняк из /api/shodnyak/buffs
        shodnyak_buffs_list = shodnyak_data.get("buffs") or shodnyak_data.get("data", {}).get("buffs") or []
        shod_map = {}
        if isinstance(shodnyak_buffs_list, list):
            for sb in shodnyak_buffs_list:
                if isinstance(sb, dict):
                    sid = sb.get("id") or sb.get("buffId")
                    if sid:
                        shod_map[str(sid)] = sb
        elif isinstance(shodnyak_buffs_list, dict):
            shod_map = {str(k): v for k, v in shodnyak_buffs_list.items() if isinstance(v, dict)}

        # Ранг / место сходняка бригады
        shodnyak_rank = shodnyak_data.get("place") or shodnyak_data.get("rank") or guild_info.get("shodnyakRank")

        def _calc_shodnyak_buff_state(buff_id: str, place_req: str, min_p: int, max_p: int, title: str, desc: str, icon: str) -> Dict[str, Any]:
            live_sb = shod_map.get(buff_id, {})
            is_act = bool(live_sb.get("isActive") or buff_id in active_ids)
            cd_val = live_sb.get("cooldownEndsAt") or cd_map.get(buff_id)
            is_unlocked = bool(live_sb.get("unlocked") or live_sb.get("available") or (shodnyak_rank and min_p <= int(shodnyak_rank) <= max_p))

            if not in_guild:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"{place_req} место в Сходняке",
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": True,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": "Вы не состоите в бригаде",
                    "cooldownEndsAt": None,
                }
            if not is_unlocked and not is_act:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"{place_req} место в Сходняке",
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": True,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": f"Закрыто (требуется {place_req} место в Сходняке)",
                    "cooldownEndsAt": None,
                }
            if is_act:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"{place_req} место в Сходняке",
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": False,
                    "isActive": True,
                    "canActivate": False,
                    "unlockReason": "Усиление активно",
                    "cooldownEndsAt": cd_val,
                }
            if cd_val:
                return {
                    "id": buff_id,
                    "title": title,
                    "description": desc,
                    "requirement": f"{place_req} место в Сходняке",
                    "icon": icon,
                    "iconUrl": icon,
                    "isLocked": False,
                    "isActive": False,
                    "canActivate": False,
                    "unlockReason": "На перезарядке (откат)",
                    "cooldownEndsAt": cd_val,
                }
            return {
                "id": buff_id,
                "title": title,
                "description": desc,
                "requirement": f"{place_req} место в Сходняке",
                "icon": icon,
                "iconUrl": icon,
                "isLocked": False,
                "isActive": False,
                "canActivate": True,
                "unlockReason": None,
                "cooldownEndsAt": None,
            }

        brigade_buffs = [
            {
                "category": "guild",
                "categoryTitle": "Усиление бригады",
                "description": "Бонусы по уровню вашей бригады",
                "items": [
                    _calc_guild_buff_state(
                        "guild_buff_poison", 50, "Навались", "Увеличивает урон ядом на 10%",
                        "/static/assets/icons/guild_buff_poison.png"
                    ),
                    _calc_guild_buff_state(
                        "guild_buff_gunshot", 40, "Смотри не разбей", "Увеличивает урон самопалом на 10%",
                        "/static/assets/icons/guild_buff_gunshot.png"
                    ),
                ],
            },
            {
                "category": "shodnyak_1",
                "categoryTitle": "Сходняк 1",
                "description": "Награда за 1-е место в Сходняке",
                "items": [
                    _calc_shodnyak_buff_state(
                        "shodnyak_zloba", "1", 1, 1, "Злоба (Яд)", "+2500 к урону ядом",
                        "/static/assets/icons/shodnyak_zloba.webp"
                    ),
                    _calc_shodnyak_buff_state(
                        "shodnyak_pepel", "1", 1, 1, "Пепел (Самопал)", "+2500 к урону самопалом",
                        "/static/assets/icons/shodnyak_pepel.webp"
                    ),
                ],
            },
            {
                "category": "shodnyak_2",
                "categoryTitle": "Сходняк 2",
                "description": "Награда за 2-е место в Сходняке",
                "items": [
                    _calc_shodnyak_buff_state(
                        "shodnyak_zhalo", "2", 2, 2, "Жало (Яд)", "+1500 к урону ядом",
                        "/static/assets/icons/shodnyak_zhalo.webp"
                    ),
                    _calc_shodnyak_buff_state(
                        "shodnyak_vzryvchatka", "2", 2, 2, "Взрывчатка (Самопал)", "+1500 к урону самопалом",
                        "/static/assets/icons/shodnyak_vzryvchatka.webp"
                    ),
                ],
            },
            {
                "category": "shodnyak_3",
                "categoryTitle": "Сходняк 3",
                "description": "Награда за 3-е место в Сходняке",
                "items": [
                    _calc_shodnyak_buff_state(
                        "shodnyak_zhestokiy", "3", 3, 3, "Жестокий (Яд)", "+1000 к урону ядом",
                        "/static/assets/icons/shodnyak_zhestokiy.webp"
                    ),
                    _calc_shodnyak_buff_state(
                        "shodnyak_shrapnel", "3", 3, 3, "Шрапнель (Самопал)", "+1000 к урону самопалом",
                        "/static/assets/icons/shodnyak_shrapnel.webp"
                    ),
                ],
            },
            {
                "category": "shodnyak_4_10",
                "categoryTitle": "Сходняк 4-10",
                "description": "Награда за 4-10 места в Сходняке",
                "items": [
                    _calc_shodnyak_buff_state(
                        "shodnyak_otrava", "4-10", 4, 10, "Отрава (Яд)", "+500 к урону ядом",
                        "/static/assets/icons/shodnyak_otrava.webp"
                    ),
                ],
            },
            {
                "category": "shodnyak_11_20",
                "categoryTitle": "Сходняк 11-20",
                "description": "Награда за 11-20 места в Сходняке",
                "items": [
                    _calc_shodnyak_buff_state(
                        "shodnyak_kislota", "11-20", 11, 20, "Кислота (Яд)", "+250 к урону ядом",
                        "/static/assets/icons/shodnyak_kislota.webp"
                    ),
                ],
            },
        ]

        return {
            "success": True,
            "ordinary": normalized,
            "brigade": brigade_buffs,
            "buffs": normalized,
        }
    except Exception as e:
        logger.error("Error fetching boss buffs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/boss/buffs/activate")
async def action_activate_boss_buff(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Активация обычного или бригадного усиления."""
    buff_id = payload.get("buffId") or payload.get("buff_id") or payload.get("id")
    if not buff_id:
        raise HTTPException(status_code=400, detail="buffId обязателен")
    buff_id_str = str(buff_id)

    boss_api = bot_context.boss_api
    if not boss_api:
        raise HTTPException(status_code=503, detail="BossAPI not available")

    engine = bot_context.db_engine
    endpoint = "/api/boss-buffs/activate"
    try:
        if buff_id_str.startswith("guild_buff_"):
            endpoint = "/api/guild/buff/activate"
            guild_id = int(payload.get("guildId", 1))
            res = await boss_api.activate_guild_buff(guild_id, buff_id_str)
        elif buff_id_str.startswith("shodnyak_"):
            endpoint = "/api/shodnyak/buffs/activate"
            res = await boss_api.activate_shodnyak_buff(buff_id_str)
        else:
            res = await boss_api.activate_boss_buff(buff_id_str)

        await _log_action(account_id, "activate_boss_buff", endpoint, 200, True, res)
        if engine:
            parsed = DropParser.parse_other(
                title="Активация усиления",
                subtitle=f"Усиление {buff_id_str} успешно активировано",
                rewards=[],
            )
            await DropParser.save_notification(account_id, parsed, engine)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "activate_boss_buff", endpoint, 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


def _classify_wardrobe_source(desc: str, sdesc: str, sname: str) -> str:
    text = f"{desc} {sdesc} {sname}".lower()
    if "убийство" in text or "босс" in text:
        return "bosses"
    if "комбо" in text:
        return "combo"
    if "слепого кольщика" in text or "кольщик" in text:
        return "kolsik"
    if any(k in text for k in ["покер", "карт", "колес", "фартов", "кост", "чемодан"]):
        return "gambling"
    if "заруб" in text:
        return "zaruby"
    if "лагер" in text:
        return "camps"
    if "баул" in text:
        return "baul"
    if any(k in text for k in ["тюрьм", "ходк", "зон", "централ", "крест", "бутырк"]):
        return "prisons"
    if "мастер" in text:
        return "masters"
    if "достижен" in text:
        return "achievements"
    if "посылк" in text:
        return "parcels"
    if any(k in text for k in ["акци", "событи", "варить", "шкафчик"]):
        return "events"
    return "other"


def _is_blind_kolsik(item: Dict[str, Any]) -> bool:
    desc = (item.get("description") or "").lower()
    sdesc = (item.get("sourceDescription") or "").lower()
    sname = (item.get("setName") or "").lower()
    img = (item.get("imageUrl") or "").lower()
    rew = (item.get("rewardPreviewUrl") or "").lower()
    return (
        "слепого кольщика" in desc
        or "слепого кольщика" in sdesc
        or "tattoos/kolsik" in img
        or "kolsik.png" in rew
        or "слепой кольщик" in sname
        or "tattoos/skull" in img
        or sname == 'комплект "череп"'
    )


SET_TIER_STAT_MAP = {
    "яду": "poison",
    "яда": "poison",
    "самопалу": "gunshot",
    "самопала": "gunshot",
    "финке": "knife",
    "финки": "knife",
    "энергии": "energy",
}

SET_TIER_STAT_PATTERNS = [
    (re.compile(r"яд", re.I), "poison"),
    (re.compile(r"самопал", re.I), "gunshot"),
    (re.compile(r"финк", re.I), "knife"),
    (re.compile(r"энерги", re.I), "energy"),
    (re.compile(r"бицух", re.I), "biceps"),
    (re.compile(r"лимит\s+атаки\s+босс", re.I), "bossAttackLimit"),
]


def parse_set_description(desc: str, has_item_bonuses: bool = False) -> Optional[Dict[str, Any]]:
    """Парсинг пороговых бонусов сета из setDescription (Module 980493 в Тюряге)."""
    if not desc:
        return None
    m1 = re.search(r"бонус\s+за\s+(\d+)\s+[^:\n]*:\s*([^\n]+)", desc, re.I)
    if m1:
        try:
            threshold = int(m1.group(1))
            bonus_str = m1.group(2)
            bonus: Dict[str, int] = {}
            for bm in re.finditer(r"\+(\d+)\s*к\s+([а-яё]+)", bonus_str, re.I):
                stat_word = bm.group(2).lower()
                stat_key = SET_TIER_STAT_MAP.get(stat_word)
                if stat_key:
                    bonus[stat_key] = bonus.get(stat_key, 0) + int(bm.group(1))
            if bonus and threshold > 0:
                return {"threshold": threshold, "bonus": bonus}
        except Exception:
            pass

    if has_item_bonuses:
        return None

    bonus: Dict[str, int] = {}
    threshold = 0
    for m2 in re.finditer(
        r"увеличивает\s+([^\n]+?)\s+на\s+(\d+)[^\n(]*\(эффект\s+за\s+(?:полный\s+комплект\s+из\s+)?(\d+)",
        desc,
        re.I,
    ):
        stat_raw = m2.group(1)
        val = int(m2.group(2))
        th = int(m2.group(3))
        for pat, stat_key in SET_TIER_STAT_PATTERNS:
            if pat.search(stat_raw):
                bonus[stat_key] = bonus.get(stat_key, 0) + val
                threshold = max(threshold, th)
                break
    if threshold > 0 and bonus:
        return {"threshold": threshold, "bonus": bonus}
    return None


def _build_wardrobe_sets(items: List[Dict[str, Any]], owned_ids: set, equipped_zones: Dict[str, Any]) -> List[Dict[str, Any]]:
    sets_map: Dict[str, Dict[str, Any]] = {}
    for itm in items:
        sname = itm.get("setName") or itm.get("name") or "Без сета"
        if sname not in sets_map:
            sets_map[sname] = {
                "name": sname,
                "setName": sname,
                "setDescription": itm.get("setDescription") or "",
                "description": itm.get("description") or itm.get("sourceDescription") or "",
                "sourceCategory": _classify_wardrobe_source(itm.get("description") or "", itm.get("sourceDescription") or "", sname),
                "sourceText": itm.get("description") or itm.get("sourceDescription") or "",
                "isSet": bool(itm.get("isSet", True)),
                "parts": [],
            }

        iid = itm.get("id")
        is_owned = iid in owned_ids
        zone = itm.get("zone") or 1
        zone_info = equipped_zones.get(str(zone)) or equipped_zones.get(zone) or {}
        if isinstance(zone_info, dict):
            eq_id = zone_info.get("tattooId") or zone_info.get("clothingId")
        elif isinstance(zone_info, int):
            eq_id = zone_info
        else:
            eq_id = None
        is_equipped = bool(eq_id and eq_id == iid)

        price = itm.get("price") or 0
        currency = itm.get("currency") or ""
        can_buy = bool(not is_owned and price > 0 and currency)

        z_int = int(zone) if str(zone).isdigit() else 1
        side = "back" if z_int >= 23 else "front"
        back_url = itm.get("imageBackUrl") or itm.get("backImageUrl") or ""

        sets_map[sname]["parts"].append({
            "id": iid,
            "name": itm.get("name") or "",
            "zone": z_int,
            "side": side,
            "hasBack": bool(back_url),
            "imageBackUrl": _proxy_asset_url(back_url) if back_url else "",
            "owned": is_owned,
            "equipped": is_equipped,
            "canBuy": can_buy,
            "price": price,
            "currency": currency,
            "rarity": itm.get("rarity") or "B2",
            "imageUrl": _proxy_asset_url(itm.get("imageUrl") or ""),
            "cardPreviewUrl": _proxy_asset_url(itm.get("cardPreviewUrl") or ""),
            "bonuses": itm.get("combat_stats_bonus") or {},
            "description": itm.get("description") or "",
        })

    set_list = []
    for sname, sdata in sets_map.items():
        parts = sdata["parts"]
        total_p = len(parts)
        owned_p = sum(1 for p in parts if p["owned"])

        col_bonus: Dict[str, int] = {}
        max_bonus: Dict[str, int] = {}
        for p in parts:
            for b_key, b_val in (p["bonuses"] or {}).items():
                norm_key = "energy" if b_key == "maxEnergy" else b_key
                max_bonus[norm_key] = max_bonus.get(norm_key, 0) + int(b_val)
                if p["owned"]:
                    col_bonus[norm_key] = col_bonus.get(norm_key, 0) + int(b_val)

        tier_info = parse_set_description(sdata.get("setDescription") or "", has_item_bonuses=bool(max_bonus))
        sdata["bonusTier"] = tier_info
        if tier_info:
            t_thresh = tier_info["threshold"]
            t_bonus = tier_info["bonus"]
            for b_key, b_val in t_bonus.items():
                norm_key = "energy" if b_key in ("maxEnergy", "maxenergy") else b_key
                max_bonus[norm_key] = max_bonus.get(norm_key, 0) + int(b_val)
                if owned_p >= t_thresh:
                    col_bonus[norm_key] = col_bonus.get(norm_key, 0) + int(b_val)

        sdata["totalParts"] = total_p
        sdata["ownedParts"] = owned_p
        sdata["progress"] = f"{owned_p}/{total_p}"
        sdata["isComplete"] = bool(owned_p == total_p and total_p > 0)
        sdata["collectedBonus"] = col_bonus
        sdata["maxBonus"] = max_bonus
        set_list.append(sdata)

    return set_list


def _calc_wardrobe_summary(sets: List[Dict[str, Any]]) -> Dict[str, Any]:
    collected: Dict[str, int] = {
        "knife": 0, "poison": 0, "gunshot": 0, "energy": 0,
        "biceps": 0, "punchChest": 0, "kickBalls": 0, "pokeEyes": 0, "kneeEar": 0,
    }
    max_b: Dict[str, int] = {
        "knife": 0, "poison": 0, "gunshot": 0, "energy": 0,
        "biceps": 0, "punchChest": 0, "kickBalls": 0, "pokeEyes": 0, "kneeEar": 0,
    }
    special: Dict[str, Dict[str, int]] = {
        "bossAttackLimit": {"collected": 0, "max": 0},
        "comboSaveChance": {"collected": 0, "max": 0},
    }

    for s in sets:
        for k, v in (s.get("collectedBonus") or {}).items():
            if k in collected:
                collected[k] += int(v)
            elif k in special:
                special[k]["collected"] += int(v)
        for k, v in (s.get("maxBonus") or {}).items():
            if k in max_b:
                max_b[k] += int(v)
            elif k in special:
                special[k]["max"] += int(v)

    if special["bossAttackLimit"]["max"] == 0:
        special["bossAttackLimit"]["max"] = 1
    if special["comboSaveChance"]["max"] == 0:
        special["comboSaveChance"]["max"] = 5

    missing: Dict[str, int] = {}
    for k, v in max_b.items():
        missing[k] = max(0, v - collected.get(k, 0))

    return {
        "collected": collected,
        "max": max_b,
        "missing": missing,
        "special": special,
    }


@api_router.get("/wardrobe/overview")
async def get_wardrobe_overview() -> Dict[str, Any]:
    """
    Агрегированный обзор гардероба «Тату и Шмот»:
    - сеты татуировок и одежды
    - разделение на обычные сеты и 'Слепого кольщика' без дублирования ID
    - сводная таблица бонусов 'Собрано' / 'Не собрано' / 'Особое'
    - камеры (Хаты) и слои персонажа для визуальной Примерочной
    Кэшируется через _SingleFlightCache на 30 секунд.
    """
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    async def _compute_wardrobe_overview() -> Dict[str, Any]:
        try:
            init_res, inv_res, cam_res, tattoos_cat, clothing_cat = await asyncio.gather(
                player_api.init_player(),
                player_api.get_wardrobe_inventory(),
                player_api.get_cameras(),
                player_api.get_tattoos_catalog(),
                player_api.get_clothing_catalog(),
                return_exceptions=True,
            )

            init_data = init_res if isinstance(init_res, dict) else {}
            if not init_data:
                cached_p = _last_live_player_data.get(1)
                if isinstance(cached_p, dict) and cached_p:
                    init_data = cached_p
                elif bot_context.db_engine:
                    try:
                        async with get_session(bot_context.db_engine) as _s:
                            snap_stmt = (
                                select(PlayerSnapshot)
                                .where(PlayerSnapshot.account_id == 1)
                                .order_by(PlayerSnapshot.id.desc())
                                .limit(1)
                            )
                            snap_row = (await _s.execute(snap_stmt)).scalar_one_or_none()
                            if snap_row and isinstance(snap_row.raw_payload, dict) and snap_row.raw_payload:
                                init_data = snap_row.raw_payload
                    except Exception:
                        pass
            else:
                _last_live_player_data[1] = init_data

            inv_data = inv_res if isinstance(inv_res, dict) else {}
            cam_data = cam_res if isinstance(cam_res, dict) else {}
            tattoos_raw = tattoos_cat if isinstance(tattoos_cat, list) else []
            clothing_raw = clothing_cat if isinstance(clothing_cat, list) else []

            # Fallback to local cache file if catalog calls returned empty
            if not tattoos_raw or not clothing_raw:
                cache_file = Path(__file__).resolve().parent.parent / "storage" / "tattoo_clothing_cache.json"
                if cache_file.exists():
                    try:
                        import json as _json
                        with open(cache_file, "r", encoding="utf-8") as f:
                            cdata = _json.load(f)
                            if not tattoos_raw:
                                tattoos_raw = cdata.get("tattoos", [])
                            if not clothing_raw:
                                clothing_raw = cdata.get("clothing", [])
                            if not cam_data or not cam_data.get("cameras"):
                                cam_data = {"cameras": cdata.get("cameras", [])}
                    except Exception as ce:
                        logger.warning("Fallback load of tattoo_clothing_cache.json failed: %s", ce)

            owned_tattoos = set(inv_data.get("ownedTattoos") or [])
            owned_clothing = set(inv_data.get("ownedClothing") or [])
            owned_cameras = set(inv_data.get("ownedCameras") or [])

            tattoo_zones = init_data.get("tattooZones") or {}
            clothing_zones = init_data.get("clothingZones") or {}
            clothing_front_ids = init_data.get("clothingFrontIds") or {}
            face = init_data.get("face") or {}
            beard_phase = init_data.get("beardPhase") or 0
            room_camera_url = init_data.get("roomCameraUrl") or ""

            # Строгое разделение без пересечений
            reg_tattoos = [t for t in tattoos_raw if not _is_blind_kolsik(t)]
            blind_tattoos = [t for t in tattoos_raw if _is_blind_kolsik(t)]

            reg_clothing = [c for c in clothing_raw if not _is_blind_kolsik(c)]
            blind_clothing = [c for c in clothing_raw if _is_blind_kolsik(c)]

            reg_tattoo_sets = _build_wardrobe_sets(reg_tattoos, owned_tattoos, tattoo_zones)
            blind_tattoo_sets = _build_wardrobe_sets(blind_tattoos, owned_tattoos, tattoo_zones)

            reg_clothing_sets = _build_wardrobe_sets(reg_clothing, owned_clothing, clothing_zones)
            blind_clothing_sets = _build_wardrobe_sets(blind_clothing, owned_clothing, clothing_zones)

            summ_reg_tattoos = _calc_wardrobe_summary(reg_tattoo_sets)
            summ_reg_clothing = _calc_wardrobe_summary(reg_clothing_sets)
            summ_blind_tattoos = _calc_wardrobe_summary(blind_tattoo_sets)
            summ_blind_clothing = _calc_wardrobe_summary(blind_clothing_sets)

            raw_cameras = cam_data.get("cameras") or []
            cameras_list = []
            for cam in raw_cameras:
                cid = cam.get("id")
                is_owned = bool(cid in owned_cameras or cam.get("owned", False) or cid == 1)
                raw_c_img = cam.get("imageUrl") or ""
                img_url = _proxy_asset_url(raw_c_img)
                m_folder = re.search(r"RoomCameraUrl/([^/]+)/", str(raw_c_img))
                folder_id = m_folder.group(1) if m_folder else str(cid)
                is_equipped = bool(raw_c_img and raw_c_img == room_camera_url) or (not room_camera_url and cid == 1)
                cameras_list.append({
                    "id": cid,
                    "folderId": folder_id,
                    "name": cam.get("name") or f"Камера #{cid}",
                    "owned": is_owned,
                    "equipped": is_equipped,
                    "price": cam.get("price") or 0,
                    "currency": cam.get("currency") or "",
                    "imageUrl": img_url,
                    "rawImageUrl": raw_c_img,
                    "currencyIconUrl": cam.get("currencyIconUrl") or "",
                })

            character_layers = _build_character_layers(init_data, cameras_list)

            return {
                "success": True,
                "sets": {
                    "regular": {
                        "tattoos": reg_tattoo_sets,
                        "clothing": reg_clothing_sets,
                    },
                    "blind_kolsik": {
                        "tattoos": blind_tattoo_sets,
                        "clothing": blind_clothing_sets,
                    },
                },
                "summaryStats": {
                    "sets_tattoos": summ_reg_tattoos,
                    "sets_clothing": summ_reg_clothing,
                    "blind_tattoos": summ_blind_tattoos,
                    "blind_clothing": summ_blind_clothing,
                },
                "cameras": cameras_list,
                "ownedCamerasCount": sum(1 for c in cameras_list if c["owned"]),
                "totalCamerasCount": len(cameras_list),
                "characterLayers": character_layers,
            }
        except Exception as e:
            logger.error("Error building wardrobe overview: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    return await _flight_cache.get_or_set("wardrobe_overview", 30.0, _compute_wardrobe_overview)


@api_router.post("/actions/wardrobe/equip")
async def action_wardrobe_equip(
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Надевание / снятие отдельного предмета, сета или выбор хаты."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    kind = payload.get("kind")
    action = payload.get("action", "equip")
    item_id = payload.get("id")

    if not kind:
        raise HTTPException(status_code=400, detail="kind обязателен ('tattoo', 'clothing', 'tattoo_set', 'clothing_set', 'camera')")

    try:
        if kind == "tattoo":
            zone = int(payload.get("zone", 1))
            image_url = payload.get("imageUrl", "")
            if action == "unequip":
                res = await player_api.unequip_tattoo(zone)
            else:
                res = await player_api.equip_tattoo(zone, int(item_id or 0), image_url)
        elif kind == "tattoo_set":
            zones_map = payload.get("zonesMap", {})
            res = await player_api.equip_tattoo_set(zones_map)
        elif kind == "clothing":
            zone = int(payload.get("zone", 1))
            image_url = payload.get("imageUrl", "")
            if action == "unequip":
                res = await player_api.unequip_clothing(zone)
            else:
                res = await player_api.equip_clothing(zone, int(item_id or 0), image_url)
        elif kind == "clothing_set":
            zones_map = payload.get("zonesMap", {})
            res = await player_api.equip_clothing_set(zones_map)
        elif kind == "camera":
            res = await player_api.select_camera(int(item_id))
        else:
            raise HTTPException(status_code=400, detail=f"Неизвестный kind: {kind}")

        await _log_action(account_id, f"wardrobe_{action}_{kind}", f"/api/{kind}/{action}", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, f"wardrobe_{action}_{kind}", f"/api/{kind}/{action}", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/wardrobe/buy")
async def action_wardrobe_buy(
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Покупка разблокированного предмета или хаты."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    kind = payload.get("kind")
    item_id = payload.get("id")
    if not kind or item_id is None:
        raise HTTPException(status_code=400, detail="kind и id обязательны")

    try:
        if kind == "tattoo":
            res = await player_api.buy_tattoo(int(item_id))
        elif kind == "clothing":
            res = await player_api.buy_clothing(int(item_id))
        elif kind == "camera":
            res = await player_api.buy_camera(int(item_id))
        else:
            raise HTTPException(status_code=400, detail=f"Неизвестный kind для покупки: {kind}")

        await _log_action(account_id, f"wardrobe_buy_{kind}", f"/api/{kind}/buy", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, f"wardrobe_buy_{kind}", f"/api/{kind}/buy", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/talents")
async def get_talents() -> Dict[str, Any]:
    """Получение состояния дерева талантов."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    try:
        res = await player_api.get_talents_status()
        state = res.get("state") or {}
        raw_config = res.get("config") or []
        spent = int(state.get("spentPoints") or 0)
        unspent = int(state.get("unspentPoints") or 0)
        total_points = spent + unspent
        current_damage = int(state.get("currentDamage") or 0)
        required_damage = int(res.get("requiredDamage") or state.get("requiredDamage") or 0)
        talent_levels = state.get("talentLevels") or {}
        biceps = int(res.get("biceps") or 0)

        talents_list = []
        if isinstance(raw_config, list):
            for t_cfg in raw_config:
                if not isinstance(t_cfg, dict):
                    continue
                tid = int(t_cfg.get("id", 0))
                cur_lvl = int(talent_levels.get(str(tid), talent_levels.get(tid, t_cfg.get("currentLevel", 0))))
                talents_list.append({
                    "id": tid,
                    "name": t_cfg.get("name") or f"Талант {tid}",
                    "description": t_cfg.get("description") or "",
                    "currentLevel": cur_lvl,
                    "maxLevel": int(t_cfg.get("maxLevel") or t_cfg.get("levels") or 5),
                    "icon": t_cfg.get("icon") or "",
                    "cost": t_cfg.get("cost") or 1,
                })
        elif isinstance(raw_config, dict):
            for t_id_str, t_cfg in raw_config.items():
                try:
                    tid = int(t_id_str)
                except ValueError:
                    continue
                cur_lvl = int(talent_levels.get(t_id_str, talent_levels.get(tid, 0)))
                talents_list.append({
                    "id": tid,
                    "name": t_cfg.get("name") or f"Талант {tid}",
                    "description": t_cfg.get("description") or "",
                    "currentLevel": cur_lvl,
                    "maxLevel": int(t_cfg.get("maxLevel") or t_cfg.get("levels") or 5),
                    "icon": t_cfg.get("icon") or "",
                    "cost": t_cfg.get("cost") or 1,
                })

        talents_list.sort(key=lambda x: x["id"])

        return {
            "success": True,
            "state": {
                "spentPoints": spent,
                "unspentPoints": unspent,
                "totalPoints": total_points,
                "currentDamage": current_damage,
                "requiredDamage": required_damage,
                "biceps": biceps,
                "talentLevels": talent_levels,
            },
            "talents": talents_list,
            "raw": res,
        }
    except Exception as e:
        logger.error("Error fetching talents: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/talents/upgrade")
async def action_upgrade_talent(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Прокачка таланта."""
    talent_id = payload.get("talentId")
    if not talent_id:
        raise HTTPException(status_code=400, detail="talentId обязателен")

    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    try:
        res = await player_api.upgrade_talent(int(talent_id))
        await _log_action(account_id, "upgrade_talent", "/api/talent/upgrade", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "upgrade_talent", "/api/talent/upgrade", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/collections")
async def get_collections(user_id: Optional[int] = Query(None)) -> Dict[str, Any]:
    """Получение коллекций игрока (справочник, прогресс и нычки)."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    uid = user_id or 0
    try:
        res = await player_api.get_collections(uid)
        raw_collections = res.get("collections") or []
        player_progress = res.get("playerProgress") or {}
        progress_data = player_progress.get("data") or {}

        stashes = []
        stash_items = []
        try:
            init_data = await player_api.init_player()
            stashes = init_data.get("stashes") or []
        except Exception:
            pass

        try:
            sg = await player_api.get_stashgear_all()
            if isinstance(sg, dict):
                stash_items = (sg.get("camera") or []) + (sg.get("baryga") or [])
        except Exception:
            pass

        parsed_prisons = []
        for entry in raw_collections:
            # Двухуровневая структура: внешний элемент - тюрьма со списком collections: [...]
            if isinstance(entry, dict) and "collections" in entry and isinstance(entry["collections"], list):
                p_id = entry.get("prisonid") or entry.get("prisonId") or 0
                p_name = entry.get("prison") or entry.get("name") or f"Тюрьма #{p_id}"
                prison_progress = progress_data.get(str(p_id)) or progress_data.get(p_id) or {}
                if not isinstance(prison_progress, dict):
                    prison_progress = {}

                for col in entry["collections"]:
                    c_id = col.get("id") or col.get("collectionid") or col.get("collectionId") or 0
                    col_name = col.get("name") or f"Коллекция #{c_id}"
                    col_items = col.get("items") or []
                    col_progress = prison_progress.get(str(c_id)) or prison_progress.get(c_id) or {}
                    if not isinstance(col_progress, dict):
                        col_progress = {}

                    col_items_map = col_progress.get("items") if isinstance(col_progress.get("items"), dict) else col_progress

                    collected_items = 0
                    total_items = len(col_items) if col_items else 7
                    items_detail = []
                    all_ge_1 = True

                    for itm in col_items:
                        itm_id = itm.get("id") or itm.get("itemId")
                        cnt = int(col_items_map.get(str(itm_id), col_items_map.get(itm_id, 0)))
                        if cnt > 0:
                            collected_items += 1
                        else:
                            all_ge_1 = False

                        raw_img = itm.get("image") or itm.get("imageUrl") or itm.get("icon") or f"assets/PrisonV3/collections/{p_id}/{c_id}/{itm_id}.webp"
                        img_proxied = _proxy_asset_url(raw_img)

                        items_detail.append({
                            "id": itm_id,
                            "name": itm.get("name") or f"Предмет #{itm_id}",
                            "count": cnt,
                            "icon": img_proxied,
                            "imageUrl": img_proxied,
                            "owned": cnt > 0,
                        })

                    can_exchange = bool(total_items > 0 and collected_items >= total_items and all_ge_1)

                    parsed_prisons.append({
                        "prisonId": p_id,
                        "prisonName": p_name,
                        "collectionId": c_id,
                        "name": col_name,
                        "reward": col.get("rewards") or col.get("reward") or {},
                        "collected": collected_items,
                        "total": total_items,
                        "canExchange": can_exchange,
                        "items": items_detail,
                    })
            else:
                # Одноуровневая структура (для совместимости с плоскими моками)
                col = entry
                p_id = col.get("prisonid") or col.get("prisonId") or 0
                c_id = col.get("id") or col.get("collectionid") or col.get("collectionId") or 0
                col_name = col.get("name") or f"Коллекция #{c_id}"
                col_items = col.get("items") or []

                col_progress = progress_data.get(str(p_id), {}).get(str(c_id), {}) if isinstance(progress_data.get(str(p_id)), dict) else progress_data
                if not isinstance(col_progress, dict):
                    col_progress = {}

                col_items_map = col_progress.get("items") if isinstance(col_progress.get("items"), dict) else col_progress

                collected_items = 0
                total_items = len(col_items) if col_items else 7
                items_detail = []
                all_ge_1 = True

                for itm in col_items:
                    itm_id = itm.get("id") or itm.get("itemId")
                    cnt = int(col_items_map.get(str(itm_id), col_items_map.get(itm_id, 0)))
                    if cnt > 0:
                        collected_items += 1
                    else:
                        all_ge_1 = False

                    raw_img = itm.get("image") or itm.get("imageUrl") or itm.get("icon") or f"assets/PrisonV3/collections/{p_id}/{c_id}/{itm_id}.webp"
                    img_proxied = _proxy_asset_url(raw_img)

                    items_detail.append({
                        "id": itm_id,
                        "name": itm.get("name") or f"Предмет #{itm_id}",
                        "count": cnt,
                        "icon": img_proxied,
                        "imageUrl": img_proxied,
                        "owned": cnt > 0,
                    })

                can_exchange = bool(total_items > 0 and collected_items >= total_items and all_ge_1)

                parsed_prisons.append({
                    "prisonId": p_id,
                    "prisonName": f"Тюрьма #{p_id}",
                    "collectionId": c_id,
                    "name": col_name,
                    "reward": col.get("rewards") or col.get("reward") or {},
                    "collected": collected_items,
                    "total": total_items,
                    "canExchange": can_exchange,
                    "items": items_detail,
                })

        # Ранжирование: коллекции, доступные для обмена прямо сейчас (canExchange == True), всегда первыми
        parsed_prisons.sort(
            key=lambda c: (
                0 if c.get("canExchange") else 1,
                -(c.get("collected", 0) / max(1, c.get("total", 1))),
                c.get("prisonId", 0),
                c.get("collectionId", 0),
            )
        )

        return {
            "success": True,
            "collections": parsed_prisons,
            "stashes": stashes,
            "stashItems": stash_items,
            "raw": res,
        }
    except Exception as e:
        logger.error("Error fetching collections: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/live/collections")
async def get_live_collections(
    user_id: Optional[int] = Query(None),
    account_id: int = 1,
    force: bool = Query(False),
) -> Dict[str, Any]:
    """Алиас для получения коллекций игрока (с приоритетом готовых к обмену)."""
    hub = _get_hub()
    tag = _hub_source_tag()
    if user_id is None and not force:
        warm = hub.get_slice(account_id, "collections", max_age_seconds=180.0, source_tag=tag)
        if warm is not None:
            return warm.data
    res = await get_collections(user_id=user_id)
    if user_id is None and isinstance(res, dict):
        hub.update_slice(account_id, "collections", res, source_tag=tag)
    return res


@api_router.post("/daily/toilet-paper")
async def action_claim_toilet_paper(account_id: int = 1) -> Dict[str, Any]:
    """Ручной сбор бесплатной туалетной бумаги."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    try:
        from workers.routine_worker import get_toilet_paper_reset_info
        res = await player_api.claim_toilet_paper()
        _flight_cache.invalidate(f"profile:{account_id}")
        can_claim_after = bool(res.get("canClaimToiletPaper", False)) if isinstance(res, dict) else False
        return {
            "success": True,
            "result": res,
            "toiletPaper": get_toilet_paper_reset_info(can_claim_after),
        }
    except Exception as e:
        logger.error("Ошибка сбора туалетной бумаги: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/daily/podogrev-send")
async def action_send_podogrev(account_id: int = 1) -> Dict[str, Any]:
    """Ручная отправка бесплатных суточных подогревов друзьям."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    try:
        res = await player_api.send_all_podogrev()
        return {"success": True, "result": res}
    except Exception as e:
        logger.error("Ошибка отправки подогревов: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/daily/katala-play")
async def action_play_katala(account_id: int = 1) -> Dict[str, Any]:
    """Ручной запуск бесплатной суточной игры у Каталы."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    try:
        from client.api.katala import KatalaAPI, play_free_daily_game
        game_client = getattr(player_api, "client", None) or getattr(player_api, "_client", None)
        if not game_client and hasattr(bot_context, "game_client"):
            game_client = bot_context.game_client
        katala_api = KatalaAPI(client=game_client)
        res = await play_free_daily_game(katala_api=katala_api, player_api=player_api, account_id=account_id)
        return {"success": True, "result": res}
    except Exception as e:
        logger.error("Ошибка игры у Каталы: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/daily/monthly-claim")
async def action_claim_monthly(account_id: int = 1) -> Dict[str, Any]:
    """Ручной запуск проверки и сбора наград за выполненные тиры месячных делюг."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    try:
        state = await player_api.get_monthly_state(track_open=True)
        tiers_data = state.get("tiers") or state.get("items") or []
        claimable = state.get("claimableTiers") or []
        if not claimable and isinstance(tiers_data, list):
            for t in tiers_data:
                if isinstance(t, dict) and t.get("completed") and not t.get("claimed"):
                    t_id = t.get("tier") or t.get("id") or t.get("tierId")
                    if t_id is not None:
                        claimable.append(int(t_id))

        claimed = []
        for t_id in claimable:
            try:
                c_res = await player_api.claim_monthly_tier(t_id)
                claimed.append({"tier": t_id, "result": c_res})
            except Exception as e:
                logger.warning("Ошибка сбора тира %s месячных делюг: %s", t_id, e)

        return {"success": True, "claimableCount": len(claimable), "claimed": claimed}
    except Exception as e:
        logger.error("Ошибка сбора месячных делюг: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


_SPINE_ROOM_IDS = set(range(27, 38))
_SPINE_ALT_ROOT_IDS = {30, 31, 32, 33, 34, 35, 37}
_BUNDLE_ROOM_IDS = {39, 40, 41, 42, 44, 45, 54}
_EFFECT_ROOM_IDS = (
    set(range(1, 11))
    | {14, 15}
    | set(range(18, 27))
    | {42, 43, 46, 47, 48}
)


@api_router.get("/wardrobe/room-render/{room_id}")
async def get_room_render_info(room_id: int) -> Dict[str, Any]:
    """Дескриптор подлинного рендера комнаты (Spine 4.2/4.3, room.bundle MovieClip, effect_config, static)."""
    preview_url = _proxy_asset_url(f"assets/PrisonV3/RoomCameraUrl/{room_id}/1.png")
    is_spine = room_id in _SPINE_ROOM_IDS
    is_bundle = room_id in _BUNDLE_ROOM_IDS
    has_effects = (room_id in _EFFECT_ROOM_IDS) and (not is_spine) and (not is_bundle or room_id == 42)
    is_animated = is_spine or is_bundle or has_effects

    render_mode = "spine" if is_spine else "bundle" if is_bundle else "effects" if has_effects else "static"

    spine_info = None
    if is_spine:
        spine_info = {
            "skeletonUrl": _proxy_asset_url(f"assets/PrisonV3/RoomCameraUrl/{room_id}/skeleton.json"),
            "atlasUrl": _proxy_asset_url(f"assets/PrisonV3/RoomCameraUrl/{room_id}/skeleton.atlas"),
            "textureUrl": _proxy_asset_url(f"assets/PrisonV3/RoomCameraUrl/{room_id}/skeleton.webp"),
            "altRootOffset": room_id in _SPINE_ALT_ROOT_IDS,
        }

    bundle_url = _proxy_asset_url(f"assets/PrisonV3/RoomCameraUrl/{room_id}/room.bundle") if is_bundle else None
    effect_config_url = (
        _proxy_asset_url(f"assets/PrisonV3/RoomCameraUrl/{room_id}/effect_config.json")
        if has_effects
        else None
    )

    return {
        "success": True,
        "roomId": room_id,
        "renderMode": render_mode,
        "previewUrl": preview_url,
        "hasForeground": (room_id == 54),
        "foregroundSource": "room.bundle:gameBirthday_back_front" if room_id == 54 else None,
        "bundleUrl": bundle_url,
        "effectConfigUrl": effect_config_url,
        "isAnimated": is_animated,
        "spine": spine_info,
    }


@api_router.post("/actions/collections/exchange")
async def action_exchange_collection(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Обмен (впаривание) собранной коллекции."""
    collection_id = payload.get("collectionId")
    if not collection_id:
        raise HTTPException(status_code=400, detail="collectionId обязателен")
    prison_id = payload.get("prisonId")
    user_id = payload.get("userId")

    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    try:
        res = await player_api.exchange_collection(int(collection_id), prison_id=prison_id, user_id=user_id)
        await _log_action(account_id, "exchange_collection", "/api/collection/player/vparit", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "exchange_collection", "/api/collection/player/vparit", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/bauls")
async def get_bauls(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """Получение статистики баулов с обогащенными иконками и подписями наград."""
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")
    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "bauls", max_age_seconds=180.0, source_tag=tag)
        if warm is not None:
            return warm.data
    try:
        res = await player_api.get_bauls_stat()
        data = res.get("data") if isinstance(res.get("data"), dict) and "stats" in res.get("data", {}) else res
        stats = data.get("stats") or {}
        lvl = int(stats.get("level") or 0)
        max_lvl = int(stats.get("maxLevel") or stats.get("max") or 30)
        cur_exp = int(stats.get("currentExp") or 0)
        exp_next = int(stats.get("expToNext") or 0)
        is_active = bool(stats.get("active", True))
        raw_pending = stats.get("pendingRewards") or []

        currency_names = {
            "authority": "Авторитет",
            "cigarettes": "Сигареты",
            "sugar": "Сахар",
            "rubles": "Рубли",
            "paper": "Бумага",
            "soap": "Мыло",
            "signet": "Перстни",
            "ore_signet": "Рудные перстни",
            "keys": "Ключи",
            "biceps": "Бицуха",
            "energy": "Энергия",
        }

        weapon_names = {
            "knife": "Финка",
            "poison": "Яд",
            "gunshot": "Самопал",
        }

        enriched_pending = []
        for item in raw_pending:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type", "")).lower()
            i_id = str(item.get("id", ""))
            amt = int(item.get("amount") or 0)

            label = ""
            icon_key = ""
            img_url = None

            if t == "currency":
                label = currency_names.get(i_id, i_id.capitalize())
                icon_key = i_id
            elif t == "weapon":
                label = weapon_names.get(i_id, i_id.capitalize())
                icon_key = i_id
            elif t == "key":
                from client.api.boss import FALLBACK_BOSSES
                boss_map = {str(b["id"]): b["name"] for b in FALLBACK_BOSSES}
                b_title = item.get("bossTitle") or boss_map.get(str(i_id)) or f"Босс #{i_id}"
                label = f"Ключ: {b_title}"
                icon_key = "keys"
            elif t == "stash":
                label = "Нычка"
                icon_key = "stash"
            elif t == "tattoo":
                t_name = item.get("tattooName") or f"Тату #{i_id}"
                label = f"Тату: {t_name}"
                icon_key = "kolsik"
                raw_img = item.get("image")
                if raw_img:
                    img_url = _proxy_asset_url(str(raw_img))
            else:
                label = i_id or t or "Награда"
                icon_key = "boss"

            enriched_pending.append({
                **item,
                "type": t,
                "id": i_id,
                "amount": amt,
                "label": label,
                "iconKey": icon_key,
                "imageUrl": img_url,
            })

        payload = {
            "success": True,
            "stats": {
                "active": is_active,
                "level": lvl,
                "maxLevel": max_lvl,
                "currentExp": cur_exp,
                "expToNext": exp_next,
                "pendingRewards": enriched_pending,
                "isMaxLevel": lvl >= max_lvl,
            },
            "raw": res,
        }
        hub.update_slice(account_id, "bauls", payload, source_tag=tag)
        return payload
    except Exception as e:
        logger.error("Error fetching bauls: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/bauls/buy")
async def action_buy_baul(payload: Dict[str, Any] = Body(...), account_id: int = 1) -> Dict[str, Any]:
    """Покупка / открытие баула."""
    baul_id = payload.get("baulId", 1)
    player_api = bot_context.player_api
    if not player_api:
        raise HTTPException(status_code=503, detail="PlayerAPI not available")

    try:
        res = await player_api.buy_baul(int(baul_id))
        await _log_action(account_id, "buy_baul", "/api/bauls/buy", 200, True, res)
        return {"success": True, "result": res}
    except Exception as e:
        await _log_action(account_id, "buy_baul", "/api/bauls/buy", 500, False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


_raids_api = RaidsAPI()


@api_router.get("/raids")
async def get_raids_overview(account_id: int = 1) -> Dict[str, Any]:
    """Получение списка активных рейдов (включая кэшированные посты из TG-каналов)."""
    res = await _raids_api.get_raids()

    # Загрузка кэшированных рейдов из TG-каналов
    tg_raids = []
    engine = bot_context.db_engine
    if engine:
        try:
            async with get_session(engine) as session:
                from datetime import timedelta
                cutoff = datetime.utcnow() - timedelta(hours=72)
                stmt = (
                    select(CachedRaidPost)
                    .where(
                        CachedRaidPost.account_id == account_id,
                        CachedRaidPost.created_at >= cutoff,
                    )
                    .order_by(CachedRaidPost.created_at.desc())
                    .limit(20)
                )
                posts = (await session.execute(stmt)).scalars().all()
                for p in posts:
                    tg_raids.append({
                        "id": p.id,
                        "channelUsername": p.channel_username,
                        "messageId": p.message_id,
                        "title": p.title,
                        "postDate": p.post_date.isoformat() if p.post_date else None,
                        "rawPreview": p.raw_preview,
                        "participants": p.participants or [],
                        "createdAt": p.created_at.isoformat() if p.created_at else None,
                    })
        except Exception as e:
            logger.warning(f"Ошибка получения CachedRaidPost: {e}")

    res["telegramRaids"] = tg_raids
    res["tgScanCooldownSec"] = _raids_api.rate_guard.can_scan_tg()[1]
    return res


@api_router.get("/news")
async def get_news_list(limit: int = 20) -> Dict[str, Any]:
    """Получение ленты новостей."""
    return await _raids_api.get_news(limit=limit)


@api_router.get("/raids/active-players")
async def get_active_players(
    source: str = Query("all"),
    minDamage: int = Query(0),
    maxDamage: int = Query(0),
    minAuthority: int = Query(0),
    maxAuthority: int = Query(0),
    tier: Optional[str] = Query(None),
    limit: int = Query(50),
    excludeFriends: bool = Query(False),
    account_id: int = 1,
    force: bool = Query(False),
) -> Dict[str, Any]:
    """Получение активных дамагеров из локальной БД и официального топа с детектором активности за 24ч."""
    social_api = bot_context.social_api
    player_api = bot_context.player_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    is_default_radar = (
        source == "all" and minDamage == 0 and maxDamage == 0
        and minAuthority == 0 and maxAuthority == 0 and tier is None
        and not excludeFriends and limit == 50
    )
    hub = _get_hub()
    tag = _hub_source_tag()
    if is_default_radar and not force:
        warm = hub.get_slice(account_id, "radar", max_age_seconds=180.0, source_tag=tag)
        if warm is not None:
            return warm.data

    async def _fetch_my_uid():
        if not player_api:
            return None
        try:
            my_info = await player_api.get_me()
            return my_info.get("id") or my_info.get("userId")
        except Exception:
            return None

    async def _fetch_friends():
        f_ids = set()
        try:
            friends_res = await social_api.get_friends_list()
            raw_friends = friends_res if isinstance(friends_res, list) else friends_res.get("friends", []) if isinstance(friends_res, dict) else []
            for f in raw_friends:
                f_id = f.get("userId") or f.get("id")
                if f_id:
                    f_ids.add(int(f_id))
        except Exception:
            pass
        return f_ids

    async def _fetch_sent_ids():
        s_ids = set()
        if bot_context.db_engine:
            try:
                async with get_session(bot_context.db_engine) as session:
                    result = await session.execute(
                        select(SentFriendRequest.target_user_id).where(SentFriendRequest.account_id == account_id)
                    )
                    for row in result.scalars().all():
                        s_ids.add(int(row))
            except Exception:
                pass
        return s_ids

    my_uid, friend_ids, sent_ids = await asyncio.gather(_fetch_my_uid(), _fetch_friends(), _fetch_sent_ids())

    players = await _raids_api.get_active_players_radar(
        social_api=social_api,
        player_api=player_api,
        db_engine=bot_context.db_engine,
        account_id=account_id,
        current_user_id=my_uid,
        friend_ids=friend_ids,
        sent_user_ids=sent_ids,
        source=source,
        min_damage=minDamage,
        max_damage=maxDamage,
        limit=limit,
        exclude_friends=excludeFriends,
        tier=tier,
        min_authority=minAuthority,
        max_authority=maxAuthority,
    )
    for p in players:
        if p.get("photoUrl"):
            p["photoUrl"] = _proxy_asset_url(str(p["photoUrl"]))

    cfg = await get_or_create_config(account_id, bot_context.db_engine)
    safety = await _raids_api.rate_guard.get_safety_status(
        account_id=account_id,
        daily_limit=getattr(cfg, "friend_outreach_daily_limit", 50),
        db_engine=bot_context.db_engine,
    )

    payload = {
        "success": True,
        "total": len(players),
        "players": players,
        "safety": safety,
    }
    if is_default_radar:
        hub.update_slice(account_id, "radar", payload, source_tag=tag)
    return payload


@api_router.post("/raids/scan-guilds")
async def scan_guilds_endpoint(
    payload: Dict[str, Any] = Body(default_factory=dict),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Ручной запуск сканера активных бригад (до 8 шт.) с серверным кулдауном 300с."""
    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    force = bool(payload.get("force", False))
    max_guilds = int(payload.get("maxGuilds", 8))
    cfg = await get_or_create_config(account_id, bot_context.db_engine) if bot_context.db_engine else None
    tier = str(payload.get("tier") or getattr(cfg, "friends_parser_tier", "accessible") or "accessible")
    min_auth = int(payload.get("minAuthority") if payload.get("minAuthority") is not None else (getattr(cfg, "friends_parser_min_authority", 0) or 0))
    max_auth = int(payload.get("maxAuthority") if payload.get("maxAuthority") is not None else (getattr(cfg, "friends_parser_max_authority", 0) or 0))

    res = await _raids_api.scan_active_guilds(
        social_api=social_api,
        db_engine=bot_context.db_engine,
        account_id=account_id,
        max_guilds=max_guilds,
        delay_range=(1.5, 3.0),
        force=force,
        tier=tier,
        min_authority=min_auth,
        max_authority=max_auth,
    )
    return res


@api_router.post("/raids/scan-channels")
async def scan_channels_endpoint(
    payload: Dict[str, Any] = Body(default_factory=dict),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Read-Only проверка публичных Telegram-каналов на наличие постов с рейдами."""
    channels = payload.get("channels")
    if channels is None:
        cfg = await get_or_create_config(account_id, bot_context.db_engine)
        channels = getattr(cfg, "raid_tg_channels", []) or RaidChannelScanner.DEFAULT_RECOMMENDED_CHANNELS

    force = bool(payload.get("force", False))
    scanner = RaidChannelScanner()
    res = await scanner.scan_channels(
        channels=channels,
        db_engine=bot_context.db_engine,
        raids_api=_raids_api,
        account_id=account_id,
        force=force,
    )
    return res


@api_router.get("/raids/safety-status")
async def get_safety_status_endpoint(account_id: int = 1) -> Dict[str, Any]:
    """Получение статуса лимитов набора друзей и предохранителя Circuit Breaker."""
    cfg = await get_or_create_config(account_id, bot_context.db_engine)
    safety = await _raids_api.rate_guard.get_safety_status(
        account_id=account_id,
        daily_limit=getattr(cfg, "friend_outreach_daily_limit", 50),
        db_engine=bot_context.db_engine,
    )
    return {"success": True, "safety": safety}


@api_router.post("/raids/parse-text")
async def parse_raid_post(
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Парсинг скопированного текста рейда."""
    text_content = payload.get("text", "")
    player_api = bot_context.player_api

    friend_ids = set()
    social_api = bot_context.social_api
    if social_api:
        try:
            friends_res = await social_api.get_friends_list()
            raw_friends = friends_res if isinstance(friends_res, list) else friends_res.get("friends", []) if isinstance(friends_res, dict) else []
            for f in raw_friends:
                f_id = f.get("userId") or f.get("id")
                if f_id:
                    friend_ids.add(int(f_id))
        except Exception:
            pass

    sent_ids = set()
    if bot_context.db_engine:
        async with get_session(bot_context.db_engine) as session:
            result = await session.execute(
                select(SentFriendRequest.target_user_id).where(SentFriendRequest.account_id == account_id)
            )
            for row in result.scalars().all():
                sent_ids.add(int(row))

    my_uid = None
    if player_api:
        try:
            my_info = await player_api.get_me()
            my_uid = my_info.get("id") or my_info.get("userId")
        except Exception:
            pass

    parsed = await _raids_api.parse_raid_text(
        raw_text=text_content,
        player_api=player_api,
        friend_ids=friend_ids,
        sent_user_ids=sent_ids,
        current_user_id=my_uid,
    )
    return {"success": True, "result": parsed}


@api_router.post("/actions/friendship/send")
async def action_send_friend_request(
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Отправка одиночной заявки в друзья с проверкой суточного лимита и Circuit Breaker."""
    to_user_id = payload.get("toUserId")
    if not to_user_id:
        raise HTTPException(status_code=400, detail="toUserId is required")

    nickname = payload.get("nickname")
    source = payload.get("source", "radar")

    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    cfg = await get_or_create_config(account_id, bot_context.db_engine)
    allowed, rem, reason = await _raids_api.rate_guard.can_send(
        account_id=account_id,
        daily_limit=getattr(cfg, "friend_outreach_daily_limit", 50),
        db_engine=bot_context.db_engine,
    )
    if not allowed:
        return {
            "success": False,
            "message": reason,
            "limitReached": True,
            "userId": to_user_id,
        }

    try:
        res = await social_api.send_friend_request(int(to_user_id))
        is_ok = bool(res.get("success", True)) if isinstance(res, dict) else True
        msg = res.get("message", "Заявка отправлена") if isinstance(res, dict) else "Заявка отправлена"

        if "лимит" in msg.lower() or "limit" in msg.lower():
            _raids_api.rate_guard.record_friends_limit_reached()

        async with get_session(bot_context.db_engine) as session:
            sent_rec = SentFriendRequest(
                account_id=account_id,
                target_user_id=int(to_user_id),
                target_nickname=nickname,
                source=source,
                status="sent" if is_ok else "failed",
            )
            session.add(sent_rec)
            await session.commit()

        if is_ok:
            _raids_api.rate_guard.record_success()

        await _log_action(account_id, "send_friend_request", f"/api/friendship/send-request?toUserId={to_user_id}", 200, is_ok, res)
        return {"success": is_ok, "message": msg, "userId": to_user_id}
    except Exception as e:
        err_str = str(e)
        if "429" in err_str:
            _raids_api.rate_guard.record_error(429)
        elif "limit" in err_str.lower() or "лимит" in err_str.lower():
            _raids_api.rate_guard.record_friends_limit_reached()
        else:
            _raids_api.rate_guard.record_error(500)
        await _log_action(account_id, "send_friend_request", f"/api/friendship/send-request?toUserId={to_user_id}", 500, False, {"error": err_str})
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/actions/friendship/send-batch")
async def action_send_friend_batch(
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Безопасная пакетная отправка заявок в друзья с джиттером и защитой от лимитов."""
    user_ids = payload.get("userIds", [])
    req_max_count = int(payload.get("maxCount", 15))
    min_delay = float(payload.get("minDelay", 2.5))
    max_delay = float(payload.get("maxDelay", 4.5))
    source = payload.get("source", "radar")

    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    cfg = await get_or_create_config(account_id, bot_context.db_engine)
    allowed, rem, reason = await _raids_api.rate_guard.can_send(
        account_id=account_id,
        daily_limit=getattr(cfg, "friend_outreach_daily_limit", 50),
        db_engine=bot_context.db_engine,
    )
    if not allowed:
        return {
            "success": False,
            "sentCount": 0,
            "skippedCount": 0,
            "failedCount": 0,
            "limitReached": True,
            "message": reason,
            "results": [],
        }

    max_count = min(req_max_count, rem, 15)

    if not user_ids or max_count <= 0:
        return {"success": True, "sentCount": 0, "skippedCount": 0, "failedCount": 0, "limitReached": False, "results": []}

    sent_ids = set()
    async with get_session(bot_context.db_engine) as session:
        result = await session.execute(
            select(SentFriendRequest.target_user_id).where(SentFriendRequest.account_id == account_id)
        )
        for row in result.scalars().all():
            sent_ids.add(int(row))

    friend_ids = set()
    try:
        friends_res = await social_api.get_friends_list()
        raw_friends = friends_res if isinstance(friends_res, list) else friends_res.get("friends", []) if isinstance(friends_res, dict) else []
        for f in raw_friends:
            f_id = f.get("userId") or f.get("id")
            if f_id:
                friend_ids.add(int(f_id))
    except Exception:
        pass

    results = []
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    limit_reached = False

    for uid in user_ids:
        if sent_count >= max_count:
            break

        uid_int = int(uid)
        if uid_int in friend_ids or uid_int in sent_ids:
            skipped_count += 1
            results.append({"userId": uid_int, "status": "skipped", "reason": "already_friend_or_sent"})
            continue

        if sent_count > 0:
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

        try:
            res = await social_api.send_friend_request(uid_int)
            is_ok = bool(res.get("success", True)) if isinstance(res, dict) else True
            msg = res.get("message", "") if isinstance(res, dict) else ""

            if "лимит" in msg.lower() or "limit" in msg.lower():
                limit_reached = True
                _raids_api.rate_guard.record_friends_limit_reached()

            async with get_session(bot_context.db_engine) as session:
                sent_rec = SentFriendRequest(
                    account_id=account_id,
                    target_user_id=uid_int,
                    source=source,
                    status="sent" if is_ok else "failed",
                )
                session.add(sent_rec)
                await session.commit()
            sent_ids.add(uid_int)

            if is_ok:
                sent_count += 1
                _raids_api.rate_guard.record_success()
                results.append({"userId": uid_int, "status": "sent", "message": msg})
            else:
                failed_count += 1
                results.append({"userId": uid_int, "status": "failed", "message": msg})

            if limit_reached:
                break
        except Exception as e:
            failed_count += 1
            err_str = str(e)
            results.append({"userId": uid_int, "status": "failed", "error": err_str})
            if "429" in err_str:
                limit_reached = True
                _raids_api.rate_guard.record_error(429)
                break
            elif "limit" in err_str.lower() or "лимит" in err_str.lower():
                limit_reached = True
                _raids_api.rate_guard.record_friends_limit_reached()
                break
            else:
                _raids_api.rate_guard.record_error(500)

    await _log_action(account_id, "send_friend_batch", "/api/friendship/send-batch", 200, True, {
        "sentCount": sent_count, "skippedCount": skipped_count, "failedCount": failed_count, "limitReached": limit_reached
    })

    return {
        "success": True,
        "sentCount": sent_count,
        "skippedCount": skipped_count,
        "failedCount": failed_count,
        "limitReached": limit_reached,
        "results": results,
    }


@api_router.get("/friends/summary")
async def get_friends_summary(account_id: int = 1, force: bool = Query(False)) -> Dict[str, Any]:
    """
    Возвращает сводку по друзьям: актуальное число друзей, суточную дельту (за 24ч) и конверсию по источникам.
    Кэшируется в LiveStateHub и _SingleFlightCache.
    """
    engine = bot_context.db_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Database engine not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force:
        warm = hub.get_slice(account_id, "friends", max_age_seconds=120.0, source_tag=tag)
        if warm is not None:
            return warm.data

    async def _compute_summary() -> Dict[str, Any]:
        now = datetime.utcnow()
        target_ts = now - timedelta(hours=24)

        async with get_session(engine) as session:
            # 1. Проверяем наличие снимков в БД
            snaps_count_stmt = select(func.count(FriendsCountSnapshot.id)).where(
                FriendsCountSnapshot.account_id == account_id
            )
            snaps_count = int((await session.execute(snaps_count_stmt)).scalar() or 0)

            # 2. Актуальное число друзей (из FriendStats, если 0 - проверяем самый свежий снимок)
            cur_stmt = select(func.count(FriendStats.id)).where(
                FriendStats.account_id == account_id,
                FriendStats.is_current_friend == True,
            )
            total_friends = int((await session.execute(cur_stmt)).scalar() or 0)
            if total_friends == 0:
                latest_snap_stmt = select(FriendsCountSnapshot.friends_count).where(
                    FriendsCountSnapshot.account_id == account_id
                ).order_by(FriendsCountSnapshot.created_at.desc()).limit(1)
                latest_val = (await session.execute(latest_snap_stmt)).scalar_one_or_none()
                if latest_val is not None:
                    total_friends = int(latest_val)

            # Если снимков еще нет в БД (или total_friends == 0), запрашиваем список друзей у social_api
            if (snaps_count == 0 or total_friends == 0) and bot_context.social_api:
                try:
                    f_ids = await bot_context.social_api.get_all_friend_ids()
                    if f_ids is not None:
                        total_friends = len(f_ids)
                        first_snap = FriendsCountSnapshot(
                            account_id=account_id,
                            friends_count=total_friends,
                            created_at=now,
                        )
                        session.add(first_snap)
                        await session.commit()
                        snaps_count = 1
                except Exception as e:
                    logger.warning(f"Не удалось получить список друзей для первичного снимка: {e}")

            # 3. Поиск снимка за 24ч
            snap_24h_stmt = select(FriendsCountSnapshot).where(
                FriendsCountSnapshot.account_id == account_id,
                FriendsCountSnapshot.created_at <= target_ts,
            ).order_by(FriendsCountSnapshot.created_at.desc()).limit(1)
            snap_24h = (await session.execute(snap_24h_stmt)).scalar_one_or_none()

            has_24h_history = True
            if snap_24h:
                baseline_count = snap_24h.friends_count
                baseline_at = snap_24h.created_at.isoformat() + "Z"
            else:
                # Если истории за 24ч еще нет, берем самый ранний доступный снимок
                earliest_snap_stmt = select(FriendsCountSnapshot).where(
                    FriendsCountSnapshot.account_id == account_id
                ).order_by(FriendsCountSnapshot.created_at.asc()).limit(1)
                earliest_snap = (await session.execute(earliest_snap_stmt)).scalar_one_or_none()
                if earliest_snap:
                    baseline_count = earliest_snap.friends_count
                    baseline_at = earliest_snap.created_at.isoformat() + "Z"
                    has_24h_history = False
                else:
                    baseline_count = total_friends
                    baseline_at = now.isoformat() + "Z"
                    has_24h_history = False

            delta_24h = total_friends - baseline_count

            # 3. Конверсия по источникам из SentFriendRequest
            reqs_stmt = select(SentFriendRequest).where(SentFriendRequest.account_id == account_id)
            all_reqs = (await session.execute(reqs_stmt)).scalars().all()

            cands_stmt = select(TrackedCandidate.user_id, TrackedCandidate.total_damage).where(
                TrackedCandidate.account_id == account_id
            )
            cand_dmg_map = {row[0]: row[1] for row in (await session.execute(cands_stmt)).all()}

            stats_stmt = select(FriendStats.user_id, FriendStats.total_damage_to_my_bosses).where(
                FriendStats.account_id == account_id
            )
            stat_dmg_map = {row[0]: row[1] for row in (await session.execute(stats_stmt)).all()}

            sources_data: Dict[str, Dict[str, Any]] = {}
            for req in all_reqs:
                src = req.source or "unknown"
                if src not in sources_data:
                    sources_data[src] = {
                        "source": src,
                        "sent": 0,
                        "accepted": 0,
                        "ignored": 0,
                        "pending": 0,
                        "accepted_damages": [],
                    }
                item = sources_data[src]
                item["sent"] += 1
                if req.status == "accepted":
                    item["accepted"] += 1
                    uid = req.target_user_id
                    dmg = max(cand_dmg_map.get(uid, 0), stat_dmg_map.get(uid, 0))
                    if dmg > 0:
                        item["accepted_damages"].append(dmg)
                elif req.status == "ignored":
                    item["ignored"] += 1
                elif req.status == "sent":
                    item["pending"] += 1

            conversion_by_source = []
            for src, d in sources_data.items():
                sent_cnt = d["sent"]
                acc_cnt = d["accepted"]
                conv_rate = round((acc_cnt / sent_cnt * 100.0), 1) if sent_cnt > 0 else 0.0
                avg_dmg = int(sum(d["accepted_damages"]) / len(d["accepted_damages"])) if d["accepted_damages"] else 0
                conversion_by_source.append({
                    "source": src,
                    "sent": sent_cnt,
                    "accepted": acc_cnt,
                    "ignored": d["ignored"],
                    "pending": d["pending"],
                    "conversionRate": conv_rate,
                    "avgDamage": avg_dmg,
                })

            conversion_by_source.sort(key=lambda x: (x["conversionRate"], x["sent"]), reverse=True)

            return {
                "totalFriends": total_friends,
                "friendsCount": total_friends,
                "delta24h": delta_24h,
                "baselineCount": baseline_count,
                "baselineAt": baseline_at,
                "snapshotAt": baseline_at,
                "has24hHistory": has_24h_history,
                "conversionBySource": conversion_by_source,
            }

    summary_payload = await _flight_cache.get_or_set(f"friends_summary:{account_id}", 15.0, _compute_summary)
    hub.update_slice(account_id, "friends", summary_payload, source_tag=tag)
    return summary_payload


@api_router.get("/friends/stats")
async def get_friends_stats(
    sort: str = Query("damage_7d"),
    limit: int = Query(100, ge=1, le=500),
    account_id: int = 1,
    force: bool = Query(False),
) -> Dict[str, Any]:
    """
    Выгрузка списка друзей с боевой статистикой, уроном за 7 дней и статусом неактивности.
    sort: 'damage_7d' | 'total_damage' | 'inactive'
    """
    engine = bot_context.db_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Database engine not available")

    hub = _get_hub()
    tag = _hub_source_tag()
    if not force and sort == "damage_7d" and limit == 100:
        warm = hub.get_slice(account_id, "friends_stats", max_age_seconds=120.0, source_tag=tag)
        if warm is not None:
            return warm.data

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    async with get_session(engine) as session:
        stmt = select(FriendStats).where(
            FriendStats.account_id == account_id,
            FriendStats.is_current_friend == True,
        )
        friends = (await session.execute(stmt)).scalars().all()

        dmg_7d_stmt = (
            select(BossFriendDamageLog.user_id, func.sum(BossFriendDamageLog.recorded_damage))
            .where(
                BossFriendDamageLog.account_id == account_id,
                BossFriendDamageLog.updated_at >= week_ago,
                BossFriendDamageLog.recorded_damage > 0,
            )
            .group_by(BossFriendDamageLog.user_id)
        )
        dmg_7d_rows = (await session.execute(dmg_7d_stmt)).all()
        dmg_7d_map = {row[0]: int(row[1] or 0) for row in dmg_7d_rows}

        results = []
        for f in friends:
            d7 = dmg_7d_map.get(f.user_id, 0)
            wep_power = (f.poison_damage or 0) + (f.gunshot_damage or 0) + (f.knife_damage or 0)
            days_inactive = (now - f.last_active_at).days if f.last_active_at else 0

            results.append({
                "userId": f.user_id,
                "nickname": f.nickname or f"Кореш {f.user_id}",
                "photoUrl": f.photo_url,
                "level": f.level,
                "authority": f.authority,
                "biceps": f.biceps,
                "talents": f.talents,
                "weaponPower": wep_power,
                "poisonDamage": f.poison_damage,
                "gunshotDamage": f.gunshot_damage,
                "knifeDamage": f.knife_damage,
                "damage7d": d7,
                "totalDamageToMyBosses": f.total_damage_to_my_bosses,
                "bossHitsCount": f.boss_hits_count,
                "lastBossHitAt": f.last_boss_hit_at.isoformat() + "Z" if f.last_boss_hit_at else None,
                "lastActiveAt": f.last_active_at.isoformat() + "Z" if f.last_active_at else None,
                "daysInactive": days_inactive,
                "isWhitelisted": f.is_whitelisted,
            })

        if sort == "damage_7d":
            results.sort(key=lambda x: (x["damage7d"], x["totalDamageToMyBosses"]), reverse=True)
        elif sort == "total_damage":
            results.sort(key=lambda x: (x["totalDamageToMyBosses"], x["damage7d"]), reverse=True)
        elif sort == "inactive":
            results.sort(key=lambda x: x["daysInactive"], reverse=True)

        payload = {
            "success": True,
            "total": len(results),
            "friends": results[:limit],
        }
        if sort == "damage_7d" and limit == 100:
            hub.update_slice(account_id, "friends_stats", payload, source_tag=tag)
        return payload


@api_router.post("/friends/whitelist")
async def toggle_friend_whitelist(
    payload: Dict[str, Any] = Body(...),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Добавление/удаление друга из белого списка (защита от авто-кика)."""
    user_id = payload.get("userId")
    if user_id is None:
        raise HTTPException(status_code=400, detail="userId is required")
    whitelisted = bool(payload.get("whitelisted", True))

    engine = bot_context.db_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Database engine not available")

    async with get_session(engine) as session:
        stmt = select(FriendStats).where(
            FriendStats.account_id == account_id,
            FriendStats.user_id == int(user_id),
        )
        fs = (await session.execute(stmt)).scalar_one_or_none()
        if fs:
            fs.is_whitelisted = whitelisted
            fs.updated_at = datetime.utcnow()
        else:
            fs = FriendStats(
                account_id=account_id,
                user_id=int(user_id),
                is_whitelisted=whitelisted,
                is_current_friend=True,
            )
            session.add(fs)
        await session.commit()

    return {
        "success": True,
        "userId": int(user_id),
        "isWhitelisted": whitelisted,
    }


@api_router.get("/friends/cleanup/preview")
async def preview_friends_cleanup(account_id: int = 1) -> Dict[str, Any]:
    """
    Предпросмотр кандидатов на удаление по текущим правилам BotConfig.
    """
    engine = bot_context.db_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Database engine not available")

    cfg = await get_or_create_config(account_id, engine)
    inactive_days = getattr(cfg, "friend_cleanup_inactive_days", 14) or 14
    daily_limit = min(getattr(cfg, "friend_cleanup_daily_limit", 5) or 5, 15)

    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    async with get_session(engine) as session:
        action_stmt = select(ActionLog).where(
            ActionLog.account_id == account_id,
            ActionLog.action_type == "friend_remove",
            ActionLog.created_at >= day_ago,
            ActionLog.success == True,
        )
        removed_24h = len((await session.execute(action_stmt)).scalars().all())
        remaining_budget = max(0, daily_limit - removed_24h)

        stmt = select(FriendStats).where(
            FriendStats.account_id == account_id,
            FriendStats.is_current_friend == True,
            FriendStats.is_whitelisted == False,
            FriendStats.total_damage_to_my_bosses <= 0,
        )
        all_candidates = (await session.execute(stmt)).scalars().all()

        eligible = []
        for cand in all_candidates:
            if cand.first_seen_at and (now - cand.first_seen_at).days < inactive_days:
                continue
            if cand.last_active_at and (now - cand.last_active_at).days < inactive_days:
                continue

            dmg_stmt = select(BossFriendDamageLog).where(
                BossFriendDamageLog.account_id == account_id,
                BossFriendDamageLog.user_id == cand.user_id,
                BossFriendDamageLog.updated_at >= week_ago,
                BossFriendDamageLog.recorded_damage > 0,
            )
            recent_logs = (await session.execute(dmg_stmt)).scalars().all()
            if recent_logs:
                continue

            days_inactive = (now - cand.last_active_at).days if cand.last_active_at else 0
            days_added = (now - cand.first_seen_at).days if cand.first_seen_at else 0
            wep_power = (cand.poison_damage or 0) + (cand.gunshot_damage or 0) + (cand.knife_damage or 0)

            eligible.append({
                "userId": cand.user_id,
                "nickname": cand.nickname or f"Кореш {cand.user_id}",
                "photoUrl": cand.photo_url,
                "daysInactive": days_inactive,
                "daysSinceAdded": days_added,
                "totalDamageToMyBosses": cand.total_damage_to_my_bosses,
                "weaponPower": wep_power,
                "_sort_key": (
                    cand.total_damage_to_my_bosses or 0,
                    wep_power,
                    cand.last_active_at or datetime.min,
                )
            })

        eligible.sort(key=lambda x: x["_sort_key"])
        for e in eligible:
            del e["_sort_key"]

    return {
        "success": True,
        "totalEligible": len(eligible),
        "dailyLimit": daily_limit,
        "removedLast24h": removed_24h,
        "remainingDailyLimit": remaining_budget,
        "candidates": eligible,
    }


@api_router.post("/friends/cleanup/run")
async def run_friends_cleanup(
    payload: Dict[str, Any] = Body(default_factory=dict),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Ручной запуск чистки неактивных друзей."""
    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    engine = bot_context.db_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Database engine not available")

    cfg = await get_or_create_config(account_id, engine)
    user_ids = payload.get("userIds")

    from workers.social_worker import SocialWorker
    worker = bot_context.social_worker or SocialWorker(
        account_id=account_id,
        social_api=social_api,
        db_engine=engine,
        enable_jitter=False,
    )

    if user_ids and isinstance(user_ids, list):
        now = datetime.utcnow()
        day_ago = now - timedelta(hours=24)
        daily_limit = min(getattr(cfg, "friend_cleanup_daily_limit", 5) or 5, 15)

        async with get_session(engine) as session:
            action_stmt = select(ActionLog).where(
                ActionLog.account_id == account_id,
                ActionLog.action_type == "friend_remove",
                ActionLog.created_at >= day_ago,
                ActionLog.success == True,
            )
            removed_24h = len((await session.execute(action_stmt)).scalars().all())
            budget = max(0, daily_limit - removed_24h)

        if budget <= 0:
            raise HTTPException(status_code=429, detail=f"Суточный лимит удалений ({daily_limit}) исчерпан.")

        removed_count = 0
        for uid in user_ids[:budget]:
            try:
                async with get_session(engine) as session:
                    fs = (await session.execute(
                        select(FriendStats).where(FriendStats.account_id == account_id, FriendStats.user_id == int(uid))
                    )).scalar_one_or_none()
                    if fs and fs.is_whitelisted:
                        continue

                res = await social_api.remove_friend(int(uid))
                is_ok = bool(res.get("success", True)) if isinstance(res, dict) else True
                if is_ok:
                    removed_count += 1
                    async with get_session(engine) as session:
                        fs_upd = (await session.execute(
                            select(FriendStats).where(FriendStats.account_id == account_id, FriendStats.user_id == int(uid))
                        )).scalar_one_or_none()
                        if fs_upd:
                            fs_upd.is_current_friend = False
                            fs_upd.updated_at = datetime.utcnow()
                        log_entry = ActionLog(
                            account_id=account_id,
                            action_type="friend_remove",
                            endpoint=f"/api/friendship/remove-friend?friendUserId={uid}",
                            status_code=200,
                            success=True,
                            details={"userId": uid, "manual": True},
                        )
                        session.add(log_entry)
                        await session.commit()
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning("Ошибка ручного удаления друга %s: %s", uid, e)
    else:
        removed_count = await worker.cleanup_inactive_friends(config=cfg)

    return {
        "success": True,
        "removedCount": removed_count,
        "message": f"Удалено {removed_count} неактивных друзей.",
    }


@api_router.post("/raids/scan-news")
async def scan_news_endpoint(account_id: int = 1) -> Dict[str, Any]:
    """Ручной триггер парсинга постов /api/news и объявлений /api/news-ads."""
    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    engine = bot_context.db_engine
    res = await _raids_api.scan_news_for_candidates(
        game_http_client=social_api.http,
        db_engine=engine,
        account_id=account_id,
        force=True,
    )
    return res


@api_router.post("/raids/sync-top")
async def sync_top_endpoint(
    payload: Dict[str, Any] = Body(default_factory=dict),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Ручной запуск синхронизации с еженедельным топом и достижениями."""
    social_api = bot_context.social_api
    if not social_api:
        raise HTTPException(status_code=503, detail="SocialAPI not available")

    engine = bot_context.db_engine
    force = bool(payload.get("force", True))
    res = await _raids_api.sync_weekly_top_and_achievements(
        social_api=social_api,
        db_engine=engine,
        account_id=account_id,
        force=force,
    )
    return res


# ============================================================================
# LIVESTATEHUB SSE STREAM & DELTA SYNC (24/7 БЕСШОВНАЯ СИНХРОНИЗАЦИЯ)
# ============================================================================

async def refresh_hub_slice(account_id: int = 1, slice_name: str = "profile", force: bool = True) -> Any:
    """
    Обновляет срез в LiveStateHub под single-flight защитой.
    Вызывается фоновым SchedulerController и мутациями без дублирования запросов к игре.
    """
    hub = _get_hub()
    tag = _hub_source_tag()

    async def _do_refresh():
        if slice_name == "profile":
            return await get_live_profile(account_id=account_id, force=force)
        elif slice_name == "state":
            return await get_state(account_id=account_id, force=force)
        elif slice_name == "boss":
            return await get_live_boss(account_id=account_id, force=force)
        elif slice_name == "presets":
            res_p = await get_boss_presets(account_id=account_id)
            hub.update_slice(account_id, "presets", res_p, source_tag=tag)
            return res_p
        elif slice_name == "prisons":
            return await get_live_prisons(account_id=account_id, force=force)
        elif slice_name == "friends":
            return await get_friends_summary(account_id=account_id, force=force)
        elif slice_name == "friend_requests":
            return await get_friendship_requests(page=0, page_size=50, account_id=account_id, force=force)
        elif slice_name == "friends_stats":
            return await get_friends_stats(sort="damage_7d", limit=100, account_id=account_id, force=force)
        elif slice_name == "radar":
            return await get_active_players(
                source="all",
                minDamage=0,
                maxDamage=0,
                limit=50,
                excludeFriends=False,
                account_id=account_id,
                force=force,
            )
        elif slice_name == "collections":
            return await get_live_collections(user_id=None, account_id=account_id, force=force)
        elif slice_name == "monthly":
            return await get_monthly_state(account_id=account_id, force=force)
        elif slice_name == "bauls":
            return await get_bauls(account_id=account_id, force=force)
        elif slice_name == "routine":
            m_res = None
            b_res = None
            if bot_context.social_api:
                try:
                    m_res = await get_monthly_state(account_id=account_id, force=force)
                except Exception:
                    pass
            if bot_context.player_api:
                try:
                    b_res = await get_bauls(account_id=account_id, force=force)
                except Exception:
                    pass
            bundle = {"monthly": m_res, "bauls": b_res}
            hub.update_slice(account_id, "routine", bundle, source_tag=tag)
            return bundle
        return None

    try:
        return await hub.run_single_flight(f"refresh:{account_id}:{slice_name}", _do_refresh)
    except HTTPException:
        return None
    except Exception as e:
        logger.debug("refresh_hub_slice('%s') error: %s", slice_name, e)
        return None


def _parse_client_versions(versions_raw: Optional[str]) -> Dict[str, int]:
    if not versions_raw:
        return {}
    raw = versions_raw.strip()
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return {str(k): int(v or 0) for k, v in obj.items()}
        except Exception:
            return {}
    parsed: Dict[str, int] = {}
    for pair in raw.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            k = k.strip()
            if k:
                try:
                    parsed[k] = int(v.strip() or 0)
                except ValueError:
                    pass
    return parsed


@api_router.get("/live/delta")
async def get_live_delta(
    versions: Optional[str] = Query(None, description="JSON map or comma-separated slice:version"),
    account_id: int = 1,
) -> Dict[str, Any]:
    """Fallback-эндпоинт: возвращает только срезы, чья version новее версии клиента."""
    hub = _get_hub()
    parsed_versions = _parse_client_versions(versions)
    delta = hub.get_delta(account_id, parsed_versions)
    return {"success": True, **delta}


@api_router.get("/live/stream")
async def stream_live_state(
    request: Request,
    account_id: int = 1,
    once: bool = Query(False),
) -> StreamingResponse:
    """
    Поток Server-Sent Events (SSE) для мгновенной синхронизации всех вкладок UI без мерцаний:
    - Немедленно отправляет event: snapshot со всеми прогретыми срезами.
    - Пушит event: slice_update при реальном изменении содержимого любого среза.
    - Шлет `: ping` каждые 25 секунд для удержания соединения за reverse-proxy.
    """
    hub = _get_hub()

    # Если хаб ещё пустой, запускаем неблокирующий фоновый прогрев
    if not hub.get_versions(account_id):
        ctrl = getattr(bot_context, "scheduler_controller", None)
        if ctrl is not None:
            try:
                asyncio.create_task(ctrl.warmup_all())
            except RuntimeError:
                pass

    async def event_generator():
        q = hub.subscribe(account_id)
        try:
            snap = hub.get_snapshot(account_id)
            yield f"event: snapshot\ndata: {json.dumps(snap, ensure_ascii=False, default=str)}\n\n"
            if once:
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=25.0)
                    evt_type = evt.get("type", "slice_update")
                    yield f"event: {evt_type}\ndata: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            return
        finally:
            hub.unsubscribe(account_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




