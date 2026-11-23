"""
Тесты целостности, полноты и безопасности эталонного архива @pro_prison_bot.
"""

import json
import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = PROJECT_ROOT / "reference_archive" / "pro_prison_bot"
DOCS_DIR = PROJECT_ROOT / "docs"


def test_archive_structure_and_documentation():
    """Проверка наличия всех ключевых файлов документации и манифеста."""
    blueprint = DOCS_DIR / "pro_prison_bot_blueprint.md"
    assert blueprint.is_file(), f"Файл {blueprint} не найден"
    assert len(blueprint.read_text(encoding="utf-8").strip()) > 500

    required_md_files = [
        "INDEX.md",
        "ARCHITECTURE_AND_FEATURES.md",
        "API_CONTRACTS.md",
        "AUTOMATION_LOGIC.md",
        "UI_CATALOG.md",
        "GAP_ANALYSIS.md",
    ]

    for fname in required_md_files:
        p = ARCHIVE_ROOT / fname
        assert p.is_file(), f"Документ {fname} не найден в {ARCHIVE_ROOT}"
        content = p.read_text(encoding="utf-8").strip()
        assert len(content) > 500, f"Документ {fname} пуст или слишком короткий ({len(content)} символов)"
        assert content.startswith("#"), f"Документ {fname} должен начинаться с заголовка H1"

    manifest_file = ARCHIVE_ROOT / "manifest.json"
    assert manifest_file.is_file(), "manifest.json не найден"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest.get("version") == "1.0.0"
    assert manifest.get("totalFiles", 0) > 100
    assert len(manifest.get("files", [])) > 100


def test_code_dump_completeness():
    """Проверка полноты дампа кода фронтенда (raw_js, parsed_js, css)."""
    raw_dir = ARCHIVE_ROOT / "raw_js"
    parsed_dir = ARCHIVE_ROOT / "parsed_js"
    css_dir = ARCHIVE_ROOT / "css"

    assert raw_dir.is_dir()
    assert parsed_dir.is_dir()
    assert css_dir.is_dir()

    raw_files = list(raw_dir.glob("*.js"))
    parsed_files = list(parsed_dir.glob("*.js"))
    css_files = list(css_dir.glob("*.css"))

    assert len(raw_files) >= 50, f"Слишком мало raw JS-файлов: {len(raw_files)}"
    assert len(parsed_files) >= 50, f"Слишком мало parsed JS-файлов: {len(parsed_files)}"
    assert len(css_files) >= 1, "CSS файлы не найдены"

    # Проверка, что parsed_js действительно отформатирован (содержит переносы строк)
    for sample in parsed_files[:10]:
        lines = sample.read_text(encoding="utf-8").splitlines()
        assert len(lines) > 5, f"Файл {sample.name} не отформатирован (всего {len(lines)} строк)"

    # Проверка CSS переменных
    vars_json = css_dir / "variables.json"
    assert vars_json.is_file()
    with open(vars_json, "r", encoding="utf-8") as f:
        vars_data = json.load(f)
    assert len(vars_data) >= 50, f"Мало CSS-переменных: {len(vars_data)}"


def test_json_and_media_validity():
    """Проверка валидности всех JSON-файлов и сигнатур скриншотов."""
    snapshots_dir = ARCHIVE_ROOT / "api_snapshots"
    ui_dom_dir = ARCHIVE_ROOT / "ui_dom"
    screenshots_dir = ARCHIVE_ROOT / "screenshots"

    assert snapshots_dir.is_dir()
    assert ui_dom_dir.is_dir()
    assert screenshots_dir.is_dir()

    # Проверка всех JSON-файлов
    for jf in ARCHIVE_ROOT.rglob("*.json"):
        with open(jf, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                assert data is not None
            except Exception as e:
                pytest.fail(f"Ошибка парсинга JSON в {jf}: {e}")

    # Проверка ключевых файлов API
    registry_file = snapshots_dir / "api_registry.json"
    assert registry_file.is_file()
    with open(registry_file, "r", encoding="utf-8") as f:
        registry = json.load(f)
    assert len(registry) >= 100, f"Реестр API содержит мало эндпоинтов: {len(registry)}"

    storage_file = snapshots_dir / "storage_schema.json"
    assert storage_file.is_file()
    with open(storage_file, "r", encoding="utf-8") as f:
        storage = json.load(f)
    assert "localStorageKeys" in storage

    # Проверка скриншотов: не пустые и валидная сигнатура PNG (\x89PNG\r\n\x1a\n)
    screenshots = list(screenshots_dir.glob("*.png"))
    assert len(screenshots) >= 15, f"Слишком мало скриншотов: {len(screenshots)}"
    png_magic = b"\x89PNG\r\n\x1a\n"

    for shot in screenshots:
        assert shot.stat().st_size > 5000, f"Скриншот {shot.name} поврежден или слишком мал"
        with open(shot, "rb") as f:
            header = f.read(8)
            assert header == png_magic, f"Файл {shot.name} не является валидным PNG (сигнатура: {header})"


def test_zero_secret_leaks():
    """Строгий аудит безопасности: проверка отсутствия незамаскированных токенов, JWT и хешей."""
    jwt_pattern = re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}")
    tg_data_pattern = re.compile(r"tgWebAppData=")
    query_id_pattern = re.compile(r"query_id=[A-Za-z0-9_\-]+")
    bearer_real_pattern = re.compile(r"Bearer\s+(?!<REDACTED)[A-Za-z0-9_\-\.]{25,}", re.IGNORECASE)

    text_extensions = {".json", ".html", ".md", ".txt", ".css"}
    checked_files = 0

    targets = list(ARCHIVE_ROOT.rglob("*")) + [DOCS_DIR / "pro_prison_bot_blueprint.md"]

    for p in targets:
        if p.is_file() and p.suffix.lower() in text_extensions:
            # Исключаем файлы, являющиеся исходным минифицированным бандлом JS (в них могут быть совпадения по коду парсера)
            if "raw_js" in p.parts or "parsed_js" in p.parts:
                continue

            checked_files += 1
            content = p.read_text(encoding="utf-8")

            assert not jwt_pattern.search(content), f"Обнаружена утечка реального JWT в {p}"
            assert not tg_data_pattern.search(content), f"Обнаружена утечка tgWebAppData= в {p}"
            assert not query_id_pattern.search(content), f"Обнаружена утечка query_id= в {p}"
            assert not bearer_real_pattern.search(content), f"Обнаружена утечка реального Bearer-токена в {p}"

    assert checked_files >= 20, f"Проверено слишком мало текстовых файлов: {checked_files}"
