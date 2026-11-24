# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: БЕЗОПАСНАЯ ОПТИМИЗАЦИЯ VPS, ДОЛГОЖИВУЩИЙ СВЕРХБЫСТРЫЙ КЭШ АССЕТОВ (NGINX + SERVICE WORKER) И ДЕПЛОЙ PRISON BOT

Ты выступаешь в роли Senior DevOps / Full-Stack Performance инженера (Linux systemd / Nginx / Docker / Python / FastAPI / AsyncIO / Service Worker). На основе проведенного аудита `vps_audit.md` твоя задача - безопасно разгрузить VPS (`178.17.60.16`, `1 vCPU`, `1.9 GiB RAM`), устранить троттлинг памяти `prisonbot.service` и редкий `HTTP 429`, внедрить трехуровневый долгоживущий кэш всех ассетов игры (тату, шмот, хаты, нычки) с мгновенной отдачей за миллисекунды, покрыть изменения автотестами и **выполнить безопасный деплой с проверкой на VPS**[cite: 45].

**КРИТИЧЕСКОЕ ПРАВИЛО БЕЗОПАСНОСТИ СОСЕДНИХ ПРОЕКТОВ**:
На этом же VPS работают два соседних Docker-проекта: `autoclip_service` (`/opt/autoclip`, порт `8080`, конвейер вертикальных клипов) и `crayfish_omni_hub` (`/opt/crayfish`, порт `8081`)[cite: 45]. **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** перезапускать, останавливать, изменять лимиты CPU/RAM, редактировать конфиги или удалять образы/файлы `autoclip_service` и `crayfish_omni_hub`. Любые оптимизации должны **освобождать** общие ресурсы хоста (RAM/диск), а не душить соседние контейнеры.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Безопасное оздоровление VPS без ущерба соседним проектам**:
   - Освободить застрявшую память и диск, ограничив системный журнал `systemd-journald` (сейчас он занимает `2.3 GiB` на диске и держит `192.8 MiB` RAM)[cite: 45] до адекватного лимита (`250 MiB` на диске, `64 MiB` в RAM).
   - Бережно очистить только старый неиспользуемый Docker build cache старше 7 дней (сейчас `2.35 GiB` мусора), **не трогая** работающие контейнеры, volumes и именованные образы (`autoclip-autoclip`, `crayfish-crayfish-hub`, `crayfish-test`)[cite: 45].
   - Устранить постоянный троттлинг памяти `prisonbot.service`: сейчас процесс потребляет `296-315 MiB` при установленном мягком лимите `MemoryHigh=300M`, из-за чего ядро Linux тормозит event loop и вытесняет бота в swap[cite: 45]. Поднять `MemoryHigh` до `380M` и `MemoryMax` до `480M` (это полностью покрывается освобожденной от `journald` памятью), а также выставить мягкий приоритет планировщика (`CPUWeight=130`), который помогает UI/пингу оставаться отзывчивым, но не душит рендер видеоклипов.
   - Устранить единичный `HTTP 429 Too Many Requests` на `/api/player/init`, возникающий при одновременном запуске `LiveStateHub Tier 1` и `Tier 3` в одну секунду[cite: 45].
2. **Долгоживущий постоянный кэш всех ассетов игры (тату, шмот, хаты, нычки)**:
   - Вынести директорию кэша на VPS в постоянный каталог `/var/cache/prisonbot/assets` (вне зоны перезаписи при деплое, пережить любые рестарты и будущие переезды в Docker), аккуратно перенеся туда уже накопленные `1710` файлов из `/opt/prisonbot/storage/asset_cache`[cite: 45].
   - Внедрить жесткие страховки по диску (чтобы никогда не помешать конвейеру клипов): верхний лимит размера кэша (`ASSET_CACHE_MAX_MB = 600` с LRU-очисткой старых файлов) и обязательная проверка свободного места (`ASSET_CACHE_MIN_FREE_GB = 4.0` - при меньшем остатке запись/прогрев кэша ставится на паузу).
   - **Без перекодировки на CPU VPS**: сохранять ассеты с CDN в оригинальном виде (без `Pillow`/конвертации PNG->WebP на сервере), чтобы не конкурировать с `ffmpeg` за единственное ядро CPU[cite: 45].
