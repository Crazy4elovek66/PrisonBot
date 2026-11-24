# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: МГНОВЕННОЕ ОТКРЫТИЕ НЕПРОСМОТРЕННЫХ СЕТОВ, ШМОТА И ХАТ (ПРЯМАЯ ОТДАЧА NGINX В ОБХОД PYTHON + ПОЛНЫЙ ПРОГРЕВ КЭША НА VPS)

Ты выступаешь в роли Senior Full-Stack & DevOps Performance инженера (Nginx / Linux systemd / Python / FastAPI / Vanilla JS / Canvas / Spine). Сейчас уже просмотренные комплекты открываются быстро за счет браузерного кэша, но **любые непросмотренные сеты, шмотки и хаты все еще грузятся долго**. Твоя задача - найти точную причину медленного первого открытия на VPS (`178.17.60.16`), перевести отдачу кэшированных спрайтов в **прямой обход Python через Nginx (`try_files`)**, довести серверный кэш до честного 100% покрытия всех комплектов, вещей, хат и нычек через надежный низкоприоритетный прогрев, оптимизировать параллельную загрузку слоев на фронтенде, покрыть изменения тестами и **обязательно задеплоить и верифицировать результат на VPS**[cite: 45].

**СТРОГИЕ ОГРАНИЧЕНИЯ**:
1. **НЕ добавлять** тихую предзагрузку при наведении курсора (hover prefetching запрещен).
2. **Неприкосновенность соседних проектов на VPS**: на сервере работают Docker-контейнеры `autoclip_service` (`/opt/autoclip`, конвейер вертикальных клипов) и `crayfish_omni_hub` (`/opt/crayfish`)[cite: 45]. **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** останавливать, перезапускать, менять лимиты или затрагивать файлы и тома этих контейнеров.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

Сделать так, чтобы **абсолютно любой непросмотренный комплект тату, предмет одежды, хата (включая Spine-анимации) или нычка** при первом же клике в браузере открывался за доли секунды (целевой ориентир: `< 150-300 мс` на весь комплект):

1. **Реальная диагностика медленного первого открытия на VPS**:
   - Проверить текущее состояние `/var/cache/prisonbot/assets` и фонового прогрева на VPS: завершился ли прошлый прогрев, не оборвался ли он при закрытии SSH-сессии и не уперся ли в прежний потолок `600 MB`.
   - Проверить совпадение URL и хеш-ключей между `scripts/prewarm_asset_cache.py`, `core/asset_cache.py`, `web/routes.py`, `web/static/app.js` и `web/static/spine_room_player.js` (убедиться, что непросмотренные сеты и хаты не получают `MISS` из-за разной нормализации URL, query-параметров или пропущенных типов ассетов).
   - Проверить, нет ли скрытого тормоза на фронтенде/бэкенде перед загрузкой картинок (последовательный `await` слоев в цикле, лишние тяжелые запросы к API игры при открытии примерки).
2. **Прямая отдача кэшированных спрайтов через Nginx вообще в обход Python**:
   - Сейчас при открытии нового сета из 30-40 слоев все 40 запросов сначала прилетают в одноядерный Python (`1 vCPU`, `prisonbot.service`)[cite: 45] и встают в очередь за `X-Accel-Redirect`.
   - Перевести URL кэшируемых ассетов на детерминированный маршрут вида `/assets_cache/<sha256><ext>?url=<encoded_url>`:
     - При наличии файла в `/var/cache/prisonbot/assets/<sha256><ext>` Nginx отдает его напрямую с диска через `try_files` + `sendfile on` по HTTP/2 за `1-10 мс` **с нулевой нагрузкой на Python**.
     - При отсутствии файла (`MISS`) Nginx прозрачно передает запрос через `error_page` / fallback `@prison_asset_miss` в FastAPI (`127.0.0.1:8085`), который скачивает файл с CDN, атомарно сохраняет его в `/var/cache/prisonbot/assets/<sha256><ext>` и отдает клиенту.
