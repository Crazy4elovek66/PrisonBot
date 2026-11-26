# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: СИСТЕМНАЯ СИНХРОНИЗАЦИЯ СОСТОЯНИЯ (`StateHub` SINGLE SOURCE OF TRUTH + EVENT-DRIVEN ИНВАЛИДАЦИЯ), ПОЧИНКА РАССИНХРОНА ПРОГРЕССА ХОДОК И РАЗБЛОКИРОВКИ БОССОВ (КРЕСТЫ -> ЛЮТЫЙ) И ПОВЫШЕНИЕ ТОЧНОСТИ ФОНОВЫХ ВОРКЕРОВ БЕЗ РЕГРЕССИЙ + ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Principal Full-Stack & Distributed Systems инженера (Python / AsyncIO / FastAPI / SQLite / Vanilla JS / CSS / Chrome DevTools MCP / Linux systemd). В проекте выявлена системная архитектурная проблема рассинхрона состояния между модулями и фоновыми воркерами, которая ярко проявилась на продакшене:
- в разделе «Ходки» отображается `КРЕСТЫ · День: 2 | Ночь: 0` (замок открыт, две дневные ходки завершены более часа назад)[cite: 56];
- при этом в разделе «Боссы» босс `Лютый` (Беспредельщики) остается заблокированным со статусом `Закрыт · 0 из 2 · Нужно 2 дневные ходки в Кресты, пройдено 0 (0 из 2)` (при том что ключи `8/3 (от Махно)` отображаются верно)[cite: 57].

Эта ошибка - симптом более широкой проблемы: разные воркеры, эндпоинты и кэши читают состояние из несогласованных или устаревших источников, мутации одного модуля не инвалидируют кэши зависимых модулей, а часть данных обновляется с задержкой или с разными правилами парсинга.
Твоя задача - провести глубокий сквозной аудит всей цепочки данных (от живого API игры и `StateHub` до каждого воркера, `web/routes.py` и `web/static/app.js`), починить конкретный баг с разблокировкой боссов по ходкам (Кресты -> Лютый и все аналогичные боссы), выстроить надежную событийно-синхронизированную архитектуру `StateHub` (Single Source of Truth + кросс-инвалидация + single-flight свежесть данных) и **при этом строго НЕ СЛОМАТЬ ни один существующий воркер, предохранитель траты ресурсов, Ночной режим, `ServerHealthMonitor` или UI-функцию**. Все изменения покрыть автотестами (сохранив 100% прохождение всех существующих 259+ тестов), обновить cache-busting и **обязательно задеплоить и верифицировать на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Починка рассинхрона «Ходки -> Боссы» (Лютый / Кресты и все боссы с условиями разблокировки)**:
   - Точно установить первопричину на коде и живом VPS (`178.17.60.16`): почему раздел «Ходки» видит `КРЕСТЫ: День 2`[cite: 56], а раздел «Боссы» / `BossWorker` видит `пройдено 0 (0 из 2)` для босса `Лютый`[cite: 57].
   - Проверить все возможные слои расхождения:
     - разные API-источники (`GET /api/player/init` vs `GET /api/prison/...` vs `GET /api/boss/...`) и разные имена/форматы полей счетчика пройденных дневных/ночных ходок;
     - несовпадение ID тюрьмы или маппинга названий/ключей в каталоге боссов (`storage/bosses_catalog.json`, `client/api/boss.py`, `client/api/prison.py`, `web/routes.py`, `workers/boss_worker.py`);
     - устаревший/разделенный кэш в `StateHub`, `BossWorker`, `PrisonWorker` или `web/routes.py`.
   - Гарантировать, что разблокировка **всех** боссов (Лютый и все остальные боссы с требованиями по дневным/ночным ходкам, ключам, уровню или победам) рассчитывается по **единому актуальному источнику** и мгновенно отражается как в UI («Боссы» -> меню выбора боссов), так и в автопризыве `BossWorker`.
2. **Единый источник истины (`StateHub` Single Source of Truth) и мгновенная кросс-инвалидация**:
   - Устранить ситуацию, когда разные вкладки и воркеры живут в «разных реальностях» или обновляются с часовыми задержками:
     - разбить состояние игрока в `core/state_hub.py` на явно версионируемые домены (`player`, `prisons`, `boss`, `katala`, `poker`, `fartovy`, `wheel`, `zaruby`, `social`), у каждого из которых есть `updated_at`, `revision`, `dirty`, `stale_after_sec`;
     - внедрить внутреннюю шину событий / механизм кросс-инвалидации (`mark_dirty` / `notify_mutation` + single-flight `ensure_fresh` через per-domain `asyncio.Lock`): как только **любой** воркер или ручное действие пользователя совершает мутацию, зависимые домены мгновенно помечаются грязными и синхронно/немедленно обновляются с игрового сервера, а связанные воркеры при необходимости сразу получают `schedule_wakeup`.
