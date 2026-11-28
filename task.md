# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: КОМПЛЕКСНОЕ ОЗДОРОВЛЕНИЕ PRISONBOT (АНТИ-429/400, ЕДИНЫЕ КЭШИ И ШЛЮЗ ПЕРСОНАЖА, ЧЕСТНЫЙ ЗЕЛЕНЫЙ ПИНГ, БЕЗОПАСНОСТЬ, GRACEFUL SHUTDOWN И НАДЕЖНЫЙ CI/CD)

Ты выступаешь в роли Principal Full-Stack / DevOps / Security инженера (Python / FastAPI / SQLite WAL / asyncio / Nginx / GitHub Actions / Vanilla JS) на проекте PrisonBot.

**Контекст и результаты проведенного аудита (`2026-11-28`, VPS `178.17.60.16:/opt/prisonbot`):**
- Проект работает 24/7, автодеплой через `.github/workflows/deploy.yml` активен, 320 тестов проходят, `obshak_coverage` достиг `401/401 (100%)`.
- Живой аудит выявил критичные P0/P1 проблемы, которые необходимо устранить комплексно, используя архитектурное преимущество системы (игра одна и персонаж один -> единый транспорт, единый кэш справочников, сквозное разделение статических и динамических данных между воркерами и UI):
  1. **Шторм `14 132 HTTP 429` и `4 188 HTTP 400` за 24 часа**:
     - В `main.py:103-128` воркерам не передается `db_engine=get_engine()`, из-за чего `daily_interaction_targets` пуста (`0` строк) и `RoutineWorker` шлет тысячи повторных `POST /api/interaction/perform` -> `400`;
     - `send_podogrev_if_ready()` и `business/collect` каждые 15 минут шлют повторные `400` без суточного кэша / парсинга `timeLeft`;
     - `SchedulerController.refresh_tier2` (`core/scheduler.py:420-430`) каждые 105 сек дергает `prisons`/`friends`/`friends_stats` с `force=True`, пробивая кэш и залпом опрашивая `masters/1..16/enter` и все чекпоинты (`9 000+` `429`), а в `GameHttpClient` нет глобального rate-limiter и обработки `429`.
  2. **Желтый пинг `311 мс` в HUD**:
     - `GET /api/v1/ping` (`web/routes.py:507-520`) отдает заглушку `random.randint(35, 55)`;
     - `app.js:284-341` игнорирует `game_ping_ms` и красит в желтый клиентский RTT через Cloudflare (`~160-315 мс` при пороге `< 150 мс`), хотя реальный прогретый пинг `VPS -> Игра` составляет `~44.6 мс`, а локальный `/api/v1/ping` отвечает за `2.8 мс`;
     - в `GameHttpClient` нет `HTTP/2` (`h2`), в Nginx отключены `http2`, `upstream keepalive` и `gzip_proxied any`, а `forwarded_prefix_middleware` буферизует даже `/api/v1/ping`.
  3. **Безопасность (P0 + P1)**:
     - боевой 4-символьный `WEB_ADMIN_TOKEN` на VPS совпадает с хардкодом в публичном `web/static/app.js:228,6996` и 241 раз попал в `access.log` Nginx через `?token=`;
     - открыт `/docs`, CORS `*` + `allow_credentials=True`, `POST /api/v1/assets/batch` без авторизации и allowlist префиксов, БД на VPS имеет права `0666`, есть векторы XSS в `innerHTML` (`app.js`).
  4. **Стабильность, RAM (`304 МБ` из `380 МБ`) и CI/CD**:
     - `root_assets_proxy` (`web/app.py:259-268`) падает с `TypeError` (19 раз за 24 ч);
     - `SIGTERM` при рестарте приводит к `SIGKILL` через 20 сек из-за SSE `timeout=25.0` и отсутствия `timeout_graceful_shutdown`;
     - `cp` в `deploy.yml` копирует SQLite в WAL-режиме с потерей 48 минут данных и без автоотката `$PREV_SHA`;
     - `bosses_catalog.json` (1.75 МБ) не кэшируется, а `tattoo_clothing_cache.json` (8.5 МБ) загружен в память 3 копиями; `player_snapshots` (11 531) и `action_logs` (11 168) растут без автоочистки; `repomix-output.xml` (50.5 МБ) и `desktop.ini` раздувают Git.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