3. **Мгновенная загрузка спрайтов за доли секунды (Nginx + Browser Cache + Service Worker)**:
   - Настроить прямую отдачу кэшированных файлов в обход Python через Nginx (`X-Accel-Redirect` на `/_prison_asset_cache/` с `sendfile on`, `expires 365d`, `Cache-Control: public, max-age=31536000, immutable`) - это снизит время отдачи до `1-5 мс` и полностью снимет нагрузку с RAM/CPU Python.
   - Настроить долгоживущее кэширование в браузере через легковесный Service Worker (`web/static/sw.js`) со стратегией **Cache-First** строго для неизменяемых игровых ассетов (спрайты, иконки, хаты, проксируемые картинки) и **Network-Only** для API, SSE-стрима и HTML/JS/CSS-кода (чтобы обновления интерфейса никогда не залипали в кэше).
4. **Бережный фоновый прогрев кэша (Pre-warmer)**:
   - Реализовать скрипт `scripts/prewarm_asset_cache.py`, который собирает URL всех комплектов тату, шмота, хат (включая Spine-атласы/JSON/PNG) и нычек из локальных каталогов и аккуратно докачивает отсутствующие файлы на VPS с низким приоритетом (`nice -n 19 ionice -c 3`), малым числом потоков (`<= 3`), паузами между запросами и авто-паузой при росте `Load Average` (если в этот момент `autoclip_service` рендерит видео).
5. **Обязательный деплой и проверка на VPS**:
   - Выкатить код и конфиги на VPS (`178.17.60.16`), применить настройки `journald`, Nginx (`nginx -t` + `systemctl reload nginx`), `prisonbot.service`, выполнить перенос кэша и фоновый прогрев, и документально подтвердить, что `autoclip_service` и `crayfish_omni_hub` ни разу не перезапустились и работают штатно.

---

## 2. КОНФИГУРАЦИЯ

### Среда VPS (подтверждено `vps_audit.md`)
- Хост: `178.17.60.16` (подключение через `vps.py` / SSH), Ubuntu 22.04.2 LTS, `1 vCPU`, `1.9 GiB RAM`, `2.0 GiB Swap`, `13 GiB` свободно на `/` (`1.7M` свободных inodes).
- Проект PrisonBot: `/opt/prisonbot`, venv `/opt/prisonbot/venv/bin/python`, сервис `/etc/systemd/system/prisonbot.service`, локальный порт `127.0.0.1:8085`.
- Nginx: `/etc/nginx/sites-enabled/zvezdoed.space`, публичный префикс `/prison/` (`X-Forwarded-Prefix /prison`), уже есть `location /prison/static/assets/`.
- Соседние контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`127.0.0.1:8080`) и `crayfish_omni_hub` (`127.0.0.1:8081`)[cite: 45].

