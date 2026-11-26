# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ДЕТЕКТОР ТЕХНИЧЕСКИХ РАБОТ ИГРЫ (`ServerHealthMonitor`), ЗАМОРОЗКА ВОРКЕРОВ БЕЗ СБРОСА ТАЙМЕРОВ, АКТИВНЫЙ ДЕЖУРНЫЙ WATCHDOG, TG/WEB-УВЕДОМЛЕНИЯ И ЭКРАН ТЕХРАБОТ В ВЕБ-ПАНЕЛИ + ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack & Distributed Systems инженера (Python / AsyncIO / FastAPI / APScheduler / SQLite / Vanilla JS / CSS / Linux systemd). На серверах игры «Тюряга» (`oldprison-prod.luckygem.online`) периодически начинаются технические работы / падения (`Error: Server Error`, 5xx, HTML-заглушки, таймауты). Сейчас в такие моменты все воркеры продолжают долбить мертвый сервер, засыпают логи ошибками, а веб-панель «умирает» - затирает данные на прочерки `-` и нули `0` (`Загрузка...`, `Ур. -`, `Энергия: -/-`, `Очередь автоатаки пуста`)[cite: 46, 47].
Твоя задача - спроектировать и реализовать отказоустойчивую подсистему мониторинга доступности игровых серверов по образцу референсного бота (`reference_archive/pro_prison_bot/` и скриншот окна техработ)[cite: 48]:
1) централизованный `ServerHealthMonitor` (Circuit Breaker + перехват сбоев на уровне HTTP-клиента);
2) мгновенную заморозку всех рабочих воркеров (`BossWorker`, `PrisonWorker`, `RoutineWorker`, `SocialWorker`, фоновых опросов `StateHub`) **без сброса их таймеров, расписаний, очередей и последнего валидного состояния**;
3) отдельный активный дежурный Watchdog, который во время техработ часто проверяет оживление игрового сервера (каждые `10-15` секунд, не раз в 30 минут!) и автоматически пробуждает все процессы, как только игра оживет;
4) мгновенные однократные уведомления в Telegram и Web (при входе в техработы и при восстановлении с точной длительностью простоя) + полноэкранное модальное окно «В игре технические работы» в веб-панели с живым таймером длительности, кнопкой `Проверить снова` и авто-закрытием при оживлении игры[cite: 48].
Все изменения необходимо покрыть автотестами (включая `node` runtime-тест JS), синхронно поднять cache-busting и **обязательно задеплоить и верифицировать на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Мгновенное обнаружение технических работ / недоступности серверов игры**:
   - Отличать реальное падение игрового сервера (HTTP `500/502/503/504/520-526`, HTML-ответ `Error: Server Error` вместо JSON, флаги/тексты техработ, сетевые `ConnectError` / `ReadTimeout` / `ConnectTimeout`) от обычных бизнес- или auth-ошибок (`400/401/403/404/422/429`).
   - Избегать ложных срабатываний на одиночном сетевом лаге (гистерезис: `1` явный ответ техработ / `503` / HTML `Server Error` ИЛИ `3` подряд ошибки `5xx`/таймаута за короткое окно `20-30` секунд -> мгновенный переход в режим `MAINTENANCE`).
2. **Мягкая заморозка всех воркеров БЕЗ сброса таймеров и БЕЗ затирания данных**:
   - Как только зафиксированы техработы:
     - `BossWorker`, `PrisonWorker`, `RoutineWorker`, `SocialWorker` и фоновые опросы `StateHub` мгновенно засыпают (перестают слать запросы к мертвому игровому API);
     - задачи в `APScheduler` **не удаляются и их таймеры/интервалы не сбрасываются**;
     - активный снимок боя с боссом **не сбрасывается и не классифицируется ложно как поражение/победа** из-за сетевого сбоя;
     - `StateHub` и веб-панель **не перетирают** последние валидные данные игрока, ресурсов, оружия, боссов и очереди автоатаки на `-` и `0`[cite: 46, 47].
   - Также сам `prisonbot.service` обязан стартовать быстро (`<= 5` секунд) даже если его перезапустили прямо во время техработ в игре (веб-сервер поднимается сразу и показывает экран техработ).