### 1.1. ЖЕЛЕЗНЫЕ РАМКИ И ИНВАРИАНТЫ СОХРАННОСТИ (ОБЯЗАТЕЛЬНО К СОБЛЮДЕНИЮ)
- **Принцип нулевых регрессий:** исправление одной проблемы НЕ ИМЕЕТ ПРАВА ломать или ухудшать существующий функционал, UX или скорость отклика интерфейса.
- **Тюрьмы и мастера (сохранение мгновенного расчета энергии на круг):**
  - стоимость энергии на полный круг в тюрьмах и у мастеров статична и в игре не меняется;
  - **НЕЛЬЗЯ** удалять кэши тюрем/мастеров или ломать отображение энергии на круг;
  - необходимо разделить данные на два слоя: **статический справочник** (список тюрем, чекпоинты/стоимость энергии, каталог мастеров - долгий кэш TTL `12-24 часа` как резервная проверка на появление новых тюрем/мастеров после апдейтов игры + ручной сброс при необходимости) и **живой прогресс персонажа** (только активная/выбранная тюрьма и активный `master_target_id`, обновляемые без залпового простукивания всех 16 мастеров каждые 105 сек).
- **Гардероб (сохранение молниеносной примерки наколок, шмота и хат):**
  - **НЕЛЬЗЯ** замедлять примерку или удалять `storage/tattoo_clothing_cache.json` и активный кэш ассетов `/var/cache/prisonbot/assets` (`X-Accel-Redirect` / `HIT-NGINX`);
  - снижение RAM достигается строго за счет устранения **тройного дублирования** одного и того же JSON в памяти (единый read-only синглтон) и кэширования `bosses_catalog.json` в RAM.
- **Честная оптимизация задержки без урезания нужной частоты:**
  - **НЕЛЬЗЯ** искусственно замедлять критичные интервалы (`BossWorker` 12с, быстрая проверка заявок в друзья 30с, `LiveStateHub`, SSE) или подкручивать фейковые цифры пинга;
  - зеленый пинг и снижение нагрузки достигаются за счет сквозного переиспользования данных одного персонажа, пассивного замера реального `game_ping_ms`, HTTP/2, keep-alive и устранения паразитных `429`/`400` запросов.
