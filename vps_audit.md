# Аудит VPS-сервера PrisonBot (`178.17.60.16`)

Дата снятия среза: `2026-11-25 02:09 MSK` (`2026-11-24 23:09 UTC`)
Режим сбора: строго **read-only** (без модификации конфигов, без рестарта сервисов/контейнеров и без утечки секретов).

---

## 3.1. Железо, ОС и текущая утилизация ресурсов

| Параметр | Значение |
| --- | --- |
| Хост | `instance303930.waicore.network` |
| ОС | Ubuntu 22.04.2 LTS (`jammy`, x86_64) |
| Ядро | `5.15.0-198-generic #208-Ubuntu SMP` |
| Аптайм | `5 days, 21:34` |
| Часовой пояс | `Europe/Moscow (MSK, +0300)`, NTP `active` (synchronized) |
| CPU | `1 vCPU` - `AMD EPYC 9454P 48-Core Processor` (1 socket, 1 core, 1 thread) |
| Load Average | `0.00, 0.00, 0.00` (в момент замера) |
| RAM | Всего `1.9Gi`, занято `1.0Gi`, свободно `325Mi`, `buff/cache 566Mi`, **доступно `720Mi`** |
| Swap | `/swapfile` `2.0Gi`, использовано `694.6Mi`, свободно `1.3Gi` |
| OOM-killer | Событий OOM в `dmesg` / `journalctl -k` не обнаружено |

### Краткий замер I/O и CPU (`vmstat 1 3`)
- `wa` (iowait): `0%` во всех трех выборках, `id` (idle): `93% - 99%`, `si/so`: `0` (в момент простоя).
- Примечание: утилита `iostat` не установлена, использован `vmstat 1 3`.

### Топ процессов по CPU / RAM (`ps aux`)
| Процесс | PID | %CPU | %MEM | RSS | Назначение |
| --- | --- | --- | --- | --- | --- |
| `python main.py` (`autoclip_service`) | 1223 | 1.3% | 29.0% | `583 MiB` | Конвейер вертикальных клипов (Docker) |
| `/opt/prisonbot/venv/bin/python /opt/prisonbot/main.py` | 632437 | 1.5% | 15.7% | `315.7 MiB` | PrisonBot (`prisonbot.service`) |
| `/lib/systemd/systemd-journald` | 126196 | 0.0% | 9.5% | `192.8 MiB` | Системный журнал (`2.3G` на диске) |
| `uvicorn src.main:app` (`crayfish_omni_hub`) | 1215 | 0.1% | 2.1% | `43.5 MiB` | Crayfish Hub (Docker) |
| `/usr/bin/dockerd` + `containerd` | 805 / 784 | 0.0% | 2.8% | `~59.5 MiB` | Docker runtime |
| `nginx: worker process` | 556886 | 0.0% | 0.7% | `16.0 MiB` | Reverse Proxy |

---

## 3.2. Диски, разделы и карта занятого места