3. **Активный дежурный Watchdog (быстрое авто-пробуждение)**:
   - Во время `MAINTENANCE` работает **только** выделенный легковесный дежурный Watchdog, который пингует безопасный read-only эндпоинт игрового сервера (без мутаций и трат ресурсов):
     - интервал проверки: **каждые `10` секунд** (первые 10 минут простоя) и далее **каждые `15` секунд** с коротким таймаутом `5-6` секунд и легким джиттером `±1s` (никаких 30-минутных пауз!);
     - немедленная внеочередная проверка по нажатию кнопки `Проверить снова` из веб-панели.
   - Как только игровой сервер вернул валидный HTTP `200` JSON (не HTML-ошибку и без флага техработ; для надежности подтвердить `2` валидных ответа с паузой `1-1.5` сек или `1` валидный ответ `init_player` с `player_id > 0`):
     - режим `MAINTENANCE` мгновенно снимается (`ONLINE`);
     - `StateHub` сразу обновляет актуальные данные;
     - все воркеры автоматически пробуждаются и продолжают работу с сохраненными таймерами и настройками (без «громового стада» - с мягким разнесением `0.5-2` сек, если нужно).
4. **Уведомления в Telegram + Web и экран техработ в стиле референса**:
   - При переходе `ONLINE -> MAINTENANCE` (строго 1 раз на инцидент, без спама):
     - отправка уведомления в Telegram (`🔧 В игре технические работы...`) и запись события в Web-уведомления.
   - При переходе `MAINTENANCE -> ONLINE` (строго 1 раз на инцидент):
     - отправка уведомления в Telegram (`✅ Сервера игры снова работают!`) с точной длительностью техработ и запись в Web-уведомления.
   - В веб-панели - полноэкранный затемненный оверлей по образцу референса[cite: 48]:
     - оранжевая иконка гаечного ключа в темном круглом бейдже;
     - заголовок: **«В игре технические работы»**;
     - подзаголовок: `Игровой сервер не отвечает, все задачи поставлены на паузу.`;
     - живой счетчик длительности: `Длится меньше минуты` -> `Длится 2 мин` -> `Длится 1 ч 14 мин` (плюс аккуратная строка с числом проверок / причиной сбоя по тултипу или мелким текстом);
     - яркая желтая кнопка на всю ширину карточки: **`Проверить снова`** (дергает живую проверку на сервере с защитой от двойного клика);
     - подпись снизу: `Экран пропадёт сам, как только игра оживёт`;
     - оверлей автоматически опрашивает локальный API бота каждые `5` секунд и сам исчезает + обновляет все виджеты панели, как только игра ожила.
5. **Автотесты, cache-busting и обязательный деплой на VPS**:
   - Покрыть всю машину состояний, HTTP-детектор, заморозку воркеров, Watchdog, уведомления, Web API и UI-оверлей (`node` runtime-тест) автотестами, поднять версии кэша и задеплоить на VPS (`178.17.60.16`, `/opt/prisonbot`), подтвердив `0` рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Источники истины и инструменты диагностики
