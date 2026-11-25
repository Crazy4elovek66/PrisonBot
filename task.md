# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: УСТРАНЕНИЕ 404 НА КАРТИНКАХ НЫЧЕК (БАГ ДВОЙНОГО /PRISON/PRISON/, ПОТЕРИ ПРЕФИКСА /PRISON/ И SERVICE WORKER) + ДЕПЛОЙ И ПРОВЕРКА НА ПРОДЕ

Ты выступаешь в роли Senior Full-Stack & DevOps инженера (Python / FastAPI / Vanilla JS / Service Worker / Nginx / Linux systemd). Из DevTools живого продакшена (`https://zvezdoed.space/prison/`) поймана точная причина сломанных иконок нычек в аккордеоне `Нычки`: одновременно возникают две ошибки формирования URL (потеря `/prison/` -> `https://zvezdoed.space/api/v1/assets/proxy?path=assets/PrisonV3/collections/30/1/1.webp` и двойной префикс -> `https://zvezdoed.space/prison/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp`), а ответ `404 Not Found` (`Content-Type: application/json`) отдается через Service Worker (`from service worker`)[cite: 31]. Твоя задача - полностью вылечить маршрутизацию URL ассетов на бэкенде, фронтенде и в `sw.js`, проверить проксирование на VPS, покрыть идемпотентность путей автотестами и **обязательно задеплоить и верифицировать загрузку реальных картинок по публичному URL `https://zvezdoed.space/prison/...` на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Устранение двух несовместимых багов URL в аккордеоне «Нычки»**:
   - Факт 1 из живого DOM продакшена: при копировании адреса картинки получается `https://zvezdoed.space/api/v1/assets/proxy?path=assets/PrisonV3/collections/30/1/1.webp` - потерян префикс `/prison/`, запрос уходит в корень домена и падает с `404`.
   - Факт 2 из DevTools -> Network: запросы уходят на `https://zvezdoed.space/prison/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp` - префикс `/prison/` продублирован дважды (`/prison/prison/`), из-за чего бэкенд возвращает `404 Not Found` с `Content-Type: application/json`[cite: 31].
   - Оба бага должны быть устранены раз и навсегда через единый канонический и **идемпотентный** механизм резолва URL, одинаково надежно работающий:
     - на `https://zvezdoed.space/prison/` (со слэшем на конце);
     - на `https://zvezdoed.space/prison` (без слэша на конце);
     - на `http://127.0.0.1:8085/` (напрямую без префикса).
2. **Лечение Service Worker (`web/static/sw.js`)**:
   - В DevTools зафиксировано `404 Not Found (from service worker)`[cite: 31].
   - Необходимо проверить `web/static/sw.js`: убрать любую возможность переписывания URL в `/prison/prison/`, строго запретить кэширование ответов с `!response.ok` (`status !== 200` или `Content-Type`, не являющимся изображением для прокси ассетов), обеспечить мгновенную активацию новой версии SW (`skipWaiting()` + `clients.claim()`) и полную очистку старых кэшей на `activate`.
3. **Запрет маскировки заглушками**:
   - Как и прежде, **запрещено** подменять слоты предметов коллекций иконкой `stash.webp` или скрывать битые `<img>` через `onerror`. Каждая ячейка обязана загружать реальную уникальную картинку предмета через валидный `/prison/api/v1/assets/proxy?path=...` с `HTTP 200` и `Content-Type: image/webp` (или `image/png`).
4. **Обязательный деплой и проверка именно продакшен-URL**:
   - Обновить cache-busting `?v=20261125_12` в `web/static/index.html` и имя кэша `prisonbot-assets-v7` в `web/static/sw.js`, задеплоить на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service` и проверить **публичный URL `https://zvezdoed.space/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp` и `.../30/1/1.webp`**, сохранив 0 рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Ключевые файлы под аудит и доработку
- Фронтенд и Service Worker: `web/static/app.js`, `web/static/sw.js`, `web/static/index.html`[cite: 32].
- Бэкенд и прокси ассетов: `web/routes.py`, `core/state_hub.py`, `core/asset_cache.py`, `web/app.py`[cite: 32].
- Конфигурация Nginx на VPS (только аудит/точечная проверка маршрута `/prison` - **НЕ трогать** конфиги и контейнеры `autoclip_service` и `crayfish_omni_hub`).
- Cache-busting: `?v=20261125_12` в `web/static/index.html`, `prisonbot-assets-v7` в `web/static/sw.js`.
- Продакшен VPS: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), публичный префикс `https://zvezdoed.space/prison/`.
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Точный аудит места появления `/prison/prison/` и `/api/...`
- Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
- Проверить все места в `web/static/app.js`, `web/static/sw.js`, `web/routes.py` и `core/state_hub.py`, где фигурируют `assets/proxy`, `API_BASE`, `BASE_PATH`, `apiUrl`, `renderCollectionsData`, `prefix`, `/prison`:
  1. Найти, откуда в Network взялся двойной `/prison/prison/api/v1/assets/proxy?...` (например, относительный путь `prison/api/...` на странице `/prison/`, либо повторное добавление `API_BASE` поверх уже префиксного пути, либо переписывание внутри `sw.js`)[cite: 31].
  2. Найти, откуда в скопированном адресе взялся `/api/v1/assets/proxy?path=assets/PrisonV3/collections/30/1/1.webp` без `/prison/` (например, ведущий слэш `/` в ответе `/api/v1/collections` или в `liveSlices`, либо открытие страницы по `/prison` без завершающего слэша `/`).
  3. Проверить конфиг Nginx на VPS для `zvezdoed.space` (`/prison` и `/prison/`): убедиться, как Nginx передает `/prison/api/v1/assets/proxy?...` на `127.0.0.1:8085` (должно приходить `/api/v1/assets/proxy?...` на FastAPI, а не `/prison/api/...`).

