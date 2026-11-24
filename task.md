# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ВЫКАТКА ОБНОВЛЕНИЯ PRISONBOT НА РАБОТАЮЩИЙ VPS (КОНВЕЙЕР БОССОВ, АВТОСЛИВ ХОДОК, LIVESTATEHUB + SSE) БЕЗ ПОТЕРИ ДАННЫХ ПРОДАКШЕНА

Ты выступаешь в роли Senior DevOps & Python Backend инженера. Твоя задача - подключиться к уже настроенному Linux VPS по реквизитам из локального файла `.env_server`, определить текущую рабочую директорию и активный `systemd`-сервис `PrisonBot`, сделать резервную копию продакшен-БД, накатить **только свежее обновление кода и статики** (конвейер боссов, `drain_all_energy` + точный реген ходок, `LiveStateHub`, SSE `/api/v1/live/stream`, `LiveSyncClient` и keyed DOM-патчинг) строго **без перезаписи** серверного `.env`, продакшен-БД `storage/prison_bot.db` и сессии `storage/user_session.session`, донастроить существующий обратный прокси под небуферизуемый SSE-поток, перезапустить сервис и подтвердить исправную работу всего конвейера и живой синхронизации 24/7.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Инкрементальное обновление поверх существующей установки (НЕ деплой с нуля):**
   - Подключиться к VPS по `.env_server` (под Windows использовать Python `paramiko` / SFTP при парольном входе или нативный `ssh` при ключевом).
   - Автоматически обнаружить текущий `systemd`-юнит `PrisonBot`, его `WorkingDirectory`, путь к `venv`, занятый локальный порт и настроенный прокси-конфиг (Nginx/Caddy/tunnel).
   - **Категорически запрещено** пересоздавать `venv` с нуля без необходимости, трогать соседние проекты (Docker-контейнер «Ракомания`» и конвейер клипов) или выводить секреты из `.env_server` / `.env` в консоль и отчет.
2. **Полная сохранность продакшен-данных на VPS:**
   - **Категорически запрещено** затирать на сервере:
     - `.env`;
     - `storage/prison_bot.db` (и его `-wal` / `-shm`);
     - `storage/user_session.session`;
     - `storage/asset_cache/`.
   - Перед обновлением кода обязательно создать резервную копию серверной `storage/prison_bot.db` (через `sqlite3` backup в `/tmp/prison_bot_backup_<timestamp>.db` или рядом в `storage/backups/`) и проверить, нет ли на сервере лишнего корневого файла `prison_bot.db` рядом с `storage/prison_bot.db` (с учетом новой `normalize_db_url()` в `core/database.py`).
3. **Выгрузка полного комплекта обновленного кода и статики:**
   - Синхронизировать на сервер все обновленные модули из локального репозитория:
     - `main.py`, `requirements.txt`;
     - `core/` (включая новый `core/state_hub.py`, обновленные `core/scheduler.py`, `core/database.py`, `core/models.py`, `core/config.py`, `core/drop_parser.py`);
     - `workers/` (`boss_worker.py`, `prison_worker.py`, `routine_worker.py`, `social_worker.py`);
     - `client/`, `bot/`, `telegram/`;
     - `web/` (`app.py`, `auth.py`, `routes.py`, `web/static/app.js`, `web/static/index.html`, `web/static/styles.css`, `web/static/spine_room_player.js`, `web/static/vendor/`, `web/static/assets/`).
   - Исключить из синхронизации: `.env`, `.env_server`, `storage/prison_bot.db*`, `storage/user_session.session*`, `storage/asset_cache/`, `reference_archive/`, `raw_dump/`, `parsed_js/`, `inf/`, `ref/`, `scratch/`, `screenshots/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `repomix*.xml`.
   - При наличии новых зависимостей в `requirements.txt` доустановить их в существующий `venv` сервера.
4. **Донастройка обратного прокси для SSE (`/api/v1/live/stream`):**
   - Проверить текущий конфиг обратного прокси (Nginx / Caddy / Cloudflare Tunnel), обслуживающий веб-панель `PrisonBot`.
   - Если перед ботом стоит Nginx - обязательно добавить (или проверить наличие) отдельного блока `location /api/v1/live/stream` с отключенной буферизацией (`proxy_buffering off;`, `proxy_cache off;`, `proxy_read_timeout 86400s;`, `proxy_http_version 1.1;`, `proxy_set_header Connection "";`, `add_header X-Accel-Buffering no;`), чтобы живые события `LiveStateHub` доходили до браузера мгновенно и соединение не рвалось по таймауту.
   - Если стоит Caddy - убедиться в наличии `flush_interval -1` (или стандартного стриминга без буферизации).
   - Проверить конфиг прокси (`nginx -t` / `caddy validate`) и выполнить мягкий `reload` без простоя соседних сайтов.
5. **Чистый перезапуск и боевая проверка конвейера:**
   - Убедиться, что локальный экземпляр `PrisonBot` на ПК не запущен (исключить `409 Conflict` и конфликт Telethon-сессии).
   - Перезапустить `systemd`-сервис на VPS и подтвердить по живым логам и HTTP/SSE-запросам, что:
     - `LiveStateHub` прогрел все 12 срезов и отдает `event: snapshot` через локальный порт **и** через публичный HTTPS URL;
     - `BossWorker` и `PrisonWorker` перешли на новый конвейерный режим (12с/60с адаптивный цикл боссов, точный реген ходок, `POST /api/v1/prisons/drain`, крон туалетки `00:01` МСК);
     - в `journalctl` нет `Traceback`, `409 Conflict`, ошибок БД или прокси, а потребление RAM в норме.

---

## 2. КОНФИГУРАЦИЯ

Задействованные файлы и компоненты:

```text
Локальный источник обновления (PrisonBot/):
├── .env_server                         # Реквизиты SSH (ТОЛЬКО чтение локально, НЕ выгружать)
├── main.py                             # Единая инициализация bot_context и LiveStateHub
├── requirements.txt                    # Проверка/доустановка зависимостей в существующий venv
├── core/
│   ├── state_hub.py                    # Новый модуль фонового живого состояния + SSE pub/sub
│   ├── scheduler.py                    # Тиры прогрева LiveStateHub, адаптивный 12с/60с BossWorker, точный next_run_time PrisonWorker
│   └── database.py                     # normalize_db_url() к storage/prison_bot.db
├── workers/
│   ├── boss_worker.py                  # Конвейер боссов (reward/claim -> мгновенный next start)
│   ├── prison_worker.py                # drain_all_energy() + compute_next_stage_wait_seconds()
│   ├── routine_worker.py               # Пуш обновлений в LiveStateHub + 00:01 МСК туалетка
│   └── social_worker.py                # Пуш обновлений друзей/радара в LiveStateHub
├── client/, bot/, telegram/            # Актуальные API-клиенты и обработчики
└── web/
    ├── app.py                          # SSEAwareGZipMiddleware + инициализация LiveStateHub
    ├── auth.py                         # Поддержка SSE-авторизации (?token= / ?init_data=)
    ├── routes.py                       # POST /api/v1/prisons/drain, GET /api/v1/live/stream, GET /api/v1/live/delta, мгновенные wake-up триггеры
    └── static/                         # app.js (LiveSyncClient + reconcileKeyedList), styles.css, index.html, spine_room_player.js, vendor/, assets/

Неприкосновенные файлы на VPS (НЕ перезаписывать!):
├── <REMOTE_DIR>/.env
├── <REMOTE_DIR>/storage/prison_bot.db (+ -wal/-shm)
├── <REMOTE_DIR>/storage/user_session.session
└── <REMOTE_DIR>/storage/asset_cache/
```

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Шаг обнаружения текущей установки на VPS
1. Прочитать `.env_server` локально (проверить, что `.env_server` в `.gitignore`).
2. Найти на VPS активный сервис и директорию `PrisonBot`:
   ```bash
   systemctl list-units --type=service --all | grep -iE 'prison|obshak|bot' || true
   systemctl cat prisonbot.service 2>/dev/null || true
   ps aux | grep -iE 'main\.py|uvicorn|prison' | grep -v grep || true
   ```
3. Зафиксировать реальные значения: `SERVICE_NAME`, `REMOTE_DIR`, `VENV_PYTHON`, `WEB_PORT`, `WEBAPP_PUBLIC_URL` (из серверного `.env`, без вывода токенов/паролей в отчет) и путь к конфигу обратного прокси.

### 3.2. Бэкап продакшен-БД и аудит пути БД на VPS
1. Убедиться, что на локальном ПК не запущен процесс `PrisonBot`.
2. На VPS аккуратно остановить `systemctl stop <SERVICE_NAME>` перед заменой кода и бэкапом SQLite (простой составит всего ~10-20 секунд, зато гарантирует чистый WAL-checkpoint без гонок записи).
3. Сделать консистентный бэкап `<REMOTE_DIR>/storage/prison_bot.db` через Python `sqlite3.backup()` в `<REMOTE_DIR>/storage/backups/prison_bot_pre_update_<YYYYMMDD_HHMMSS>.db`.
4. Проверить, нет ли пустого/старого `<REMOTE_DIR>/prison_bot.db` в корне директории на VPS:
   - если файл отсутствует - ничего не делать;
   - если присутствует и он пустой/меньше рабочей `storage/prison_bot.db` - перенести его в `storage/backups/`, чтобы не путать среду.

### 3.3. Упаковка и раскатка обновления кода
1. Собрать локально временный компактный `.tar.gz` **строго из кода и статики** (`main.py`, `requirements.txt`, `core/`, `workers/`, `client/`, `bot/`, `telegram/`, `web/`, плюс обновленные каталоги `storage/bosses_catalog.json` и `storage/tattoo_clothing_cache.json` при наличии локальных изменений).
2. **Строго не включать** в архив `.env`, `.env_server`, `storage/prison_bot.db*`, `storage/user_session.session*`, `storage/asset_cache/`, `reference_archive/`, `raw_dump/`, `parsed_js/`, `inf/`, `ref/`, `scratch/`, `screenshots/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `repomix*.xml`.
3. Загрузить архив на VPS, распаковать поверх `<REMOTE_DIR>` (предварительно очистив старые `__pycache__` внутри `core/`, `workers/`, `web/`, `client/`, `bot/`), удалить временный архив локально и на сервере.
4. Проверить и при необходимости доустановить зависимости в существующий `venv`:
   ```bash
   <REMOTE_DIR>/venv/bin/pip install --no-cache-dir -r <REMOTE_DIR>/requirements.txt
   <REMOTE_DIR>/venv/bin/python -c "import main, core.state_hub, core.scheduler, web.app, workers.boss_worker, workers.prison_worker"
   ```

### 3.4. Донастройка прокси под SSE и запуск сервиса
1. Проинспектировать конфиг обратного прокси для `PrisonBot` (Nginx/Caddy/tunnel):
   - если это Nginx и в конфиге еще нет отдельного `location /api/v1/live/stream` с `proxy_buffering off;` - аккуратно добавить этот блок в существующий `server { ... }` бота (не затрагивая «Ракоманию`» и остальные сайты!), выполнить `nginx -t` и `systemctl reload nginx`;
   - если это Caddy - убедиться, что `reverse_proxy` не буферизует SSE (`flush_interval -1`), проверить `caddy validate` и выполнить `systemctl reload caddy`.