- **Референс-бот (для сверки UX и механики техработ)**: `reference_archive/pro_prison_bot/parsed_js/` (найти реализации экрана «В игре технические работы» и health-check поллинга, если есть в чанках) и скриншот референсного экрана[cite: 48].
- **Продакшен VPS**: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), БД `/opt/prisonbot/storage/prison_bot.db`, логи `journalctl -u prisonbot.service`, публичный URL `https://zvezdoed.space/prison/`.
- **Соседние Docker-контейнеры (НЕ ТРОГАТЬ)**: `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

### Ключевые файлы проекта под создание и доработку
- Новый модуль мониторинга: `core/server_health.py` (`ServerHealthMonitor`, классификатор сбоев, активный Watchdog).
- HTTP-клиент и синхронизация: `client/http_client.py`, `core/state_hub.py`, `core/scheduler.py`, `core/database.py`, `main.py`.
- Воркеры (добавление мягкого gate без сброса таймеров): `workers/boss_worker.py`, `workers/prison_worker.py`, `workers/routine_worker.py`, `workers/social_worker.py`.
- Уведомления и Web API: `bot/notifier.py`, `web/routes.py`, `web/app.py`.
- Фронтенд и PWA: `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/static/sw.js`.
- Автотесты: новый `tests/test_server_health.py` + обновления в `tests/test_web_api.py`, `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`.

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Централизованный `ServerHealthMonitor` и активный Watchdog (`core/server_health.py`)
- Спроектировать класс `ServerHealthMonitor` (единый инстанс на приложение, прокидывается в `PrisonHttpClient`, `StateHub`, `Scheduler`, воркеры и `web/routes.py`):
  - **Состояние (`HealthSnapshot`)**:
    - `status`: `"online"` | `"maintenance"`
    - `is_maintenance`: `bool`
    - `started_at`: `Optional[datetime]` (UTC / ISO-8601)
    - `last_check_at`: `Optional[datetime]`
    - `next_check_in_sec`: `int`
    - `check_attempts`: `int`
    - `consecutive_failures`: `int`
    - `last_error`: `str` (короткая человекочитаемая причина, например `HTTP 503 Service Unavailable`, `Server Error (HTML)`, `Таймаут соединения`)
    - `last_recovered_at`: `Optional[datetime]`
    - `last_outage_duration_sec`: `Optional[int]`
  - **Чистая функция классификации сбоев `classify_server_failure(exc=None, status_code=None, content_type=None, body_text=None) -> tuple[bool, bool, str]`**:
    - возвращает `(is_server_outage, is_immediate_maintenance, reason)`:
      - `is_immediate_maintenance = True` для:
        - HTTP `503` (Service Unavailable);
        - HTTP `500/502/504/520-526` с HTML-телом (`Error: Server Error`, `text/html`, `maintenance`, `технические работы`, `under maintenance`, `502 Bad Gateway`, `504 Gateway`);
        - JSON-ответа с явным признаком техработ (`maintenance: true`, `isMaintenance: true`, `status == "maintenance"`, сообщение о техработах).
      - `is_server_outage = True` (требует `failure_threshold = 3` подряд в пределах `30` сек) для:
        - одиночных `httpx.ConnectError`, `httpx.ConnectTimeout`, `httpx.ReadTimeout`, `httpx.RemoteProtocolError`, `httpx.NetworkError`, `HTTP 500/502/504` без явного маркера техработ.
      - `is_server_outage = False` (НЕ считать техработами!):
        - HTTP `400`, `401`, `403`, `404`, `409`, `422`, `429` (бизнес-ошибки, протухший токен, лимиты) и `asyncio.CancelledError`.
  - **Реакция на входе в `MAINTENANCE` (`record_failure`)**:
    - Атомарно под `asyncio.Lock` переводит статус в `MAINTENANCE` (запоминает `started_at = datetime.now(timezone.utc)`).
    - Запускает/будит выделенную asyncio-задачу Watchdog (`_watchdog_loop`), если она еще не запущена.
    - Вызывает зарегистрированный callback уведомлений (`on_maintenance_start`) строго **один раз** за инцидент (в TG + запись в таблицу Web-уведомлений).
  - **Дежурный Watchdog (`_watchdog_loop` и `probe_now()`)**:
    - Во время `MAINTENANCE` выполняет легковесную read-only пробу через `probe_fn` (например, прямой HTTP GET к `/api/player/init` или легкому эндпоинту игры с таймаутом `5.5` сек, минуя блокировку `is_maintenance` через внутренний флаг `bypass_maintenance_gate=True`).
    - **Активный интервал опроса**:
      - первые `10` минут простоя: каждые **`10` секунд** (`±1s` jitter);
      - далее: каждые **`15` секунд** (`±1.5s` jitter);
      - по ручной кнопке `Проверить снова` (`probe_now()`): немедленная внеочередная проверка (с debounce `2` секунды, чтобы не спамить при частых кликах).
    - **Подтверждение оживления (`MAINTENANCE -> ONLINE`)**:
      - Успешная проба = HTTP `200`, валидный JSON (не HTML и не `maintenance: true`), содержащий ожидаемую структуру ответа игрока/API.
      - Если проба успешна -> сделать короткую контрольную проверку через `1.5` сек (или сразу подтвердить при полном валидном `/api/player/init` с `id`/`player`), перевести статус в `ONLINE`, сбросить `consecutive_failures = 0`, зафиксировать `last_outage_duration_sec`, вызвать `on_maintenance_end` (TG + Web уведомление + мгновенное обновление `StateHub` + мягкое пробуждение воркеров).
      - Если во время пробы пришел `401 Unauthorized` (например, за время долгих техработ протух токен) -> инициировать `auth_provider.refresh_token()` и повторить пробу, чтобы бот не застрял в техработах из-за протухшего токена после подъема игры!

### 3.2. Интеграция с `PrisonHttpClient`, `Scheduler`, `StateHub` и всеми воркерами
- **`client/http_client.py`**:
  - Принимает опциональную ссылку на `health_monitor: Optional[ServerHealthMonitor]`.
  - Если `health_monitor.is_maintenance` и запрос НЕ помечен `bypass_maintenance_gate=True` -> немедленно бросает легкое типизированное исключение `GameMaintenanceError("Игровые сервера на технических работах")` **без отправки сетевого запроса** (полностью снимает нагрузку с мертвого сервера и убирает каскады 30-секундных таймаутов).
  - На реальных сетевых запросах:
    - при получении валидного ответа (включая `200` JSON) вызывает `health_monitor.record_success()`;
    - при сетевой ошибке / `5xx` / HTML-заглушке вызывает `health_monitor.record_failure(...)`.
- **`core/scheduler.py` и `workers/*.py` (`boss_worker.py`, `prison_worker.py`, `routine_worker.py`, `social_worker.py`)**:
  - На входе каждого рабочего тика (`tick` / `run_cycle` / `check_scheduled_presets` и фоновых задач `APScheduler`) добавить проверку `if self.health_monitor and self.health_monitor.is_maintenance: return` (логировать не чаще раза в 5 минут в `DEBUG`, чтобы не засорять `journalctl`).
  - В блоках `except GameMaintenanceError:` всех воркеров выходить **молча и чисто**, не меняя состояние боя с боссом, не записывая фейковые поражения/ошибки, не сдвигая внутренние счетчики и не перезаписывая БД.
  - Проверить `workers/boss_worker.py`: во время техработ и сразу в первые секунды после оживления не считать пустой/упавший ответ по боссу поражением и не терять `BossBattleSnapshot`.
  - **Сохранение таймеров**: задачи `APScheduler` остаются в расписании как обычно; во время `MAINTENANCE` каждый сработавший тик мгновенно выходит за `0 мс`, не трогая расписание и настройки; при переходе `MAINTENANCE -> ONLINE` воркеры естественно продолжают работу на следующем тике (а `StateHub` и `BossWorker` выполняют мягкий внеочередной refresh через `1-2` сек).
- **`core/state_hub.py` и `main.py`**:
  - При ошибке обновления профиля / техработах `StateHub` **строго сохраняет последний валидный кэш профиля/ресурсов/боссов** и никогда не заменяет его пустым объектом с нулями и прочерками[cite: 46, 47].
  - При старте приложения (`main.py`): инициализировать `ServerHealthMonitor`, связать с `PrisonHttpClient`, `StateHub`, `Scheduler`, всеми воркерами и `Notifier`; запускать первичное наполнение `StateHub` в фоне, чтобы веб-сервер на `127.0.0.1:8085` поднимался за `<= 5` секунд даже при мертвой игре.

### 3.3. Telegram и Web-уведомления + API статуса техработ (`web/routes.py`, `bot/notifier.py`)
- **TG-уведомления**:
  - Вход в техработы:
    ```text
    🔧 В игре технические работы
    Игровой сервер не отвечает (причина: HTTP 503 / Server Error).
    Все воркеры поставлены на паузу без сброса таймеров. Дежурный мониторинг проверяет доступность каждые 10 сек.
    ```
  - Восстановление:
    ```text
    ✅ Игровой сервер снова онлайн!
    Технические работы длились: 00:14:32.
    Все задачи и воркеры автоматически возобновлены.
    ```
  - Оба события также пишутся в таблицу Web-уведомлений (`notifications`) для истории.
- **Новые и обновленные Web API эндпоинты (`web/routes.py`)**:
  - `GET /api/v1/server-health` (с `Cache-Control: no-store`): возвращает текущий `HealthSnapshot`:
    ```json
    {
      "status": "maintenance",
      "active": true,
      "started_at": "2026-11-26T18:35:00+00:00",
      "duration_sec": 42,
      "last_check_at": "2026-11-26T18:35:40+00:00",
      "next_check_in_sec": 8,
      "check_attempts": 4,
      "reason": "HTTP 503 / Server Error",
      "last_recovered_at": null
    }
    ```
  - `POST /api/v1/server-health/check`: запускает немедленную проверку `health_monitor.probe_now()` и возвращает свежий `HealthSnapshot` (плюс `recovered: bool`).
  - Включить объект `"maintenance": health_monitor.to_dict()` в ответ `/api/v1/state` (при этом сам `/api/v1/state` обязан всегда возвращать HTTP `200` с последним валидным кэшем данных даже во время техработ игры, а не падать с `500` и не отдавать пустые нули).

### 3.4. Экран техработ и защита данных в Web UI (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)
- **HTML (`web/static/index.html`)**:
  - Добавить полноэкранный контейнер `#maintenance-overlay` (скрыт по умолчанию, `aria-modal="true"`, `role="dialog"`), повторяющий лаконичный и читаемый дизайн референсного скриншота[cite: 48]:
    - темная полупрозрачная подложка с `backdrop-filter: blur(6px)`;
    - центральная темная карточка с тонкой рамкой и скруглениями;
    - круглая подложка с оранжевой SVG-иконкой гаечного ключа;
    - заголовок `В игре технические работы`;
    - описание `Игровой сервер не отвечает, все задачи поставлены на паузу.`;
    - строка живой длительности `#maintenance-duration` (`Длится меньше минуты` / `Длится 5 мин` / `Длится 1 ч 12 мин`) и аккуратная дополнительная строка статуса проверки `#maintenance-meta` (например, `Проверок: 4 · автопроверка каждые 10 сек`);
    - яркая желтая кнопка на всю ширину `#btn-maintenance-recheck`: `Проверить снова`;
    - нижняя подсказка: `Экран пропадёт сам, как только игра оживёт`.
- **JS (`web/static/app.js`)**:
  - Добавить чистые, тестируемые функции `formatMaintenanceDuration(seconds)` и `renderMaintenanceOverlay(maintenanceState)`:
    - `< 60` сек -> `Длится меньше минуты`;
    - `60..3599` сек -> `Длится N мин`;
    - `>= 3600` сек -> `Длится H ч M мин`.
  - При `maintenance.active === true`:
    - показать `#maintenance-overlay`, запустить локальный секундный таймер обновления `#maintenance-duration` (считает от `started_at`) и легкий polling `GET /api/v1/server-health` каждые `5` секунд;
    - **не затирать** отрендеренные на фоне панели значения профиля/ресурсов/боссов, если пришедший ответ не содержит валидных новых данных[cite: 46, 47].
  - При клике на `Проверить снова`:
    - заблокировать кнопку, показать `Проверяем...`, вызвать `POST /api/v1/server-health/check`;
    - если `active === false` -> мгновенно скрыть оверлей, показать toast `Игра ожила! Все воркеры возобновлены`, и запустить полное обновление данных панели (`refreshState()` + активная вкладка);
    - если все еще `active === true` -> обновить счетчик проверок, показать легкий toast `Игровой сервер пока не отвечает`, разблокировать кнопку.
  - При автоматическом переходе `active: true -> false` по поллингу:
    - автоматически скрыть `#maintenance-overlay`, остановить таймер/поллинг оверлея и сразу перезагрузить данные активного экрана панели.

### 3.5. Cache-busting, уборка и обязательный деплой на VPS
- Проверить текущие `ASSET_VERSION` в `web/static/index.html` / `web/static/app.js` и имя кэша в `web/static/sw.js` и синхронно поднять их на следующую версию выше текущей (обновив проверки версий в тестах).
- Удалить любые временные скрипты агента в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).
- Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую верификацию на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`, локальный `127.0.0.1:8085` поднимается быстро (`<= 5s`) даже если игровые сервера в момент деплоя всё еще на техработах!
  2. Проверить через `curl` отдачу свежей статики на `127.0.0.1:8085` и `https://zvezdoed.space/prison/`.
  3. Проверить живые ответы `GET https://zvezdoed.space/prison/api/v1/server-health` и `POST https://zvezdoed.space/prison/api/v1/server-health/check` (подтвердить HTTP `200`, `Cache-Control: no-store`, корректный статус `online` или `maintenance` в зависимости от реального состояния игры на момент проверки).
  4. Проверить `journalctl -u prisonbot.service -n 80 --no-pager` на отсутствие `Traceback` и отсутствие спама запросами во время техработ.
  5. Подтвердить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Создать `tests/test_server_health.py` и обновить `tests/test_web_api.py`, `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`:

1. **Детектор сбоев и машина состояний (`tests/test_server_health.py`)**:
   - **Явные техработы (мгновенный вход)**: HTTP `503` и HTML `500 Error: Server Error` с первого раза переводят монитор в `MAINTENANCE` и вызывают `on_maintenance_start` строго 1 раз.
   - **Гистерезис на сетевые ошибки**: `1-2` одиночных таймаута не включают `MAINTENANCE` и сбрасываются после успешного ответа; `3` подряд сетевых сбоя включают `MAINTENANCE`.
   - **Игнор бизнес-ошибок**: HTTP `400`, `401`, `404`, `422`, `429` никогда не включают режим техработ.
   - **Блокировка обычных HTTP-запросов и пропуск Watchdog**: при `is_maintenance == True` обычный запрос через `PrisonHttpClient` немедленно бросает `GameMaintenanceError` без выхода в сеть, а запрос с `bypass_maintenance_gate=True` (дежурный Watchdog) выполняется штатно.
   - **Активный Watchdog и авто-пробуждение**: пока проба падает, Watchdog опрашивает часто (`<= 15s`) и не спамит повторными уведомлениями; как только проба вернула валидный JSON - статус переходит в `ONLINE`, вызывается `on_maintenance_end` (с ненулевой длительностью), воркеры разблокируются.
   - **Рефреш токена при `401` после долгих техработ**: если после подъема игры проба получила `401`, Watchdog вызывает `refresh_token` и успешно выводит бота из `MAINTENANCE`.
2. **Заморозка воркеров без сброса таймеров и сохранность данных (`tests/test_server_health.py`)**:
   - Во время `MAINTENANCE` `BossWorker`, `PrisonWorker`, `RoutineWorker`, `SocialWorker` выходят мгновенно без сетевых вызовов, не сбрасывают расписание `APScheduler`, не портят `BossBattleSnapshot` и не затирают последний валидный профиль в `StateHub` на нули/прочерки.
3. **Web API и UI-оверлей (`tests/test_web_api.py`, `tests/test_web_endpoints.py`)**:
   - Проверка `GET /api/v1/server-health` (`Cache-Control: no-store`), `POST /api/v1/server-health/check` и поля `maintenance` в `/api/v1/state`.
   - Проверка наличия `#maintenance-overlay`, `#maintenance-duration`, `#btn-maintenance-recheck` в `web/static/index.html`.
   - Runtime-тест JS через `node` для `formatMaintenanceDuration` (`< 60s -> "Длится меньше минуты"`, `185s -> "Длится 3 мин"`, `3900s -> "Длится 1 ч 5 мин"`) и `renderMaintenanceOverlay` (показ оверлея при `active: true`, скрытие и триггер обновления при `active: false`).
   - Актуализация версий `ASSET_VERSION` и `sw.js` в тестах.
4. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и весь `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Baseline VPS + аудит референса и текущих воркеров**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Проверить логи `journalctl -u prisonbot.service` на VPS во время текущего сбоя игровых серверов (зафиксировать реальные HTTP-коды/тела ответов `oldprison-prod.luckygem.online` при техработах) и сверить детали в `reference_archive/pro_prison_bot/`.
  - Проверить все точки запуска фоновых задач в `main.py`, `core/scheduler.py`, `core/state_hub.py`, `client/http_client.py` и `workers/*.py`.
- [ ] **Шаг 2. Реализация `ServerHealthMonitor`, активного Watchdog и защиты HTTP/воркеров (`core/server_health.py`, `client/http_client.py`, `core/state_hub.py`, `core/scheduler.py`, `workers/*.py`, `main.py`)**:
  - Создать `core/server_health.py` с классификатором сбоев, машиной состояний `ONLINE <-> MAINTENANCE`, дедуплицированными TG+Web уведомлениями и частым дежурным Watchdog (`10-15s` + `probe_now()` + обработка `401` refresh).
  - Встроить gate в `PrisonHttpClient` (`GameMaintenanceError` + `bypass_maintenance_gate=True`), мягкую паузу без сброса таймеров во все 4 воркера и сохранение последнего валидного кэша в `StateHub` (плюс неблокирующий быстрый старт `main.py`).
- [ ] **Шаг 3. Web API и экран техработ (`web/routes.py`, `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)**:
  - Добавить `GET /api/v1/server-health`, `POST /api/v1/server-health/check` и поле `maintenance` в `/api/v1/state`.
  - Сверстать и подключить полноэкранный оверлей `#maintenance-overlay` по образцу референса («В игре технические работы», оранжевый ключ, живой таймер длительности, желтая кнопка `Проверить снова`, авто-закрытие и авто-обновление панели при оживлении игры) без затирания фоновых данных на `-` и `0`[cite: 46, 47, 48].
- [ ] **Шаг 4. Cache-busting, автотесты и уборка**:
  - Синхронно поднять `ASSET_VERSION` (`index.html`, `app.js`) и версию кэша SW (`sw.js`) на следующую версию выше текущей.
  - Создать `tests/test_server_health.py` и обновить тесты Web API / endpoints (включая `node` runtime-тест JS), прогнать `node --check` и весь `python -m pytest -q tests/`.
  - Удалить временные скрипты агента в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 5. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ЖИВАЯ ВЕРИФИКАЦИЯ**:
  - Загрузить все измененные и новые файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Проверить быстрый старт `127.0.0.1:8085`, отдачу свежей статики на `https://zvezdoed.space/prison/`, живые ответы `/api/v1/server-health` и `/api/v1/server-health/check`, чистоту `journalctl -u prisonbot.service -n 80` (0 `Traceback`) и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_server_health.py tests/test_web_api.py tests/test_web_endpoints.py tests/test_asset_cache.py tests/test_improvements_v2.py
python -m pytest -q tests/
```