### 3.2. Единый канонический и идемпотентный резолв URL (`web/routes.py`, `core/state_hub.py`, `web/static/app.js`)
- **На бэкенде (`web/routes.py`, `core/state_hub.py`)**:
  - Все эндпоинты (`GET /api/v1/collections`, срез `collections` в `StateHub`, и прочие роуты с `assets/proxy`) должны возвращать **единообразный канонический путь без префикса `/prison/`**, например:
    `api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp` (или `/api/v1/assets/proxy?...`, но строго одинаково везде, без зашитого `/prison`).
- **На фронтенде (`web/static/app.js`)**:
  - Создать единый **идемпотентный** helper `resolveAppAssetUrl(rawUrl)` (и использовать его в `renderCollectionsData` и всех остальных местах рендера картинок/прокси):
    1. Определять префикс приложения `getAppBasePrefix()` надежно по `window.location.pathname`:
       - Если путь равен `/prison` или начинается с `/prison/` -> `base = "/prison"`.
       - Иначе -> `base = ""` (работа на `http://127.0.0.1:8085/`).
    2. Если `rawUrl` начинается с `http://` или `https://` или `data:` - не трогать внешний URL (кроме случая, если это `window.location.origin` + `/api/v1/assets/proxy` или `/prison/prison/...`, тогда нормализовать путь).
    3. Для локального пути:
       - Удалить любые ведущие `./` и ведущие `/` и любые повторные префиксы `^(/?prison)+/` (например `prison/api/...`, `/prison/api/...`, `/prison/prison/api/...`, `/api/...`, `api/...` -> все сводятся к чистому `api/v1/assets/proxy?path=...`).
       - Вернуть строго `${base}/${cleanPath}` (то есть всегда с **одним** ведущим слэшем: `/prison/api/v1/assets/proxy?path=...` на `zvezdoed.space/prison` и `zvezdoed.space/prison/`, и `/api/v1/assets/proxy?path=...` на `127.0.0.1:8085/`).
    4. Гарантировать свойство идемпотентности: `resolveAppAssetUrl(resolveAppAssetUrl(x)) === resolveAppAssetUrl(x)` для любых входных форматов (`api/...`, `/api/...`, `prison/api/...`, `/prison/api/...`, `/prison/prison/api/...`).
    5. Проверить, что с таким абсолютным от корня путем (`/prison/api/v1/assets/proxy?...`) картинки работают одинаково идеально даже если пользователь открыл `https://zvezdoed.space/prison` БЕЗ завершающего слэша `/`!

### 3.3. Починка Service Worker (`web/static/sw.js`)
- Провести полный аудит `web/static/sw.js`:
  - Убедиться, что при обработке `fetch`:
    - `sw.js` никогда не модифицирует путь запроса с добавлением лишнего `/prison/`.
    - Запросы к `assets/proxy` кэшируются **ТОЛЬКО** если `response.ok && response.status === 200` и `Content-Type` начинается с `image/` (или допустимых ассетов `application/octet-stream` / `application/json` для spine/atlas, но **НИКОГДА** для `404`/`500`!).
    - Если в кэше вдруг лежит старый ошибочный ответ (`!cached.ok`), немедленно удалять его и идти в сеть.
  - Инкрементировать имя кэша до `prisonbot-assets-v7`, вызвать `self.skipWaiting()` в `install` и `self.clients.claim()` + удаление всех кэшей кроме `prisonbot-assets-v7` в `activate`.

