# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ПОЛНЫЙ АУДИТ, СИНХРОНИЗАЦИЯ И ИСПРАВЛЕНИЕ ВСЕХ ТАЙМЕРОВ СИСТЕМЫ (МЕНЯЛА, ЗАРУБЫ, БОССЫ, ЭНЕРГИЯ, РУТИНА) + ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack разработчика (Python / FastAPI / Asyncio + Vanilla JS / HTML / CSS) и специалиста по надежности real-time систем на проекте PrisonBot.

**Контекст и источники правды:**
- В проекте выявлено расхождение таймера Менялы: в веб-интерфейсе бота отображается `До отъезда: 1д 23:29:09`, в то время как в самом игровом приложении на иконке фургона Менялы указано `1 день`.
- Твоя задача - провести глубокий аудит первопричины этого расхождения (сверив реальный сырой ответ `/api/smuggling/state`, логику форматирования в `parsed_js/bundle.js` и, при доступности, живой WebApp на `localhost:9222`), а затем проверить и привести к 100% точности **все таймеры во всей системе** (бэкенд, воркеры и фронтенд), устранив любые проблемы с часовыми поясами, расхождением часов клиента/сервера, дрейфом `setInterval` в фоновых вкладках и дублированием тикеров. После этого покрыть все тестами и выгрузить релиз на VPS с живой проверкой.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

### 1.1. Точная проверка и исправление таймера Менялы (`1д 23:29:09` vs `1 день`)
- Проверить сырой ответ живого `/api/smuggling/state` на VPS (`startedAtUtc`, `endsAtUtc`, `nextStartAtUtc`, HTTP-заголовок `Date` от игрового сервера) и код расчета/форматирования таймера в `parsed_js/bundle.js` (для кнопки фургона в HUD и внутри `SmugglingScene`).
- Точно установить и задокументировать в отчете, чем вызвана разница между `1д 23:29:09` в боте и `1 день` в игре:
  - является ли это особенностью округления вниз в игре (`Math.floor(remainingSec / 86400)` -> при `1д 23ч 29м` игра просто отбрасывает `23ч 29м` и пишет `1 день`),
  - ИЛИ есть реальное смещение времени (например, `endsAtUtc` в МСК без суффикса `Z`, ошибка парсинга таймзоны в `_parse_iso_ts`, расхождение системных часов браузера/VPS с игровым сервером, неверное поле окончания или сдвиг на сутки).
- Обеспечить 100% точное совпадение оставшегося времени с реальным серверным временем игры (до секунды):
  - если в данных сервера есть смещение/неверная таймзона/поле - исправить парсинг в `client/api/menyala.py`;
  - если игра на иконке просто округляет дни вниз (`floor`), а точное время до отъезда действительно `1д 23:29:09` - дополнительно убедиться в точности до секунды по серверным часам (убрать любой сдвиг клиентских часов) и вывести в тултипе (`title`) точную дату и время отъезда/приезда по МСК (например, `Отъезд: 30.11 00:00 МСК`), чтобы пользователь всегда мог мгновенно сверить и видеть точность.

### 1.2. Единая точность и исправность ВСЕХ таймеров в системе
Провести ревизию и стандартизировать абсолютно все таймеры в PrisonBot:
1. **Меняла и акции**: таймер «До приезда» и «До отъезда», автоматическое бесшовное переключение состояния при достижении `00:00:00` (без спама запросами).
2. **Зарубы**: таймер активной зарубы `#zaruby-timer` (`endUnix` в секундах/миллисекундах), автоматическое обновление состояния при завершении.
3. **Энергия (Ходки и мастера)**: таймер восстановления следующей единицы энергии («восстановление: ММ:СС») и время до полного восстановления, без отставания и отрицательных значений.
4. **Боссы**: таймер текущего боя с боссом, таймер кулдаунов/автоатаки, сброс дневных лимитов (00:00 МСК).
5. **Рутина и мини-игры**: таймеры колеса, каталы, покера, фартового, посылок/подогревов/тушенки, таймер суточного сброса дельт (00:00 МСК), таймеры активных бустов/акций.
6. **Отсутствие дрейфа и багов рендера**:
   - ни один таймер не должен зависеть от точности локальных часов ПК/телефона пользователя (компенсация `server_now_ts - Date.now()`);
   - ни один таймер не должен «отставать» после сворачивания вкладки браузера (считать строго от абсолютного `target_ts`, а не через декремент `seconds--`);
   - ни один таймер не должен «скакать» по 2-3 секунды за тик из-за утечки/дублирования `setInterval` при SSE-обновлениях или смене вкладок;
   - ни один таймер не должен показывать `NaN`, `undefined`, отрицательные значения (`-1с`) или зависать на `00:00:00`.