2. Убедиться, что в `systemd`-юните заданы `Environment=PYTHONUNBUFFERED=1` и адекватные лимиты (`MemoryHigh=300M`, `MemoryMax=450M`), при правке юнита выполнить `systemctl daemon-reload`.
3. Запустить сервис:
   ```bash
   systemctl start <SERVICE_NAME>
   ```

---

## 4. ТЕСТИРОВАНИЕ

После старта обновленного сервиса выполнить полную проверку на VPS (без вывода секретов в отчет):

1. **Статус `systemd` и логи прогрева (через 15-20 секунд после старта):**
   ```bash
   systemctl status <SERVICE_NAME> --no-pager
   journalctl -u <SERVICE_NAME> -n 120 --no-pager
   ```
   - подтвердить `active (running)` и `0` перезапусков;
   - подтвердить в логах успешный прогрев `LiveStateHub`, запуск всех задач `APScheduler` (`BossWorker`, `PrisonWorker`, `RoutineWorker`, `SocialWorker`, `refresh_tier1/2/3`, крон туалетки `00:01` МСК) и запуск `aiogram` без `Traceback` и `409 Conflict`.
2. **Проверка обновленного API, статики и SSE-потока (локально на VPS и через публичный URL):**
   - проверить, что `GET http://127.0.0.1:<PORT>/` возвращает `200 OK`, а `GET /static/app.js` содержит новый код (`LiveSyncClient` и `/prisons/drain`);
   - проверить локальный SSE-поток:
```bash
curl -sS -N --max-time 6 "[http://127.0.0.1](http://127.0.0.1):<PORT>/api/v1/live/stream?token=<ADMIN_TOKEN>" | head -n 15
```
     убедиться, что в первые 1-2 секунды сразу приходит `event: snapshot` с прогретыми срезами;
   - проверить **публичный HTTPS URL (`WEBAPP_PUBLIC_URL`)** снаружи: `200 OK` на главной странице и немедленное получение `event: snapshot` через прокси на `<WEBAPP_PUBLIC_URL>/api/v1/live/stream?token=<ADMIN_TOKEN>` (подтверждение, что Nginx/Caddy действительно НЕ буферизует SSE!);
   - проверить `GET /api/v1/live/delta` (`200 OK`).
3. **Проверка ресурсов и сохранности соседних сервисов:**
   ```bash
   free -h
   df -h
   systemctl show <SERVICE_NAME> -p MemoryCurrent -p MainPID
   docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true
   ```
   - подтвердить штатную работу контейнера «Ракомания» и конвейера клипов, нормальное потребление RAM у `PrisonBot` и наличие свободного места на диске.
4. **Проверка чистоты:**
   - убедиться, что временные архивы деплоя удалены локально и на сервере, а локальный `git status` чист от временных файлов.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