3. **Честное 100% покрытие всех ассетов на диске VPS (безопасный полный прогрев)**:
   - На диске VPS сейчас `15 GiB` свободного места (`50%` занято, `1.7M` свободных inodes)[cite: 45]. Безопасно поднять лимит `ASSET_CACHE_MAX_MB` с `600` до `2500` (2.5 GiB), одновременно усилив страховку свободного места до `ASSET_CACHE_MIN_FREE_GB = 5.0` (конвейеру вертикальных клипов всегда гарантировано минимум `5 GiB` свободного диска).
   - Запустить полный прогрев на VPS как отдельный отвязанный от SSH низкоприоритетный юнит (`systemd-run` с `Nice=19`, `IOSchedulingClass=idle`, `CPUWeight=20`), чтобы он гарантированно дошел до конца, не мешая ни `autoclip_service`, ни `prisonbot.service`.
4. **Ускорение параллельной загрузки и рендера на фронтенде (без hover-предзагрузки)**:
   - Убедиться, что все слои открываемого комплекта/хаты (статичные PNG/WebP, анимированные кадры, Spine `.json`/`.atlas`/`.png`/`.bundle`) запрашиваются параллельно (`Promise.allSettled`), а открытие примерки не ждет лишних синхронных/сетевых запросов к игровому серверу, если метаданные комплекта уже загружены в каталоге.
5. **Наведение порядка и обязательный деплой на VPS**:
   - Удалить оставшиеся с прошлой сессии временные скрипты в корне локального репозитория (`deploy_and_optimize_vps.py`, `verify_accel_and_prewarm.py`, `verify_get.py`), если они там присутствуют.
   - Выкатить все обновления на VPS (`178.17.60.16`), перезагрузить Nginx (`nginx -t && systemctl reload nginx`), перезапустить `prisonbot.service`, запустить и проконтролировать прогрев кэша и замерить реальное время открытия непросмотренных комплектов.

---

## 2. КОНФИГУРАЦИЯ

### Среда VPS (`vps_audit.md`)
- Хост: `178.17.60.16` (`zvezdoed.space`, публичный префикс `/prison/`), `1 vCPU`, `1.9 GiB RAM`, `15 GiB` свободно на `/`, `1.7M` свободных inodes[cite: 45].
- Директория кода: `/opt/prisonbot`, сервис: `prisonbot.service` (`127.0.0.1:8085`), постоянный кэш: `/var/cache/prisonbot/assets`.
- Конфиг Nginx: `/etc/nginx/sites-enabled/zvezdoed.space` (бэкап обязателен перед правкой!).
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`127.0.0.1:8080`), `crayfish_omni_hub` (`127.0.0.1:8081`)[cite: 45].

