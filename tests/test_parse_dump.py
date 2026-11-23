import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from scripts.parse_dump import (
    is_ignored_url,
    mask_sensitive_value,
    mask_dict_recursively,
    normalize_path,
    extract_endpoints_from_js,
    parse_network_log,
    generate_api_map,
    IGNORED_DOMAINS,
    IGNORED_EXTENSIONS,
    SENSITIVE_KEYS
)


def test_ignored_urls_filtering():
    """1. Проверка фильтрации мусорных доменов и статических ассетов."""
    # Должны игнорироваться домены
    for domain in IGNORED_DOMAINS:
        assert is_ignored_url(f"https://{domain}/analytics.js") is True
        assert is_ignored_url(f"https://sub.{domain}/api/test") is True

    # Должны игнорироваться расширения ассетов
    for ext in IGNORED_EXTENSIONS:
        assert is_ignored_url(f"https://game.online/assets/image{ext}") is True
        assert is_ignored_url(f"https://game.online/sound{ext}?v=123") is True

    # Легитимные API-запросы НЕ должны игнорироваться
    assert is_ignored_url("https://oldprison-prod.luckygem.online/api/player/init") is False
    assert is_ignored_url("https://oldprison-prod.luckygem.online/api/guild/status") is False
    assert is_ignored_url("https://oldprison-prod.luckygem.online/api/auth/login") is False


def test_sensitive_masking():
    """2. Проверка маскирования чувствительных заголовков и параметров."""
    # Заголовок Authorization с Bearer
    masked_auth = mask_sensitive_value("Authorization", "Bearer eyJhbGciOiJIUzI1Ni...")
    assert masked_auth == "Bearer <REDACTED>"

    # Чувствительные ключи
    for key in SENSITIVE_KEYS:
        val = mask_sensitive_value(key, "super_secret_token_123")
        assert val == "<REDACTED>"

    # Нечувствительные ключи
    assert mask_sensitive_value("Content-Type", "application/json") == "application/json"
    assert mask_sensitive_value("userId", 9000000000466709) == 9000000000466709

    # Рекурсивное маскирование словаря
    test_dict = {
        "headers": {
            "Authorization": "Bearer secret_jwt",
            "Content-Type": "application/json",
            "X-Custom-Token": "secret_custom"
        },
        "body": {
            "initData": "user_id=123&hash=abc",
            "nickname": "Player1",
            "nested": {
                "refreshToken": "secret_refresh",
                "normalKey": "normalValue"
            }
        }
    }
    masked = mask_dict_recursively(test_dict)
    assert masked["headers"]["Authorization"] == "Bearer <REDACTED>"
    assert masked["headers"]["Content-Type"] == "application/json"
    assert masked["headers"]["X-Custom-Token"] == "<REDACTED>"
    assert masked["body"]["initData"] == "<REDACTED>"
    assert masked["body"]["nickname"] == "Player1"
    assert masked["body"]["nested"]["refreshToken"] == "<REDACTED>"
    assert masked["body"]["nested"]["normalKey"] == "normalValue"


def test_endpoint_extraction_and_deduplication():
    """3. Проверка дедупликации эндпоинтов и извлечения путей из JS."""
    # Извлечение из минифицированного JS
    minified_js = '''
    const a="/api/player/init",b="/api/boss/attack",c="https://oldprison-prod.luckygem.online/api/guild/status";
    const img="assets/test.png",sound="assets/click.mp3";
    fetch("/api/auth/login",{method:"POST"});
    '''
    endpoints = extract_endpoints_from_js(minified_js)
    assert "/api/player/init" in endpoints
    assert "/api/boss/attack" in endpoints
    assert "/api/auth/login" in endpoints
    assert not any(ep.endswith(".png") for ep in endpoints)
    assert not any(ep.endswith(".mp3") for ep in endpoints)

    # Дедупликация сетевых запросов
    raw_log = [
        {
            "url": "https://oldprison-prod.luckygem.online/api/player/init?t=1",
            "method": "POST",
            "status": 200,
            "requestHeaders": {"Authorization": "Bearer token1"},
            "requestBody": {"foo": "bar"},
            "responseBody": {"success": True}
        },
        {
            "url": "https://oldprison-prod.luckygem.online/api/player/init?t=2",
            "method": "POST",
            "status": 200,
            "requestHeaders": {"Authorization": "Bearer token2"},
            "requestBody": {"foo": "bar"},
            "responseBody": {"success": True}
        },
        {
            "url": "https://telegram.org/assets/sticker.webp",
            "method": "GET",
            "status": 200
        }
    ]
    deduped = parse_network_log(raw_log)
    assert len(deduped) == 1
    assert ("POST", "/api/player/init") in deduped
    entry = deduped[("POST", "/api/player/init")]
    assert entry["requestHeaders"]["Authorization"] == "Bearer <REDACTED>"


def test_api_map_generation(tmp_path: Path):
    """4. Проверка генерации валидного api_map.md во временной директории."""
    out_file = tmp_path / "docs" / "api_map.md"

    confirmed = {
        ("POST", "/api/auth/login"): {
            "method": "POST",
            "url": "https://oldprison-prod.luckygem.online/api/auth/login",
            "path": "/api/auth/login",
            "status": 200,
            "requestHeaders": {"Content-Type": "application/json"},
            "requestBody": {"initData": "<REDACTED>"},
            "responseHeaders": {"Content-Type": "application/json"},
            "responseBody": {"success": True, "token": "<REDACTED>"}
        },
        ("POST", "/api/player/init"): {
            "method": "POST",
            "url": "https://oldprison-prod.luckygem.online/api/player/init",
            "path": "/api/player/init",
            "status": 200,
            "requestHeaders": {"Authorization": "Bearer <REDACTED>"},
            "requestBody": {},
            "responseHeaders": {"Content-Type": "application/json"},
            "responseBody": {"success": True, "userId": 12345}
        }
    }
    static_eps = {"/api/auth/login", "/api/player/init", "/api/boss/secret-boss"}

    content = generate_api_map(confirmed, static_eps, out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 0
    assert "## 1. АВТОРИЗАЦИЯ И ФОРМАТ СЕССИИ" in content
    assert "## 2. ПОДТВЕРЖДЕННЫЕ ЭНДПОИНТЫ ИЗ СЕТЕВОГО ЛОГА" in content
    assert "## 3. СТАТИЧЕСКИ ОБНАРУЖЕННЫЕ ЭНДПОИНТЫ И СОБЫТИЯ" in content
    assert "/api/boss/secret-boss" in content
    assert "<REDACTED>" in content