- **Неприкосновенность файлов и сервисов:**
  - **НЕ удалять** `reference_archive/pro_prison_bot/`, `tests/test_reference_archive.py`, `storage/bosses_catalog.json`, `storage/collections_catalog.json`, `storage/tattoo_clothing_cache.json`, `/var/cache/prisonbot/assets`, `.env`, `storage/prison_bot.db*`, `storage/user_session.session`;
  - **НЕ затрагивать** на VPS соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`).

### 1.2. Блок A - Остановка шторма `429`/`400` и единый шлюз персонажа (`GameHttpClient` + воркеры)
1. **Единый шлюз `GameHttpClient` (`client/http_client.py`):**
   - добавить `httpx[http2]` (`h2`) в `requirements.txt` и включить `http2=True` (с безопасным fallback на HTTP/1.1, если `h2` недоступен) в едином пуле соединений к `oldprison-prod.luckygem.online`;
   - реализовать **пассивный EWMA-трекер реальной задержки `game_ping_ms`**: на каждом успешном HTTP-ответе от игрового сервера фиксировать `rtt_ms = (time.perf_counter() - t0) * 1000`, обновлять сглаженное значение (`ewma_ping_ms`, `last_ping_ms`, `last_ping_ts`) и отдавать через метод `get_ping_stats()`;
   - реализовать **глобальный мягкий rate-limiter и защиту от `429`** для аккаунта:
     - ограничить одновременную конкурентность запросов к игре через `asyncio.Semaphore` (например `4-5`) + минимальный pacing для фоновых батчей, сохраняя приоритет пользовательских действий из WebApp;
     - при получении `HTTP 429` читать заголовок `Retry-After` (или применять адаптивный backoff `3..30s`, экспоненциально при серии `429`), выставлять общее окно `rate_limit_until_ts` на клиенте, чтобы фоновые задачи (`Tier 2`, обогащение, `RoutineWorker`) не добивали сервер в момент лимита, и безопасно ретраить идемпотентные GET-запросы (не более 1-2 раз с backoff, не вешая UI).
2. **Подключение БД ко всем воркерам и устранение `4 188 HTTP 400` (`main.py`, `workers/routine_worker.py`, `workers/boss_worker.py`):**
   - в `main.py:103-128` явно передать `db_engine=get_engine()` в `RoutineWorker`, `BossWorker`, `PrisonWorker`, `SocialWorker` (и внутри методов `RoutineWorker` использовать `engine = self.db_engine or get_engine()`, чтобы персистентность работала всегда);
   - добавить `self._cycle_lock = asyncio.Lock()` в `RoutineWorker` против наложения cron и `run_cycle`;
   - в `RoutineWorker.send_podogrev_if_ready()` (`workers/routine_worker.py:138-167`): при успехе или `HTTP 400` с текстом «уже отправлен сегодня» фиксировать суточный флаг по `day_msk` (в памяти + БД/конфиге или таблице), чтобы до 00:00 МСК не слать повторные `POST /api/podogrev/send` каждые 15 минут;
   - в `RoutineWorker` при `business/collect` `HTTP 400` (`workers/routine_worker.py:693-704`): парсить `timeLeft` (`hours`, `minutes`) из JSON-ответа, сохранять `next_business_collect_ts`, вызывать `on_business_reschedule` и не долбить `POST /api/player/business/collect` до наступления времени сбора;
   - в `BossWorker`: проверить причину `boss_melee_hit` `429`/`400` (`678`/`736` в `action_logs`) - убедиться, что при `429` воркер не пробивает остальные 3 удара в том же цикле, а при `400` (удар на КД / бой уже завершен) обновляет локальный КД и не повторяет удар каждые 12 секунд.
3. **Умное разделение кэшей Тюрем/Мастеров и оптимизация `Tier 2` (`core/scheduler.py`, `web/routes.py`, `workers/friend_outreach_worker.py`):**
   - в `core/scheduler.py:420-430` (`refresh_tier2`) **убрать `force=True`** для статических каталогов мастеров и чекпоинтов тюрем; запускать подзадачи `Tier 2` последовательно с короткой паузой `0.3-0.5s` (а не залповым `asyncio.gather` в одну миллисекунду);
   - в `web/routes.py:2144` и `web/routes.py:2238`: отделить статический кэш стоимости энергии/чекпоинтов и списка мастеров (долгий TTL `12-24 часа` для резервной проверки обновлений игры, плюс явный `force_catalog=True` только по ручному запросу) от живого состояния (опрашивать только выбранный `master_target_id` и активную тюрьму);
   - переиспользовать данные, уже загруженные в `LiveStateHub` / `SingleFlightCache`, между воркерами и UI (единый источник правды для одного персонажа);
   - в `FriendOutreachWorker` добавить проверку `server_health_monitor.is_maintenance` (как во всех остальных воркерах) и уважение глобального `429` окна `GameHttpClient`.

### 1.3. Блок B - Честный зеленый пинг и ускорение транспорта (`web/routes.py`, `web/app.py`, `web/static/app.js`, Nginx на VPS)
1. **Честный `GET /api/v1/ping` (`web/routes.py:507-520`):**
   - полностью удалить фейковый `random.randint(35, 55)`;
   - отдавать реальный `game_ping_ms` (округленный EWMA из `GameHttpClient.get_ping_stats()`) + `game_ping_last_ms`, `game_ping_age_sec`, `server_ts`;
   - если с момента старта еще не было ни одного боевого запроса к игре (или последний запрос был > 60 сек назад), делать один легкий асинхронный замер (с кэшем и защитой от одновременных вызовов через `asyncio.Lock`), не блокируя при нормальной работе.
2. **Оптимизация middleware (`web/app.py:183-224`):**
   - исключить `/api/v1/ping`, `/api/v1/server-health`, `/api/v1/live/stream` и бинарные/ассетные ответы из буферизации в `forwarded_prefix_middleware` (не читать тело и не гонять `.replace()` на каждом пинге).
3. **Честный HUD на фронтенде (`web/static/app.js:284-341`):**
   - в `measurePing()` разбирать JSON-ответ `/api/v1/ping`, получать реальный `gamePing = Number(data.game_ping_ms)` и клиентский `uiRtt = Math.round(performance.now() - t0)`;
   - отображать в `#hud-ping` реальный `gamePing` (если валиден > 0, иначе fallback `uiRtt`) - в штатном режиме это честные `~40-55 мс` (зеленый цвет);
   - обновлять `title` (всплывающую подсказку) обеими реальными метриками: `Игра (VPS -> Сервер): ${gamePing} мс | Интерфейс (Браузер <-> VPS): ${uiRtt} мс`;
   - цветовые пороги для `gamePing`: `< 150 мс` зеленый (`#34d399`), `150..349 мс` желтый (`#fbbf24`), `>= 350 мс` красный (`#f87171`).
4. **Оптимизация Nginx на VPS (`178.17.60.16`):**
   - сделать бэкап текущих конфигов `/etc/nginx/sites-enabled/zvezdoed.space` и `/etc/nginx/nginx.conf` в `/opt/prisonbot/backups/nginx_backup_<ts>/`;
   - включить `http2` на `listen 443 ssl http2;` (или `http2 on;` в зависимости от версии Nginx - предварительно проверить `nginx -v`);
   - добавить `upstream prisonbot_backend { server 127.0.0.1:8085; keepalive 16; }`;
   - в `location /prison/` перевести `proxy_pass http://prisonbot_backend/;` с `proxy_http_version 1.1;` и `proxy_set_header Connection "";` (сохранив отдельно `location = /prison/api/v1/live/stream` с `proxy_buffering off;` и `proxy_cache off;` для SSE);
   - включить `gzip_proxied any;` и `gzip_types` в `/etc/nginx/nginx.conf` (не ломая `crayfish_omni_hub` / `autoclip_service`);
   - проверить `nginx -t && systemctl reload nginx` и выполнить контрольные замеры RTT через `curl`.