### Разделы и Inodes (`df -hT`, `df -ih`, `lsblk -f`)
| ФС / Точка монтирования | Тип | Размер | Занято | Свободно | % | Inodes всего | Inodes занято | Inodes свободно | Inodes % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/dev/vda2` -> `/` | `ext4` | `30G` | `16G` | **`13G`** (`12.2G` avail) | 57% | `1.9M` | `227K` | **`1.7M`** | 12% |
| `/run` | `tmpfs` | `197M` | `892K` | `196M` | 1% | `246K` | `683` | `245K` | 1% |
| `/dev/shm` | `tmpfs` | `982M` | `0` | `982M` | 0% | `246K` | `1` | `246K` | 1% |

### Карта объема (`du -xh --max-depth=1`)
- `/` - `16G`
- `/var` - `9.9G` (включая `/var/log` `2.6G`, `journalctl --disk-usage` `2.3G`, `/var/lib/docker` `2.5G`)
- `/usr` - `3.6G`
- `/boot` - `258M`
- `/opt` - `220M`
- `/etc` - `5.1M`, `/root` - `2.6M`, `/tmp` - `120K`, `/home` - `24K`

### Детализация по ключевым зонам
- **`/opt/prisonbot`**: общий объем `196M`
  - `/opt/prisonbot/storage/asset_cache`: `1710` файлов
  - `storage/prison_bot.db`: `6.5M`
  - `storage/prison_bot.db-wal`: `4.0M`
  - `storage/prison_bot.db-shm`: `32K`
- **Соседние проекты**:
  - `/opt/autoclip`: `15M` (код и конфиги, образы и кэш Docker в `/var/lib/docker`)
  - `/opt/crayfish`: `9.9M`
  - `/var/lib/docker`: `2.5G` (с учетом overlay/образов/build cache по `docker system df` суммарный виртуальный объем Docker-артефактов: образы ~3.38GB, build cache `2.349GB`).

---

## 3.3. Docker-инфраструктура и соседние проекты

- **Версия**: `Docker version 29.8.1`, `Docker Compose version v5.5.1`
- **Контейнеры (`docker ps -a`)**:

| Имя | Образ | Статус | Порты (host -> container) | Потребление (CPU / RAM / Limit) |
| --- | --- | --- | --- | --- |
| `autoclip_service` | `autoclip-autoclip` | `Up 5 days` | `127.0.0.1:8080->8080/tcp` | CPU `0.15%`, RAM `564.2MiB / 1.66GiB` (`33.19%`), Block IO `1.56GB / 6.62GB` |
| `crayfish_omni_hub` | `crayfish-crayfish-hub` | `Up 5 days (healthy)` | `127.0.0.1:8081->8000/tcp` | CPU `0.15%`, RAM `44.53MiB / 256MiB` (`17.40%`), Block IO `166MB / 59.7MB` |

- **Неиспользуемые образы / Build Cache**:
  - Образ `crayfish-test:latest` (`279MB`, 0 контейнеров).
  - Build cache: `2.349GB` (преимущественно неиспользуемые слои 10-11-дневной давности).
- **Изоляция и монтирование (`docker inspect`)**:
  - `autoclip_service`: `WorkDir=/opt/autoclip`, `Restart=unless-stopped`, `Memory=1782579200` (`~1.66GiB`), `NanoCPUs=900000000` (`0.9 vCPU`), `Network=autoclip_default`. Mounts: `/opt/autoclip/credentials -> /app/credentials (rw)`, `/opt/autoclip/storage -> /app/storage (rw)`, `/etc/localtime` (ro), `/etc/timezone` (ro). Роль: конвейер вертикальных видеоклипов (в простое ~564 MiB RAM, при активном рендере/скачивании возможны пики до 0.9 CPU и 1.66 GiB RAM).
  - `crayfish_omni_hub`: `WorkDir=/opt/crayfish`, `Restart=unless-stopped`, `Memory=268435456` (`256MiB`), `NanoCPUs=350000000` (`0.35 vCPU`), `Network=crayfish_default`. Mounts: `/opt/crayfish/data -> /app/data (rw)`.

---

## 3.4. Systemd-сервисы, фоновые задачи и планировщики

### Юнит `prisonbot.service` (`/etc/systemd/system/prisonbot.service`)
- Статус: `active (running)` с `2026-11-25 01:32:48 MSK`, Main PID `632437`, Tasks `12`, Memory `296.0M` (`high: 300.0M`, `max: 450.0M`).

```ini
[Unit]
Description=PrisonBot 24/7 Automation & WebApp Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/prisonbot
EnvironmentFile=/opt/prisonbot/.env
Environment=PYTHONUNBUFFERED=1
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

### Остальные сервисы, Cron и Таймеры
- Активные системные сервисы (18): `nginx.service`, `docker.service`, `containerd.service`, `prisonbot.service`, `ssh.service`, `systemd-journald.service`, `systemd-resolved.service`, `systemd-timesyncd.service`, `unattended-upgrades.service`, `multipathd.service`, `qemu-guest-agent.service` и др.
- Пользовательский crontab (`root`): отсутствует.
- `/etc/cron.d`: `certbot`, `e2scrub_all`; `/etc/cron.weekly`: `docker-cleanup`, `man-db`.
- Таймеры (`systemctl list-timers --all`): `certbot.timer`, `apt-daily.timer`, `apt-daily-upgrade.timer`, `fstrim.timer`, `systemd-tmpfiles-clean.timer`, `dpkg-db-backup.timer`, `e2scrub_all.timer`.