### 3.4. Обязательный деплой на VPS и проверка по реальным публичным URL
- Удалить любые временные скрипты в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).
- Обновить `?v=20261125_12` в `web/static/index.html` и `prisonbot-assets-v7` в `web/static/sw.js`.
- Загрузить измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `systemctl restart prisonbot.service`.
- Выполнить **живую верификацию и локально на `8085`, и через публичный Nginx `https://zvezdoed.space/prison/`**:
  1. `systemctl is-active prisonbot.service` -> `active`, старт `127.0.0.1:8085` за `<= 5` секунд.
  2. Проверить живой JSON `GET http://127.0.0.1:8085/api/v1/collections` и срез `collections` в `StateHub`: убедиться, что URL предметов НЕ содержат `prison/prison` и НЕ содержат `stash.webp`.
  3. Проверить через `curl -sI` именно те пути, которые падали у пользователя:
     - `https://zvezdoed.space/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp` -> строго `HTTP 200`, `Content-Type: image/webp` (или `image/...`), размер `> 200` байт.
     - `https://zvezdoed.space/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/30/1/1.webp` -> строго `HTTP 200`, `Content-Type: image/webp` (или `image/...`), размер `> 200` байт.
     - Еще 4 разных URL из `Мастера закатки` и `Любимые женщины` через `https://zvezdoed.space/prison/...` -> все `200 OK`, разные `sha256`.
  4. Проверить, что `https://zvezdoed.space/prison/app.js?v=20261125_12` и `https://zvezdoed.space/prison/sw.js` отдают свежую версию (`200 OK`, `prisonbot-assets-v7`, `resolveAppAssetUrl`).
  5. Проверить, что на `https://zvezdoed.space/prison/` в HTML/JS нет ни одного места, которое может собрать `/prison/prison/` или `/api/v1/assets/proxy` без `/prison`.
  6. Проверить `journalctl -u prisonbot.service -n 80 --no-pager` (без `Traceback`) и 100% неизменность `StartedAt` и статуса `running` у `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Добавить и расширить автотесты (в `tests/test_web_endpoints.py`, `tests/test_web_api.py`, `tests/test_asset_cache.py`)[cite: 32]:

1. **Идемпотентность `resolveAppAssetUrl` через Node.js (`tests/test_web_endpoints.py`)**:
   - Прогнать реальную функцию `resolveAppAssetUrl` из `web/static/app.js` (через `node -e`) для обоих `pathname`: `"/prison/"`, `"/prison"` и `"/"`, и для всех входных строк:
     - `"api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp"`
     - `"/api/v1/assets/proxy?path=assets/PrisonV3/collections/30/1/1.webp"`
     - `"prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp"`
     - `"/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp"`
     - `"/prison/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp"`
   - Проверить, что для `"/prison"` и `"/prison/"` **все** 5 входов дают ровно `"/prison/api/v1/assets/proxy?path=..."` (без `/prison/prison/` и без потери `/prison`), а для `"/"` дают ровно `"/api/v1/assets/proxy?path=..."`.
2. **Проверка `sw.js` (`tests/test_web_endpoints.py`)**:
   - `web/static/sw.js` содержит `prisonbot-assets-v7`, `skipWaiting`, `clients.claim`, проверяет `response.ok` перед `cache.put` и не дублирует `/prison/`.
3. **Проверка API коллекций (`tests/test_web_api.py`)**:
   - `/api/v1/collections` и `StateHub` отдают валидные канонические URL без `/prison/prison/` и без `stash.webp`.
4. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Точная локализация бага `/prison/prison/`, потери `/prison/` и `sw.js`**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Найти в `web/static/app.js`, `web/static/sw.js`, `web/routes.py`, `core/state_hub.py` и конфиге Nginx на VPS точную причину обоих битых URL (`/api/v1/assets/proxy?...` и `/prison/prison/api/v1/assets/proxy?...`).
- [ ] **Шаг 2. Унификация бэкенда и идемпотентный `resolveAppAssetUrl` (`web/routes.py`, `core/state_hub.py`, `web/static/app.js`)**:
  - Стандартизировать путь `assets/proxy` в `/api/v1/collections` и `StateHub`.
  - Реализовать и применить в `renderCollectionsData` (и везде по `app.js`) идемпотентный `resolveAppAssetUrl`, работающий для `/prison`, `/prison/` и `/` без дублирования префикса и без потери `/prison/`.
- [ ] **Шаг 3. Починка `web/static/sw.js`**:
  - Запретить кэширование `404` / `!response.ok`, убрать любые искажения путей, поднять версию кэша до `prisonbot-assets-v7` с `skipWaiting()` + `clients.claim()` + чисткой старых кэшей.
- [ ] **Шаг 4. Автотесты (включая Node-проверку всех 5 кейсов `resolveAppAssetUrl`) и уборка**:
  - Добавить тесты в `tests/test_web_endpoints.py` и `tests/test_web_api.py`.
  - Прогнать `node --check web/static/app.js`, `node --check web/static/sw.js` и полный `python -m pytest -q tests/`.
  - Удалить временные скрипты в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 5. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ПРОВЕРКА ПУБЛИЧНЫХ URL `zvezdoed.space/prison/...`**:
  - Обновить `?v=20261125_12` в `web/static/index.html`.
  - Загрузить измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Подтвердить `HTTP 200` + `image/*` + уникальные `sha256` по публичным URL `https://zvezdoed.space/prison/api/v1/assets/proxy?path=assets/PrisonV3/collections/1/1/1.webp` и `.../30/1/1.webp` (+ еще 4 предмета), свежие `app.js` и `sw.js`, чистый `journalctl` и 0 рестартов у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_web_endpoints.py tests/test_web_api.py tests/test_asset_cache.py
python -m pytest -q tests/
```