### 1.4. Блок C - Безопасность (Токен, SSE без утечки в URL, XSS, права БД, `/docs`, `/assets/batch`)
1. **Замена `WEB_ADMIN_TOKEN` и удаление хардкода:**
   - сгенерировать на VPS криптостойкий 64-символьный hex-токен (`secrets.token_hex(32)`), обновить `WEB_ADMIN_TOKEN=...` в `/opt/prisonbot/.env` (НЕ перезапуская `prisonbot.service` до деплоя нового кода - чтобы новый `.env` и новый код поднялись атомарно при `git push` пользователя через GitHub Actions!);
   - записать новый токен в локальный игнорируемый файл `new_admin_token.txt` (строго добавить `new_admin_token.txt` в `.gitignore` и проверить `git status`, чтобы он никогда не попал в Git) - пользователь один раз введет его в браузере;
   - полностью удалить захардкоженный 4-символьный токен-заглушку из `web/static/app.js:228,6996`.
2. **Устранение утечки токена через `?token=` в SSE (`web/auth.py`, `web/routes.py`, `web/static/app.js`):**
   - реализовать безопасную авторизацию для `EventSource` (`/api/v1/live/stream`) через одноразовый короткоживущий тикет (`POST /api/v1/live/ticket`, TTL 60 сек, хранится в памяти, удаляется/гасится по TTL, передается как `?ticket=...`) ИЛИ `HttpOnly; Secure; SameSite=Strict` cookie (выдаваемую при успешной проверке `X-Admin-Token` / Telegram `initData`), сохранив полную обратную совместимость с заголовком `X-Admin-Token` (и существующими тестами);
   - Telegram Mini App авторизация через `X-Telegram-Init-Data` должна продолжать работать полностью автоматически без ручного ввода токена.
3. **Закрытие XSS и дыр API (`web/app.py`, `web/routes.py`, `web/static/app.js`):**
   - в `web/app.py:176`: отключить публичный Swagger (`docs_url=None, redoc_url=None, openapi_url=None` по умолчанию, разрешать только при `DEBUG=true`);
   - в `web/app.py:238-244`: заменить `allow_origins=["*"]` при `allow_credentials=True` на конкретный белый список (`https://zvezdoed.space`, `http://127.0.0.1:8085`, `http://localhost:8085` + опционально из `settings.CORS_ORIGINS`);
   - в `web/routes.py:442-465` (`POST /api/v1/assets/batch`): добавить строгую проверку allowlist префиксов путей (идентичную `proxy_game_asset`), защиту от `../` и перенести под `verify_admin` (или ограничить лимит + allowlist, предварительно проверив, отправляет ли фронт `getAuthHeaders()` в `/assets/batch` - если отправляет, смело переносить под `api_router`, чтобы не сломать фронт);
   - в `web/routes.py:5607` (`get_official_news_media`): заменить синхронное `file_path.read_bytes()` на `FileResponse`;
   - в `web/static/app.js`: закрыть все выявленные XSS-векторы (`lines 10183, 10240, 10249, 10460, 10570, 4065, 2405-2406, 9212` и остальные `innerHTML` с внешними данными): везде применять `escapeHtml()`, заменить inline `onerror="...textContent='${initial}'"` на безопасный `data-fallback-initial` + делегированный/без-интерполяции обработчик, а `p.html` в новостях прогонять через строгий allowlist-санитайзер (оставляя только безопасные теги `b, strong, i, em, u, s, code, pre, br, p, a[href^=http|https|tg]` и удаляя `script, img, svg, iframe, on*` атрибуты);
   - на VPS выставить права `chmod 700 /opt/prisonbot/storage` и `chmod 600 /opt/prisonbot/storage/prison_bot.db*`.

### 1.5. Блок D - Стабильность, RAM-синглтон, БД, Graceful Shutdown, CI/CD и чистота проекта
1. **Фикс падения `/assets/{rest_path:path}` (`web/app.py:259-268`):**
   - добавить `request: Request` в `root_assets_proxy` и передавать `await proxy_game_asset(request=request, path=f"assets/{rest_path}")`.