---

## 2. КОНФИГУРАЦИЯ

### 2.1. Модули и файлы для аудита и изменений
- **Клиенты игрового API и синхронизация времени**:
  - `client/http_client.py` - фиксация `game_server_time_offset_sec` по заголовку `Date` (и/или серверному timestamp в ответах игры).
  - `client/api/menyala.py` - `_parse_iso_ts`, `_next_friday_arrival_ts`, `parse_menyala_state`.
  - `client/api/zaruby.py` - парсинг `endUnix` и таймеров раунда.
  - `client/api/prison.py`, `client/api/player.py` - расчет таймеров восстановления энергии.
  - `client/api/boss.py`, `client/api/wheel.py`, `client/api/katala.py`, `client/api/poker.py`, `client/api/fartovy.py` - все таймеры боев и кулдаунов.
- **Ядро и Web API**:
  - `core/state_hub.py`, `web/routes.py` - проброс единого поля `server_now_ts` (float/int UTC epoch seconds с учетом смещения игрового сервера) в `/api/v1/state`, `/api/v1/live/stream`, `/api/v1/menyala/state`, `/api/v1/zaruby/state`, `/api/v1/live/prisons`, `/api/v1/live/profile`, `/api/v1/bosses/live` и прочие live-эндпоинты с таймерами.
- **Фронтенд**:
  - `web/static/app.js` - единый модуль синхронизации времени (`syncServerClock`, `getSyncedNowMs`, `getSyncedNowSec`), единый форматтер таймеров (`formatCountdown`), централизованный или строго очищаемый менеджер тикеров, обновление при `visibilitychange`.
  - `web/static/index.html`, `web/static/styles.css`, `web/static/sw.js`.
- **Тесты и инфраструктура**:
  - `tests/test_menyala.py`, `tests/test_zaruby.py`, `tests/test_prison_worker.py`, `tests/test_boss_worker.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`.
  - `.env_server`, `vps_audit.md` (`178.17.60.16`, `/opt/prisonbot`, `prisonbot.service`).

### 2.2. Версионирование статики и кэша
- Поднять версию статики с `20261127_08` до `20261127_09` в `web/static/index.html` и `web/static/app.js`.
- Поднять версию кэша Service Worker с `prisonbot-assets-v29` до `prisonbot-assets-v30` в `web/static/sw.js`.
- Синхронизировать версии в `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`, `tests/test_web_endpoints.py`.

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Диагностика таймеров в игре (`parsed_js/bundle.js` + живой API на VPS)
1. Найти в `parsed_js/bundle.js` функции форматирования таймеров (включая кнопку фургона Менялы, сцену `SmugglingScene`, `ZarubaScene`, таймер энергии и таймер босса).
2. Получить живой ответ `/api/smuggling/state`, `/api/zaruba/state`, профиля/энергии и активного босса (с VPS или через `localhost:9222`) вместе с HTTP-заголовком `Date` ответа игрового сервера.
3. Проверить точные единицы измерения и часовой пояс каждого timestamp-поля от игры:
   - `endsAtUtc`, `startedAtUtc`, `nextStartAtUtc` у Менялы (UTC vs MSK, наличие `Z` / `+00:00`);
   - `endUnix` у Зарубов (секунды vs миллисекунды);
   - `energyRestoreAt` / `nextEnergyIn` / `energyUpdatedAt` у энергии (относительные секунды vs абсолютный timestamp);
   - `endTime` / `expiresAt` / `timeout` у босса и кулдаунов мини-игр.
4. Исправить все найденные расхождения на бэкенде в соответствующих модулях `client/api/*.py`.

### 3.2. Единая серверная синхронизация времени (Backend + Frontend)
1. **Backend (`client/http_client.py`, `core/state_hub.py`, `web/routes.py`)**:
   - При каждом ответе от игрового сервера с валидным HTTP-заголовком `Date` (парсить через `email.utils.parsedate_to_datetime`) аккуратно вычислять и сглаживать `game_server_offset_sec = game_server_utc_ts - time.time()` (с защитой от сетевых выбросов, обновлять только если `abs(delta) < 86400`).
   - Выделить хелпер `get_game_now_ts() -> float` (возвращает `time.time() + game_server_offset_sec`).
   - Все API-ответы с таймерами (и SSE `snapshot` / доменные события) должны включать поле `"server_now_ts": int(get_game_now_ts())` (или `round(..., 3)`).
   - Для всех относительных длительностей от игрового API (например, `seconds_left = 118` для энергии) немедленно фиксировать на бэкенде абсолютный `target_ts = get_game_now_ts() + seconds_left` в момент получения ответа от игры, чтобы фронтенд не терял секунды на сетевой задержке или кэшировании в `StateHub`!