### Параметры кэша (`core/config.py` и `/opt/prisonbot/.env`)
- `ASSET_CACHE_DIR=/var/cache/prisonbot/assets` (на VPS; дефолт в коде - `storage/asset_cache`).
- `ASSET_CACHE_MAX_MB=2500` (поднять с `600` до `2500` для полного покрытия всех 18 500+ ассетов игры без вытеснения).
- `ASSET_CACHE_MIN_FREE_GB=5.0` (поднять с `4.0` до `5.0` для гарантированного запаса диску под рендер клипов).
- `ASSET_CACHE_NGINX_ACCEL_PREFIX=/_prison_asset_cache` (сохранить для совместимости со старым `/api/v1/assets/proxy`).
- Cache-busting в `web/static/index.html`: обновить `?v=...` у `app.js`, `styles.css`, `spine_room_player.js` (например `?v=20261125_04`) и обновить версию кэша в `web/static/sw.js` при изменении правил матчинга.

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Диагностика первопричин на VPS (Шаг 1 перед правками)
- Подключиться по SSH к `178.17.60.16` и проверить:
  1. Жив ли процесс `prewarm_asset_cache.py` (`ps aux | grep prewarm`), сколько файлов и сколько мегабайт реально лежит в `/var/cache/prisonbot/assets` (`du -sh`, `find ... | wc -l`) и что записано в его логе.
  2. Снять реальные URL, которые фронтенд (`web/static/app.js` и `web/static/spine_room_player.js`) формирует при открытии:
     - любого непросмотренного сета тату (например 30-40 частей);
     - любого непросмотренного сета одежды;
     - анимированной Spine-хаты (например `Взлом` или `Торт Люськи`).
  3. Для каждого из этих URL проверить:
     - присутствует ли его точный `sha256(clean_path) + ext` файл в `/var/cache/prisonbot/assets`?
     - если файла нет - почему `scripts/prewarm_asset_cache.py` его пропустил (лимит 600 МБ, обрыв процесса, другое правило нормализации URL, отсутствие источника URL в парсере прогревщика)?
     - сколько миллисекунд занимают API-запросы перед стартом загрузки картинок (не блокируется ли открытие примерочной тяжелым сетевым вызовом)?

### 3.2. Прямая отдача кэша через Nginx в обход Python (`core/asset_cache.py`, `web/routes.py`, `web/static/app.js`, `web/static/spine_room_player.js`, `web/static/sw.js`)
- **Единая детерминированная формула имени файла**:
  - В `core/asset_cache.py` зафиксировать чистую и одинаковую для Python и JS функцию нормализации и хеширования:
    - `clean_path = normalize_asset_path(raw_url)` (убирает ведущие слэши, приводит к единому виду).
    - `filename = sha256_hex(clean_path) + ext` (ровно то же правило, по которому уже сохранены файлы в `/var/cache/prisonbot/assets` - чтобы не потерять уже скачанные файлы!).
- **Новый прямой маршрут `/assets_cache/{filename}`**:
  - На фронтенде (`web/static/app.js` и `web/static/spine_room_player.js`):
    - Добавить компактную синхронную реализацию `sha256Hex(str)` (около 35 строк чистого JS, без внешних библиотек и без зависимости от `crypto.subtle`, чтобы работало и на HTTP `localhost`, и на HTTPS `zvezdoed.space`) + кэш хешей в `Map`.
    - Обновить хелпер построения URL прокси (`proxyAssetUrl(path)` / `getAssetProxyUrl(path)`): вместо `/api/v1/assets/proxy?path=...` (или `url=...`) формировать URL вида:
      `{BASE}/assets_cache/{sha256}{ext}?path={encodeURIComponent(cleanPath)}` (подставив точно тот же query-параметр, который ожидает текущий прокси в `web/routes.py`).
    - Сохранить обратную совместимость старого маршрута `/api/v1/assets/proxy` в `web/routes.py`.
  - На бэкенде (`web/routes.py`):
    - Добавить маршрут `GET /assets_cache/{filename}` (для локального запуска и для fallback от Nginx при `MISS`): валидирует формат `filename`, принимает `path`/`url`, проверяет `AssetCacheManager`, при `MISS` скачивает с CDN, атомарно сохраняет в `ASSET_CACHE_DIR/{filename}` с правами `0o644` и возвращает ответ с `Cache-Control: public, max-age=31536000, immutable`.
  - В Nginx (`/etc/nginx/sites-enabled/zvezdoed.space`):
    - Сделать бэкап конфига перед правкой.
    - Добавить блок прямой отдачи с диска **в обход Python**:
      ```nginx
      location ~ ^/prison/assets_cache/([a-f0-9]{64}\.(?:png|webp|jpg|jpeg|gif|json|atlas|bundle|skel))$ {
          root /var/cache/prisonbot/assets;
          try_files /$1 @prison_asset_miss;
          expires 365d;
          add_header Cache-Control "public, max-age=31536000, immutable" always;
          add_header X-Asset-Cache "HIT-NGINX" always;
          sendfile on;
          tcp_nopush on;
          access_log off;
      }

      location @prison_asset_miss {
          proxy_pass [http://127.0.0.1:8085](http://127.0.0.1:8085);
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_set_header X-Forwarded-Prefix /prison;
          rewrite ^/prison(/.*)$ $1 break;
      }
      ```
    - Обязательно проверить `nginx -t` и корректность `rewrite` в `@prison_asset_miss` на реальном `HIT` (заголовок `X-Asset-Cache: HIT-NGINX`, ноль обращений в логи Python) и на реальном `MISS` (проксируется в FastAPI, сохраняется на диск, а второй запрос сразу дает `X-Asset-Cache: HIT-NGINX`).
  - В Service Worker (`web/static/sw.js`):
    - Добавить `/assets_cache/` в список Cache-First маршрутов (поддерживая как корневой путь `/assets_cache/`, так и префикс `/prison/assets_cache/`).
    - Проверить, что регистрация `sw.js` в `web/static/app.js` использует корректный относительный путь с учетом префикса `/prison/` (например `./sw.js` или `${API_PREFIX}/sw.js`), и через DevTools/заголовки убедиться, что `sw.js` доступен по `https://zvezdoed.space/prison/sw.js` со статусом `200 OK`.

