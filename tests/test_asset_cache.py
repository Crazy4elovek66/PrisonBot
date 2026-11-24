import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.asset_cache import AssetCacheManager, asset_cache_filename, asset_cache_key_and_ext
from scripts.prewarm_asset_cache import collect_all_asset_paths, normalize_asset_path, prewarm


def test_deterministic_cache_key_matches_prewarmer():
    url1 = "assets/PrisonV3/Clotch/Mafia/C/C_Zone1Mafia.png"
    url2 = "/api/v1/assets/proxy?path=assets/PrisonV3/Clotch/Mafia/C/C_Zone1Mafia.png"
    assert normalize_asset_path(url2) == url1
    assert asset_cache_filename(url1) == asset_cache_filename(normalize_asset_path(url2))
    h, ext = asset_cache_key_and_ext(url1)
    assert len(h) == 64
    assert ext == ".png"


@pytest.mark.asyncio
async def test_atomic_write_and_permissions(tmp_path):
    mgr = AssetCacheManager(cache_dir=tmp_path, max_mb=10, min_free_gb=0.0)
    path = "assets/PrisonV3/icons/test.webp"
    written = await mgr.atomic_write(path, b"RIFF0000WEBP")
    assert written is not None
    assert written.exists()
    assert written.read_bytes() == b"RIFF0000WEBP"
    # No leftover .tmp files
    assert [p.name for p in tmp_path.iterdir()] == [written.name]
    if os.name != "nt":
        assert (written.stat().st_mode & 0o777) == 0o644


@pytest.mark.asyncio
async def test_min_free_gb_prevents_disk_write(tmp_path):
    mgr = AssetCacheManager(cache_dir=tmp_path, max_mb=10, min_free_gb=5.0)
    low_disk = SimpleNamespace(total=10 * 1024**3, used=8 * 1024**3, free=2 * 1024**3)
    with patch("core.asset_cache.shutil.disk_usage", return_value=low_disk):
        called = 0

        async def _fetcher(_):
            nonlocal called
            called += 1
            return b"PNGDATA", "image/png", True

        cached_file, mem_bytes, c_type = await mgr.get_or_fetch("assets/a.png", _fetcher)
        assert called == 1
        assert cached_file is None
        assert mem_bytes == b"PNGDATA"
        assert c_type == "image/png"
        assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_lru_pruning_removes_oldest_files(tmp_path):
    mgr = AssetCacheManager(cache_dir=tmp_path, max_mb=1, min_free_gb=0.0)
    f_old = tmp_path / "old.png"
    f_mid = tmp_path / "mid.png"
    f_new = tmp_path / "new.png"
    f_old.write_bytes(b"a" * 500_000)
    f_mid.write_bytes(b"b" * 500_000)
    f_new.write_bytes(b"c" * 300_000)
    now = time.time()
    os.utime(f_old, (now - 300, now - 300))
    os.utime(f_mid, (now - 200, now - 200))
    os.utime(f_new, (now - 100, now - 100))

    removed = mgr.prune_lru_sync()
    assert removed >= 1
    assert not f_old.exists()
    assert f_new.exists()


@pytest.mark.asyncio
async def test_concurrent_fetch_deduplication(tmp_path):
    mgr = AssetCacheManager(cache_dir=tmp_path, max_mb=10, min_free_gb=0.0)
    fetch_calls = 0

    async def _slow_fetch(_):
        nonlocal fetch_calls
        fetch_calls += 1
        await asyncio.sleep(0.05)
        return b"SPRITE_BYTES", "image/png", True

    results = await asyncio.gather(
        *[mgr.get_or_fetch("assets/PrisonV3/Clotch/dedup.png", _slow_fetch) for _ in range(5)]
    )
    assert fetch_calls == 1
    assert all(r[0] is not None and r[0].exists() for r in results)


@pytest.mark.asyncio
async def test_proxy_returns_x_accel_redirect_when_configured(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from web.app import create_app
    import web.routes as routes_mod

    mgr = AssetCacheManager(
        cache_dir=tmp_path,
        max_mb=10,
        min_free_gb=0.0,
        nginx_accel_prefix="/_prison_asset_cache",
    )
    asset_rel = "assets/PrisonV3/Clotch/test_accel.webp"
    await mgr.atomic_write(asset_rel, b"WEBP_ACCEL")
    monkeypatch.setattr(routes_mod, "get_asset_cache_manager", lambda: mgr)

    app = create_app()
    client = TestClient(app)
    resp = client.get(f"/api/v1/assets/proxy?path={asset_rel}")
    assert resp.status_code == 200
    assert resp.headers.get("X-Accel-Redirect") == f"/_prison_asset_cache/{asset_cache_filename(asset_rel)}"
    assert resp.headers.get("X-Asset-Cache") == "HIT-ACCEL"
    assert "max-age=31536000" in resp.headers.get("Cache-Control", "")


@pytest.mark.asyncio
async def test_prewarm_dry_run_and_disk_guard():
    paths = collect_all_asset_paths()
    assert len(paths) > 100
    res = await prewarm(dry_run=True)
    assert res["dry_run"] is True
    assert res["total_urls"] == len(paths)


def test_sw_js_rules_and_network_only():
    root = Path(__file__).resolve().parent.parent
    sw_text = (root / "web" / "static" / "sw.js").read_text(encoding="utf-8")
    assert "prisonbot-assets-v1" in sw_text
    assert "/api/v1/assets/proxy" in sw_text
    assert "/static/assets/icons/" in sw_text
    assert "/static/assets/rooms/" in sw_text
    assert "live/stream" not in sw_text or "Network-Only" in sw_text
