import os
import re
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Set, Tuple, Optional
import jsbeautifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

IGNORED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.mp3', '.ogg', '.css')
IGNORED_DOMAINS = ('telegram.org', 't.me', 'google-analytics.com', 'googletagmanager.com', 'mc.yandex.ru', 'sentry.io')
SENSITIVE_KEYS = ('authorization', 'initdata', 'tgwebappdata', 'token', 'cookie', 'refreshtoken', 'accesstoken')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DUMP_DIR = PROJECT_ROOT / "raw_dump"
JS_BUNDLES_DIR = RAW_DUMP_DIR / "js_bundles"
NETWORK_LOG_FILE = RAW_DUMP_DIR / "network_log.json"
PARSED_JS_DIR = PROJECT_ROOT / "parsed_js"
DOCS_DIR = PROJECT_ROOT / "docs"
API_MAP_FILE = DOCS_DIR / "api_map.md"


def is_ignored_url(url: str) -> bool:
    """Проверяет, должен ли URL игнорироваться по домену или расширению."""
    if not url:
        return True
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or '').lower()
        path = (parsed.path or '').lower()
    except Exception:
        return True

    for domain in IGNORED_DOMAINS:
        if domain in hostname:
            return True

    for ext in IGNORED_EXTENSIONS:
        if path.endswith(ext):
            return True

    return False


def mask_sensitive_value(key: Any, value: Any) -> Any:
    """Маскирует чувствительные данные, сохраняя префикс 'Bearer ' при наличии."""
    if not isinstance(key, str):
        key = str(key)
    k_lower = key.lower().replace('-', '').replace('_', '')
    is_sensitive = any(sk in k_lower for sk in SENSITIVE_KEYS)
    if not is_sensitive:
        return value

    if isinstance(value, str):
        if value.lower().startswith('bearer '):
            return 'Bearer <REDACTED>'
        return '<REDACTED>'
    return '<REDACTED>'


def mask_dict_recursively(data: Any) -> Any:
    """Рекурсивно маскирует чувствительные ключи в словарях и списках."""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            k_clean = str(k).lower().replace('-', '').replace('_', '')
            if any(sk in k_clean for sk in SENSITIVE_KEYS):
                masked[k] = mask_sensitive_value(k, v)
            elif isinstance(v, (dict, list)):
                masked[k] = mask_dict_recursively(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_dict_recursively(item) for item in data]
    return data


def normalize_path(url: str) -> str:
    """Извлекает нормализованный путь эндпоинта без query-параметров."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        p = parsed.path or ""
        return p.split("?")[0]
    except Exception:
        return url.split("?")[0]


def beautify_js_file(src_path: Path, dst_path: Path):
    """Форматирует JS-файл через jsbeautifier и сохраняет по новому пути."""
    opts = jsbeautifier.default_options()
    opts.indent_size = 2
    opts.max_preserve_newlines = 2
    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()
    beautified = jsbeautifier.beautify(code, opts)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(beautified)


def extract_endpoints_from_js(js_code: str) -> Set[str]:
    """Статически извлекает строковые литералы маршрутов из JS-кода."""
    patterns = [
        r'["\'`](/(?:api|v1|v2|v3|auth|boss|player|guild|dungeons|events)/[a-zA-Z0-9_\-\./:]+)["\'`]',
        r'["\'`](https?://[^"\'`]+(?:api|oauth2|signin)[^"\'`]*)["\'`]'
    ]
    endpoints = set()
    for pattern in patterns:
        for match in re.findall(pattern, js_code):
            norm = match.split("?")[0]
            if not any(norm.lower().endswith(ext) for ext in IGNORED_EXTENSIONS + ('.atlas', '.json')):
                endpoints.add(norm)
    return endpoints


def parse_network_log(raw_log: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Дедуплицирует запросы по (METHOD, normalized_path).
    Фильтрует мусор и маскирует чувствительные данные.
    """
    deduped = {}
    for entry in raw_log:
        url = entry.get("url", "")
        if is_ignored_url(url):
            continue
        method = entry.get("method", "GET").upper()
        norm_path = normalize_path(url)
        if not norm_path:
            continue
        key = (method, norm_path)
        req_headers = mask_dict_recursively(entry.get("requestHeaders", {}))
        req_body = mask_dict_recursively(entry.get("requestBody", {}))
        resp_headers = mask_dict_recursively(entry.get("responseHeaders", {}))
        resp_body = mask_dict_recursively(entry.get("responseBody", {}))
        status = entry.get("status", 200)

        deduped[key] = {
            "method": method,
            "url": url,
            "path": norm_path,
            "status": status,
            "requestHeaders": req_headers,
            "requestBody": req_body,
            "responseHeaders": resp_headers,
            "responseBody": resp_body
        }
    return deduped