### Новые переменные конфигурации (`core/config.py` и `/opt/prisonbot/.env`)
- `ASSET_CACHE_DIR`: путь к кэшу ассетов (дефолт в коде - `storage/asset_cache` для локальной разработки и тестов; на VPS в `/opt/prisonbot/.env` прописать `/var/cache/prisonbot/assets`).
- `ASSET_CACHE_MAX_MB`: максимальный объем кэша в МБ (дефолт `600`).
- `ASSET_CACHE_MIN_FREE_GB`: минимальный порог свободного места на разделе для записи/прогрева (дефолт `4.0`).
- `ASSET_CACHE_NGINX_ACCEL_PREFIX`: внутренний префикс для `X-Accel-Redirect` (дефолт `""` - выключено локально; на VPS в `.env` прописать `/_prison_asset_cache`).
- Cache-busting статики: инкрементировать `?v=...` у `app.js`, `styles.css` и `spine_room_player.js` в `web/static/index.html` (например `?v=20261125_1`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Оптимизация `core/config.py` и дедупликация `HTTP 429` (`core/state_hub.py`, `client/api/player.py`)
- В `core/config.py` добавить настройки кэша ассетов (`ASSET_CACHE_DIR`, `ASSET_CACHE_MAX_MB`, `ASSET_CACHE_MIN_FREE_GB`, `ASSET_CACHE_NGINX_ACCEL_PREFIX`) с чтением из `.env`.
- В `core/state_hub.py` (и/или `client/api/player.py`) устранить одновременные дублирующие вызовы `/api/player/init` от `Tier 1` и `Tier 3`[cite: 45]:
  - Добавить `single-flight` / коалесинг (если запрос `player/init` уже выполняется прямо сейчас, второй вызывающий ждет результат этого же `Future`/`Task` вместо отправки второго HTTP-запроса) или короткий micro-TTL кэш (`2-3s`) + небольшой рассинхрон запуска `Tier 3` относительно `Tier 1`.

### 3.2. Трехуровневый кэш ассетов на бэкенде (`core/asset_cache.py` или модуль в `web/routes.py`)
- Вынести логику работы с дисковым кэшем ассетов в чистый тестируемый класс/модуль `core/asset_cache.py` и подключить его в прокси-эндпоинте ассетов в `web/routes.py`[cite: 43, 44]:
  1. **Постоянный путь и атомарная запись**:
     - Писать новые файлы через временный файл `<hash>.tmp.<pid>` + `os.replace(...)` внутри `asyncio.to_thread`, чтобы исключить битые наполовину скачанные спрайты при параллельных запросах или рестартах.
     - Использовать per-key `asyncio.Lock` (или dict активных загрузок), чтобы 5 одновременных запросов одного спрайта скачали его с CDN ровно **1 раз**.
  2. **Защита диска и LRU-лимит**:
     - Перед сохранением нового файла проверять `shutil.disk_usage(cache_dir).free >= ASSET_CACHE_MIN_FREE_GB * 1024**3`. Если свободного места меньше порога - отдавать байты клиенту напрямую без записи на диск и логировать предупреждение (раз в 5 минут, без спама).
     - Периодически (не на каждый запрос, например раз в 100 записей или в фоне) проверять общий размер `cache_dir`: если он превышает `ASSET_CACHE_MAX_MB`, удалять самые старые по `mtime` файлы до `85%` лимита.
     - При попадании в кэш (`cache hit`) не перечитывать файл в RAM Python, если задан `ASSET_CACHE_NGINX_ACCEL_PREFIX`: возвращать мгновенный ответ с заголовками:
       ```python
       headers = {
           "X-Accel-Redirect": f"{accel_prefix}/{cache_filename}",
           "Cache-Control": "public, max-age=31536000, immutable",
           "X-Asset-Cache": "HIT-ACCEL",
       }
       ```
       (с корректным `Content-Type` по расширению `.webp`, `.png`, `.json`, `.atlas`, `.bundle`).
     - Если `ASSET_CACHE_NGINX_ACCEL_PREFIX` пуст (локальный запуск / тесты), отдавать файл через `FileResponse` с теми же заголовками `Cache-Control: public, max-age=31536000, immutable` и `X-Asset-Cache: HIT-DISK`.
  3. **Индикатор/статистика кэша (опционально легковесный read-only эндпоинт)**:
     - Добавить в `/api/v1/...` (или статус-эндпоинт) легковесный `GET /api/v1/cache/stats` (количество файлов, размер в МБ, свободное место на диске, путь) с кэшированием результата на 60с.

### 3.3. Мгновенный клиентский кэш в браузере (`web/static/sw.js`, `web/static/app.js`, `web/routes.py`)
- Создать компактный Service Worker `web/static/sw.js` (и при необходимости отдавать его также по маршруту `/sw.js` в `web/routes.py` с заголовком `Cache-Control: no-cache` и `Service-Worker-Allowed: /`, чтобы он корректно работал и на `localhost:8085/`, и под префиксом `https://zvezdoed.space/prison/`[cite: 45]):
  - Имя кэша: `prisonbot-assets-v1`.
  - **Cache-First (мгновенный ответ из диска браузера, 0 сетевых запросов)** строго для GET-запросов, чей URL соответствует неизменяемым игровым ресурсам:
    - пути проксируемых ассетов (проверить точный путь в `web/routes.py`, например `/wardrobe/asset` / `/assets/proxy`);
    - пути `/static/assets/icons/` и `/static/assets/rooms/` (учитывая возможный префикс `/prison/`).
  - **Network-Only (никогда не кэшировать в SW)**:
    - все остальные `/api/` вызовы, SSE `/live/stream`, `/`, `index.html`, `app.js`, `styles.css`, `spine_room_player.js`, `sw.js`.
  - В `activate` очищать старые версии кэша `prisonbot-assets-*` (кроме текущей).
  - В `web/static/app.js` аккуратно зарегистрировать Service Worker (`if ('serviceWorker' in navigator)`), с безопасным `try/catch`, чтобы при блокировке SW в нестандартных WebView приложение продолжало работать штатно через стандартный HTTP-кэш (`max-age=31536000, immutable`).

### 3.4. Бережный прогрев кэша (`scripts/prewarm_asset_cache.py`)
- Написать автономный CLI-скрипт `scripts/prewarm_asset_cache.py`:
  - Извлекает все уникальные URL ассетов из:
    - `storage/tattoo_clothing_cache.json` (все комплекты тату, одежды, передние/задние слои, иконки);
    - `storage/collections_catalog.json` (иконки нычек и коллекций);
    - `storage/bosses_catalog.json` (ассеты боссов и наград);
    - каталога хат / комнат (статичные фоны, передние планы, Spine `.json`, `.atlas`, `.png`, `.bundle` из кода `web/routes.py` / `app.js`).
  - Принимает флаги `--concurrency 3`, `--delay 0.15`, `--max-load 1.5`, `--max-mb 600`, `--min-free-gb 4.0`, `--dry-run`.
  - Использует ровно ту же функцию хеширования и именования файлов из `core/asset_cache.py`, что и `web/routes.py` (100% совпадение ключей кэша!).
  - Пропускает уже существующие на диске файлы (идемпотентность).
  - Перед каждой пачкой проверяет:
    1. `free_gb >= min_free_gb` (иначе корректно завершается с логом, не забивая диск).
    2. `cache_mb < max_mb` (иначе корректно останавливается).
    3. На Linux: `os.getloadavg()[0] < max_load` (если `autoclip_service` нагрузил CPU - ждет `5-10s` перед продолжением, не мешая рендеру).
  - В конце выводит итоговую сводку: всего URL, уже в кэше, докачано, ошибок, итоговый размер кэша в МБ.

### 3.5. Безопасная настройка VPS (строго без вреда `autoclip_service` и `crayfish_omni_hub`)
Выполнить на VPS (`178.17.60.16`) в строгом порядке:
1. **Зафиксировать baseline соседей**: снять текущие `ID` и `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub`, а также `df -h /` и `free -h`.
2. **Ограничение `systemd-journald`** (освобождает ~`2 GiB` диска и ~`140 MiB` RAM для всей системы[cite: 45]):
   - Создать `/etc/systemd/journald.conf.d/prisonbot-limits.conf`:
     ```ini
     [Journal]
     SystemMaxUse=250M
     RuntimeMaxUse=64M
     MaxRetentionSec=14day
     ```
   - Выполнить `journalctl --vacuum-size=250M && systemctl restart systemd-journald`.
3. **Безопасная чистка только старого Docker build cache**:
   - Выполнить **только** `docker builder prune -f --filter "until=168h"` (освобождает ~`2.3 GiB` старых слоев сборки, не трогая контейнеры, volumes и образы)[cite: 45].
4. **Постоянный каталог кэша `/var/cache/prisonbot/assets`**:
   - Создать `mkdir -p /var/cache/prisonbot/assets`.
   - Скопировать существующие файлы из `/opt/prisonbot/storage/asset_cache/` в `/var/cache/prisonbot/assets/` (`cp -an` / `mv`), выставить права чтения для Nginx (`chmod 755 /var/cache/prisonbot /var/cache/prisonbot/assets`, `chmod 644 /var/cache/prisonbot/assets/*`).
   - Добавить в `/opt/prisonbot/.env` строки `ASSET_CACHE_DIR=/var/cache/prisonbot/assets`, `ASSET_CACHE_MAX_MB=600`, `ASSET_CACHE_MIN_FREE_GB=4.0`, `ASSET_CACHE_NGINX_ACCEL_PREFIX=/_prison_asset_cache`.
5. **Обновление Nginx (`/etc/nginx/sites-enabled/zvezdoed.space`)**:
   - Сначала сделать бэкап: `cp -a /etc/nginx/sites-available/zvezdoed.space /root/zvezdoed.space.bak.$(date +%Y%m%d_%H%M%S)` (проверив, симлинк ли в `sites-enabled`).
   - Добавить внутри `server` блока `zvezdoed.space` (не трогая location-блоки других проектов!):
     ```nginx
     location /_prison_asset_cache/ {
         internal;
         alias /var/cache/prisonbot/assets/;
         expires 365d;
         add_header Cache-Control "public, max-age=31536000, immutable" always;
         sendfile on;
         tcp_nopush on;
         access_log off;
     }
     ```
   - Проверить конфиг командой `nginx -t` и применить без разрыва соединений: `systemctl reload nginx`.
6. **Обновление `prisonbot.service` (`/etc/systemd/system/prisonbot.service`)**:
   - Изменить `MemoryHigh=300M` -> `MemoryHigh=380M`, `MemoryMax=450M` -> `MemoryMax=480M`, добавить мягкий `CPUWeight=130` (не ограничивая соседей).
   - Выполнить `systemctl daemon-reload` и после заливки кода - `systemctl restart prisonbot.service`.
7. **Бережный прогрев кэша на VPS**:
   - Запустить `nice -n 19 ionice -c 3 /opt/prisonbot/venv/bin/python /opt/prisonbot/scripts/prewarm_asset_cache.py --concurrency 3 --delay 0.15 --max-load 1.5 --max-mb 600 --min-free-gb 4.0`.
   - Убедиться, что права на новые скачанные файлы читаемы для Nginx (`chmod a+r` - заложить это прямо в `core/asset_cache.py` через `os.chmod(path, 0o644)` при сохранении файла!).

---

## 4. ТЕСТИРОВАНИЕ

Покрыть все новые механизмы автотестами (создать `tests/test_asset_cache.py` и обновить `tests/test_state_hub.py`, `tests/test_web_endpoints.py`[cite: 43, 44]):

1. **Модуль `core/asset_cache.py` (`tests/test_asset_cache.py`)**:
   - Детерминированное имя файла по URL и совпадение ключей между `web/routes.py` и `scripts/prewarm_asset_cache.py`.
   - Атомарная запись файла (отсутствие `.tmp` после записи, права `0o644`).
   - Возврат `X-Accel-Redirect` с заголовками `Cache-Control: public, max-age=31536000, immutable` и `X-Asset-Cache: HIT-ACCEL`, когда включен `ASSET_CACHE_NGINX_ACCEL_PREFIX`, и fallback на дисковую отдачу (`HIT-DISK`), когда префикс пуст.
   - Страховка `min_free_gb`: при имитации нехватки места на диске (`shutil.disk_usage` < порога) файл не записывается на диск, ошибка не падает, ответ клиенту отдается корректно.
   - Страховка `max_mb` (LRU-очистка): при превышении лимита удаляются самые старые файлы, а свежие сохраняются.
   - Дедупликация параллельных загрузок: 5 одновременных запросов на один некэшированный URL делают ровно 1 запрос к CDN.
2. **Скрипт `scripts/prewarm_asset_cache.py` (`tests/test_asset_cache.py`)**:
   - Сбор URL из реальных локальных каталогов (`tattoo_clothing_cache.json`, `collections_catalog.json`, `bosses_catalog.json`, комнаты) в `--dry-run` режиме возвращает непустой список валидных URL.
   - Остановка прогрева при нехватке места на диске или превышении лимита.
3. **Защита от `HTTP 429` (`tests/test_state_hub.py`)**:
   - Два одновременных вызова `player/init` схлопываются в один реальный сетевой запрос.
4. **Проверка JS и Service Worker**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js`, `node --check web/static/spine_room_player.js`.
   - Проверка, что `sw.js` кэширует только ассеты и НЕ перехватывает `/api/v1/live/stream`, `/api/v1/config`, `index.html`, `app.js`.
5. **Финальная верификация на VPS (включая неприкосновенность соседей)**:
   - Сравнить `StartedAt` и `Status` контейнеров `autoclip_service` и `crayfish_omni_hub` ДО и ПОСЛЕ - должны остаться полностью неизменными (`Up`, без рестартов).
   - Проверить `df -h /` и `free -h` ДО и ПОСЛЕ - убедиться, что освободилось ~`4 GiB` диска и снизилось потребление RAM `systemd-journald`.
   - Проверить через `curl -sI` по публичному HTTPS-адресу `https://zvezdoed.space/prison/...` (или через локальный Nginx с `Host: zvezdoed.space`) реальный запрос к проксируемому ассету: статус `200 OK`, заголовок `Cache-Control: public, max-age=31536000, immutable`, время ответа `< 30 мс`.
   - Проверить `systemctl is-active prisonbot.service` (`active`), `journalctl -u prisonbot.service -n 50` (чистые логи без ошибок и без `429`).

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Аудит текущих точек кэширования и `LiveStateHub`**:
  - Изучить в `web/routes.py` текущий эндпоинт проксирования ассетов (путь, хеширование URL, расширения, заголовки) и все места обращения к `asset_cache`.
  - Изучить в `core/state_hub.py` и `client/api/player.py`, как `Tier 1` и `Tier 3` вызывают `/api/player/init`.
- [ ] **Шаг 2. Реализация `core/asset_cache.py`, обновление `core/config.py`, `web/routes.py`, `core/state_hub.py`**:
  - Создать `core/asset_cache.py` с постоянным путем, атомарной записью (`0o644`), per-URL дедупликацией, LRU-лимитом (`600 MB`), защитой свободного места (`4.0 GB`) и поддержкой `X-Accel-Redirect`.
  - Подключить `core/asset_cache.py` в `web/routes.py` и добавить `GET /api/v1/cache/stats`.
  - Устранить гонку `Tier 1` / `Tier 3` по `/api/player/init` (single-flight).
- [ ] **Шаг 3. Клиентский кэш (`web/static/sw.js`, `web/static/app.js`, `web/static/index.html`, `web/routes.py`)**:
  - Написать `web/static/sw.js` (Cache-First строго для неизменяемых игровых ассетов, Network-Only для API/SSE/кода) с поддержкой префикса `/prison/`.
  - Зарегистрировать SW в `web/static/app.js`, обновить cache-busting `?v=...` в `web/static/index.html`.
- [ ] **Шаг 4. Бережный прогревщик кэша (`scripts/prewarm_asset_cache.py`)**:
  - Реализовать сбор всех URL тату, шмота, хат и нычек и плавную докачку с контролем `concurrency`, `delay`, `loadavg`, `max_mb`, `min_free_gb`.
- [ ] **Шаг 5. Автотесты и локальные проверки**:
  - Написать `tests/test_asset_cache.py`, обновить `tests/test_state_hub.py`, прогнать `node --check` и полный `pytest`.
- [ ] **Шаг 6. ОБЯЗАТЕЛЬНЫЙ БЕЗОПАСНЫЙ ДЕПЛОЙ И ОПТИМИЗАЦИЯ НА VPS (`178.17.60.16`)**:
  - Снять baseline `autoclip_service` / `crayfish_omni_hub` (`ID`, `StartedAt`), `df -h /`, `free -h`.
  - Настроить лимиты `systemd-journald` (`250M` диск / `64M` RAM) и почистить старый `docker builder prune -f --filter "until=168h"`.
  - Создать `/var/cache/prisonbot/assets`, перенести текущие `1710` файлов кэша, обновить `/opt/prisonbot/.env`.
  - Сделать бэкап конфига Nginx, добавить `location /_prison_asset_cache/` (`internal; alias /var/cache/prisonbot/assets/;`), проверить `nginx -t` и выполнить `systemctl reload nginx`.
  - Обновить `MemoryHigh=380M`, `MemoryMax=480M`, `CPUWeight=130` в `/etc/systemd/system/prisonbot.service` (`systemctl daemon-reload`).
  - Загрузить обновленный код/статику/скрипты в `/opt/prisonbot`, перезапустить `prisonbot.service`.
  - Прогнать бережный прогрев `nice -n 19 ionice -c 3 /opt/prisonbot/venv/bin/python /opt/prisonbot/scripts/prewarm_asset_cache.py` и зафиксировать статистику.
  - Проверить неприкосновенность `autoclip_service` и `crayfish_omni_hub`, свободное место/RAM, `X-Accel-Redirect` + `max-age=31536000` и чистые логи `prisonbot.service`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
node --check web/static/spine_room_player.js
python -m pytest -v tests/test_asset_cache.py tests/test_state_hub.py tests/test_wardrobe_api.py tests/test_web_endpoints.py
python -m pytest -q tests/
```