3. **Проверка и выравнивание всех независимых фоновых воркеров**:
   - Проверить все 7 воркеров (`BossWorker`, `PrisonWorker`, `RoutineWorker`, `SocialWorker`, `PokerWorker`, `FartovyWorker`, `ZarubyWorker`) и `StateHub` на:
     - отсутствие «мертвых»/залипающих кэшей и расхождений между тем, что видит воркер, и тем, что видит веб-панель;
     - корректный пересчет `next_wakeup_at` после каждой мутации;
     - отсутствие лишнего спама в игровой API (использование single-flight коалесценции одновременных запросов к одному и тому же эндпоинту).
4. **Абсолютное сохранение работоспособности всей существующей логики (Zero Regression)**:
   - **НЕ СЛОМАТЬ** ни одну существующую функцию и защитный механизм:
     - Fail-Closed защиту рублей в Катале (`katala_guard_state`, 1 раз в день бесплатно по МСК, `allow_paid=False`);
     - Fail-Closed защиту мыла/рублей в Покере (`GameGuardState`, строго за красную фишку в авторежиме, ручной платный режим за 5 мыла только с модалкой подтверждения);
     - Фартовый (точный таймер `5760` сек, 4 бонуса «Отец народов» / «Топ» / «Колокол воли» / «Козёл», запрет автопокупки за рубли);
     - Колесо фортуны (билетики, синие спички, запрет автопокупки билетов);
     - Зарубы (4 тира, 8 задач, пропуск урона, пропуск энергии при активных «Ходках и мастерах», прогресс `X/8 (Y%)` в Делюгах);
     - Точечный Ночной режим (стопорит только автопризыв и автоатаку боссов, не трогая ходки, рутину, социалку, Покер, Фартового, Зарубы и `claim` завершенных боев);
     - `ServerHealthMonitor` (заморозка воркеров без сброса таймеров во время техработ игры, сохранение последнего валидного кэша без затирания на `-` и `0`, активный Watchdog `10-15s`).
5. **Прозрачная диагностика свежести данных + автотесты + обязательный деплой на VPS**:
   - Добавить диагностику свежести доменов в `/api/v1/workers/status` и `/api/v1/state` (`domain_revisions`, `updated_at`), обновить фронтенд-синхронизацию при смене ревизий, покрыть всё автотестами, поднять cache-busting и выкатить на VPS (`178.17.60.16`, `/opt/prisonbot`), подтвердив на живых данных, что `Лютый` разблокирован (`2 из 2`), и `0` рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Источники истины и инструменты диагностики