### 3.3. Устранение лишних задержек при открытии примерочной (строго БЕЗ hover-предзагрузки)
- Файлы: `web/static/app.js`, `web/static/spine_room_player.js`, `web/routes.py`.
- Проверить весь путь от клика по карточке сета/шмота/хаты до отрисовки кадра:
  - Убедиться, что все слои открываемого комплекта загружаются строго параллельно (`Promise.allSettled`), без последовательных `for (...) { await loadImage(...) }`.
  - Убедиться, что при открытии хаты `spine_room_player.js` грузит `.json`, `.atlas`, `.png` и `.bundle` через новый прямой `/assets_cache/...` маршрут и параллельно (где возможно).
  - Убедиться, что метаданные каталога (тату, одежда, комплекты, хаты) кэшируются в памяти фронтенда после первой загрузки вкладки и клик по новому комплекту не делает лишних тяжелых запросов к игровому API.
  - **НЕ добавлять** никакую фоновую предзагрузку при наведении мыши (`mouseenter` / `mouseover` / `pointerenter`).

### 3.4. Полный и надежный прогрев кэша на VPS (`scripts/prewarm_asset_cache.py` + `systemd-run`)
- Файлы: `scripts/prewarm_asset_cache.py`, `core/asset_cache.py`.
- Доработать `scripts/prewarm_asset_cache.py`:
  1. Убедиться, что парсер URL извлекает **100%** всех ассетов, которые реально запрашивает фронтенд:
     - все части всех комплектов тату (передние и задние слои + превью);
     - все предметы одежды и комплекты шмота (статичные + анимированные кадры + превью);
     - все хаты / комнаты (статичные фоны, передние планы, все файлы Spine-комнат `.json`, `.atlas`, `.png`, `.bundle`, превью);
     - все нычки, коллекции, боссы и их награды.
  2. Поддержать чтение лимитов из `.env` (`ASSET_CACHE_DIR`, `ASSET_CACHE_MAX_MB=2500`, `ASSET_CACHE_MIN_FREE_GB=5.0`).
  3. Выводить периодический прогресс в stdout/лог (каждые 250 файлов: `downloaded`, `skipped`, `failed`, `cache_mb`, `free_gb`, `load1`), чтобы легко отслеживать ход прогрева.
  4. Добавить паузу при `load1 >= max_load` (например `1.4`), чтобы мгновенно уступать CPU, если `autoclip_service` начал рендер клипа.
  5. Приоритет очереди прогрева: сначала скачать **все хаты (включая Spine)**, затем **все комплекты шмота**, затем **все комплекты тату**, затем остальные одиночные предметы и нычки - так самые заметные пользователю экраны станут мгновенными в первые же минуты.
