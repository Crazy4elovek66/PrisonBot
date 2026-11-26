# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ИСПРАВЛЕНИЕ ЛОЖНОГО ОТОБРАЖЕНИЯ «БЕСПЛАТНАЯ ИГРА ДОСТУПНА (0 ₽)» КАТАЛЫ В ВЕБ-ПАНЕЛИ И FAIL-CLOSED СИНХРОНИЗАЦИЯ UI С ЖИВЫМ API + ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack & Reverse-Engineering инженера (Python / AsyncIO / FastAPI / Vanilla JS / CSS / Chrome DevTools MCP / Linux systemd). На продакшене выявлен баг рассинхрона интерфейса Каталы: в самой игре «Тюряга» бесплатная попытка уже недоступна (кнопка показывает `ИГРАТЬ 1` за 1 рубль)[cite: 40], но в веб-панели в блоке `Катала (Карты)` отображается зеленый статус `🟢 Бесплатная игра доступна (0 ₽)` и активная кнопка `Сыграть партию`[cite: 39]. Твоя задача - найти точную причину этого расхождения (проверить `web/static/index.html`, `web/static/app.js`, `web/routes.py`, `client/api/katala.py`, живой ответ `https://zvezdoed.space/prison/api/v1/daily/katala-status` и живой клиент через MCP DevTools `--remote-debugging-port=9222`), перевести отображение статуса и кнопки Каталы на строгий принцип **Fail-Closed**, покрыть автотестами (включая runtime-проверки JS через `node`), обновить cache-busting и **обязательно задеплоить и верифицировать на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Устранить ложный статус `🟢 Бесплатная игра доступна (0 ₽)` в веб-панели**:
   - Если в игре бесплатной партии нет (кнопка `ИГРАТЬ 1` за рубли), веб-панель **ни при каких обстоятельствах** не должна показывать `Бесплатная игра доступна (0 ₽)` - ни до загрузки данных, ни при ошибке сети, ни после перезагрузки/переключения вкладок.
   - Бейдж `#katala-free-status-badge` обязан 100% соответствовать реальному состоянию игры (`GET /api/card/state`) и локального предохранителя (`katala_guard_state`)[cite: 39, 40].
2. **Принцип Fail-Closed в UI и блокировка кнопки `Сыграть партию`**:
   - В исходном HTML до прихода живого ответа от API статус должен быть нейтральным (`Проверка статуса...`), а кнопка `Сыграть партию` - временно заблокированной (`disabled`).
   - При `free_available === true` (явное подтверждение от сервера игры с ценой `0` и пройденный локальный guard): показывать `🟢 Бесплатная игра доступна (0 ₽)` и разблокировать `Сыграть партию`.
   - При `free_available === false` (активный кулдаун / уже сыграна сегодня): показывать приглушенный/оранжевый статус с точным временем ожидания (например, `⏳ Бесплатная игра использована · следующая через 13ч 14м`) и держать кнопку `Сыграть партию` в состоянии `disabled`.
   - При `guard_tripped === true`: показывать красный статус `🛑 Авто-Катала остановлена защитой рублей` и блокировать кнопку `Сыграть партию` до ручного сброса защиты.
   - При любой сетевой/серверной ошибке (`401`, `404`, `500`, таймаут): показывать `⚠️ Не удалось проверить статус Каталы (запуск заблокирован)` и оставлять кнопку `disabled`.
3. **Проверка точного правила сброса бесплатной Каталы в игре**:
   - Проверить в живом приложении (`--remote-debugging-port=9222`) и в `parsed_js/bundle.js` точную логику игры для бесплатной партии (24 часа от `lastFreePlayTime` vs сброс в `00:00` UTC/МСК, а также любые дополнительные поля `GET /api/card/state`), чтобы расчет `free_available` и `seconds_left` на бэкенде совпадал с игровой кнопкой `БЕСПЛАТНО` / `ИГРАТЬ 1` на 100%[cite: 40].