2. **Мягкий рестарт без `SIGKILL` (`main.py`, `web/routes.py`, `core/state_hub.py`):**
   - добавить глобальный `shutdown_event` (или метод `state_hub.begin_shutdown()`, который рассылает sentinel `None` всем активным очередям SSE-подписчиков);
   - в `event_generator()` (`/api/v1/live/stream`, `web/routes.py:7624-7632`) ожидать очередь и `shutdown_event` (либо проверять `request.is_disconnected()` + шаг heartbeat <= 5 сек с немедленным выходом при shutdown);
   - в `main.py:298-305` задать `timeout_graceful_shutdown=5` в `uvicorn.Config(...)`, в `finally` (`main.py:363-381`) вызывать `state_hub.begin_shutdown()`, отменять `startup_workers_task` и фоновые задачи `scheduler.controller` (`_battle_watcher_task`, `_wakeup_tasks`) и выполнять `await get_engine().dispose()`.
3. **Единый RAM-синглтон справочников (`core/catalog_cache.py`):**
   - создать легкий модуль `core/catalog_cache.py` с `mtime`-кэшированием в памяти (один экземпляр на весь процесс):
     - `get_bosses_catalog()` -> кэширует `storage/bosses_catalog.json` (1.75 МБ);
     - `get_tattoo_clothing_cache()` -> кэширует `storage/tattoo_clothing_cache.json` (8.5 МБ) **ровно в одной копии**;
     - `get_collections_catalog()` -> кэширует `storage/collections_catalog.json`;
   - переключить `client/api/boss.py`, `client/api/player.py`, `client/api/social.py`, `core/drop_parser.py`, `web/routes.py` на `core/catalog_cache.py` (сохраняя обратную совместимость публичных функций вроде `_load_bosses_catalog()`, чтобы все тесты работали без поломок).
4. **Гигиена SQLite и удаление дубля `/news` (`core/database.py`, `core/scheduler.py`, `web/routes.py`):**
   - в `init_db()` (`core/database.py`) добавить безопасное создание недостающих индексов (`CREATE INDEX IF NOT EXISTS`):
     - `idx_player_snapshots_acc_created` на `player_snapshots(account_id, created_at)`;
     - `idx_action_logs_acc_created` на `action_logs(account_id, created_at)`;
     - `idx_tracked_candidates_acc_obshak_seen` на `tracked_candidates(account_id, obshak_type, last_seen_at)`;
     - удалить дублирующиеся индексы `notifications`, если они создаются повторно;
   - добавить ежесуточную фоновую задачу прунинга БД (`prune_old_records`: удалять `player_snapshots` старше 7 дней, `action_logs` старше 14 дней, пачками по 1000 строк, без блокировки event loop);
   - удалить мертвый дубликат `@api_router.get("/news")` (`get_news_list` в `web/routes.py:6165`, затененный `get_official_news` на `5581`).
5. **Безопасный WAL-бэкап и автооткат в CI/CD (`.github/workflows/deploy.yml`):**
   - заменить небезопасный `cp /opt/prisonbot/storage/prison_bot.db ...` на консистентный онлайн-бэкап через Python SQLite Backup API (`python -c "import sqlite3; ... src.backup(dst)"`) с сохранением последних 5 бэкапов;
   - сохранить `PREV_SHA=$(git rev-parse HEAD)` до `git reset --hard origin/main`: если `pip install`, `systemctl restart` или health-check провалился - автоматически выполнить `git reset --hard "$PREV_SHA"`, перезапустить `prisonbot.service`, вывести последние 40 строк `journalctl` и завершить джобу с `exit 1`.
6. **Чистка Git, 12 warnings `pytest` и осиротевшего кэша на VPS:**
   - добавить `pytest.ini` с `asyncio_default_fixture_loop_scope = function`;
   - устранить все 12 warnings в `tests/` (`await engine.dispose()` в async-тестах `test_boss_worker.py`, `test_raids_api.py`, `test_bot_handlers.py`; корректные `AsyncMock` для `get_monthly_state` в `test_social_worker.py` и фоновых задач в `test_web_api.py`);
   - убрать из Git (через `git rm --cached` + `.gitignore`, не удаляя важные локальные файлы без нужды) `repomix-output.xml` (50.5 МБ), `desktop.ini`, неиспользуемый `web/static/assets/icons/bot_logo.png` (2.55 МБ - убедившись, что нигде в коде и тестах он не используется, а используется `bot_logo_128.webp`), добавить `new_admin_token.txt` и `audit_report.md` в `.gitignore`;
   - на VPS проверить `.env` (`ASSET_CACHE_DIR=/var/cache/prisonbot/assets`): если `/opt/prisonbot/storage/asset_cache` действительно не используется сервисом - удалить только осиротевшую папку `/opt/prisonbot/storage/asset_cache` (272 МБ), **НЕ трогая `/var/cache/prisonbot/assets`**;
   - обновить версии статики (`20261128_01` / `prisonbot-assets-v38`) во всех нужных файлах (`index.html`, `app.js`, `sw.js` и тестах версий).

