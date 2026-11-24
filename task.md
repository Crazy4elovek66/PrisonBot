# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: АУДИТ РЕСУРСОВ VPS, ПРОВЕРКА СЕТЕВОЙ ДОСТУПНОСТИ ИГРЫ И ПРОДАКШЕН-ДЕПЛОЙ PRISONBOT 24/7 НА СЕРВЕР

Ты выступаешь в роли Senior DevOps, Linux Systems & Python Backend инженера. Твоя задача - подключиться к удаленному Linux VPS по реквизитам из локального файла `.env_server`, выполнить полный аудит свободных ресурсов сервера (RAM, Swap, CPU, SSD, занятые порты и соседние сервисы) без остановки и нарушения работы уже запущенных проектов (конвейера клипов и Docker-контейнера «Ракомания»), проверить сетевую доступность игрового сервера через `curl -I https://oldprison-prod.luckygem.online/` и сопутствующие эндпоинты, после чего собрать чистый релиз `PrisonBot`, выгрузить его на VPS, настроить изолированное окружение, `systemd`-сервис с лимитами памяти и HTTPS-доступ для Telegram WebApp, и подтвердить стабильную автономную работу бота 24/7.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Безопасное чтение реквизитов из `.env_server`:**
   - Прочитать параметры подключения (host, port, user, password/ssh-key) из `.env_server` в корне проекта `PrisonBot`.
   - **Строгое правило безопасности:** никогда не выводить пароли, приватные ключи, токены из `.env_server` и `.env` в логи, терминальный вывод отчета или коммиты; убедиться, что `.env_server` добавлен в `.gitignore`, и **не** загружать `.env_server` на удаленный сервер.
   - Учесть, что локальная машина работает под Windows (где нет `sshpass`), поэтому при парольной SSH-аутентификации использовать `paramiko` / `scp` из Python либо нативный `ssh` при ключевой аутентификации.
2. **Неприкосновенность существующих проектов на VPS:**
   - **Категорически запрещено** останавливать, перезапускать или модифицировать контейнер «Ракомания» и работающий конвейер клипов (кроме неразрушающей диагностики их текущего потребления ресурсов).
   - Любой веб-порт `PrisonBot` и конфиг обратного прокси (Nginx/Caddy) должны быть подобраны так, чтобы полностью исключить конфликт портов и маршрутов с существующими сервисами.
3. **Аудит свободных ресурсов и вердикт по стабильности (`Go / No-Go`):**
   - Снять с VPS актуальные метрики: RAM и Swap (`free -h`, `swapon --show`), диск (`df -h`), CPU и load average (`nproc`, `uptime`, `top -bn1`), список активных Docker-контейнеров (`docker ps`, `docker stats --no-stream`), список активных `systemd`-сервисов и занятых TCP-портов (`ss -tulpn`).
   - Дать четкий инженерный анализ: хватит ли RAM, Swap, CPU и SSD для стабильной работы `PrisonBot` 24/7 параллельно с текущими проектами.
   - Если на сервере отсутствует Swap (или он меньше 2 ГБ) и на диске достаточно места (>= 5 ГБ свободно), безопасно создать и активировать `/swapfile` на 2 ГБ (`swapon` + запись в `/etc/fstab`) как страховку от OOM-killer при пиках рендера клипов.
4. **Проверка сетевой доступности серверов игры с VPS:**
   - Выполнить с самого VPS команду `curl -I https://oldprison-prod.luckygem.online/` (а также проверить доступность игрового CDN ассетов и Telegram API `https://api.telegram.org`).
   - Проанализировать HTTP-статус, TLS-рукопожатие, время ответа, заголовки ответа (отсутствие блокировки IP дата-центра, Cloudflare challenge `403`/`503` или geo-ban).
   - Если `oldprison-prod.luckygem.online` отвечает корректно (`200` / `301` / `302` / ожидаемый ответ API без блокировок) - переходить к деплою; если есть блокировка - зафиксировать точный ответ и остановиться до согласования маршрутизации/прокси.