2. **Frontend (`web/static/app.js`)**:
   - Реализовать единый clock-sync:
     ```javascript
     let serverClockOffsetMs = 0;
     let hasServerClockSync = false;

     function syncServerClock(serverNowTs) {
       const ts = Number(serverNowTs);
       if (!Number.isFinite(ts) || ts <= 0) return;
       const serverMs = ts > 1e12 ? ts : ts * 1000;
       const measuredOffset = serverMs - Date.now();
       if (!hasServerClockSync || Math.abs(measuredOffset - serverClockOffsetMs) > 2000) {
         serverClockOffsetMs = measuredOffset;
         hasServerClockSync = true;
       } else {
         serverClockOffsetMs = serverClockOffsetMs * 0.7 + measuredOffset * 0.3;
       }
     }

     function getSyncedNowMs() {
       return Date.now() + serverClockOffsetMs;
     }

     function getSyncedNowSec() {
       return Math.floor(getSyncedNowMs() / 1000);
     }
     ```
   - Вызывать `syncServerClock(data.server_now_ts)` при каждом ответе `/api/v1/*` и каждом SSE-событии.
   - Реализовать единый безопасный форматтер `formatCountdown(totalSeconds, opts)`:
     - строго нормализует вход (`Math.max(0, Math.floor(Number(totalSeconds) || 0))`), никогда не возвращает `NaN` или отрицательные значения;
     - корректно форматирует:
       - `>= 86400`: `${d}д ${hh}:${mm}:${ss}` (плюс при необходимости хелпер для компактного/подробного отображения);
       - `>= 3600`: `${hh}:${mm}:${ss}`;
       - `< 3600`: `${mm}:${ss}` (или `00:MM:SS`, в зависимости от компактности слота).
   - Перевести **все** живые таймеры в `web/static/app.js` на расчет от абсолютного `target_ts` через `getSyncedNowMs()` и на единый тикер (или строго управляемый реестр таймеров без утечек `setInterval`):
     - Меняла (`departure_ts` / `next_arrival_ts`) + понятный тултип с точной датой/временем по МСК и защищенный от спама авто-рефетч при переходе через `0`;
     - Зарубы (`#zaruby-timer` от `end_unix`) + авто-рефетч при переходе через `0`;
     - Энергия (от абсолютного `next_energy_at_ts` / `full_energy_at_ts`, а не декрементом локальной переменной) + синхронизация при переходе через `0`;
     - Бой с боссом и кулдауны боссов (от абсолютного `boss_end_ts` / `cooldown_until_ts`);
     - Мини-игры, рутина, бусты и суточный сброс (00:00 МСК).
   - При событии `document.visibilitychange` (`visible`) немедленно пересчитывать все активные таймеры и синхронизировать состояние.

### 3.3. Проверка точности расписания Менялы и уведомлений
- В `client/api/menyala.py` убедиться, что:
  - `_parse_iso_ts` корректно обрабатывает все форматы (`Z`, `+00:00`, `+03:00`, миллисекунды `.123Z`, unix sec, unix ms);
  - `remaining_sec` (если возвращается рядом с `departure_ts` / `next_arrival_ts`) рассчитывается строго от `get_game_now_ts()`;
  - fallback `_next_friday_arrival_ts` точно соответствует реальному времени старта события в игре (сверить с `startedAtUtc` и `nextStartAtUtc` живого API на VPS).

---

## 4. ТЕСТИРОВАНИЕ

### 4.1. Новые и обновленные тесты
Добавить и обновить тесты в `tests/test_menyala.py`, `tests/test_zaruby.py`, `tests/test_prison_worker.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`:
1. **Тесты парсинга времени и server clock offset**:
   - `_parse_iso_ts` на форматах `2026-11-29T21:00:00Z`, `2026-11-29T21:00:00.500Z`, `2026-11-30T00:00:00+03:00`, unix sec и unix ms дает строго одинаковый UTC epoch timestamp.
   - `client/http_client.py` корректно извлекает смещение из HTTP-заголовка `Date`, а эндпоинты `/api/v1/menyala/state`, `/api/v1/zaruby/state`, `/api/v1/state`, `/api/v1/live/prisons` возвращают валидный `server_now_ts`.