---

## 2. КОНФИГУРАЦИЯ

### 2.1. Затрагиваемые файлы в репозитории
- `core/catalog_cache.py` (новый файл) - единый синглтон-кэш JSON-справочников.
- `client/http_client.py` - `http2=True`, пассивный EWMA `game_ping_ms`, глобальный семафор + `429` backoff.
- `client/api/boss.py`, `client/api/player.py`, `client/api/social.py`, `core/drop_parser.py` - переход на `core/catalog_cache.py`.
- `main.py` - передача `db_engine=get_engine()` всем воркерам, `timeout_graceful_shutdown=5`, корректный cleanup в `finally`.
- `core/database.py` - индексы, `prune_old_records()`, суточные метаданные/флаги при необходимости.
- `core/state_hub.py` - `begin_shutdown()` для мгновенного пробуждения и закрытия SSE-потоков.
- `core/scheduler.py` - последовательный `Tier 2` без `force=True` на каталоги, ежесуточная задача прунинга БД.
- `workers/routine_worker.py` - `asyncio.Lock`, fallback `self.db_engine or get_engine()`, суточный кэш подогревов, парсинг `timeLeft` на `business/collect` 400.
- `workers/boss_worker.py` - защита от повторных `boss_melee_hit` при `429`/`400`.
- `workers/friend_outreach_worker.py` - проверка `server_health_monitor.is_maintenance`.
- `web/app.py` - фикс `root_assets_proxy(request)`, отключение публичного `/docs`, ограничение CORS, исключение `/api/v1/ping` и `/api/v1/server-health` из `forwarded_prefix_middleware`.
- `web/auth.py`, `web/routes.py` - честный `/api/v1/ping`, безопасная SSE-авторизация (ticket/cookie), разделение статического/живого кэша тюрем и мастеров, защита `/assets/batch`, `FileResponse` для `/news/media/{id}`, удаление дубля `/news`, graceful SSE shutdown.
- `web/static/index.html`, `web/static/app.js`, `web/static/sw.js` - удаление хардкода токена, честный HUD-пинг с тултипом двух метрик, закрытие XSS, обновление версии кэша (`20261128_01` / `prisonbot-assets-v38`).
- `.github/workflows/deploy.yml`, `.gitignore`, `requirements.txt`, `pytest.ini` (новый файл).
- `tests/` - правка 12 warnings + новые автотесты на все P0/P1 фиксы.

### 2.2. Инфраструктурные изменения на VPS (`178.17.60.16`)
- `/etc/nginx/sites-enabled/zvezdoed.space` и `/etc/nginx/nginx.conf` (с предварительным бэкапом и проверкой `nginx -t && systemctl reload nginx`).
- `/opt/prisonbot/.env` - обновление `WEB_ADMIN_TOKEN` на новый 64-символьный hex (вступит в силу атомарно при рестарте после CI/CD деплоя; копия сохраняется локально в игнорируемый `new_admin_token.txt`).
- `chmod 700 /opt/prisonbot/storage` и `chmod 600 /opt/prisonbot/storage/prison_bot.db*`.
- Удаление осиротевшего `/opt/prisonbot/storage/asset_cache` (только после подтверждения, что активен `/var/cache/prisonbot/assets`).
- **НЕ перезапускать `prisonbot.service` вручную и НЕ заливать файлы кода вручную на VPS** - код выкатится автоматически через GitHub Actions после `git push` пользователя!

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Архитектурная синергия «один персонаж - единый контур»
```text
                    ┌──────────────────────────────────────────┐
                    │   core/catalog_cache.py (1 копия в RAM)  │
                    │  bosses (1.75MB) + wardrobe (8.5MB) +    │
                    │  collections + static prisons/masters    │
                    └────────────────────┬─────────────────────┘
                                         │ (0 disk I/O в event loop,
                                         │  молниеносная примерка)
                                         ▼
WebApp / SSE ──▶ FastAPI (web/routes.py) ◀──▶ LiveStateHub (общие снимки)
                                         ▲
                                         │ (переиспользование без дублей)
                Workers (main.py -> db_engine=get_engine())
                Boss | Prison | Routine(Lock) | Social | Outreach
                                         │
                                         ▼
                    ┌──────────────────────────────────────────┐
                    │   GameHttpClient (единый шлюз аккаунта)  │
                    │  - HTTP/2 (h2) keep-alive                │
                    │  - Пассивный EWMA game_ping_ms (~45 ms)  │
                    │  - Semaphore + глобальный 429 backoff    │
                    └────────────────────┬─────────────────────┘
                                         ▼
                         oldprison-prod.luckygem.online
```