4. **Автотесты, cache-busting и обязательный деплой на VPS**:
   - Покрыть бэкенд и фронтенд-рендер (`node` runtime-тест) автотестами, синхронно поднять `ASSET_VERSION` и версию Service Worker кэша, выкатить на VPS (`178.17.60.16`, `/opt/prisonbot`), проверить публичный URL `https://zvezdoed.space/prison/` и подтвердить `0` рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Источники истины и инструменты диагностики
- **Живое приложение «Тюряга» (Telegram WebApp)**: доступно через MCP Chrome DevTools (`--remote-debugging-port=9222`) для сверки реального `GET /api/card/state` и UI-кнопки `ИГРАТЬ 1`[cite: 40].
- **Продакшен VPS**: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), БД `/opt/prisonbot/storage/prison_bot.db`, публичный URL `https://zvezdoed.space/prison/`.
- **Соседние Docker-контейнеры (НЕ ТРОГАТЬ)**: `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

### Ключевые файлы проекта под аудит и доработку
- Бэкенд Каталы и Web API: `client/api/katala.py`, `workers/routine_worker.py`, `core/database.py`, `web/routes.py`[cite: 41].
- Фронтенд и PWA: `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/static/sw.js`[cite: 41].
- Автотесты: `tests/test_katala.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`[cite: 41].

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Диагностика первопричины расхождения (UI vs API vs Игра)
Проверить по порядку все возможные точки отказа и зафиксировать точную причину в отчете:
1. **Дефолтный HTML и жизненный цикл загрузки в `web/static/index.html` и `web/static/app.js`**:
   - Проверить исходное содержимое `#katala-free-status-badge` в `web/static/index.html` (нет ли там захардкоженного `🟢 Бесплатная игра доступна (0 ₽)`).
   - Проверить в `web/static/app.js`, как и когда вызывается `fetch` к `/api/v1/daily/katala-status`:
     - используется ли правильный базовый путь / `apiFetch` с учетом reverse proxy `/prison/` (если в `app.js` написан голый `fetch('/api/v1/daily/katala-status')`, то на `https://zvezdoed.space/prison/` запрос улетает на `https://zvezdoed.space/api/v1/daily/katala-status` и падает с `404`!);
     - передаются ли нужные заголовки/куки авторизации;
     - вызывается ли обновление статуса при первом открытии панели, при переходе на вкладку Рутины/Ежедневных действий, при нажатии `Обновить` и сразу после запуска `Сыграть партию`;
     - корректно ли разбирается JSON-ответ (`data.free_available === true` вместо ошибочной проверки truthy-полей или неверного ключа).
2. **Проверка живого ответа бэкенда (`web/routes.py`, `client/api/katala.py`)**:
   - Выполнить на VPS авторизованный запрос к `http://127.0.0.1:8085/api/v1/daily/katala-status` И к публичному `https://zvezdoed.space/prison/api/v1/daily/katala-status`: сравнить HTTP-коды и JSON-тела.
   - Проверить в `client/api/katala.py` и `parsed_js/bundle.js`, совпадает ли `is_free_game_available` с реальным расчетом игры (проверить `lastFreePlayTime`, `hasActiveGame` / `activeGame`, `freeGameAvailable`, `cost`, `rubles`, часовой пояс и длительность кулдауна).
   - Убедиться, что если в игре активная партия отсутствует и `lastFreePlayTime` был сегодня (менее 24ч назад или в текущие сутки - в точности как в `bundle.js`), то `free_available` всегда строго `False` и `seconds_left > 0`.
3. **Проверка Service Worker и кэша (`web/static/sw.js`)**:
   - Проверить, не кэширует ли `sw.js` запросы к `/api/...` или старую версию `index.html`/`app.js`.

