# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ОБНОВЛЕНИЕ ИКОНОК РЕСУРСОВ (ПАПИРОСЫ, РУБЛИ, САХАР, МЫЛО) ВО ВСЕЙ СИСТЕМЕ ИЗ REFERENCE_ARCHIVE + CACHE-BUSTING И ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack & Front-End инженера (Python / FastAPI / Vanilla JS / CSS / Service Worker / Linux systemd). Твоя задача - заменить текущие иконки четырех базовых ресурсов (`папиросы`, `рубли`, `сахар`, `мыло`) в `web/static/assets/icons/` на более качественные оригинальные HUD-иконки из `reference_archive/pro_prison_bot/assets/`, провести полный аудит всех мест отображения этих ресурсов в интерфейсе веб-панели (шапка/HUD, профиль, уведомления, награды тюрьмы и боссов, рутина, магазины/игры, карточки действий) для гарантированного использования обновленных ассетов без остаточных эмодзи или старых CDN-ссылок, обеспечить надежный cache-busting (включая `web/static/sw.js` и Cloudflare/браузерный кэш), покрыть изменения автотестами и **обязательно задеплоить и верифицировать побайтовую отдачу новых иконок на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Замена 4 ресурсных иконок на качественные HUD-версии**:
   - Скопировать (побайтово заменить) целевые иконки в `web/static/assets/icons/` из следующих источников:
     - `reference_archive/pro_prison_bot/assets/HUD_cigarettes.webp` -> `web/static/assets/icons/cigarettes.webp`
     - `reference_archive/pro_prison_bot/assets/HUD_rubles.webp` -> `web/static/assets/icons/rubles.webp`
     - `reference_archive/pro_prison_bot/assets/HUD_sugar.webp` -> `web/static/assets/icons/sugar.webp`
     - `reference_archive/pro_prison_bot/assets/HUD_soap.webp` -> `web/static/assets/icons/soap.webp`[cite: 30]
2. **Единообразное применение новых иконок во всей системе**:
   - Во всех экранах и компонентах веб-интерфейса (HUD/шапка баланса, карточка профиля, панель уведомлений, бейджи наград с боссов и тюремных действий, рутина, Катала/игры, Барыга/обмены, таланты/затраты и т.д.) для `папирос`, `рублей`, `сахара` и `мыла` должны использоваться строго обновленные локальные `.webp`-иконки.
   - Убедиться, что нигде в UI не остались дублирующие текстовые эмодзи (`🚬`, `💵`, `💰`, `🍬`, `🧂`, `🧼` и т.п.) или прямые внешние CDN-ссылки вместо локальных `assets/icons/{cigarettes,rubles,sugar,soap}.webp`.
   - Проверить визуальное выравнивание и пропорции (`object-fit: contain`, `width`/`height`, `vertical-align`) во всех контейнерах, чтобы новые HUD-иконки не растягивались, не обрезались и четко читались на всех размерах экранов (десктоп и мобилка).
3. **Гарантированный сброс кэша (браузер + Service Worker + CDN/Nginx)**:
   - Поскольку имена файлов (`cigarettes.webp`, `rubles.webp`, `sugar.webp`, `soap.webp`) остаются прежними, браузер, Service Worker (`web/static/sw.js`) и Cloudflare могут отдавать старые закэшированные изображения[cite: 30].
   - Необходимо обновить версию кэша в `web/static/sw.js`, добавить/обновить параметр версии `?v=...` для статики в `web/static/index.html` и обеспечить версионирование URL локальных иконок в `web/static/app.js` (через единый `ASSET_VERSION` / `resolveAppAssetUrl`), чтобы пользователи сразу увидели новые иконки без ручной чистки кэша.
4. **Защита от случайной перезаписи и обязательный деплой на VPS**:
   - Проверить `scripts/fetch_game_icons.py` (если он перезаписывает эти 4 файла старыми версиями, обновить/синхронизировать логику)[cite: 30].
   - Задеплоить обновленные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service` и инструментально проверить `SHA256` отдаваемых файлов на `127.0.0.1:8085` и через публичный URL `https://zvezdoed.space/prison/`, сохранив 0 рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Карта замены ассетов
- `reference_archive/pro_prison_bot/assets/HUD_cigarettes.webp` -> `web/static/assets/icons/cigarettes.webp`
- `reference_archive/pro_prison_bot/assets/HUD_rubles.webp` -> `web/static/assets/icons/rubles.webp`
- `reference_archive/pro_prison_bot/assets/HUD_sugar.webp` -> `web/static/assets/icons/sugar.webp`
- `reference_archive/pro_prison_bot/assets/HUD_soap.webp` -> `web/static/assets/icons/soap.webp`[cite: 30]

