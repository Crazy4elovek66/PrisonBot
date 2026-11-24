import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.asset_cache import AssetCacheManager  # noqa: E402
from core.config import settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("prewarm_asset_cache")

CDN_BASE = "https://oldprison-prod-assets-cdn-yandex.luckygem.online"
SPINE_ROOM_IDS = list(range(27, 38))
BUNDLE_ROOM_IDS = [39, 40, 41, 42, 44, 45, 54]


def normalize_asset_path(raw_url: str) -> str:
    if not raw_url:
        return ""
    s = str(raw_url).strip()
    if not s or s.startswith("/static/") or s.startswith("data:"):
        return ""
    if s.startswith(CDN_BASE + "/"):
        s = s[len(CDN_BASE) + 1:]
    elif s.startswith("http://") or s.startswith("https://"):
        try:
            from urllib.parse import urlparse
            s = urlparse(s).path
        except Exception:
            return ""
    if "path=" in s:
        from urllib.parse import unquote
        s = unquote(s.split("path=", 1)[1].split("&", 1)[0])
    s = s.lstrip("/").strip()
    if not s or ".." in s:
        return ""
    return s


def _walk_extract_urls(obj, out: Set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in (
                "image",
                "imageUrl",
                "imageBackUrl",
                "backImageUrl",
                "previewUrl",
                "cardPreviewUrl",
                "eyesUrl",
                "noseUrl",
                "mouthUrl",
                "icon",
                "iconUrl",
            ):
                if isinstance(v, str):
                    p = normalize_asset_path(v)
                    if p:
                        out.add(p)
            else:
                _walk_extract_urls(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_extract_urls(item, out)


def collect_all_asset_paths(root: Path = PROJECT_ROOT) -> List[str]:
    """
    Собирает 100% URL ассетов с приоритетным порядком:
    1. Хаты (включая Spine и Bundle)
    2. Одежда (clothing)
    3. Татуировки (tattoos)
    4. Нычки и боссы
    """
    ordered: List[str] = []
    seen: Set[str] = set()

    def _add_many(items: Set[str]) -> None:
        for p in sorted(items):
            if p not in seen:
                seen.add(p)
                ordered.append(p)

    storage = root / "storage"
    tc_path = storage / "tattoo_clothing_cache.json"
    tc_data: Dict = {}
    if tc_path.exists():
        try:
            tc_data = json.loads(tc_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Ошибка чтения %s: %s", tc_path, e)

    # 1. Хаты и Spine/Bundle ассеты
    room_urls: Set[str] = set()
    _walk_extract_urls(tc_data.get("cameras") or [], room_urls)
    for rid in SPINE_ROOM_IDS:
        room_urls.add(f"assets/PrisonV3/RoomCameraUrl/{rid}/skeleton.json")
        room_urls.add(f"assets/PrisonV3/RoomCameraUrl/{rid}/skeleton.atlas")
        room_urls.add(f"assets/PrisonV3/RoomCameraUrl/{rid}/skeleton.webp")
    for rid in BUNDLE_ROOM_IDS:
        room_urls.add(f"assets/PrisonV3/RoomCameraUrl/{rid}/room.bundle")
    _add_many(room_urls)

    # 2. Одежда
    cloth_urls: Set[str] = set()
    _walk_extract_urls(tc_data.get("clothing") or [], cloth_urls)
    _add_many(cloth_urls)

    # 3. Татуировки
    tattoo_urls: Set[str] = set()
    _walk_extract_urls(tc_data.get("tattoos") or [], tattoo_urls)
    _add_many(tattoo_urls)

    # 4. Коллекции и боссы
    extra_urls: Set[str] = set()
    for fname in ("collections_catalog.json", "bosses_catalog.json"):
        fpath = storage / fname
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                _walk_extract_urls(data, extra_urls)
            except Exception as e:
                logger.warning("Ошибка чтения %s: %s", fpath, e)
    _add_many(extra_urls)

    return ordered


def _current_load_avg() -> float:
    if hasattr(os, "getloadavg"):
        try:
            return float(os.getloadavg()[0])
        except OSError:
            return 0.0
    return 0.0


async def prewarm(
    concurrency: int = 4,
    delay: float = 0.05,
    max_load: float = 1.4,
    max_mb: int = settings.ASSET_CACHE_MAX_MB,
    min_free_gb: float = settings.ASSET_CACHE_MIN_FREE_GB,
    dry_run: bool = False,
) -> dict:
    mgr = AssetCacheManager(max_mb=max_mb, min_free_gb=min_free_gb)
    all_paths = collect_all_asset_paths()
    already_cached = 0
    to_download: List[str] = []

    for p in all_paths:
        target = mgr.get_cached_path(p)
        if target.exists() and target.stat().st_size > 0:
            already_cached += 1
        else:
            to_download.append(p)

    summary = {
        "total_urls": len(all_paths),
        "already_cached": already_cached,
        "downloaded": 0,
        "errors": 0,
        "skipped_limits": 0,
        "dry_run": dry_run,
    }

    if dry_run or not to_download:
        stats = await mgr.get_stats(force=True)
        summary["final_cache_mb"] = stats["total_mb"]
        summary["free_gb"] = stats["free_gb"]
        return summary

    try:
        import h2  # noqa: F401
        use_http2 = True
    except ImportError:
        use_http2 = False

    sem = asyncio.Semaphore(max(1, concurrency))
    limits = httpx.Limits(max_keepalive_connections=concurrency + 2, max_connections=concurrency + 4)
    processed = 0

    async with httpx.AsyncClient(http2=use_http2, timeout=20.0, limits=limits, follow_redirects=True) as client:
        for i in range(0, len(to_download), concurrency):
            if not mgr.has_enough_disk_space():
                logger.warning("Остановка прогрева: недостаточно свободного места на диске (< %.2f GB)", min_free_gb)
                summary["skipped_limits"] += len(to_download) - i
                break

            if i % (concurrency * 20) == 0:
                stats = await mgr.get_stats(force=True)
                if stats["total_mb"] >= max_mb:
                    logger.warning("Остановка прогрева: достигнут лимит кэша %.2f MB >= %d MB", stats["total_mb"], max_mb)
                    summary["skipped_limits"] += len(to_download) - i
                    break

            load = _current_load_avg()
            if max_load > 0 and load >= max_load:
                logger.info("Высокий Load Average (%.2f >= %.2f), пауза 5с...", load, max_load)
                await asyncio.sleep(5.0)

            batch = to_download[i:i + concurrency]

            async def _fetch_one(clean_path: str) -> None:
                async with sem:
                    cdn_path = clean_path if (clean_path.startswith("assets/") or clean_path.startswith("avatars/")) else f"assets/{clean_path}"
                    url = f"{CDN_BASE}/{cdn_path}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and resp.content:
                            written = await mgr.atomic_write(clean_path, resp.content)
                            if written is not None:
                                summary["downloaded"] += 1
                            else:
                                summary["skipped_limits"] += 1
                        else:
                            summary["errors"] += 1
                    except Exception:
                        summary["errors"] += 1

            await asyncio.gather(*[_fetch_one(p) for p in batch])
            processed += len(batch)
            if processed % 250 < concurrency:
                st = await mgr.get_stats(force=True)
                logger.info(
                    "Прогресс: downloaded=%d, skipped=%d, failed=%d, cache_mb=%.2f, free_gb=%.2f, load1=%.2f",
                    summary["downloaded"],
                    already_cached,
                    summary["errors"],
                    st["total_mb"],
                    st["free_gb"],
                    _current_load_avg(),
                )
            if delay > 0:
                await asyncio.sleep(delay)

    final_stats = await mgr.get_stats(force=True)
    summary["final_cache_mb"] = final_stats["total_mb"]
    summary["free_gb"] = final_stats["free_gb"]
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Бережный фоновый прогрев кэша ассетов PrisonBot")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--max-load", type=float, default=1.4)
    parser.add_argument("--max-mb", type=int, default=settings.ASSET_CACHE_MAX_MB)
    parser.add_argument("--min-free-gb", type=float, default=settings.ASSET_CACHE_MIN_FREE_GB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    res = asyncio.run(
        prewarm(
            concurrency=args.concurrency,
            delay=args.delay,
            max_load=args.max_load,
            max_mb=args.max_mb,
            min_free_gb=args.min_free_gb,
            dry_run=args.dry_run,
        )
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