### 3.2. Исправление бэкенда (`client/api/katala.py`, `web/routes.py`)
- Гарантировать, что `GET /api/v1/daily/katala-status` всегда возвращает `Cache-Control: no-store` и полную консистентную структуру:
  ```json
  {
    "success": true,
    "free_available": false,
    "server_free_ok": false,
    "guard_tripped": false,
    "already_played_today": true,
    "last_free_day_msk": "2026-11-26",
    "seconds_left": 47647,
    "next_free_at_msk": "2026-11-27 06:57 МСК",
    "reason": "cooldown_24h_47647s"
  }
  ```
- Если при запросе `/api/card/state` произошла любая ошибка (сеть, токен, парсинг) - возвращать `free_available: false`, `server_free_ok: false`, `error: "<детали>"` (строго fail-closed).
- В `web/routes.py` проверить также, не подмешивает ли общий эндпоинт `/api/v1/state` (или `/api/v1/daily/...`) старый флаг Каталы, который мог перезаписывать бейдж в `app.js` на `true`.

### 3.3. Fail-Closed UI и синхронный рендер (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)
- В `web/static/index.html`:
  - Установить в `#katala-free-status-badge` безопасный начальный текст `⏳ Проверяем статус бесплатной игры...` (без зеленого цвета) и атрибут `disabled` на кнопку `Сыграть партию` до первого успешного ответа API.
- В `web/static/app.js`:
  - Выделить чистую тестируемую функцию `renderKatalaFreeStatus(statusData)` (экспортируемую/доступную для `node` runtime-теста):
    - при `!statusData || statusData.success === false`: статус `⚠️ Статус Каталы не проверен (запуск заблокирован)`, кнопка `Сыграть партию` `disabled = true`;
    - при `statusData.guard_tripped === true`: статус `🛑 Авто-Катала остановлена защитой рублей`, кнопка `disabled = true`;
    - при `statusData.free_available === true`: статус `🟢 Бесплатная игра доступна (0 ₽)`, кнопка `disabled = false`;
    - во всех остальных случаях (`free_available !== true`):
      - если `seconds_left > 0`, форматировать оставшееся время в `ЧЧч ММм` (или `ММм ССс`, если меньше часа) и выводить `⚪ Бесплатная игра использована · следующая через <ЧЧч ММм>` (плюс `title` с точным `next_free_at_msk` и `reason`);
      - если `seconds_left` отсутствует - `⚪ Бесплатная игра сегодня уже использована`;
      - кнопка `Сыграть партию` строго `disabled = true`.
  - Убедиться, что запрос `/api/v1/daily/katala-status` идет строго через проектный API-хелпер (работающий корректно под `/prison/`), вызывается при инициализации приложения, при открытии вкладки с Каталой, при нажатии `Обновить` и сразу после завершения ручной игры.
  - Добавить защиту от гонки: более старый запрос статуса не перезаписывает более свежий.

### 3.4. Cache-busting, уборка и обязательный деплой на VPS
- Синхронно поднять `ASSET_VERSION` в `web/static/index.html` и `web/static/app.js` до `20261126_05` и имя кэша Service Worker в `web/static/sw.js` до `prisonbot-assets-v17` (обновить проверки версий в тестах).
- Удалить любые временные скрипты в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).
- Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую верификацию на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`, локальный `127.0.0.1:8085` стартует `<= 5s`.
  2. Проверить через `curl` отдачу свежих версий (`20261126_05` и `prisonbot-assets-v17`) на `127.0.0.1:8085` и `https://zvezdoed.space/prison/`.
  3. Проверить авторизованный ответ `GET https://zvezdoed.space/prison/api/v1/daily/katala-status` (подтвердить HTTP `200`, `Cache-Control: no-store`, `free_available: false` при текущем состоянии игры `ИГРАТЬ 1`[cite: 40]).
  4. Проверить `journalctl -u prisonbot.service -n 80 --no-pager` на отсутствие `Traceback`.
  5. Подтвердить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Добавить и обновить автотесты в `tests/test_katala.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`:

1. **Бэкенд и API (`tests/test_katala.py`, `tests/test_web_api.py`)**:
   - Проверка `GET /api/v1/daily/katala-status` в 4 состояниях: (a) бесплатная доступна (`free_available: true`), (b) идет кулдаун / сыграна сегодня (`free_available: false`, `seconds_left > 0`), (c) сработал `guard_tripped` (`free_available: false`), (d) сбой игрового API (`free_available: false`, fail-closed).
   - Проверка заголовка `Cache-Control: no-store` на `/api/v1/daily/katala-status`.
2. **Фронтенд и `node` runtime-тест (`tests/test_web_endpoints.py`)**:
   - В `web/static/index.html` внутри `#katala-free-status-badge` отсутствует ложный дефолтный текст `Бесплатная игра доступна (0 ₽)`, а кнопка запуска изначально `disabled`.
   - Runtime-тест через `node` для `renderKatalaFreeStatus` в `web/static/app.js`:
     - `free_available: false, seconds_left: 47647` -> текст показывает использованную игру и оставшееся время (`13ч 14м`), кнопка `disabled = true`;
     - `free_available: true` -> текст `Бесплатная игра доступна (0 ₽)`, кнопка `disabled = false`;
     - `guard_tripped: true` -> красный статус остановки защитой рублей, кнопка `disabled = true`;
     - `null` / `{success: false}` -> fail-closed статус ошибки, кнопка `disabled = true`.
   - Проверка, что запрос к `/api/v1/daily/katala-status` в `app.js` использует корректный префикс/хелпер (не ломается под `/prison/`).
   - Обновить проверки версий `20261126_05` и `prisonbot-assets-v17` в `tests/test_web_endpoints.py`, `tests/test_asset_cache.py`, `tests/test_improvements_v2.py`.
3. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и весь `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Baseline VPS + диагностика причины ложного `Бесплатная игра доступна (0 ₽)`**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Проверить `web/static/index.html`, `web/static/app.js`, `web/routes.py`, `client/api/katala.py`, живой ответ `https://zvezdoed.space/prison/api/v1/daily/katala-status` и реальный `GET /api/card/state` (через `9222` / `bundle.js`), установив точную причину, почему в браузере горел зеленый статус при `ИГРАТЬ 1` в игре[cite: 39, 40].
- [ ] **Шаг 2. Исправление бэкенда и Fail-Closed UI (`client/api/katala.py`, `web/routes.py`, `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)**:
  - Устранить выявленный баг (URL под `/prison/`, вызов при загрузке/переключении вкладки, парсинг полей, дефолтный HTML и/или логику кулдауна).
  - Реализовать строгий Fail-Closed рендер `#katala-free-status-badge` с таймером и автоматическим `disabled` кнопки `Сыграть партию` во всех состояниях, кроме подтвержденного `free_available === true`.
- [ ] **Шаг 3. Cache-busting, автотесты и уборка**:
  - Синхронно поднять `ASSET_VERSION` до `20261126_05` (`index.html`, `app.js`) и кэш SW до `prisonbot-assets-v17` (`sw.js`).
  - Добавить/обновить автотесты (включая `node` runtime-тест `renderKatalaFreeStatus`), прогнать `node --check` и полный `python -m pytest -q tests/`.
  - Удалить временные скрипты агента в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 4. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ЖИВАЯ ВЕРИФИКАЦИЯ**:
  - Загрузить измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Проверить `127.0.0.1:8085` и `https://zvezdoed.space/prison/` (версии `20261126_05` / `prisonbot-assets-v17`), проверить живой ответ `https://zvezdoed.space/prison/api/v1/daily/katala-status` (`free_available: false`), отсутствие `Traceback` в `journalctl -u prisonbot.service -n 80` и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - В итоговом отчете обязательно указать точную первопричину, почему панель показывала `Бесплатная игра доступна (0 ₽)` при `ИГРАТЬ 1` в игре, и очистить локальные кэши `.pytest_cache` / `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_katala.py tests/test_web_api.py tests/test_web_endpoints.py tests/test_asset_cache.py tests/test_improvements_v2.py
python -m pytest -q tests/
```