- Запуск на VPS:
  - Остановить старый зависший/незавершенный процесс прогрева (если еще висит).
  - Запустить прогрев как независимый от SSH-сессии transient-юнит systemd:
    ```bash
    systemd-run --unit=prisonbot-prewarm \
      --description="PrisonBot Low-Priority Asset Cache Prewarmer" \
      --working-directory=/opt/prisonbot \
      --property=Nice=19 \
      --property=IOSchedulingClass=idle \
      --property=CPUWeight=20 \
      --property=MemoryHigh=120M \
      --property=MemoryMax=200M \
      /opt/prisonbot/venv/bin/python /opt/prisonbot/scripts/prewarm_asset_cache.py \
      --concurrency 4 --delay 0.05 --max-load 1.4 --max-mb 2500 --min-free-gb 5.0
    ```
  - Проконтролировать работу `prisonbot-prewarm` (`journalctl -u prisonbot-prewarm -n 30`), дождаться завершения (или подтвердить активное наполнение с высокой долей прогрева основных сетов/хат, если файлов много, и зафиксировать в отчете точные цифры `files`, `MB`, `free_GB` и `HIT-NGINX`).

---

## 4. ТЕСТИРОВАНИЕ

Покрыть изменения автотестами и живыми замерами на VPS:

1. **Совпадение ключей Python <-> JS и маршрут `/assets_cache/{filename}` (`tests/test_asset_cache.py`, `tests/test_web_endpoints.py`)**:
   - Проверить через `node` (в unit-тесте или отдельном проверочном запуске), что JS-функция `sha256Hex` + нормализация URL из `web/static/app.js` выдает **побайтово идентичное** имя файла, что и `AssetCacheManager` в Python на реальных URL тату, одежды, хат и Spine-ассетов.
   - Тест `GET /assets_cache/{filename}?path=...`: на `HIT` отдает файл с `Cache-Control: public, max-age=31536000, immutable`, на `MISS` скачивает с CDN, сохраняет атомарно с правами `0o644` и отдает клиенту, при невалидном `filename` возвращает `400/404`.
   - Проверка новых дефолтов/чтения из env: `ASSET_CACHE_MAX_MB`, `ASSET_CACHE_MIN_FREE_GB=5.0`.
   - Проверка отсутствия hover-предзагрузки (`mouseenter`/`mouseover` prefetch) в `web/static/app.js`.
2. **Service Worker (`web/static/sw.js`)**:
   - Проверка, что `sw.js` кэширует `/assets_cache/`, `/api/v1/assets/proxy`, `/static/assets/icons/`, `/static/assets/rooms/` (включая префикс `/prison/`), но не кэширует API-эндпоинты и код приложения.
3. **Проверка JS и полный `pytest`**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js`, `node --check web/static/spine_room_player.js`.
   - Полный прогон `python -m pytest -q tests/`.
4. **Обязательная живая верификация на VPS (`178.17.60.16`)**:
   - Проверить неизменность `StartedAt` и статуса `running` у `autoclip_service` и `crayfish_omni_hub` (0 рестартов!).
   - Проверить `https://zvezdoed.space/prison/sw.js` -> `HTTP/2 200`.
   - Взять реальный ассет из непросмотренного комплекта и сделать запрос на `https://zvezdoed.space/prison/assets_cache/<hash><ext>?path=...`:
     - проверить `HTTP/2 200`, заголовок `X-Asset-Cache: HIT-NGINX`, `Cache-Control: public, max-age=31536000, immutable`, время ответа `< 30 мс`;
     - проверить, что на `HIT-NGINX` в `journalctl -u prisonbot.service` не появляется никаких записей о запросе (Python полностью обойден!);
     - проверить `MISS` -> fallback `@prison_asset_miss` -> сохранение на диск -> повторный запрос дает `HIT-NGINX`.
   - Проверить `df -h /` (свободно `>= 10 GiB`), `free -h`, `systemctl is-active prisonbot.service` (`active`), и статистику `/prison/api/v1/cache/stats`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Живая диагностика на VPS и в коде**:
  - Снять baseline `autoclip_service` / `crayfish_omni_hub` (`StartedAt`), `df -h /`, `free -h`, количество/объем файлов в `/var/cache/prisonbot/assets` и статус прошлого прогрева.
  - Проверить реальные URL запросов непросмотренных сетов/хат в `web/static/app.js` и `web/static/spine_room_player.js` и сравнить с тем, что качает `scripts/prewarm_asset_cache.py`.