### 3.2. Поведение `GET /api/v1/ping` и `#hud-ping`
- Бэкенд возвращает:
  ```json
  {
    "ok": true,
    "game_ping_ms": 45,
    "game_ping_last_ms": 44,
    "game_ping_age_sec": 3.2,
    "server_ts": 1795800000.12
  }
  ```
- Если `GameHttpClient` еще не делал запросов (холодный старт), делается один защищенный `Lock` легкий запрос (`GET /api/player/me`), иначе ответ формируется чисто из RAM за `~2 мс` без нагрузки на игру.
- На фронте `#hud-ping` отображает `${game_ping_ms} мс` (зеленый `< 150 мс`, желтый `150..349 мс`, красный `>= 350 мс`), а атрибут `title` показывает обе честные метрики (`Игра: 45 мс | Браузер <-> VPS: 140 мс`).

### 3.3. Консистентный онлайн-бэкап SQLite и автооткат в `.github/workflows/deploy.yml`
```bash
PREV_SHA="$(git rev-parse HEAD)"
rollback() {
  echo "Deploy failed! Rolling back to $PREV_SHA..."
  git reset --hard "$PREV_SHA"
  systemctl restart prisonbot.service || true
  journalctl -u prisonbot.service -n 40 --no-pager || true
  exit 1
}
# Онлайн-бэкап через SQLite Backup API (безопасно для WAL!)
/opt/prisonbot/venv/bin/python -c "import sqlite3, time; src=sqlite3.connect('/opt/prisonbot/storage/prison_bot.db'); dst=sqlite3.connect(f'/opt/prisonbot/backups/prison_bot_{time.strftime(\"%Y%m%d_%H%M%S\")}.db'); src.backup(dst); dst.close(); src.close()"
```
- Проверить точный путь к `python` в `/opt/prisonbot/venv/bin/python` из текущего `deploy.yml` и убедиться, что тест `tests/test_ci_workflow.py` валидирует обновленный YAML.

### 3.4. Безопасная авторизация SSE без `?token=`
- Добавить `POST /api/v1/live/ticket` (под `verify_admin`): генерирует `secrets.token_urlsafe(24)`, сохраняет в памяти с `expires_at = time.monotonic() + 60.0` (с автоочисткой просроченных), возвращает `{"ticket": "..."}`.
- В `GET /api/v1/live/stream`: принимать либо валидный `ticket` (погашая или проверяя TTL), либо `HttpOnly` cookie, либо стандартный `X-Admin-Token` / `initData`. В `app.js` перед открытием `new EventSource(...)` сначала запрашивать `/api/v1/live/ticket` с `getAuthHeaders()` и открывать `/api/v1/live/stream?ticket=...` - реальный `WEB_ADMIN_TOKEN` больше никогда не попадает в URL и `access.log` Nginx.

---

## 4. ТЕСТИРОВАНИЕ

Обязательно сохранить 100% прохождение всех существующих 320 тестов (0 failed, **0 warnings**) и добавить целевые автотесты на каждый новый фикс:
1. **Тест `GameHttpClient` (`tests/test_http_client_resilience.py` или расширение существующих):**
   - пассивный замер реального EWMA `game_ping_ms`;
   - обработка `HTTP 429` с `Retry-After` и выставление глобального `rate_limit_until_ts`.
2. **Тест `RoutineWorker` и `BossWorker`:**
   - при `db_engine` таблица `daily_interaction_targets` реально заполняется и повторный цикл в тот же день не шлет `POST /api/interaction/perform`;
   - `send_podogrev_if_ready()` после `HTTP 400` («уже отправлен сегодня») не повторяет запрос в тот же день;
   - `business/collect` после `HTTP 400` с `timeLeft` планирует перенос и не спамит повторно.
3. **Тест `core/catalog_cache.py`:**
   - однократная загрузка `bosses_catalog.json` и `tattoo_clothing_cache.json` (повторные вызовы возвращают кэшированный объект без повторного чтения с диска).
4. **Тест веб-эндпоинтов и безопасности (`tests/test_web_endpoints.py` / `tests/test_web_api.py`):**
   - `GET /assets/PrisonV3/...` (`root_assets_proxy`) не падает с `TypeError`;
   - `GET /api/v1/ping` возвращает реальное значение из `GameHttpClient`, без `random.randint`;
   - `POST /api/v1/live/ticket` выдает одноразовый тикет, принимаемый `/api/v1/live/stream`, а невалидный/просроченный тикет отклоняется `401`;
   - `/docs` недоступен в продакшен-режиме;
   - `POST /api/v1/assets/batch` отклоняет пути вне allowlist и с `../`;
   - в `web/static/app.js` отсутствует захардкоженный 4-символьный токен-заглушка и внешние поля в критичных шаблонах экранированы через `escapeHtml`.
