"""
Скрипт полного извлечения, архивации и документирования референсного бота @pro_prison_bot
для автономной офлайн-работы.
"""

import asyncio
import base64
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

import jsbeautifier
import websockets

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = PROJECT_ROOT / "reference_archive" / "pro_prison_bot"
RAW_JS_DIR = ARCHIVE_ROOT / "raw_js"
PARSED_JS_DIR = ARCHIVE_ROOT / "parsed_js"
CSS_DIR = ARCHIVE_ROOT / "css"
SNAPSHOTS_DIR = ARCHIVE_ROOT / "api_snapshots"
UI_DOM_DIR = ARCHIVE_ROOT / "ui_dom"
SCREENSHOTS_DIR = ARCHIVE_ROOT / "screenshots"
ASSETS_DIR = ARCHIVE_ROOT / "assets"
DOCS_DIR = PROJECT_ROOT / "docs"

for d in [ARCHIVE_ROOT, RAW_JS_DIR, PARSED_JS_DIR, CSS_DIR, SNAPSHOTS_DIR, UI_DOM_DIR, SCREENSHOTS_DIR, ASSETS_DIR, DOCS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Регулярные выражения для санитизации секретов
SECRET_PATTERNS = [
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "<REDACTED_JWT>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE), "Bearer <REDACTED_TOKEN>"),
    (re.compile(r"tgWebAppData=[^&\s\"'\\]+"), "<REDACTED_TG_DATA>"),
    (re.compile(r"hash=[a-f0-9]{32,64}", re.IGNORECASE), "<REDACTED_HASH>"),
    (re.compile(r"signature=[A-Za-z0-9_\-]{32,}", re.IGNORECASE), "<REDACTED_SIGNATURE>"),
    (re.compile(r"auth_date=\d+"), "<REDACTED_AUTH_DATE>"),
    (re.compile(r"query_id=[A-Za-z0-9_\-]+"), "<REDACTED_QUERY_ID>"),
    (re.compile(r"chat_instance=[^&\s\"'\\]+"), "<REDACTED_CHAT_INSTANCE>"),
    (re.compile(r"user(%3D|=)%257B.*?%257D"), "<REDACTED_USER>"),
    (re.compile(r"Cookie:[^\r\n]+", re.IGNORECASE), "Cookie: <REDACTED_COOKIE>"),
    (re.compile(r"\"cookie\"\s*:\s*\"[^\"]+\"", re.IGNORECASE), '"cookie": "<REDACTED_COOKIE>"'),
    (re.compile(r"\"token\"\s*:\s*\"[^\"]+\""), '"token": "<REDACTED_TOKEN>"'),
    (re.compile(r"\"accessToken\"\s*:\s*\"[^\"]+\""), '"accessToken": "<REDACTED_TOKEN>"'),
    (re.compile(r"\"refreshToken\"\s*:\s*\"[^\"]+\""), '"refreshToken": "<REDACTED_TOKEN>"'),
    (re.compile(r"\"session_id\"\s*:\s*\"[^\"]+\""), '"session_id": "<REDACTED_SESSION>"'),
]


def sanitize_text(text: str) -> str:
    """Санитизирует секретные токены, хеши и подписи в тексте."""
    if not text:
        return text
    res = text
    for pattern, repl in SECRET_PATTERNS:
        res = pattern.sub(repl, res)
    return res


def sanitize_json(obj: Any) -> Any:
    """Рекурсивная санитизация словарей и списков."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            lower_k = k.lower()
            if any(s in lower_k for s in ["token", "secret", "auth", "hash", "signature", "cookie", "initdata"]):
                sanitized[k] = "<REDACTED>"
            else:
                sanitized[k] = sanitize_json(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_json(x) for x in obj]
    elif isinstance(obj, str):
        return sanitize_text(obj)
    return obj


def _beautify_worker(item: Tuple[str, str, str]) -> bool:
    """Воркер для многопроцессорного форматирования JS-файла."""
    raw_path_str, parsed_path_str, _ = item
    raw_p = Path(raw_path_str)
    parsed_p = Path(parsed_path_str)
    try:
        content = raw_p.read_text(encoding="utf-8")
        opts = jsbeautifier.default_options()
        opts.indent_size = 2
        opts.wrap_line_length = 120
        beautified = jsbeautifier.beautify(content, opts)
        parsed_p.write_text(beautified, encoding="utf-8")
        return True
    except Exception:
        try:
            parsed_p.write_text(raw_p.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
        return False


class BotCDPClient:
    """Клиент для общения с Chrome DevTools Protocol."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=100 * 1024 * 1024)

    async def close(self):
        if self.ws:
            await self.ws.close()

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._msg_id += 1
        mid = self._msg_id
        payload = {"id": mid, "method": method}
        if params:
            payload["params"] = params
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP error in {method}: {msg['error']}")
                return msg.get("result", {})

    async def eval_js(self, expression: str, await_promise: bool = True) -> Any:
        res = await self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True
        })
        return res.get("result", {}).get("value")

    async def capture_screenshot(self, clip: Optional[Dict[str, Any]] = None) -> bytes:
        params: Dict[str, Any] = {"format": "png"}
        if clip:
            params["clip"] = clip
        res = await self.call("Page.captureScreenshot", params)
        b64 = res.get("data", "")
        return base64.b64decode(b64)