5. **Чистая сборка и выгрузка `PrisonBot` на VPS (24/7):**
   - Выгрузить на сервер (например, в `/opt/prisonbot`) только рабочий код и актуальное состояние (`storage/prison_bot.db`, `storage/user_session.session`, `storage/bosses_catalog.json`, `storage/tattoo_clothing_cache.json`, `.env`).
   - **Исключить из выгрузки** весь тяжелый и девелоперский мусор (`reference_archive/`, `raw_dump/`, `parsed_js/`, `inf/`, `ref/`, `scratch/`, `screenshots/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `storage/asset_cache/`, `.env_server`, `repomix*.xml`), чтобы экономить SSD сервера.
   - Настроить изолированный Python `venv`, установить зависимости из `requirements.txt`, настроить `systemd`-сервис `prisonbot.service` с автозапуском после перезагрузки, авторестартом и жесткими лимитами памяти (`MemoryHigh=300M`, `MemoryMax=450M`).
   - Проверить и настроить HTTPS-точку входа для Telegram WebApp (`WEBAPP_PUBLIC_URL`), используя уже установленный на сервере Nginx/Caddy (если есть домен/поддомен) либо бесплатный `cloudflared` (если свободного домена нет), и синхронизировать `WEBAPP_PUBLIC_URL` в серверном `.env`.
   - Убедиться, что локальный экземпляр бота на ПК остановлен (во избежание конфликта `aiogram` `409 Conflict` и конфликта сессии Telethon `user_session.session`), запустить `prisonbot.service` и подтвердить живую работу всех воркеров, веб-панели и Telegram-бота.

---

## 2. КОНФИГУРАЦИЯ

Локальные и серверные файлы, задействованные в задаче:

```text
Локальный проект (PrisonBot/):
├── .env_server                         # Реквизиты SSH (ТОЛЬКО чтение локально, НЕ коммитить, НЕ выгружать)
├── .env                                # Рабочая конфигурация бота (адаптировать порт/WEBAPP_PUBLIC_URL при выгрузке на VPS)
├── .gitignore                          # Убедиться, что .env_server добавлен в игнор
├── main.py                             # Точка входа бота и веб-сервера
├── requirements.txt                    # Python-зависимости
├── core/, client/, bot/, web/, workers/, telegram/   # Исходный код для выгрузки
└── storage/
    ├── prison_bot.db                   # Актуальная SQLite БД (перенести чистую консистентную копию!)
    ├── user_session.session            # Активная сессия Telethon (перенести для бесшовного запуска)
    ├── bosses_catalog.json             # Каталог боссов
    └── tattoo_clothing_cache.json      # Кэш примерочной

Удаленный сервер (VPS):
├── /opt/prisonbot/                     # Целевая директория продакшен-установки
│   ├── venv/                           # Изолированное Python-окружение (Python 3.10+)
│   ├── .env                            # Продакшен-конфиг (права chmod 600)
│   ├── storage/                        # Перенесенные БД, сессия, каталоги + автонаполняемый asset_cache/
│   └── ...                             # Чистый исходный код без reference_archive/raw_dump/scratch
├── /etc/systemd/system/prisonbot.service   # Systemd-юнит с Restart=always и MemoryMax=450M
└── /etc/nginx/sites-available/... или /etc/caddy/Caddyfile (если настраивается HTTPS-прокси)
```

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Этап 1 - Безопасное подключение и аудит ресурсов VPS
1. Проверить `.gitignore` и при отсутствии добавить `.env_server`.
2. Подключиться к VPS по данным из `.env_server` и собрать диагностический срез:
   ```bash
   uname -a
   nproc
   uptime
   free -h
   swapon --show
   df -h
   ps aux --sort=-%mem | head -n 15
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
   docker stats --no-stream 2>/dev/null || true
   ss -tulpn
   python3 --version
   which nginx caddy cloudflared 2>/dev/null || true
   ```
3. Проанализировать полученную картину:
   - рассчитать доступный запас RAM (свободно + reclaimable cache) и свободное место на SSD;
   - проверить наличие Swap: если Swap == 0 и свободно >= 5 ГБ на SSD, аккуратно создать `/swapfile` размером 2 ГБ (`fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` + добавить в `/etc/fstab` и выставить `vm.swappiness=20`);
   - определить свободный локальный TCP-порт для `PrisonBot` (по умолчанию `8080`, если занят - выбрать свободный, например `8085`, и зафиксировать его в серверном `.env`).

### 3.2. Этап 2 - Проверка доступности игрового сервера с VPS
1. Выполнить с удаленного VPS диагностику сетевой связности:
   ```bash
   curl -I -sS -m 15 -w "\nHTTP_CODE:%{http_code} TIME_TOTAL:%{time_total}s REMOTE_IP:%{remote_ip}\n" [https://oldprison-prod.luckygem.online/](https://oldprison-prod.luckygem.online/)
   curl -I -sS -m 15 -w "\nHTTP_CODE:%{http_code} TIME_TOTAL:%{time_total}s\n" [https://api.telegram.org/](https://api.telegram.org/)
   ```
2. Проверить дополнительно один из публичных CDN-ассетов игры (из `docs/wardrobe_contracts.md` или `web/routes.py`) через `curl -I`, чтобы убедиться, что проксирование иконок/хат с VPS также работает без 403/таймаутов.
3. Оценить результаты:
   - подтвердить отсутствие блокировок по IP/региону, валидность SSL-сертификата и низкую задержку;
   - если игровой сервер возвращает ошибку блокировки (например, `403` от WAF/Cloudflare или таймаут) - зафиксировать точные заголовки и тело ответа в отчете и **остановить** запуск до решения сетевой маршрутизации.

### 3.3. Этап 3 - Консистентная подготовка состояния и выгрузка на VPS
1. **Консистентный бэкап SQLite перед переносом:**
   - убедиться, что локальный процесс `PrisonBot` (`main.py` / `uvicorn`) остановлен, чтобы избежать повреждения WAL-журнала и конфликта `aiogram`/`Telethon`;
   - выполнить SQLite checkpoint (`PRAGMA wal_checkpoint(TRUNCATE);`) или сделать консистентную копию через `sqlite3.backup()` в временный архив, чтобы в `prison_bot.db` попали 100% данных из `.db-wal`/`.db-shm`.
2. **Упаковка чистого релизного архива (`.tar.gz`):**
   - включить: `main.py`, `requirements.txt`, `bot/`, `client/`, `core/`, `telegram/`, `web/`, `workers/`, `.env` и только нужные файлы `storage/` (`prison_bot.db`, `user_session.session`, `bosses_catalog.json`, `tattoo_clothing_cache.json`);
   - строго исключить: `.env_server`, `reference_archive/`, `raw_dump/`, `parsed_js/`, `inf/`, `ref/`, `scratch/`, `screenshots/`, `storage/asset_cache/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `repomix*.xml`, `*.log`.
3. **Развертывание на VPS (`/opt/prisonbot`):**
   - загрузить архив на VPS, распаковать в `/opt/prisonbot`, удалить временный архив локально и на сервере;
   - выставить безопасные права `chmod 600 /opt/prisonbot/.env /opt/prisonbot/storage/user_session.session`;
   - создать `python3 -m venv /opt/prisonbot/venv` и установить зависимости (`/opt/prisonbot/venv/bin/pip install --no-cache-dir -r /opt/prisonbot/requirements.txt`);
   - при необходимости проверить/установить системные пакеты для Pillow/компиляции, только если `pip install` их потребует;
   - выполнить быстрый импорт-тест (`python -c "import main, web.app, core.scheduler"`) внутри серверного `venv`.

### 3.4. Этап 4 - Настройка HTTPS для Telegram WebApp и `systemd` 24/7
1. **Обратный прокси / HTTPS (`WEBAPP_PUBLIC_URL`):**
   - проверить существующую конфигурацию Nginx/Caddy на VPS:
     - если на сервере есть домен/Caddy/Nginx - аккуратно добавить отдельный конфиг (поддомен или выделенный location-маршрут) с проксированием на `http://127.0.0.1:<PORT>` (не затрагивая существующие конфиги «Ракомании`» и других сайтов!), проверить `nginx -t` / `caddy validate` и мягко сделать `reload`;
     - если свободного домена нет - проинспектировать возможность запуска локального сервиса `cloudflared` (или оставить рабочий доступ по `http://<VPS_IP>:<PORT>` / туннелю с явным указанием в отчете, что именно настроено для `WEBAPP_PUBLIC_URL`).
   - обновить `WEB_PORT` / `WEB_HOST=127.0.0.1` (или нужный бинд) и `WEBAPP_PUBLIC_URL` в `/opt/prisonbot/.env`.
2. **Конфигурация `systemd`-сервиса (`/etc/systemd/system/prisonbot.service`):**
   ```ini
   [Unit]
   Description=PrisonBot 24/7 Automation & WebApp Service
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/prisonbot
   EnvironmentFile=/opt/prisonbot/.env
   ExecStart=/opt/prisonbot/venv/bin/python /opt/prisonbot/main.py
   Restart=always
   RestartSec=5
   TimeoutStopSec=20
   MemoryHigh=300M
   MemoryMax=450M
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```
3. Активировать и запустить сервис:
   ```bash
   systemctl daemon-reload
   systemctl enable prisonbot.service
   systemctl start prisonbot.service
   ```

---

## 4. ТЕСТИРОВАНИЕ

После запуска `prisonbot.service` на VPS выполнить полную боевую проверку и отразить все результаты (без секретов!) в финальном отчете:

1. **Статус `systemd` и логи запуска (через 10-15 секунд после старта):**
   ```bash
   systemctl status prisonbot.service --no-pager
   journalctl -u prisonbot.service -n 80 --no-pager
   ```
   - убедиться, что сервис в состоянии `active (running)`, `Restart` count == `0`;
   - подтвердить в логах старт `uvicorn` (FastAPI), `APScheduler` (задачи воркеров + `00:01` МСК крон туалетки) и `aiogram` polling без ошибок `409 Conflict`, `AuthKeyDuplicatedError` или `Traceback`.
2. **Проверка HTTP API и веб-панели на VPS:**
   ```bash
   curl -sS -o /dev/null -w "INDEX:%{http_code}\n" [http://127.0.0.1](http://127.0.0.1):<PORT>/
   curl -sS -w "\nSTATUS:%{http_code}\n" [http://127.0.0.1](http://127.0.0.1):<PORT>/api/v1/status
   ```
   - проверить, что главная страница и ключевые эндпоинты возвращают `200 OK` (либо ожидаемый ответ авторизации), а настроенный HTTPS URL (`WEBAPP_PUBLIC_URL`) также отдает `200 OK`.
3. **Проверка потребления ресурсов и сохранности соседних проектов:**
   ```bash
   free -h
   df -h
   systemctl show prisonbot.service -p MemoryCurrent -p MainPID
   docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true
   ```
   - подтвердить, что `PrisonBot` потребляет в рамках нормы (< 300 МБ RAM), Swap активен, свободного места на диске достаточно, а «Ракомания» и конвейер клипов продолжают штатную работу без сбоев.
4. **Проверка чистоты локального репозитория:**
   - убедиться, что временные архивы удалены, `.env_server` находится в `.gitignore`, и локальный набор автотестов по-прежнему проходит (если вносились правки в код):
```bash
python -m pytest -v tests/
```

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

Выполняй задачи последовательно, отмечая прогресс:

- [ ] **Шаг 1:** Проверить `.gitignore` (добавить `.env_server`, если отсутствует), безопасно прочитать реквизиты из `.env_server` и подключиться к VPS без утечки секретов в логи.
- [ ] **Шаг 2:** Собрать полный отчет по ресурсам VPS (`RAM`, `Swap`, `CPU`, `SSD`, `docker ps`, `docker stats`, `ss -tulpn`, запущенные сервисы) и оценить, хватит ли ресурсов для бесперебойной работы `PrisonBot` рядом с конвейером клипов и «Ракоманией». При отсутствии Swap и достаточном месте на SSD создать и подключить `/swapfile` на 2 ГБ.
- [ ] **Шаг 3:** Выполнить с VPS проверку `curl -I https://oldprison-prod.luckygem.online/`, проверку CDN ассетов игры и `https://api.telegram.org/`, проанализировать статус-коды, TLS и задержки.
- [ ] **Шаг 4:** Убедиться, что локальный `PrisonBot` остановлен, сделать консистентный слепок `storage/prison_bot.db` (checkpoint WAL), упаковать чистый релиз без `reference_archive/`, `raw_dump/`, `parsed_js/`, `inf/`, `ref/`, `scratch/`, `storage/asset_cache/`, `.env_server` и выгрузить его в `/opt/prisonbot/` на VPS.
- [ ] **Шаг 5:** Развернуть `/opt/prisonbot/venv`, установить зависимости из `requirements.txt`, выбрать свободный локальный порт, настроить серверный `.env` (права `600`) и HTTPS-доступ для WebApp (через существующий Nginx/Caddy без вмешательства в соседние сайты либо через безопасный туннель).
- [ ] **Шаг 6:** Создать и запустить `/etc/systemd/system/prisonbot.service` с `Restart=always`, `MemoryHigh=300M`, `MemoryMax=450M` и автозапуском (`systemctl enable --now prisonbot.service`).
- [ ] **Шаг 7:** Проверить работу бота 24/7 (`systemctl status`, `journalctl`, `curl` локального и HTTPS эндпоинтов, потребление RAM/SSD, сохранность контейнера «Ракомания» и конвейера клипов), удалить временные архивы и выдать структурированный итоговый отчет с результатами аудита ресурсов, `curl`-ответами, адресом WebApp и командами управления сервисом.