### Ключевые файлы проекта под аудит и доработку
- Статика и фронтенд: `web/static/assets/icons/`, `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/static/sw.js`.
- Бэкенд и вспомогательные скрипты: `web/routes.py`, `core/drop_parser.py`, `scripts/fetch_game_icons.py`.
- Автотесты: `tests/test_asset_cache.py`, `tests/test_web_endpoints.py`, `tests/test_web_api.py`[cite: 30].
- Продакшен VPS: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), публичный префикс `https://zvezdoed.space/prison/`.
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Замена файлов и проверка целостности ассетов
- Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
- Проверить наличие, валидность (`RIFF....WEBP`) и размеры (в пикселях и байтах) исходных файлов `HUD_cigarettes.webp`, `HUD_rubles.webp`, `HUD_sugar.webp`, `HUD_soap.webp` в `reference_archive/pro_prison_bot/assets/`[cite: 30].
- Зафиксировать `SHA256`-хеши старых и новых файлов, выполнить побайтовое копирование в `web/static/assets/icons/cigarettes.webp`, `rubles.webp`, `sugar.webp`, `soap.webp` и убедиться, что новые хеши 100% совпадают с эталонными файлами в `reference_archive/pro_prison_bot/assets/`.

### 3.2. Сквозной аудит всех упоминаний ресурсов по всей системе
- Выполнить поиск по всему репозиторию (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/routes.py`, `core/drop_parser.py`) всех ссылок на `cigarettes`, `rubles`, `sugar`, `soap`, а также любых эмодзи-заменителей ресурсов в веб-UI:
  - Проверить шапку / HUD ресурсов в `web/static/index.html` и рендер профиля в `web/static/app.js`.
  - Проверить единую карту иконок наград (`getDropIconHtml` / `RESOURCE_ICONS` / чипы уведомлений и наград боссов и тюрьмы) в `web/static/app.js`.
  - Проверить все вторичные экраны (Барыга, Катала/игры, рутина, подарки/подогревы, делюги, сборы, стоимости улучшений) - везде, где отображаются папиросы, рубли, сахар или мыло в HTML-интерфейсе, должна рендериться единая иконка `assets/icons/{cigarettes,rubles,sugar,soap}.webp` (в Telegram-уведомлениях текстовые эмодзи, естественно, сохраняются).
  - Проверить `web/static/styles.css`: убедиться, что у всех классов иконок ресурсов (`.res-icon`, `.hud-icon`, `.drop-icon`, `.notif-icon` и аналогичных) задано `object-fit: contain` без искажения пропорций для новых HUD-ассетов.

### 3.3. Надежный cache-busting (HTML + JS + Service Worker)
- Проверить текущую версию `?v=...` в `web/static/index.html` и текущее имя кэша `prisonbot-assets-v*` в `web/static/sw.js` и инкрементировать обе (например, `ASSET_VERSION = "20261125_14"` и следующая версия кэша `sw.js`).
- Убедиться, что:
  1. Все `<img>` иконок ресурсов в `web/static/index.html` имеют актуальный `?v=<ASSET_VERSION>`.
  2. В `web/static/app.js` функция построения пути локальных иконок (`resolveAppAssetUrl` или специализированный helper для `assets/icons/...`) автоматически добавляет `?v=<ASSET_VERSION>` к локальным путям `assets/icons/*.webp` (идемпотентно, не ломая `api/v1/assets/proxy?path=...` и не дублируя `?v=` и префикс `/prison/`).
  3. В `web/static/sw.js` новая версия кэша активируется через `skipWaiting()` + `clients.claim()` и очищает все предыдущие кэши на `activate`, чтобы ни у кого не залипли старые `cigarettes.webp`, `rubles.webp`, `sugar.webp`, `soap.webp`.

### 3.4. Проверка `scripts/fetch_game_icons.py` и уборка
- Проверить `scripts/fetch_game_icons.py`: если там прописаны старые пути/источники для `cigarettes.webp`, `rubles.webp`, `sugar.webp`, `soap.webp`, обновить маппинг или пометить приоритет HUD-ассетов, чтобы повторный запуск скрипта не откатил качество иконок[cite: 30].
- Удалить любые временные скрипты агента в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).

### 3.5. Обязательный деплой на VPS и инструментальная верификация
- Загрузить все обновленные иконки (`cigarettes.webp`, `rubles.webp`, `sugar.webp`, `soap.webp`) и измененные файлы (`index.html`, `app.js`, `styles.css`, `sw.js` и др.) на VPS (`178.17.60.16`, `/opt/prisonbot`).
- Перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую верификацию на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`, старт `127.0.0.1:8085` за `<= 5` секунд.
  2. Скачать все 4 иконки через `http://127.0.0.1:8085/assets/icons/{cigarettes,rubles,sugar,soap}.webp?v=<ASSET_VERSION>` И через публичный URL `https://zvezdoed.space/prison/assets/icons/{cigarettes,rubles,sugar,soap}.webp?v=<ASSET_VERSION>`:
     - Проверить `HTTP 200`, `Content-Type: image/webp`.
     - Сверить `SHA256` каждого скачанного с прода файла с `SHA256` эталона в `reference_archive/pro_prison_bot/assets/HUD_*.webp` - должно быть 100% совпадение 4 из 4.
  3. Проверить `https://zvezdoed.space/prison/` (`index.html`), `app.js` и `sw.js` на наличие новой версии кэша и cache-busting.
  4. Проверить `journalctl -u prisonbot.service -n 60 --no-pager` на отсутствие `Traceback`.
  5. Проверить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Добавить и расширить автотесты в `tests/test_asset_cache.py` и `tests/test_web_endpoints.py`[cite: 30]:

1. **Побайтовая целостность и совпадение с HUD-эталонами (`tests/test_asset_cache.py`)**:
   - Для всех 4 файлов (`cigarettes.webp`, `rubles.webp`, `sugar.webp`, `soap.webp`) проверить:
     - файл существует в `web/static/assets/icons/`, является валидным WebP (`RIFF....WEBP`);
     - `SHA256` файла в `web/static/assets/icons/` совпадает с `SHA256` соответствующего `HUD_*.webp` в `reference_archive/pro_prison_bot/assets/` (если архив доступен в окружении).
2. **HTTP-отдача, версионирование и идемпотентность URL (`tests/test_web_endpoints.py`)**:
   - `GET /assets/icons/{cigarettes,rubles,sugar,soap}.webp` возвращает `200 OK` с `Content-Type: image/webp` и точным содержимым новых файлов.
   - Проверить через `node -e` на реальном `resolveAppAssetUrl` из `web/static/app.js`, что:
     - добавление cache-busting `?v=...` для `assets/icons/*.webp` работает идемпотентно на `/prison/`, `/prison` и `/`;
     - прокси-пути `api/v1/assets/proxy?path=...` при этом не ломаются и не получают лишних параметров или дублирования `/prison/prison/`.
   - Проверить синхронность версий в `web/static/index.html`, `web/static/app.js` и `web/static/sw.js`.
3. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и полный прогон `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Baseline VPS и замена 4 ресурсных иконок**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Проверить валидность и `SHA256` исходных файлов `HUD_cigarettes.webp`, `HUD_rubles.webp`, `HUD_sugar.webp`, `HUD_soap.webp` в `reference_archive/pro_prison_bot/assets/` и побайтово заменить ими `web/static/assets/icons/{cigarettes,rubles,sugar,soap}.webp`.
- [ ] **Шаг 2. Сквозной аудит UI и стилей (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `scripts/fetch_game_icons.py`)**:
  - Проверить все места отображения папирос, рублей, сахара и мыла во всех разделах веб-панели: перевести любые оставшиеся эмодзи или внешние URL в веб-UI на локальные `.webp`-иконки, проверить `object-fit: contain` и пропорции в CSS.
  - Синхронизировать `scripts/fetch_game_icons.py`, чтобы исключить откат иконок.
- [ ] **Шаг 3. Сквозной cache-busting (`web/static/index.html`, `web/static/app.js`, `web/static/sw.js`)**:
  - Поднять версию статики (`?v=...`) в `index.html`, подключить идемпотентное версионирование `assets/icons/*.webp` в `app.js` (без поломки `/prison/` и `assets/proxy`) и инкрементировать имя кэша в `sw.js`.
- [ ] **Шаг 4. Автотесты и уборка временных файлов**:
  - Добавить проверки в `tests/test_asset_cache.py` и `tests/test_web_endpoints.py`.
  - Прогнать `node --check web/static/app.js`, `node --check web/static/sw.js` и весь `python -m pytest -q tests/`.
  - Удалить временные скрипты в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 5. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И SHA256-ВЕРИФИКАЦИЯ НА ПРОДЕ**:
  - Загрузить все измененные иконки и файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Проверить быстрый старт `127.0.0.1:8085` (`<= 5s`), скачать все 4 иконки по `127.0.0.1:8085` и по `https://zvezdoed.space/prison/assets/icons/...`, подтвердить `HTTP 200`, `image/webp` и 100% совпадение `SHA256` с `HUD_*.webp` из `reference_archive`.
  - Проверить чистый `journalctl -u prisonbot.service -n 60` и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_asset_cache.py tests/test_web_endpoints.py tests/test_web_api.py
python -m pytest -q tests/
```