def generate_api_map(
    confirmed_endpoints: Dict[Tuple[str, str], Dict[str, Any]],
    all_static_endpoints: Set[str],
    output_file: Path
) -> str:
    """Генерирует чистый структурированный docs/api_map.md."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    confirmed_paths = {path for _, path in confirmed_endpoints.keys()}
    inactive_endpoints = sorted(all_static_endpoints - confirmed_paths)

    categories = {
        'Аутентификация и Сессия': [],
        'Игрок и Профиль': [],
        'Боссы и Боевая Система': [],
        'Гильдия (Кланы)': [],
        'Тюрьмы и Прогрессия': [],
        'Экипировка, Тату и Внешность': [],
        'Мини-игры и Активности': [],
        'События, Рейтинги и Подарки': [],
        'Подземелья (Dungeons)': [],
        'Прочие подтвержденные эндпоинты': []
    }

    for (method, path), data in sorted(confirmed_endpoints.items(), key=lambda x: (x[0][1], x[0][0])):
        p = path.lower()
        if 'auth' in p or 'signin' in p:
            cat = 'Аутентификация и Сессия'
        elif any(k in p for k in ('player', 'beard', 'summary')):
            cat = 'Игрок и Профиль'
        elif 'boss' in p:
            cat = 'Боссы и Боевая Система'
        elif 'guild' in p:
            cat = 'Гильдия (Кланы)'
        elif any(k in p for k in ('prison', 'baul', 'talent', 'master')):
            cat = 'Тюрьмы и Прогрессия'
        elif any(k in p for k in ('clothing', 'tattoo', 'camera', 'stashgear')):
            cat = 'Экипировка, Тату и Внешность'
        elif any(k in p for k in ('poker', 'wheel', 'dice', 'slots', 'yard')):
            cat = 'Мини-игры и Активности'
        elif any(k in p for k in ('event', 'weekly', 'gift', 'monthly', 'vpi', 'smuggling', 'luska', 'optwholesale')):
            cat = 'События, Рейтинги и Подарки'
        elif 'dungeon' in p:
            cat = 'Подземелья (Dungeons)'
        else:
            cat = 'Прочие подтвержденные эндпоинты'
        categories[cat].append((method, path, data))

    lines = [
        '# КАРТА API TELEGRAM MINI APP (OLD PRISON / ТЮРЯГА V3)\n',
        '> Документ сформирован автоматически на основе перехвата реального сетевого трафика и статического реверс-инжиниринга JS-бандлов игры.\n',
        '## 1. АВТОРИЗАЦИЯ И ФОРМАТ СЕССИИ\n',
        '### Механизм входа\n',
        'Клиент Telegram Mini App передает строку `initData` (валидированную ботом Telegram через HMAC-SHA256) в теле запроса к `POST /api/auth/login`.\n',
        '### Пример ответа авторизации:\n',
        '```json\n',
        '{\n',
        '  "userId": 9000000000466709,\n',
        '  "nickname": "Crazy4elovek",\n',
        '  "accessToken": "<REDACTED>",\n',
        '  "refreshToken": "<REDACTED>",\n',
        '  "accessExp": 1794968947\n',
        '}\n',
        '```\n',
        '### Аутентификация последующих запросов\n',
        'Все последующие запросы к API игры должны сопровождаться заголовком:\n',
        '`Authorization: Bearer <REDACTED>`\n\n',
        'Обязательные клиентские заголовки:\n',
        '- `X-Language: ru` (код языка из `initDataUnsafe.user.language_code`)\n',
        '- `X-Country: RU` (регион пользователя)\n',
        '- `X-Platform: web` (платформа запуска: `web`, `android`, `ios`)\n',
        '- `Content-Type: application/json`\n\n',
        '---\n',
        '## 2. ПОДТВЕРЖДЕННЫЕ ЭНДПОИНТЫ ИЗ СЕТЕВОГО ЛОГА\n'
    ]

    for cat_name, items in categories.items():
        if not items:
            continue
        lines.append(f'### 📂 {cat_name}\n')
        for method, path, data in items:
            status = data.get('status', 200)
            lines.append(f'#### `{method}` {path}\n')
            lines.append(f'- **Статус ответа:** `{status}`\n')
            lines.append(f'- **Полный URL:** `{data.get("url", path)}`\n')
            lines.append('- **Заголовки запроса:**\n```json\n' + json.dumps(data.get('requestHeaders', {}), ensure_ascii=False, indent=2) + '\n```\n')
            req_body = data.get('requestBody')
            if req_body:
                lines.append('- **Тело запроса:**\n```json\n' + json.dumps(req_body, ensure_ascii=False, indent=2) + '\n```\n')
            else:
                lines.append('- **Тело запроса:** *(пусто)*\n')
            resp_body = data.get('responseBody')
            if resp_body:
                lines.append('- **Пример ответа сервера:**\n```json\n' + json.dumps(resp_body, ensure_ascii=False, indent=2) + '\n```\n')
            lines.append('\n---\n')

    lines.append('## 3. СТАТИЧЕСКИ ОБНАРУЖЕННЫЕ ЭНДПОИНТЫ И СОБЫТИЯ (ИЗ JS-КОДА)\n')
    lines.append('Данные эндпоинты извлечены из модулей маршрутизации игры (`auth.js` и `bundle.js`), но не вызывались в базовой сессии (требуют повышенного уровня, специальных событий или действий игрока):\n\n')
    lines.append('| Метод (предположительный) | Эндпоинт | Категория / Описание |\n')
    lines.append('| :--- | :--- | :--- |\n')

    for ep in inactive_endpoints:
        ep_lower = ep.lower()
        method_guess = "POST" if any(w in ep_lower for w in ('buy', 'open', 'claim', 'spin', 'roll', 'hit', 'start', 'finish', 'update', 'set', 'collect', 'perform')) else "GET"
        desc = "Служебный маршрут"
        if "doorbreaker" in ep_lower:
            desc = "Рейдовое событие / Взлом дверей"
        elif "battle-train" in ep_lower:
            desc = "Боевой поезд"
        elif "lets-cook" in ep_lower:
            desc = "Ивентовая мини-игра 'Let's Cook'"
        elif "tomb-pvp" in ep_lower:
            desc = "PvP в гробнице"
        elif "shodnyak" in ep_lower:
            desc = "Сходняк гильдии"
        elif "cheat" in ep_lower:
            desc = "Отладочные методы / читы"
        elif "dungeon" in ep_lower:
            desc = "Действия в подземелье"
        elif "boss" in ep_lower:
            desc = "Бой с боссом"
        elif "realtime" in ep_lower or "sse" in ep_lower:
            desc = "Server-Sent Events (SSE) поток кошелька"
        elif "kolsik" in ep_lower:
            desc = "Кольщик (нанесение татуировок)"
        lines.append(f'| `{method_guess}` | `{ep}` | {desc} |\n')

    lines.append('\n## 4. СВОДНЫЕ ТРЕБОВАНИЯ К БОТУ-КЛИЕНТУ\n')
    lines.append('1. **Хранение состояния:** Сессионные токены `accessToken` и `refreshToken` должны сохраняться в локальную базу данных (SQLite).\n')
    lines.append('2. **Ротация токенов:** При получении `401 Unauthorized` выполнять автоматический запрос к `POST /api/auth/refresh` или пересоздавать сессию через `Telethon` с получением нового `initData`.\n')
    lines.append('3. **Имитация мобильного клиента:** Отправлять заголовки `X-Platform: android`, `X-Language: ru`, реальный User-Agent Chrome/Android для маскировки бота под настоящего игрока.\n')

    content = "".join(lines)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def main():
    logging.info("=== Запуск скрипта parse_dump.py ===")
    if JS_BUNDLES_DIR.exists():
        for js_file in JS_BUNDLES_DIR.glob("*.js"):
            dst_file = PARSED_JS_DIR / js_file.name
            logging.info(f"Форматирование {js_file.name} -> {dst_file.name}...")
            beautify_js_file(js_file, dst_file)
    else:
        logging.warning(f"Директория {JS_BUNDLES_DIR} не найдена.")

    all_static_endpoints = set()
    for parsed_file in PARSED_JS_DIR.glob("*.js"):
        logging.info(f"Поиск маршрутов в {parsed_file.name}...")
        with open(parsed_file, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        found = extract_endpoints_from_js(code)
        logging.info(f"Найдено {len(found)} эндпоинтов в {parsed_file.name}")
        all_static_endpoints.update(found)

    confirmed_endpoints = {}
    if NETWORK_LOG_FILE.exists():
        logging.info(f"Чтение сетевого лога из {NETWORK_LOG_FILE}...")
        with open(NETWORK_LOG_FILE, "r", encoding="utf-8") as f:
            raw_log = json.load(f)
        confirmed_endpoints = parse_network_log(raw_log)
        logging.info(f"Дедуплицировано {len(confirmed_endpoints)} уникальных эндпоинтов.")
    else:
        logging.warning(f"Файл {NETWORK_LOG_FILE} не найден.")

    logging.info(f"Генерация {API_MAP_FILE}...")
    generate_api_map(confirmed_endpoints, all_static_endpoints, API_MAP_FILE)
    logging.info("Генерация docs/api_map.md успешно завершена.")


if __name__ == "__main__":
    main()
