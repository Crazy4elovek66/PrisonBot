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
    resp = client.get(f"/api/v1/assets/proxy?path={asset_rel}", headers={"X-Real-IP": "127.0.0.1"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Accel-Redirect") == f"/_prison_asset_cache/{asset_cache_filename(asset_rel)}"
    resp_direct = client.get(f"/api/v1/assets/proxy?path={asset_rel}")
    assert resp_direct.status_code == 200
    assert resp_direct.content == b"WEBP_ACCEL"
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
    assert "prisonbot-assets-v30" in sw_text
    assert "/api/v1/news/media/" in sw_text
    assert "/assets_cache/" in sw_text
    assert "/api/v1/assets/proxy" in sw_text
    assert "/static/assets/icons/" in sw_text
    assert "/static/assets/rooms/" in sw_text
    assert "live/stream" not in sw_text or "Network-Only" in sw_text


def test_resource_hud_icons_match_reference_archive():
    import hashlib

    root = Path(__file__).resolve().parent.parent
    icons_dir = root / "web" / "static" / "assets" / "icons"
    ref_dir = root / "reference_archive" / "pro_prison_bot" / "assets"
    mapping = {
        "cigarettes.webp": "HUD_cigarettes.webp",
        "rubles.webp": "HUD_rubles.webp",
        "sugar.webp": "HUD_sugar.webp",
        "soap.webp": "HUD_soap.webp",
        "boss.webp": "PrisonV3_bosses_all_bosses.webp",
        "stash.webp": "poker_hidesicon.webp",
        "room_reward.webp": "PrisonV3_bosses_all_camerReward.webp",
        "complect.webp": "PrisonV3_bosses_all_complectReward.webp",
        "podogrev.webp": "podogrev_pagePodogrev.webp",
        "authority.webp": "Avtoritet.webp",
    }
    for dst_name, ref_name in mapping.items():
        dst_path = icons_dir / dst_name
        assert dst_path.exists(), f"Missing icon: {dst_path}"
        data = dst_path.read_bytes()
        assert len(data) > 0
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", f"Invalid WebP header: {dst_path}"
        ref_path = ref_dir / ref_name
        if ref_path.exists():
            assert hashlib.sha256(data).hexdigest() == hashlib.sha256(ref_path.read_bytes()).hexdigest()


def test_python_and_js_sha256_hash_parity():
    import subprocess
    root = Path(__file__).resolve().parent.parent
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    start = app_js.index("function sha256Hex(ascii)")
    end = app_js.index("if (typeof window !== \"undefined\")", start)
    js_snippet = app_js[start:end]

    test_paths = [
        "assets/PrisonV3/Clotch/Mafia/C/C_Zone1Mafia.png",
        "assets/PrisonV3/Tattoos/manga/T/manga_Zone11.png",
        "assets/PrisonV3/RoomCameraUrl/37/skeleton.json",
        "assets/PrisonV3/RoomCameraUrl/54/room.bundle",
        "assets/PrisonV3/collections/1/1/1.webp",
    ]
    import json
    node_script = f"""
    const API_BASE = "/api/v1";
    const _sha256Memo = new Map();
    {js_snippet}
    const paths = {json.dumps(test_paths)};
    console.log(JSON.stringify(paths.map(p => sha256Hex(normalizeAssetRelPath(p)) + _assetExtFromPath(normalizeAssetRelPath(p)))));
    """
    out = subprocess.check_output(["node"], input=node_script, text=True).strip()
    js_filenames = json.loads(out)
    py_filenames = [asset_cache_filename(p) for p in test_paths]
    assert js_filenames == py_filenames


@pytest.mark.asyncio
async def test_direct_assets_cache_endpoint_hit_miss_and_validation(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from web.app import create_app
    import web.routes as routes_mod

    mgr = AssetCacheManager(cache_dir=tmp_path, max_mb=10, min_free_gb=0.0)
    monkeypatch.setattr(routes_mod, "get_asset_cache_manager", lambda: mgr)

    rel = "assets/PrisonV3/Clotch/Mafia/C/C_Zone1Mafia.png"
    fname = asset_cache_filename(rel)

    async def _fake_fetch(_):
        return b"CDN_PNG_BYTES", "image/png", True

    monkeypatch.setattr(routes_mod, "_fetch_asset_from_cdn", _fake_fetch)

    app = create_app()
    client = TestClient(app)

    # 1. Invalid filename -> 400
    assert client.get("/assets_cache/bad_name.png").status_code == 400

    # 2. MISS -> fetches from CDN, stores atomically, returns MISS-STORED
    r_miss = client.get(f"/assets_cache/{fname}?path={rel}")
    assert r_miss.status_code == 200
    assert r_miss.headers.get("X-Asset-Cache") == "MISS-STORED"
    assert (tmp_path / fname).exists()

    # 3. HIT -> returns HIT-DISK with 1-year immutable Cache-Control
    r_hit = client.get(f"/assets_cache/{fname}?path={rel}")
    assert r_hit.status_code == 200
    assert r_hit.headers.get("X-Asset-Cache") == "HIT-DISK"
    assert "max-age=31536000" in r_hit.headers.get("Cache-Control", "")


def test_config_defaults_and_no_hover_prefetch():
    from core.config import Settings
    s = Settings(_env_file=None)
    assert s.ASSET_CACHE_MAX_MB == 2500
    assert s.ASSET_CACHE_MIN_FREE_GB == 5.0

    root = Path(__file__).resolve().parent.parent
    app_js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert "mouseenter" not in app_js.lower()
    assert "hoverprefetch" not in app_js.lower()