- [ ] **Шаг 2. Прямая отдача кэша в обход Python (`core/config.py`, `core/asset_cache.py`, `web/routes.py`, `web/static/app.js`, `web/static/spine_room_player.js`, `web/static/sw.js`, `web/static/index.html`)**:
  - Добавить маршрут `GET /assets_cache/{filename}` на бэкенде и синхронный `sha256Hex` + единую нормализацию URL на фронтенде (с 100% совпадением ключей с `core/asset_cache.py`).
  - Обновить `web/static/sw.js` (добавить `/assets_cache/` с поддержкой `/prison/`) и проверить регистрацию SW с префиксом `/prison/`.
  - Устранить любые последовательные `await` загрузки слоев в `app.js` / `spine_room_player.js` (**без** hover-предзагрузки!).
  - Инкрементировать cache-busting `?v=...` в `web/static/index.html`.
- [ ] **Шаг 3. Доработка `scripts/prewarm_asset_cache.py`**:
  - Гарантировать 100% охват URL (хаты + Spine, сеты шмота, сеты тату, нычки, боссы) в приоритетном порядке, поддержку `ASSET_CACHE_MAX_MB=2500` и `ASSET_CACHE_MIN_FREE_GB=5.0`, паузу по `loadavg`.
- [ ] **Шаг 4. Уборка временных файлов и автотесты**:
  - Удалить временные служебные скрипты из корня репозитория (`deploy_and_optimize_vps.py`, `verify_accel_and_prewarm.py`, `verify_get.py`), если они присутствуют.
  - Обновить `tests/test_asset_cache.py` и `tests/test_web_endpoints.py` (включая проверку точного совпадения хешей Python и JS), прогнать `node --check` и `pytest`.
- [ ] **Шаг 5. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS, НАСТРОЙКА NGINX И ЗАПУСК ПОЛНОГО ПРОГРЕВА**:
  - Загрузить обновленные файлы в `/opt/prisonbot` на `178.17.60.16`.
  - Обновить в `/opt/prisonbot/.env`: `ASSET_CACHE_MAX_MB=2500`, `ASSET_CACHE_MIN_FREE_GB=5.0`.
  - Сделать бэкап конфига Nginx, добавить `location ~ ^/prison/assets_cache/...` (`try_files` + `@prison_asset_miss`), проверить `nginx -t` и выполнить `systemctl reload nginx`.
  - Перезапустить `systemctl restart prisonbot.service`.
  - Запустить полный прогрев через отвязанный низкоприоритетный `systemd-run --unit=prisonbot-prewarm` (`Nice=19`, `IOSchedulingClass=idle`, `CPUWeight=20`, `MemoryMax=200M`).
  - Выполнить живую верификацию: `HIT-NGINX` (< 30 мс, в обход Python), `MISS -> HIT-NGINX` fallback, `HTTP/2 200` для `/prison/sw.js`, статистику кэша и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
node --check web/static/spine_room_player.js
python -m pytest -v tests/test_asset_cache.py tests/test_wardrobe_api.py tests/test_web_endpoints.py
python -m pytest -q tests/
```