- **Живое приложение «Тюряга» (Telegram WebApp)**: при необходимости проверки реальных полей API открыто с `--remote-debugging-port=9222` (MCP Chrome DevTools) + дампы `parsed_js/bundle.js`, `docs/api_map.md`, `storage/bosses_catalog.json`[cite: 58, 59].
- **Продакшен VPS**: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), БД `/opt/prisonbot/storage/prison_bot.db`, логи `journalctl -u prisonbot.service`, публичный URL `https://zvezdoed.space/prison/`.
- **Соседние Docker-контейнеры (НЕ ТРОГАТЬ)**: `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

### Ключевые файлы проекта под аудит и доработку
- Ядро состояния и планировщик: `core/state_hub.py`, `core/scheduler.py`, `core/server_health.py`, `core/database.py`, `main.py`[cite: 58, 59].
- Клиенты игрового API: `client/api/player.py`, `client/api/prison.py`, `client/api/boss.py`, `client/api/katala.py`, `client/api/poker.py`, `client/api/fartovy.py`, `client/api/wheel.py`, `client/api/zaruby.py`, `client/api/social.py`[cite: 58, 59].
- Воркеры: `workers/boss_worker.py`, `workers/prison_worker.py`, `workers/routine_worker.py`, `workers/social_worker.py`, `workers/poker_worker.py`, `workers/fartovy_worker.py`, `workers/zaruby_worker.py`[cite: 58, 59].
- Веб API и интерфейс: `web/routes.py`, `web/static/index.html`, `web/static/app.js`, `web/static/sw.js`[cite: 58, 59].
- Автотесты: `tests/test_state_hub.py`, `tests/test_boss_worker.py`, `tests/test_prison_worker.py`, `tests/test_realtime_scheduler.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`[cite: 58, 59].

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Точечное расследование бага «Кресты `День: 2` vs Лютый `пройдено 0 (0 из 2)`»
- На живом VPS (`178.17.60.16`) и в коде (`client/api/prison.py`, `client/api/boss.py`, `core/state_hub.py`, `workers/boss_worker.py`, `web/routes.py`, `storage/bosses_catalog.json`) выполнить read-only диагностику:
  1. Снять реальный JSON ответа от эндпоинта, который питает вкладку «Ходки» (где `КРЕСТЫ` имеют `День: 2 | Ночь: 0`)[cite: 56].
  2. Снять реальный JSON ответа от эндпоинта, который питает вкладку «Боссы» / меню боссов (где `Лютый` получает `locked=True`, `пройдено 0 (0 из 2)`)[cite: 57].
  3. Сравнить оба пути данных построчно и точно зафиксировать, на каком шаге `2` дневные ходки в Крестах превращаются в `0`:
     - несовпадение ключей (например, `dayCount` / `dayCompletions` / `completedDay` / `normalCount` / `passCount` или строковый vs целочисленный `prisonId`);
     - чтение прогресса тюрем из `init_player` вместо `/api/prison/...` (или наоборот - `StateHub` не подтягивает актуальный `prisons_state` перед расчетом разблокировки боссов);
     - старый кэш с большим TTL, который не сбрасывался после завершения ходки `PrisonWorker` или ручной ходки в игре.
- Исправить единую функцию проверки разблокировки боссов (`evaluate_boss_unlock` / `_compute_boss_unlock_status`):
  - она обязана брать актуальный прогресс ходок (`prisons_progress`: дневные и ночные ходки по каждому `prison_id`), ключи и победы из единого нормализованного снимка `StateHub` (с принудительной подгрузкой `prisons`, если домен еще не загружен или `dirty`);
  - убедиться, что и Web UI (`/api/v1/boss/...`), и `BossWorker` (проверка перед автопризывом босса из очереди) используют **одну и ту же** функцию проверки разблокировки, без дублирования и расхождения формул.

### 3.2. Архитектура `StateHub`: Single Source of Truth + Domain Freshness + Event-Driven Cross-Invalidation (`core/state_hub.py`)
- Не переписывать `StateHub` с нуля (чтобы не сломать существующие контракты и тесты), а аккуратно расширить его доменным реестром и шиной инвалидации:
  - **Домены состояния (`DomainState`)**:
    - `player`: профиль, уровень, энергия, авторитет, валюты, ключи, оружие, таланты (`stale_after_sec = 45`);
    - `prisons`: прогресс всех тюрем (дневные/ночные ходки, мастера, награды) (`stale_after_sec = 90`);
    - `boss`: активный бой, список боссов, лимиты, статусы разблокировки (`stale_after_sec = 30`);
    - `katala`: живой статус бесплатной Каталы (`stale_after_sec = 60`);
    - `poker`: красные фишки, уровень, попытки за мыло (`stale_after_sec = 90`);
    - `fartovy`: зеленые/красные спички, точный таймер регенерации (`stale_after_sec = 60`);
    - `wheel`: билетики, синие спички, джекпот (`stale_after_sec = 120`);
    - `zaruby`: активный заруб, 8 задач, Топ-5, перстни/осколки (`stale_after_sec = 90`);
    - `social`: входящие заявки, количество друзей, подогревы (`stale_after_sec = 120`).
  - **Single-Flight обновление (`ensure_domain_fresh(domain, force=False)`)**:
    - Каждый домен защищен собственным `asyncio.Lock` (обновление `prisons` никогда не блокирует `boss` или `fartovy`).
    - Если домен `dirty == True` или `(now - updated_at) > stale_after_sec` или `force == True`, выполняется ровно один сетевой запрос к игровому API, данные валидируются и атомарно записываются в кэш с увеличением `domain_revision` и общего `state_revision`.
    - **Защита от затирания при сбое**: если запрос упал (сеть, `GameMaintenanceError`, невалидный ответ), старые валидные данные домена **строго сохраняются** (не перетираются на `0`, `None` или пустой список).
  - **Матрица кросс-инвалидации (`notify_mutation(event_type, payload=None)`)**:
    - Единая декларативная карта зависимостей доменов при мутациях:
      - `prison_completed` / `prison_action` (ходка или мастер завершены) -> `mark_dirty("player", "prisons", "boss", "zaruby")` + немедленный фоновый refresh `prisons` и `player` + `schedule_wakeup("boss_worker")` (если разблокировался босс из очереди) и `schedule_wakeup("zaruby_worker")`;
      - `boss_finished` / `boss_claimed` / `boss_summoned` -> `mark_dirty("player", "boss", "zaruby")` + обновление `player` (ключи/валюты/оружие) и `boss`;
      - `katala_played` -> `mark_dirty("player", "katala")`;
      - `poker_played` -> `mark_dirty("player", "poker")`;
      - `fartovy_spun` -> `mark_dirty("player", "fartovy", "zaruby")`;
      - `wheel_spun` -> `mark_dirty("player", "wheel")`;
      - `zarub_updated` / `zarub_started` / `zarub_claimed` -> `mark_dirty("player", "zaruby")`;
      - `social_changed` (принятие/отклонение заявки, удаление друга, подогрев) -> `mark_dirty("social", "player", "zaruby")`;
      - `routine_action` (папиросы, барыга, нычки, бригада, делюги) -> `mark_dirty("player", "zaruby")`;
      - `maintenance_recovered` (выход `ServerHealthMonitor` из техработ) -> `mark_dirty` для всех доменов + мягкий последовательный refresh.
    - Вызывать `state_hub.notify_mutation(...)` из всех соответствующих мест в воркерах (`workers/*.py`) и ручных POST-эндпоинтах (`web/routes.py`).

### 3.3. Аудит всех воркеров, планировщика и Web API (`core/scheduler.py`, `workers/*.py`, `web/routes.py`)
- **Проверка фоновых циклов и real-time точности**:
  - Убедиться, что фоновый sync в `core/scheduler.py` регулярно и без пропусков освежает `player`, `prisons` и игровые домены (даже если игрок доделал ходку или забрал награду вручную прямо в самой игре «Тюряга», панель и воркеры увидят это максимум в пределах `<= 60-90` секунд, а при ручной кнопке «Обновить» или открытии вкладки - мгновенно!).
  - Проверить все 7 воркеров на соблюдение инвариантов:
    - каждый воркер проверяет `server_health_monitor.is_maintenance` в самом начале;
    - ни один воркер не держит чужие замки и не блокирует event loop;
    - все `schedule_wakeup(...)` защищены от ухода в прошлое и от спама частыми повторами (минимальный интервал backoff при пустой/неудачной попытке);
    - в `web/routes.py` на эндпоинтах чтения (особенно меню боссов `/api/v1/boss/...`, ходки `/api/v1/prison/...`, профиль `/api/v1/state`) использовать `ensure_domain_fresh(...)` и возвращать `Cache-Control: no-store` для динамических данных.
- **Прозрачная телеметрия свежести**:
  - Расширить ответ `GET /api/v1/workers/status` и поле `sync_meta` в `GET /api/v1/state`:
    - `state_revision`: `int` (растет при любой свежей синхронизации любого домена);
    - `domains`: словарь `{name: {updated_at, age_sec, dirty, revision, stale_after_sec}}`;
    - `workers`: статус каждого из 7 воркеров (`running/idle/paused_night/paused_maintenance`, `last_run_at`, `next_wakeup_at`, `last_error`).

### 3.4. Актуализация синхронизации на фронтенде (`web/static/app.js`, `web/static/index.html`, `web/static/sw.js`)
- В `web/static/app.js`:
  - Отслеживать `domain_revisions` из `/api/v1/state`:
    - если изменилась ревизия `prisons` или `boss` (например, `PrisonWorker` только что завершил 2-ю ходку в Крестах) - автоматически перерисовать/перезагрузить данные вкладки «Боссы» (и меню выбора боссов, если оно открыто), не дожидаясь `F5`!
    - аналогично для `poker`, `fartovy`, `wheel`, `zaruby`, `social` при изменении их ревизий.
  - При переключении на вкладку «Боссы» или открытии модалки «Меню боссов» гарантировать загрузку актуальных данных с бэкенда (с учетом защиты от гонок запросов).
  - При нажатии кнопки «Обновить» в шапке профиля запускать форсированное обновление ключевых доменов (`player`, `prisons`, `boss`, активной вкладки) через `force=true`.
  - Сохранить существующее поведение защиты от затирания данных на `-` и `0` во время техработ игры.
- Синхронно поднять `ASSET_VERSION` в `web/static/index.html` и `web/static/app.js` до `20261126_09` и имя кэша Service Worker в `web/static/sw.js` до `prisonbot-assets-v21` (обновить проверки версий в тестах).

### 3.5. Уборка и обязательный деплой на VPS
- Удалить любые временные скрипты агента в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).
- Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую read-only верификацию на VPS (строго **без траты ресурсов!**):
  1. `systemctl is-active prisonbot.service` -> `active`, локальный `127.0.0.1:8085` и публичный `https://zvezdoed.space/prison/` -> HTTP `200`, версии `20261126_09` / `prisonbot-assets-v21`.
  2. **Главный живой чек по багу пользователя**: запросить на живом VPS данные «Ходок» (Кресты) и «Боссов» (Лютый) -> подтвердить, что при `Кресты: День 2` босс `Лютый` больше НЕ заблокирован и показывает `2 из 2` (или `открыт`)!
  3. Проверить живые ответы `GET /api/v1/state`, `GET /api/v1/workers/status`, `GET /api/v1/poker/state`, `GET /api/v1/fartovy/state`, `GET /api/v1/wheel/state`, `GET /api/v1/zaruby/state`, `GET /api/v1/daily/katala-status` -> все HTTP `200`, актуальные `domain_revisions`, 0 потраченных рублей и мыла.
  4. Проверить `journalctl -u prisonbot.service -n 100 --no-pager` на отсутствие `Traceback`.
  5. Подтвердить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Добавить регрессионные тесты в `tests/test_state_hub.py`, `tests/test_boss_worker.py`, `tests/test_prison_worker.py`, `tests/test_realtime_scheduler.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py` и прогнать весь пакет (259+ тестов):

1. **Кейс «Кресты `День: 2` -> Лютый разблокирован» (`tests/test_boss_worker.py`, `tests/test_web_api.py`)**:
   - Воспроизвести точную структуру живых ответов сервера по тюрьмам (Кресты `День: 2, Ночь: 0`) и боссам (`Лютый` с требованием `2 дневные ходки в Кресты`) -> проверка разблокировки возвращает `unlocked = True`, `completed = 2`, `required = 2` (как в Web API меню боссов, так и в `BossWorker` при выборе цели для автопризыва).
   - Проверка обратного кейса (`День: 1`) -> `locked = True`, `1 из 2`.
   - Проверка, что при завершении 2-й ходки в `PrisonWorker` событие `notify_mutation("prison_completed")` немедленно инвалидирует `prisons` и `boss`, после чего `Лютый` сразу становится разблокированным без рестарта и без ожидания часовых интервалов.
2. **Доменный `StateHub`, single-flight и кросс-инвалидация (`tests/test_state_hub.py`, `tests/test_realtime_scheduler.py`)**:
   - Тест матрицы кросс-инвалидации (`prison_completed`, `boss_claimed`, `fartovy_spun`, `poker_played`, `zarub_updated`, `social_changed`, `maintenance_recovered`): нужные зависимые домены помечаются `dirty`, `revision` растет.
   - Тест single-flight (`asyncio.gather` из 5 параллельных вызовов `ensure_domain_fresh("prisons")` делает ровно `1` сетевой запрос к API игры).
   - Тест отказоустойчивости: при ошибке сети / `GameMaintenanceError` во время `ensure_domain_fresh` последний валидный кэш домена сохраняется неизменным.
3. **Zero-Regression по всем существующим системам (`tests/test_web_api.py`, `tests/test_web_endpoints.py` + полный прогон)**:
   - Проверка телеметрии `domain_revisions` и `domains` в `/api/v1/workers/status` и `/api/v1/state`.
   - Runtime-тест JS через `node`: при росте `domain_revisions.boss` / `domain_revisions.prisons` фронтенд автоматически триггерит обновление списка боссов.
   - Актуализация версий `20261126_09` и `prisonbot-assets-v21` в `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`.
   - Полный прогон `node --check web/static/app.js`, `node --check web/static/sw.js` и всего `python -m pytest -q tests/` (ни один из 259+ существующих тестов не должен упасть!).

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Baseline VPS + живая диагностика бага «Кресты `День: 2` vs Лютый `пройдено 0`» и аудит всех кэшей**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Проверить на живом VPS (`178.17.60.16`, read-only) и в коде (`client/api/prison.py`, `client/api/boss.py`, `core/state_hub.py`, `workers/boss_worker.py`, `web/routes.py`), откуда Ходки берут `День: 2` и почему Боссы показывают `пройдено 0 (0 из 2)` для `Лютого`[cite: 56, 57].
  - Составить карту всех существующих локальных кэшей и мест рассинхрона во всех 7 воркерах и `web/routes.py`.
- [ ] **Шаг 2. Починка единого расчета разблокировки боссов и доменной архитектуры `StateHub` (`core/state_hub.py`, `client/api/boss.py`, `client/api/prison.py`, `workers/boss_worker.py`, `web/routes.py`)**:
  - Починить парсинг и единую проверку разблокировки боссов по актуальному прогрессу ходок (`prisons`), чтобы UI и `BossWorker` видели одинаковый и точный статус всех боссов (включая `Лютого`).
  - Внедрить в `core/state_hub.py` версионируемые домены (`updated_at`, `revision`, `dirty`, `stale_after_sec`), single-flight `ensure_domain_fresh` и матрицу кросс-инвалидации `notify_mutation(...)` с защитой от затирания кэша при сбоях.
- [ ] **Шаг 3. Подключение кросс-инвалидации во всех 7 воркерах, планировщике и Web API (`core/scheduler.py`, `workers/*.py`, `web/routes.py`, `main.py`)**:
  - Подключить `notify_mutation(...)` после всех успешных мутаций в `PrisonWorker`, `BossWorker`, `RoutineWorker`, `SocialWorker`, `PokerWorker`, `FartovyWorker`, `ZarubyWorker` и ручных POST-роутах в `web/routes.py`.
  - Убедиться, что фоновый опрос регулярно освежает `player`, `prisons` и игровые домены без задержек, не нарушая `ServerHealthMonitor`, Ночной режим и все fail-closed предохранители траты рублей/мыла.
  - Добавить телеметрию свежести доменов в `/api/v1/workers/status` и `domain_revisions` в `/api/v1/state`.
- [ ] **Шаг 4. Реактивная синхронизация фронтенда и Cache-busting (`web/static/index.html`, `web/static/app.js`, `web/static/sw.js`)**:
  - Подключить автообновление открытых вкладок/модалок (в т.ч. «Боссы» и «Меню боссов») при росте `domain_revisions` и форсированный refresh по кнопке обновления профиля.
  - Синхронно поднять `ASSET_VERSION` до `20261126_09` (`index.html`, `app.js`) и кэш SW до `prisonbot-assets-v21` (`sw.js`).
- [ ] **Шаг 5. Автотесты (Zero Regression) и уборка**:
  - Добавить тесты по кейсу «Кресты `День: 2` -> Лютый открыт», доменной кросс-инвалидации, single-flight кэшу, отказоустойчивости и `node` runtime-проверке JS.
  - Прогнать `node --check web/static/app.js`, `node --check web/static/sw.js` и весь `python -m pytest -q tests/` - подтвердить `0` падений по всем 259+ существующим и новым тестам.
  - Удалить временные скрипты агента в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 6. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ЖИВАЯ ВЕРИФИКАЦИЯ**:
  - Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Выполнить живую read-only верификацию:
    - `systemctl is-active prisonbot.service` -> `active`, `127.0.0.1:8085` и `https://zvezdoed.space/prison/` -> HTTP `200` (`20261126_09` / `prisonbot-assets-v21`);
    - подтвердить на живых данных VPS, что босс `Лютый` теперь корректно видит `2 из 2` дневных ходок в Крестах и **разблокирован**;
    - проверить все read-only эндпоинты (`/api/v1/state`, `/api/v1/workers/status`, Катала, Покер, Фартовый, Колесо, Зарубы), отсутствие `Traceback` в `journalctl -u prisonbot.service -n 100`, сохранность рублей/мыла и `0` рестартов у `autoclip_service` и `crayfish_omni_hub`.
  - В итоговом отчете обязательно указать: (а) точную первопричину, почему `Лютый` показывал `пройдено 0 (0 из 2)` при `Кресты: День 2`, (б) какие еще точки рассинхрона найдены и устранены в `StateHub`/воркерах, (в) результаты всех тестов и живой проверки на VPS.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_state_hub.py tests/test_boss_worker.py tests/test_prison_worker.py tests/test_realtime_scheduler.py tests/test_web_api.py tests/test_web_endpoints.py
python -m pytest -q tests/
```