def find_targets() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    req = urllib.request.urlopen("http://127.0.0.1:9222/json/list")
    targets = json.loads(req.read().decode("utf-8"))
    iframe_target = None
    page_target = None
    for t in targets:
        if "pro-prison-bot" in t.get("url", ""):
            iframe_target = t
        if t.get("type") == "page" and "telegram.org" in t.get("url", ""):
            page_target = t

    if not iframe_target:
        raise RuntimeError("Iframe pro-prison-bot не найден в Chrome на 127.0.0.1:9222!")
    if not page_target:
        raise RuntimeError("Top-level страница Telegram Web не найдена в Chrome на 127.0.0.1:9222!")

    return iframe_target, page_target


async def run_archive():
    iframe_target, page_target = find_targets()
    print(f"[*] Подключение к iframe: {iframe_target['webSocketDebuggerUrl']}")
    print(f"[*] Подключение к top-level page: {page_target['webSocketDebuggerUrl']}")

    iframe_client = BotCDPClient(iframe_target["webSocketDebuggerUrl"])
    page_client = BotCDPClient(page_target["webSocketDebuggerUrl"])
    await iframe_client.connect()
    await page_client.connect()

    try:
        # ====================================================================
        # ЭТАП 1: ИЗВЛЕЧЕНИЕ КОДА ФРОНТЕНДА (HTML, ЧАНКИ, CSS, ПЕРЕМЕННЫЕ)
        # ====================================================================
        print("\n--- ЭТАП 1: Извлечение фронтенд-кода и манифестов ---")

        # 1.1. HTML и встроенные Next.js данные
        html_data = await iframe_client.eval_js("""
        (() => {
            return {
                html: document.documentElement.outerHTML,
                nextData: window.__NEXT_DATA__ || null,
                nextF: (typeof self !== 'undefined' && self.__next_f) ? self.__next_f : null,
                url: window.location.href,
                title: document.title
            };
        })()
        """)
        clean_html = sanitize_text(html_data.get("html", ""))
        (ARCHIVE_ROOT / "index.html").write_text(clean_html, encoding="utf-8")
        if html_data.get("nextData"):
            clean_next = sanitize_json(html_data["nextData"])
            (ARCHIVE_ROOT / "next_data.json").write_text(json.dumps(clean_next, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[+] Сохранен index.html и next_data.json")

        # 1.2. CSS файлы и computed CSS переменные (:root)
        css_data = await iframe_client.eval_js("""
        (async () => {
            const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href);
            const cssContents = {};
            for (const href of links) {
                try {
                    const r = await fetch(href);
                    cssContents[href] = await r.text();
                } catch (e) {
                    cssContents[href] = null;
                }
            }
            const style = getComputedStyle(document.documentElement);
            const vars = {};
            for (let i = 0; i < style.length; i++) {
                const prop = style[i];
                if (prop.startsWith('--')) {
                    vars[prop] = style.getPropertyValue(prop).trim();
                }
            }
            return { cssContents, vars };
        })()
        """)
        for href, css_text in css_data.get("cssContents", {}).items():
            if css_text:
                fname = Path(href.split("?")[0]).name
                (CSS_DIR / fname).write_text(css_text, encoding="utf-8")
                print(f"[+] Сохранен CSS: {fname} ({len(css_text)} байт)")

        css_vars = css_data.get("vars", {})
        (CSS_DIR / "variables.json").write_text(json.dumps(css_vars, ensure_ascii=False, indent=2), encoding="utf-8")
        css_vars_lines = [":root {"] + [f"  {k}: {v};" for k, v in sorted(css_vars.items())] + ["}"]
        (CSS_DIR / "variables.css").write_text("\n".join(css_vars_lines), encoding="utf-8")
        print(f"[+] Сохранены CSS переменные (:root): {len(css_vars)} шт.")

        # 1.3. Список всех JS-чанков
        manifest_data = await iframe_client.eval_js("""
        (async () => {
            let buildManifestText = "";
            let ssgText = "";
            let clientMiddlewareText = "";

            try {
                const bRes = await fetch('/_next/static/FmH16ITs5FViI3gHxEMSK/_buildManifest.js');
                buildManifestText = await bRes.text();
            } catch (e) {}

            try {
                const sRes = await fetch('/_next/static/FmH16ITs5FViI3gHxEMSK/_ssgManifest.js');
                ssgText = await sRes.text();
            } catch (e) {}

            try {
                const cRes = await fetch('/_next/static/FmH16ITs5FViI3gHxEMSK/_clientMiddlewareManifest.js');
                clientMiddlewareText = await cRes.text();
            } catch (e) {}

            // Извлекаем все .js пути из манифеста
            const allChunks = new Set();
            const chunkRegex = /["'](static\\/chunks\\/[^"']+\\.js)["']/g;
            let match;
            while ((match = chunkRegex.exec(buildManifestText)) !== null) {
                allChunks.add(match[1]);
            }

            // Добавляем скрипты из DOM
            const domScripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
            for (const s of domScripts) {
                if (s.includes('/_next/')) {
                    const rel = s.split('/_next/')[1].split('?')[0];
                    if (rel.endsWith('.js')) allChunks.add(rel);
                }
            }

            // Добавляем ресурсы из performance
            const perf = performance.getEntriesByType('resource').map(r => r.name);
            for (const p of perf) {
                if (p.includes('/_next/')) {
                    const rel = p.split('/_next/')[1].split('?')[0];
                    if (rel.endsWith('.js')) allChunks.add(rel);
                }
            }

            return {
                buildManifestText,
                ssgText,
                clientMiddlewareText,
                chunks: Array.from(allChunks)
            };
        })()
        """)

        if manifest_data.get("buildManifestText"):
            (RAW_JS_DIR / "_buildManifest.js").write_text(manifest_data["buildManifestText"], encoding="utf-8")
        if manifest_data.get("ssgText"):
            (RAW_JS_DIR / "_ssgManifest.js").write_text(manifest_data["ssgText"], encoding="utf-8")
        if manifest_data.get("clientMiddlewareText"):
            (RAW_JS_DIR / "_clientMiddlewareManifest.js").write_text(manifest_data["clientMiddlewareText"], encoding="utf-8")

        all_chunks = manifest_data["chunks"]
        total_chunks = len(all_chunks)
        print(f"[+] Обнаружено {total_chunks} валидных JS-чанков")

        # 1.4. Скачивание JS-чанков пачками через контекст браузера
        batch_size = 40
        print(f"[*] Скачивание {total_chunks} JS-чанков пакетами по {batch_size}...")

        downloaded_count = 0
        tasks_for_beautify = []

        for i in range(0, total_chunks, batch_size):
            chunk_batch = all_chunks[i:i + batch_size]
            js_batch_fetch = f"""
            (async () => {{
                const batch = {json.dumps(chunk_batch)};
                const results = await Promise.all(batch.map(async rel => {{
                    try {{
                        const r = await fetch('/_next/' + rel);
                        if (r.ok) {{
                            return {{ rel, content: await r.text() }};
                        }}
                    }} catch (e) {{}}
                    return {{ rel, content: null }};
                }}));
                return results;
            }})()
            """
            batch_res = await iframe_client.eval_js(js_batch_fetch)
            for item in batch_res:
                rel = item["rel"]
                content = item["content"]
                if content:
                    fname = Path(rel).name
                    raw_file = RAW_JS_DIR / fname
                    raw_file.write_text(content, encoding="utf-8")
                    parsed_file = PARSED_JS_DIR / fname
                    tasks_for_beautify.append((str(raw_file), str(parsed_file), fname))
                    downloaded_count += 1

            pct = int(((i + len(chunk_batch)) / total_chunks) * 100)
            print(f"  -> Загружено {downloaded_count}/{total_chunks} чанков ({pct}%)...", end="\r")

        print(f"\n[+] Загружено {downloaded_count} чанков. Запуск параллельного форматирования (14 ядер)...")
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=14) as executor:
            results = list(executor.map(_beautify_worker, tasks_for_beautify))
        formatted_count = sum(1 for r in results if r)
        print(f"[+] Отформатировано {formatted_count}/{len(tasks_for_beautify)} JS-чанков в parsed_js/ за {time.time()-t0:.1f} сек!")

        # ====================================================================
        # ЭТАП 2: ИНЖЕКЦИЯ СЕТЕВОГО РЕКОРДЕРА И БЕЗОПАСНЫЙ READ-ONLY ОБХОД UI
        # ====================================================================
        print("\n--- ЭТАП 2: Безопасный Read-Only обход экранов, снятие DOM и скриншотов ---")

        # 2.1. Инжекция перехватчика fetch в iframe
        await iframe_client.eval_js("""
        (() => {
            if (window.__ARCHIVE_NET_LOG) return;
            window.__ARCHIVE_NET_LOG = [];
            const origFetch = window.fetch;
            window.fetch = async function(...args) {
                const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
                const method = args[1]?.method || 'GET';
                const body = args[1]?.body ? String(args[1].body).slice(0, 1000) : null;
                const res = await origFetch.apply(this, args);
                try {
                    if (url.includes('/api/')) {
                        const clone = res.clone();
                        const text = await clone.text();
                        window.__ARCHIVE_NET_LOG.push({
                            url,
                            method,
                            status: res.status,
                            reqBody: body,
                            resText: text,
                            timestamp: Date.now()
                        });
                    }
                } catch (e) {}
                return res;
            };
        })()
        """)
        print("[+] Пассивный перехватчик сети инжектирован")

        # 2.2. Функция снятия скриншота через top-level page с обрезкой по iframe
        async def capture_screen(name: str):
            await asyncio.sleep(0.7)

            # Вычисляем rect iframe в родительской странице
            js_rect = """
            (() => {
                const iframe = document.querySelector('iframe');
                if (!iframe) return null;
                const r = iframe.getBoundingClientRect();
                return { x: r.x, y: r.y, width: r.width, height: r.height };
            })()
            """
            rect = await page_client.eval_js(js_rect)
            clip = None
            if rect and rect.get("width") > 0:
                clip = {
                    "x": rect["x"],
                    "y": rect["y"],
                    "width": rect["width"],
                    "height": rect["height"],
                    "scale": 1
                }

            png_bytes = await page_client.capture_screenshot(clip=clip)
            shot_file = SCREENSHOTS_DIR / f"{name}.png"
            shot_file.write_bytes(png_bytes)

            dom_summary = await iframe_client.eval_js("""
            (() => {
                const title = document.title;
                const url = window.location.href;
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, .text-lg, .font-semibold, .font-bold'))
                    .map(h => h.innerText.trim()).filter(Boolean);
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
                    .map(b => ({
                        text: b.innerText.trim().replace(/\\s+/g, ' '),
                        aria: b.getAttribute('aria-label') || '',
                        disabled: b.disabled || b.getAttribute('aria-disabled') === 'true'
                    })).filter(b => b.text || b.aria);
                const inputs = Array.from(document.querySelectorAll('input, select, textarea'))
                    .map(inp => ({
                        type: inp.type || inp.tagName.toLowerCase(),
                        name: inp.name || '',
                        value: inp.type === 'password' ? '<REDACTED>' : inp.value,
                        placeholder: inp.placeholder || '',
                        checked: inp.checked,
                        min: inp.min || '',
                        max: inp.max || ''
                    }));
                const badges = Array.from(document.querySelectorAll('[class*="badge"], [class*="chip"], [class*="pill"]'))
                    .map(b => b.innerText.trim()).filter(Boolean);
                return {
                    title,
                    url,
                    headings: Array.from(new Set(headings)),
                    buttonsCount: buttons.length,
                    sampleButtons: buttons.slice(0, 25),
                    inputs,
                    badges: Array.from(new Set(badges)).slice(0, 30)
                };
            })()
            """)
            clean_dom = sanitize_json(dom_summary)
            (UI_DOM_DIR / f"{name}.json").write_text(json.dumps(clean_dom, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[+] Экран '{name}': скриншот ({len(png_bytes)//1024} КБ), DOM ({len(dom_summary.get('headings', []))} заголовков, {dom_summary.get('buttonsCount')} кнопок)")

        # Снимаем 01_home
        await capture_screen("01_home")

        # 2.3. Полный список всех разделов и подразделов для Read-Only обхода
        target_sections = [
            ("02_news_raids", "Новости и Рейды"),
            ("03_combo", "Комбо"),
            ("04_bosses", "Боссы"),
            ("05_prisons", "Ходки"),
            ("06_zaruby", "Зарубы"),
            ("07_delyugi", "Делюги"),
            ("08_events_main", "События"),
            ("09_events_changer", "Меняла"),
            ("10_events_settings", "Настройка событий"),
            ("11_bariga", "Барыга"),
            ("12_friends", "Друзья"),
            ("13_brigade", "Бригада"),
            ("14_games_main", "Игры"),
            ("15_games_katala", "Катала"),
            ("16_games_poker", "Покер"),
            ("17_games_wheel", "Колесо фортуны"),
            ("18_games_fartovy", "Фартовый"),
            ("19_games_dice", "Кости"),
            ("20_damage_calc", "Калькулятор урона"),
            ("21_wardrobe", "Тату и Шмот"),
            ("22_giveaways", "Розыгрыши"),
            ("23_subscription", "Подписка"),
            ("24_settings", "Настройки"),
            ("25_home_return", "Главная"),
        ]

        for screen_key, menu_label in target_sections:
            print(f"[*] Переход к экрану '{menu_label}' ({screen_key})...")
            nav_result = await iframe_client.eval_js(f"""
            (async () => {{
                let dialog = document.querySelector('[role="dialog"]');
                if (!dialog) {{
                    const btn = document.querySelector('button .lucide-menu')?.closest('button') || document.querySelector('button.inline-flex');
                    if (btn) btn.click();
                    await new Promise(r => setTimeout(r, 400));
                    dialog = document.querySelector('[role="dialog"]');
                }}

                if (!dialog) {{
                    return {{ success: false, reason: "dialog not found" }};
                }}

                const items = Array.from(dialog.querySelectorAll('button, [role="button"], a')).filter(el => {{
                    const t = el.innerText.trim();
                    return t.includes('{menu_label}');
                }});

                if (items.length > 0) {{
                    items[0].click();
                    return {{ success: true, text: items[0].innerText.trim() }};
                }}

                return {{ success: false, reason: "item not found" }};
            }})()
            """)

            if nav_result and nav_result.get("success"):
                await asyncio.sleep(1.0)
                await capture_screen(screen_key)
            else:
                print(f"[-] Не удалось открыть пункт '{menu_label}': {nav_result}")

        # 2.4. Сбор и сохранение перехваченных сетевых запросов
        net_logs = await iframe_client.eval_js("window.__ARCHIVE_NET_LOG || []")
        print(f"\n[+] Перехвачено сетевых API-запросов: {len(net_logs)}")
        summary_endpoints = []
        for idx, log in enumerate(net_logs):
            url = log.get("url", "")
            method = log.get("method", "GET")
            status = log.get("status", 200)
            res_text = log.get("resText", "")
            clean_url = sanitize_text(url)
            endpoint_name = clean_url.split("?")[0].replace("https://pro-prison-bot.003220.xyz/api/", "").replace("/", "_")
            if not endpoint_name or endpoint_name == clean_url:
                endpoint_name = f"req_{idx}_{method}"

            try:
                parsed_json = json.loads(res_text)
                clean_json = sanitize_json(parsed_json)
                (SNAPSHOTS_DIR / f"{endpoint_name}.json").write_text(json.dumps(clean_json, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                clean_text = sanitize_text(res_text)
                (SNAPSHOTS_DIR / f"{endpoint_name}.txt").write_text(clean_text, encoding="utf-8")

            summary_endpoints.append({
                "method": method,
                "url": clean_url,
                "status": status,
                "snapshotFile": f"{endpoint_name}.json"
            })

        (SNAPSHOTS_DIR / "network_summary.json").write_text(json.dumps(summary_endpoints, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] Сохранены санитизированные снимки API в api_snapshots/ ({len(summary_endpoints)} записей)")

        # 2.5. Схема хранилищ (localStorage, sessionStorage, IndexedDB, Cache API)
        storage_info = await iframe_client.eval_js("""
        (async () => {
            const lsKeys = Object.keys(localStorage);
            const ssKeys = Object.keys(sessionStorage);
            let idbDatabases = [];
            try {
                if (window.indexedDB && window.indexedDB.databases) {
                    idbDatabases = (await window.indexedDB.databases()).map(db => ({ name: db.name, version: db.version }));
                }
            } catch (e) {}
            let cacheNames = [];
            try {
                if ('caches' in window) {
                    cacheNames = await caches.keys();
                }
            } catch (e) {}

            return {
                localStorageKeys: lsKeys,
                sessionStorageKeys: ssKeys,
                indexedDB: idbDatabases,
                cacheAPI: cacheNames
            };
        })()
        """)
        clean_storage = sanitize_json(storage_info)
        (SNAPSHOTS_DIR / "storage_schema.json").write_text(json.dumps(clean_storage, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[+] Сохранена схема клиентских хранилищ в storage_schema.json")

        # 2.6. Скачивание уникальных ассетов бота (/game-icons/* и логотипы)
        assets_urls = await iframe_client.eval_js("""
        (() => {
            const urls = performance.getEntriesByType('resource').map(r => r.name);
            const domImgs = Array.from(document.querySelectorAll('img')).map(i => i.src);
            const set = new Set([...urls, ...domImgs]);
            return Array.from(set).filter(u => u.includes('003220.xyz') && (u.includes('/game-icons/') || u.includes('/icons/') || u.includes('/assets/') || u.endsWith('.png') || u.endsWith('.webp') || u.endsWith('.svg')));
        })()
        """)
        print(f"[*] Скачивание {len(assets_urls)} уникальных ассетов бота...")
        for u in assets_urls:
            try:
                fname = Path(u.split("?")[0]).name
                if not fname:
                    continue
                b64_data = await iframe_client.eval_js(f"""
                (async () => {{
                    try {{
                        const r = await fetch('{u}');
                        if (!r.ok) return null;
                        const b = await r.blob();
                        return new Promise(res => {{
                            const fr = new FileReader();
                            fr.onload = () => res(fr.result.split(',')[1]);
                            fr.readAsDataURL(b);
                        }});
                    }} catch (e) {{
                        return null;
                    }}
                }})()
                """)
                if b64_data:
                    raw_bytes = base64.b64decode(b64_data)
                    (ASSETS_DIR / fname).write_bytes(raw_bytes)
            except Exception:
                pass
        print(f"[+] Скачаны ассеты в reference_archive/pro_prison_bot/assets/")

        # ====================================================================
        # ЭТАП 3: СТАТИЧЕСКИЙ АНАЛИЗ JS И ПОЛНЫЙ РЕЕСТР ВСЕХ API МАРШРУТОВ
        # ====================================================================
        print("\n--- ЭТАП 3: Статический парсинг JS-чанков и сбор всех API-маршрутов ---")
        api_pattern = re.compile(r"['\"`](/api/[a-zA-Z0-9_\-/]+)['\"`]")
        method_pattern = re.compile(r"method\s*:\s*['\"`](GET|POST|PUT|PATCH|DELETE)['\"`]", re.IGNORECASE)

        route_details = {}
        for js_file in PARSED_JS_DIR.glob("*.js"):
            try:
                content = js_file.read_text(encoding="utf-8")
                matches = api_pattern.findall(content)
                for route in matches:
                    if route not in route_details:
                        route_details[route] = {
                            "route": route,
                            "files": [js_file.name],
                            "methods": set()
                        }
                    else:
                        if js_file.name not in route_details[route]["files"]:
                            route_details[route]["files"].append(js_file.name)

                for line in content.splitlines():
                    if "/api/" in line:
                        m = method_pattern.search(line)
                        if m:
                            for r in matches:
                                if r in line:
                                    route_details[r]["methods"].add(m.group(1).upper())
            except Exception:
                pass

        clean_registry = []
        for r, d in sorted(route_details.items()):
            clean_registry.append({
                "route": r,
                "methods": sorted(list(d["methods"])) if d["methods"] else ["GET"],
                "occurrences": len(d["files"]),
                "files": d["files"][:5]
            })

        (SNAPSHOTS_DIR / "api_registry.json").write_text(json.dumps(clean_registry, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] Сформирован полный реестр API-маршрутов ({len(clean_registry)} эндпоинтов) в api_snapshots/api_registry.json")

        # ====================================================================
        # ЭТАП 4: ФИНАЛЬНАЯ САНИТИЗАЦИЯ И ГЕНЕРАЦИЯ MANIFEST.JSON
        # ====================================================================
        print("\n--- ЭТАП 4: Санитизация секретов во всем архиве и генерация manifest.json ---")
        text_extensions = {".json", ".html", ".md", ".txt", ".css"}
        sanitized_files_count = 0
        manifest_entries = []

        for p in ARCHIVE_ROOT.rglob("*"):
            if p.is_file():
                if p.suffix.lower() in text_extensions and p.name != "manifest.json":
                    try:
                        raw = p.read_text(encoding="utf-8")
                        clean = sanitize_text(raw)
                        if clean != raw:
                            p.write_text(clean, encoding="utf-8")
                            sanitized_files_count += 1
                    except Exception:
                        pass

                rel_p = str(p.relative_to(ARCHIVE_ROOT)).replace("\\", "/")
                manifest_entries.append({
                    "path": rel_p,
                    "size": p.stat().st_size,
                    "category": rel_p.split("/")[0] if "/" in rel_p else "root"
                })

        manifest = {
            "version": "1.0.0",
            "botName": "@pro_prison_bot",
            "botDomain": "pro-prison-bot.003220.xyz",
            "archivedAt": "2026-11-22T17:40:00+03:00",
            "totalFiles": len(manifest_entries),
            "files": sorted(manifest_entries, key=lambda x: x["path"])
        }
        (ARCHIVE_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] Проведена санитизация секретов в {sanitized_files_count} файлах. Сформирован manifest.json ({len(manifest_entries)} файлов)!")

    finally:
        await iframe_client.close()
        await page_client.close()
        print("\n[+] Завершено извлечение данных референсного бота.")


if __name__ == "__main__":
    asyncio.run(run_archive())