5. **Тест `tests/test_ci_workflow.py`:**
   - проверка наличия WAL-безопасного `backup(` и логики rollback `$PREV_SHA` в `.github/workflows/deploy.yml`, а также проверка `.gitignore` на `new_admin_token.txt` и `repomix-output.xml`.
6. **Тест graceful shutdown SSE и прунинга БД:**
   - `state_hub.begin_shutdown()` немедленно завершает генератор SSE;
   - `prune_old_records()` удаляет записи старше порога и сохраняет свежие.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

### Чеклист выполнения
- [ ] 1. Создать `core/catalog_cache.py` и перевести `boss.py`, `player.py`, `social.py`, `drop_parser.py`, `routes.py` на единый кэш-синглтон (сохранив мгновенную примерку в Гардеробе и все публичные сигнатуры).
- [ ] 2. Обновить `client/http_client.py` (`h2`/HTTP2, пассивный EWMA `game_ping_ms`, глобальный семафор + `429` backoff с `Retry-After`) и добавить `h2` / `httpx[http2]` в `requirements.txt`.
- [ ] 3. Исправить первопричины шторма `429`/`400`: передать `db_engine=get_engine()` всем воркерам в `main.py`, добавить `asyncio.Lock`, суточный кэш подогревов и разбор `timeLeft` бизнесов в `workers/routine_worker.py`, защитить `BossWorker` от повторов при `429`/`400`, убрать `force=True` на каталоги мастеров/тюрем в `core/scheduler.py` (`Tier 2`) и `web/routes.py` (разделив статику 12-24ч и живой прогресс), добавить `is_maintenance` в `FriendOutreachWorker`.
- [ ] 4. Реализовать честный `/api/v1/ping` (без `random`), исключить `/api/v1/ping` и `/api/v1/server-health` из `forwarded_prefix_middleware`, обновить HUD-пинг в `web/static/app.js` (вывод `game_ping_ms` + тултип с обеими метриками).
- [ ] 5. Закрыть безопасность: удалить хардкод токена из `app.js`, внедрить `/api/v1/live/ticket` для SSE, закрыть `/docs`, ограничить CORS, защитить `/assets/batch` и перевести `/news/media/{id}` на `FileResponse`, закрыть XSS в `app.js` (`escapeHtml`, убрать опасный inline `onerror`, санитайзер HTML новостей).
- [ ] 6. Исправить `root_assets_proxy` (`web/app.py`), реализовать graceful shutdown SSE + `timeout_graceful_shutdown=5` + cleanup в `main.py`, удалить дубль `/news`, добавить индексы и `prune_old_records()` в `core/database.py` + `core/scheduler.py`.
- [ ] 7. Обновить `.github/workflows/deploy.yml` (онлайн-бэкап `sqlite3.backup` + автооткат `$PREV_SHA`), почистить Git (`repomix-output.xml`, `desktop.ini`, неиспользуемый `bot_logo.png` -> `.gitignore`), добавить `pytest.ini`, устранить все 12 warnings и поднять версии статики (`20261128_01` / `prisonbot-assets-v38`).
- [ ] 8. Выполнить системную подготовку на VPS (`178.17.60.16`) БЕЗ ручного деплоя кода и БЕЗ рестарта `prisonbot.service`:
  - бэкап и оптимизация Nginx (`http2`, `upstream keepalive`, `gzip_proxied any`), проверка `nginx -t && systemctl reload nginx` и контрольный замер `curl`;
  - сгенерировать новый 64-символьный `WEB_ADMIN_TOKEN` в `/opt/prisonbot/.env` и сохранить его локально в игнорируемый `new_admin_token.txt`;
  - выставить `chmod 700 /opt/prisonbot/storage` и `chmod 600 /opt/prisonbot/storage/prison_bot.db*`;
  - подтвердить `ASSET_CACHE_DIR=/var/cache/prisonbot/assets` и удалить осиротевший `/opt/prisonbot/storage/asset_cache` (272 МБ).
- [ ] 9. Написать новые автотесты, прогнать `node --check` и полный `python -m pytest -q tests/` (добиться `0 failed, 0 warnings`), проверить `git status` (убедиться, что `new_admin_token.txt` и `repomix-output.xml` не попадают в коммит) и выдать краткий отчет готовности к `git push` пользователя из VS Code.

### Команды проверки
```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -q tests/
git ls-files storage/
git status
```