Выполняй задачи последовательно, отмечая прогресс:

- [ ] **Шаг 1:** Безопасно прочитать `.env_server` (убедиться, что он в `.gitignore`), подключиться к VPS и определить текущий `SERVICE_NAME`, `REMOTE_DIR`, `WEB_PORT`, `WEBAPP_PUBLIC_URL` и конфиг обратного прокси (Nginx/Caddy/tunnel).
- [ ] **Шаг 2:** Убедиться, что локальный `PrisonBot` на ПК остановлен; на VPS остановить `<SERVICE_NAME>`, создать консистентный бэкап `<REMOTE_DIR>/storage/prison_bot.db` в `<REMOTE_DIR>/storage/backups/` и проверить отсутствие лишнего корневого `prison_bot.db`.
- [ ] **Шаг 3:** Упаковать и загрузить на VPS только обновленный код и статику (`main.py`, `requirements.txt`, `core/`, `workers/`, `client/`, `bot/`, `telegram/`, `web/`), строго сохранив нетронутыми серверные `.env`, `storage/prison_bot.db`, `storage/user_session.session` и `storage/asset_cache/`. Удалить временные архивы.
- [ ] **Шаг 4:** Доустановить недостающие зависимости (если есть) в существующий `venv` сервера и проверить импорты (`import main, core.state_hub, core.scheduler, web.app, workers.boss_worker, workers.prison_worker`).
- [ ] **Шаг 5:** Проверить и при необходимости донастроить конфиг обратного прокси (Nginx/Caddy) для небуферизуемого SSE на `/api/v1/live/stream`, провалидировать конфиг и мягко перезагрузить прокси (не затрагивая «Ракоманию» и остальные сайты).
- [ ] **Шаг 6:** Запустить `<SERVICE_NAME>` и через 15-20 секунд проверить `systemctl status`, `journalctl` (прогрев `LiveStateHub`, конвейер `BossWorker`, точный реген `PrisonWorker`, 0 ошибок), свежесть `/static/app.js`, мгновенную доставку `event: snapshot` по локальному и публичному URL `/api/v1/live/stream`, а также ресурсы VPS и сохранность соседних сервисов. Выдать краткий итог по деплою и подтверждение работы обновления.