2. **Тесты точности Менялы, Зарубов и Энергии**:
   - Проверка `parse_menyala_state` на реальном payload `/api/smuggling/state` (точное совпадение `departure_ts`, `next_arrival_ts`, `remaining_sec`).
   - Проверка расчета таймера Зарубов (`endUnix` в мс и в сек) и энергии (абсолютный `next_energy_at_ts` не дрейфует при кэшировании).
3. **JS Runtime Smoke-тест таймеров в Node.js (`tests/test_web_endpoints.py`)**:
   - Эмулировать расхождение системных часов браузера (например, локальный `Date.now()` спешит на `+3 часа` или отстает на `-10 минут`), передать `server_now_ts` -> проверить, что `getSyncedNowSec()` и таймеры Менялы, Зарубов, Энергии и Босса показывают **точное серверное оставшееся время** с погрешностью `<= 1 сек`.
   - Проверить, что повторные ререндеры карточек Менялы / Зарубов / Ходок / Боссов не плодят дублирующие `setInterval` и не дают отрицательных значений или `NaN` при `target_ts <= now`.
4. Проверить синхронизацию версий `20261127_09` / `prisonbot-assets-v30` в `test_asset_cache.py`, `test_improvements_v2.py`, `test_web_endpoints.py` и прогнать весь пакет `pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

### Чеклист выполнения
- [ ] 1. Провести расследование расхождения Менялы (`1д 23:29:09` vs `1 день`): снять живой `/api/smuggling/state` + HTTP `Date` на VPS и сверить с логикой форматирования таймера в `parsed_js/bundle.js` (и при доступности `localhost:9222`), зафиксировать точную причину в отчете.
- [ ] 2. Провести полный аудит всех таймеров проекта (`client/api/menyala.py`, `zaruby.py`, `prison.py`, `player.py`, `boss.py`, `wheel.py`, `katala.py`, `poker.py`, `fartovy.py`, `web/routes.py`, `web/static/app.js`).
- [ ] 3. Внедрить серверную синхронизацию времени (`game_server_offset_sec` + `get_game_now_ts()` + `server_now_ts` в live/state/SSE ответах) и абсолютные `target_ts` для относительных таймеров (энергия, кулдауны).
- [ ] 4. Перевести все таймеры в `web/static/app.js` на единый `syncServerClock` / `getSyncedNowMs()` / `formatCountdown`, устранить дрейф в фоне, утечки/дубли `setInterval` и добавить точный тултип с датой/временем МСК для Менялы + авто-обновление при переходе через `00:00:00`.
- [ ] 5. Поднять версии статики и кэша Service Worker до `20261127_09` / `prisonbot-assets-v30` в `web/static/index.html`, `web/static/app.js`, `web/static/sw.js` и обновить тесты ассетов.
- [ ] 6. Написать и прогнать все unit-тесты и JS runtime smoke-тесты таймеров (`node --check`, `python -m pytest -q tests/`), очистить `.pytest_cache` / `__pycache__` и удалить временные деплой-скрипты из корня проекта (`deploy_release_v08.py` и аналоги, если остались).
- [ ] 7. **ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS**: выгрузить все измененные файлы на `178.17.60.16` (`/opt/prisonbot`), перезапустить `prisonbot.service`, не затрагивая соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`).
- [ ] 8. **ОБЯЗАТЕЛЬНАЯ ЖИВАЯ ПРОВЕРКА НА VPS И ПО ПУБЛИЧНОМУ HTTPS**:
  - проверить `systemctl is-active prisonbot.service` и отсутствие traceback в `journalctl -u prisonbot.service -n 100`;
  - проверить публичный HTTPS: `https://zvezdoed.space/prison/`, `app.js?v=20261127_09`, `styles.css?v=20261127_09`, `sw.js` (`prisonbot-assets-v30`);
  - снять живые ответы `/api/v1/menyala/state`, `/api/v1/zaruby/state`, `/api/v1/live/prisons`, `/api/v1/state` на VPS и подтвердить в отчете:
    - наличие валидного `server_now_ts` и нулевой дрейф относительно HTTP `Date` игрового сервера;
    - точные значения `endsAtUtc` / `departure_ts` / оставшегося времени Менялы и их соответствие игре;
    - корректные абсолютные таймеры Зарубов, Энергии и Боссов.

### Команды проверки
```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest tests/test_menyala.py tests/test_zaruby.py tests/test_prison_worker.py tests/test_boss_worker.py tests/test_web_api.py tests/test_web_endpoints.py tests/test_asset_cache.py tests/test_improvements_v2.py -v
python -m pytest -q tests/
```