---

## 3.5. Сеть, открытые порты, Reverse Proxy и SSL

### Слушающие порты (`ss -tulpn`)
| Адрес:Порт | Протокол | Процесс | Назначение |
| --- | --- | --- | --- |
| `0.0.0.0:80`, `0.0.0.0:443` | TCP | `nginx` | Публичный HTTPS/HTTP Reverse Proxy |
| `0.0.0.0:22`, `[::]:22` | TCP | `sshd` | SSH доступ |
| `127.0.0.1:8080` | TCP | `docker-proxy` (`autoclip_service`) | AutoClip Studio |
| `127.0.0.1:8081` | TCP | `docker-proxy` (`crayfish_omni_hub`) | Crayfish Hub |
| `127.0.0.1:8085` | TCP | `python` (`prisonbot.service`) | PrisonBot WebApp & API |
| `127.0.0.53:53` | TCP/UDP | `systemd-resolve` | Локальный DNS |

### Nginx Reverse Proxy (`/etc/nginx/sites-enabled/zvezdoed.space`)
- Домен: `zvezdoed.space` (SSL управляется Certbot, TLSv1.2/TLSv1.3, gzip level 5 в `/etc/nginx/conf.d/gzip.conf`).
- Маршруты для PrisonBot (`127.0.0.1:8085`):
  - `location /prison/static/assets/` -> прямая отдача с диска `alias /opt/prisonbot/web/static/assets/`, `expires 30d`, `Cache-Control "public, no-transform, immutable"`, `sendfile on`, `access_log off`.
  - `location = /prison/api/v1/live/stream` -> SSE-стрим без буферизации (`proxy_buffering off`, `proxy_cache off`, `gzip off`, `X-Accel-Buffering no`, `proxy_read_timeout 86400s`, `X-Forwarded-Prefix /prison`).
  - Основной прокси `/prison/` -> `http://127.0.0.1:8085/`.
- Firewall: `ufw` не активен, `INPUT` и `OUTPUT` в `iptables` с политикой `ACCEPT`, `FORWARD` ограничен правилами `DOCKER-FORWARD`.
- Доступность GitHub с сервера: `curl -sI https://github.com` возвращает `HTTP/2 200`.

---

## 3.6. Детальный аудит среды PrisonBot на VPS (`/opt/prisonbot`)

- **Владелец и пользователь сервиса**: все файлы в `/opt/prisonbot` принадлежат `root:root`, сервис запускается от `root`.
- **Права на `.env`**: `-rw-------` (600). Список ключей в `.env` (значения скрыты):
  - `API_BASE_URL=[REDACTED]`, `BOT_USERNAME=[REDACTED]`, `WEBAPP_URL=[REDACTED]`
  - `TG_API_ID=[REDACTED]`, `TG_API_HASH=[REDACTED]`, `TG_PHONE=[REDACTED]`, `TG_SESSION_PATH=[REDACTED]`
  - `DB_URL=[REDACTED]`, `CLIENT_PLATFORM=[REDACTED]`, `CLIENT_LANGUAGE=[REDACTED]`, `CLIENT_COUNTRY=[REDACTED]`
  - `ROUTINE_INTERVAL_MINUTES=[REDACTED]`, `JITTER_MIN_SEC=[REDACTED]`, `JITTER_MAX_SEC=[REDACTED]`, `BUSINESS_COLLECT_MIN_MINUTES=[REDACTED]`
  - `BOSS_INTERVAL_MINUTES=[REDACTED]`, `BOSS_ALLOW_PAID_WEAPONS=[REDACTED]`
  - `PRISON_INTERVAL_MINUTES=[REDACTED]`, `PRISON_MIN_ENERGY=[REDACTED]`, `PRISON_TARGET_ID=[REDACTED]`, `PRISON_PREFER_NIGHT=[REDACTED]`, `PRISON_ALLOW_ENERGY_REFILL=[REDACTED]`
  - `TG_BOT_TOKEN=[REDACTED]`, `ADMIN_TG_ID=[REDACTED]`, `WEB_HOST=[REDACTED]`, `WEB_PORT=[REDACTED]`, `WEBAPP_PUBLIC_URL=[REDACTED]`, `WEB_ADMIN_TOKEN=[REDACTED]`
