import asyncio
import hashlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from core.config import settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_cache_dir(raw_dir: Optional[str] = None) -> Path:
    val = (raw_dir if raw_dir is not None else settings.ASSET_CACHE_DIR) or "storage/asset_cache"
    p = Path(val)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def asset_cache_key_and_ext(clean_path: str) -> Tuple[str, str]:
    normalized = clean_path.lstrip("/").strip()
    ext = Path(normalized).suffix.lower() or ".png"
    path_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return path_hash, ext


def asset_cache_filename(clean_path: str) -> str:
    path_hash, ext = asset_cache_key_and_ext(clean_path)
    return f"{path_hash}{ext}"


def content_type_for_ext(ext: str) -> str:
    ext = ext.lower()
    if ext == ".webp":
        return "image/webp"
    if ext == ".json":
        return "application/json"
    if ext == ".atlas":
        return "text/plain; charset=utf-8"
    if ext == ".bundle":
        return "application/octet-stream"
    return "image/png"


class AssetCacheManager:
    """
    Потокобезопасный и асинхронный менеджер дискового кэша игровых ассетов:
    - Детерминированное именование sha256(clean_path) + ext
    - Атомарная запись (<hash>.tmp.<pid> -> chmod 0o644 -> os.replace)
    - Per-key asyncio.Lock для дедупликации параллельных загрузок с CDN
    - Защита свободного места на диске (min_free_gb)
    - LRU-очистка по st_mtime при превышении max_mb
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_mb: Optional[int] = None,
        min_free_gb: Optional[float] = None,
        nginx_accel_prefix: Optional[str] = None,
    ):
        self.cache_dir: Path = Path(cache_dir) if cache_dir is not None else resolve_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_mb: int = int(max_mb if max_mb is not None else settings.ASSET_CACHE_MAX_MB)
        self.min_free_gb: float = float(min_free_gb if min_free_gb is not None else settings.ASSET_CACHE_MIN_FREE_GB)
        self.nginx_accel_prefix: str = (
            nginx_accel_prefix if nginx_accel_prefix is not None else settings.ASSET_CACHE_NGINX_ACCEL_PREFIX
        ).rstrip("/")
        self._inflight_locks: Dict[str, asyncio.Lock] = {}
        self._write_count: int = 0
        self._last_low_disk_warn: float = 0.0
        self._stats_cache: Optional[Tuple[float, Dict[str, Any]]] = None

    def get_cached_path(self, clean_path: str) -> Path:
        return self.cache_dir / asset_cache_filename(clean_path)

    def has_enough_disk_space(self) -> bool:
        try:
            free_bytes = shutil.disk_usage(self.cache_dir).free
            min_bytes = int(self.min_free_gb * (1024 ** 3))
            if free_bytes < min_bytes:
                now = time.monotonic()
                if now - self._last_low_disk_warn > 300.0:
                    self._last_low_disk_warn = now
                    logger.warning(
                        "Недостаточно свободного места для записи кэша ассетов: %.2f GB < %.2f GB",
                        free_bytes / (1024 ** 3),
                        self.min_free_gb,
                    )
                return False
            return True
        except Exception as e:
            logger.debug("Ошибка проверки свободного места диска: %s", e)
            return True

    def _atomic_write_sync(self, target_file: Path, data: bytes) -> bool:
        if not data or not self.has_enough_disk_space():
            return False
        tmp_file = target_file.parent / f"{target_file.stem}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
        try:
            tmp_file.write_bytes(data)
            try:
                os.chmod(tmp_file, 0o644)
            except OSError:
                pass
            os.replace(tmp_file, target_file)
            return True
        except Exception as e:
            logger.warning("Ошибка атомарной записи ассета %s: %s", target_file.name, e)
            try:
                if tmp_file.exists():
                    tmp_file.unlink()
            except OSError:
                pass
            return False

    def prune_lru_sync(self) -> int:
        """Удаляет самые старые по mtime файлы до 85% от max_mb, если размер превышен."""
        max_bytes = int(self.max_mb * 1024 * 1024)
        if max_bytes <= 0:
            return 0
        entries = []
        total_bytes = 0
        try:
            with os.scandir(self.cache_dir) as it:
                for entry in it:
                    if not entry.is_file() or ".tmp." in entry.name:
                        continue
                    try:
                        st = entry.stat()
                        entries.append((st.st_mtime, st.st_size, Path(entry.path)))
                        total_bytes += st.st_size
                    except OSError:
                        continue
        except OSError:
            return 0

        if total_bytes <= max_bytes:
            return 0

        target_bytes = int(max_bytes * 0.85)
        entries.sort(key=lambda x: x[0])  # oldest first
        removed = 0
        for _, sz, fpath in entries:
            if total_bytes <= target_bytes:
                break
            try:
                fpath.unlink()
                total_bytes -= sz
                removed += 1
            except OSError:
                continue
        if removed:
            logger.info("LRU-очистка кэша ассетов: удалено %d файлов, осталось %.2f MB", removed, total_bytes / (1024 * 1024))
        return removed

    async def atomic_write(self, clean_path: str, data: bytes) -> Optional[Path]:
        target_file = self.get_cached_path(clean_path)
        ok = await asyncio.to_thread(self._atomic_write_sync, target_file, data)
        if not ok:
            return None
        self._write_count += 1
        if self._write_count % 100 == 0:
            await asyncio.to_thread(self.prune_lru_sync)
        self._stats_cache = None
        return target_file

    def _get_lock(self, key: str) -> asyncio.Lock:
        lock = self._inflight_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._inflight_locks[key] = lock
        return lock

    async def get_or_fetch(
        self,
        clean_path: str,
        fetcher: Callable[[str], Awaitable[Tuple[bytes, str, bool]]],
    ) -> Tuple[Optional[Path], Optional[bytes], str]:
        """
        Возвращает (cached_file_path_or_None, bytes_or_None, content_type).
        Дедуплицирует параллельные загрузки одного clean_path через per-key asyncio.Lock.
        fetcher(clean_path) -> (content_bytes, content_type, should_persist)
        """
        path_hash, ext = asset_cache_key_and_ext(clean_path)
        cached_file = self.cache_dir / f"{path_hash}{ext}"
        if cached_file.exists():
            try:
                if cached_file.stat().st_size > 0:
                    return cached_file, None, content_type_for_ext(ext)
            except OSError:
                pass

        lock = self._get_lock(path_hash)
        async with lock:
            if cached_file.exists():
                try:
                    if cached_file.stat().st_size > 0:
                        return cached_file, None, content_type_for_ext(ext)
                except OSError:
                    pass

            data, c_type, should_persist = await fetcher(clean_path)
            if should_persist and data:
                written = await self.atomic_write(clean_path, data)
                if written is not None:
                    return written, data, c_type
            return None, data, c_type

    def _compute_stats_sync(self) -> Dict[str, Any]:
        files_count = 0
        total_bytes = 0
        try:
            with os.scandir(self.cache_dir) as it:
                for entry in it:
                    if entry.is_file() and ".tmp." not in entry.name:
                        files_count += 1
                        try:
                            total_bytes += entry.stat().st_size
                        except OSError:
                            pass
        except OSError:
            pass
        try:
            free_gb = round(shutil.disk_usage(self.cache_dir).free / (1024 ** 3), 2)
        except OSError:
            free_gb = 0.0
        return {
            "files_count": files_count,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "max_mb": self.max_mb,
            "free_gb": free_gb,
            "min_free_gb": self.min_free_gb,
            "cache_dir": str(self.cache_dir),
            "nginx_accel_prefix": self.nginx_accel_prefix,
        }

    async def get_stats(self, force: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        if not force and self._stats_cache and (now - self._stats_cache[0]) < 60.0:
            return self._stats_cache[1]
        stats = await asyncio.to_thread(self._compute_stats_sync)
        self._stats_cache = (now, stats)
        return stats


_default_manager: Optional[AssetCacheManager] = None


def get_asset_cache_manager() -> AssetCacheManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = AssetCacheManager()
    return _default_manager