- **Python и системные утилиты**:
  - Venv: `/opt/prisonbot/venv/bin/python` (`Python 3.10.12`).
  - Установлены: `git`, `tar`, `curl`, `nginx`, `docker`. Отсутствуют: `rsync`, `sqlite3` CLI, `ffmpeg` на хосте (ffmpeg внутри контейнера autoclip).
- **Git и SSH**:
  - `/opt/prisonbot` **не является** git-репозиторием (`not a git repo`).
  - В `/root/.ssh/` присутствуют только `known_hosts` и `known_hosts.old` (приватных deploy-ключей нет).
- **База данных SQLite (`storage/prison_bot.db`, read-only)**:
  - Режим: `PRAGMA journal_mode = wal`.
  - Строки по таблицам: `accounts: 1`, `sessions: 1`, `player_snapshots: 1798`, `action_logs: 462`, `bot_configs: 1`, `notifications: 60`, `sent_friend_requests: 50`, `tracked_candidates: 188`, `friends_count_snapshots: 1`, `boss_presets: 1`, `cached_raid_posts: 0`, `friend_stats: 0`, `boss_friend_damage_logs: 0`.
- **Логи `journalctl -u prisonbot.service -n 70`**:
  - Сервис работает стабильно, циклы `BossWorker` (каждые 12с) и `LiveStateHub` отрабатывают штатно, все 4 таймера рукопашных атак логируются корректно.
  - Замечен единичный `HTTP 429 Too Many Requests` на `/api/player/init` при одновременном запуске `LiveStateHub Tier 1` и `Tier 3` в одну секунду (`02:08:52`), критических ошибок и `Traceback` нет.

---

## 3.7. Инженерная сводка и рекомендации

| Область | Текущее состояние | Риски / Узкие места | Рекомендации |
| --- | --- | --- | --- |
| **Запас ресурсов** | CPU: `1 vCPU`, RAM: `720Mi` свободно (`1.9Gi` total + `2Gi` swap), Диск: `13G` свободно (`1.7M` inodes) | При пиковой нагрузке `autoclip_service` (`NanoCPUs=0.9`, `Mem=1.66GiB`) на 1 vCPU и 1.9GiB RAM сумма лимитов контейнеров (`1.66G + 256M`) и `prisonbot` (`300-450M`) превышает физическую RAM (`1.9G`), что толкает систему в swap (`694M` уже занято) | Снизить `Memory` лимит `autoclip_service` или контролировать одновременные задачи; очистить `docker build cache` (`2.35GB`) и ограничить `systemd-journald` (`SystemMaxUse=300M`, сейчас `2.3G`) |
| **Риски соседства** | `autoclip_service` ограничен `0.9 vCPU` и `1.66GiB` | На 1-ядерном хосте `0.9 vCPU` у видеоконвейера может вызывать кратковременные задержки event loop и спайки пинга у PrisonBot во время рендера | Уменьшить CPU-квоту `autoclip_service` (например до `0.65 - 0.75 vCPU`) или повысить приоритет `CPUWeight` для `prisonbot.service` |
| **Кэш ассетов** | `storage/asset_cache`: `1710` файлов; в Nginx уже настроена прямая раздача `/prison/static/assets/` с `expires 30d` | `asset_cache` отдается через Python-прокси; свободных inodes достаточно (`1.7M`), места на диске с учетом очистки журналов/Docker хватит с запасом | Перенести или примонтировать долгоживущий кэш в `/opt/prisonbot/storage/asset_cache` с прямым `try_files` / `alias` через Nginx и лимитом кэша (например `1-2 GB` по LRU) |
| **Автодеплой (GitHub Actions)** | GitHub доступен (`HTTP/2 200`), `git` установлен, `prisonbot.service` под systemd | `/opt/prisonbot` не является git-репозиторием, нет `rsync` и deploy-ключа, сервис работает от `root` | Инициализировать git-репозиторий (или деплоить через `tar`/`scp`/SSH), добавить отдельный SSH deploy key или использовать GitHub Actions SSH с защитой `.env` и `storage/*.db*` (исключить из перезаписи) |
