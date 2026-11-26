# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: СУТОЧНЫЕ ДЕЛЬТЫ РЕСУРСОВ (МСК) В БЛОКЕ «ВАЛЮТЫ И РЕСУРСЫ» НА ГЛАВНОЙ СТРАНИЦЕ + ПЕРСИСТЕНТНОСТЬ В SQLITE И ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack инженера (Python / AsyncIO / FastAPI / SQLite / Vanilla JS / CSS / Linux systemd). Твоя задача - реализовать учет и отображение суточных дельт в единицах (`+N` / `-N` / `0`) по всем 5 основным ресурсам в блоке «Валюты и Ресурсы» на Главной странице (`Папиросы`, `Сахар`, `Рубли`, `Бумага`, `Мыло`) с суточным сбросом строго по московскому времени (`Europe/Moscow`, `UTC+3`), надежным хранением базовых снимков дня в SQLite (чтобы дельты не обнулялись после перезапуска `prisonbot.service` и копились в фоне даже при закрытой веб-панели), адаптивным и аккуратным UI на десктопе и мобильных устройствах, покрытием автотестами, обновлением cache-busting и **обязательным деплоем и верификацией на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Отображение суточных изменений (`+` / `-`) в единицах по всем 5 ресурсам на Главной странице**:
   - Внутри блока «Валюты и Ресурсы» для каждой из 5 плиток (`Папиросы`, `Сахар`, `Рубли`, `Бумага`, `Мыло`) выводить суточную дельту в точных единицах:
     - положительное изменение: `+1 250` (зеленый акцент);
     - отрицательное изменение: `-340` (красный/коралловый акцент);
     - без изменений: `0` (приглушенный нейтральный цвет, без визуального шума).
   - Значения должны форматироваться с пробелами-разделителями разрядов в едином стиле с основными цифрами баланса (`5 225`, `31 607`) и иметь понятную подсказку (`title`) при наведении с базовым значением на начало суток и временем фиксации (МСК).
2. **Точный учет по московским суткам (`Europe/Moscow`) и фоновая фиксация**:
   - Суточный период привязан строго к дате `YYYY-MM-DD` в часовом поясе `MSK_TZ` (`Europe/Moscow`, `UTC+3`).
   - Базовый снимок ресурсов на текущие сутки (`day_msk`) должен фиксироваться автоматически в фоне при первом валидном обновлении профиля после `00:00 МСК` (через `StateHub` / фоновые воркеры) и сохраняться в SQLite (`storage/prison_bot.db`), чтобы:
     - при открытии панели днем или вечером пользователь видел полную накопленную дельту за весь день;
     - при перезапуске `prisonbot.service` накопленная за текущие сутки дельта **не сбрасывалась**;
     - при переходе через `00:00 МСК` автоматически стартовал отсчет новых суток от актуального баланса на границе дня.
3. **Защита от битых/нулевых базовых снимков**:
   - Никогда не записывать в качестве суточной базы пустой или ошибочный ответ профиля (когда профиль не загружен или игровой сервер вернул ошибку), чтобы избежать ложных огромных плюсов после восстановления сети.
4. **Аккуратная адаптивная верстка, автотесты и обязательный деплой на VPS**:
   - Плитки в блоке «Валюты и Ресурсы» должны оставаться компактными и ровными на десктопе и мобильных экранах (`360px-430px` и `1280px+`), без переноса знака от числа, наезда текста или горизонтального скролла.
   - Покрыть бэкенд, БД-персистентность, смену московских суток, API и фронтенд-рендер (через `node`) автотестами, поднять cache-busting и задеплоить на VPS (`178.17.60.16`, `/opt/prisonbot`), подтвердив `0` рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Отслеживаемые ресурсы (5 целевых ключей)
- `cigarettes` (`Папиросы`)
- `sugar` (`Сахар`)
- `rubles` (`Рубли`)
- `paper` (`Бумага`)
- `soap` (`Мыло`)

### Ключевые файлы проекта под аудит и доработку
- Конфигурация часового пояса и модели: `core/config.py` (`MSK_TZ`), `core/models.py`.
- Хранилище и синхронизация состояния: `core/database.py`, `core/state_hub.py`, `core/scheduler.py`.
- Веб API: `web/routes.py`.
- Фронтенд и PWA: `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/static/sw.js`.
- Автотесты: `tests/test_state_hub.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`.
- Продакшен VPS: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), БД `/opt/prisonbot/storage/prison_bot.db`, публичный URL `https://zvezdoed.space/prison/`.
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Таблица суточных базовых снимков в SQLite (`core/database.py`)
- Добавить в инициализацию схемы БД идемпотентное создание таблицы `daily_resource_snapshots`:
  ```sql
  CREATE TABLE IF NOT EXISTS daily_resource_snapshots (
      day_msk TEXT PRIMARY KEY,
      cigarettes INTEGER NOT NULL,
      sugar INTEGER NOT NULL,
      rubles INTEGER NOT NULL,
      paper INTEGER NOT NULL,
      soap INTEGER NOT NULL,
      captured_at TEXT NOT NULL
  );
  ```
- Реализовать чистые и потокобезопасные методы в `core/database.py`:
  - `get_daily_resource_baseline(day_msk: str) -> Optional[dict]`: возвращает сохраненный базовый снимок за указанную московскую дату (`YYYY-MM-DD`).
  - `ensure_daily_resource_baseline(day_msk: str, resources: dict, captured_at: Optional[str] = None) -> dict`:
    - атомарно (`INSERT OR IGNORE`) фиксирует базовый снимок за `day_msk`, если его еще нет, и возвращает актуальную базовую запись за `day_msk`;
    - дополнительно сохраняет в `app_state`/памяти или отдельной легкой записи последний валидный снимок ресурсов (`last_known_resources`), чтобы при переходе через `00:00 МСК` (если бот работал непрерывно) можно было корректно инициализировать новые сутки без потери изменений в первую минуту дня.
  - `compute_daily_resource_deltas(current_resources: dict, now_msk: Optional[datetime] = None) -> dict`:
    - вычисляет `day_msk = now_msk.strftime("%Y-%m-%d")` по `MSK_TZ`;
    - проверяет валидность `current_resources` (все 5 ключей приводимы к `int` и `>= 0`; защита от незагруженного профиля);
    - вызывает `ensure_daily_resource_baseline` и возвращает словарь:
      ```python
      {
          "day_msk": day_msk,
          "captured_at": baseline["captured_at"],
          "baseline": {
              "cigarettes": ...,
              "sugar": ...,
              "rubles": ...,
              "paper": ...,
              "soap": ...,
          },
          "deltas": {
              "cigarettes": current["cigarettes"] - baseline["cigarettes"],
              "sugar": current["sugar"] - baseline["sugar"],
              "rubles": current["rubles"] - baseline["rubles"],
              "paper": current["paper"] - baseline["paper"],
              "soap": current["soap"] - baseline["soap"],
          },
      }
      ```
  - Опционально выполнять мягкую очистку записей старше 90 дней, чтобы таблица не разрасталась.

### 3.2. Интеграция с `StateHub` и Web API (`core/state_hub.py`, `web/routes.py`)
- В `core/state_hub.py`:
  - При каждом успешном обновлении валидного профиля игрока (когда получены реальные данные игрока с ненулевым `player_id` / `level > 0` или подтвержденным успешным ответом API) вызывать `db.ensure_daily_resource_baseline(...)` для текущей даты `MSK_TZ`.
  - Это гарантирует, что базовый снимок за сутки фиксируется в фоне сразу после полуночи по Москве, даже если пользователь не открывал веб-панель.
- В `web/routes.py`:
  - В ответах эндпоинтов, которые питают Главную страницу (проверить точные роуты: `/api/v1/state`, `/api/v1/profile`, `/api/v1/dashboard` и/или WebSocket/SSE-обновления `StateHub`), добавить поле `resource_deltas` (со структурой `{day_msk, captured_at, baseline, deltas}`), рассчитанное от актуальных значений ресурсов профиля.
  - Убедиться, что после любого действия в панели, меняющего ресурсы (ходка, слив энергии, сбор наград, покупка в примерочной, обмен, кнопка ручного обновления профиля на Главной), возвращаемый/обновляемый профиль сразу содержит пересчитанный `resource_deltas`.

### 3.3. Верстка и динамический рендер на Главной странице (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)
- **HTML (`web/static/index.html`)**:
  - В блоке «Валюты и Ресурсы» внутри каждой из 5 плиток (`Папиросы`, `Сахар`, `Рубли`, `Бумага`, `Мыло`) добавить элемент дельты с явным `id` (например: `#res-cigarettes-delta`, `#res-sugar-delta`, `#res-rubles-delta`, `#res-paper-delta`, `#res-soap-delta`) и классом `.resource-delta`.
  - Расположить дельту аккуратно и читаемо (например, компактным бейджем в правом верхнем/нижнем углу плитки или отдельной строкой/справа от числа в той же плитке), не увеличивая громоздкость блока «Валюты и Ресурсы» и сохраняя единую высоту всех 5 карточек.
- **JS (`web/static/app.js`)**:
  - Добавить чистый helper `formatResourceDelta(value)`:
    - если `value === null || value === undefined || Number.isNaN(Number(value))` -> возвращает `{ text: "", cls: "is-empty" }` (ничего не рисует до загрузки данных);
    - если `n > 0` -> `{ text: "+" + formatNum(n), cls: "is-positive" }`;
    - если `n < 0` -> `{ text: "-" + formatNum(Math.abs(n)), cls: "is-negative" }`;
    - если `n === 0` -> `{ text: "0", cls: "is-zero" }`.
  - Добавить функцию `renderResourceDeltas(resourceDeltas, currentProfile)` и вызывать ее из `renderProfile` / обработчика обновления состояния Главной страницы.
  - Проставлять `title` (tooltip) на элемент дельты (или на саму плитку ресурса): например `Суточная дельта (МСК, с HH:MM): было 5 100 -> стало 5 225 (+125)`.
- **CSS (`web/static/styles.css`)**:
  - Стилизовать `.resource-delta` (моноширинные/табличные цифры `font-variant-numeric: tabular-nums`, `font-size: 11px-12px`, `font-weight: 600`, `white-space: nowrap`):
    - `.resource-delta.is-positive` -> мягкий зеленый цвет + легкий полупрозрачный фон-плашка (или чистый аккуратный текст без перегруза);
    - `.resource-delta.is-negative` -> мягкий красный/коралловый цвет;
    - `.resource-delta.is-zero` -> приглушенный серый (`opacity: 0.55`).
  - Проверить адаптивность сетки блока «Валюты и Ресурсы» на экранах `360px`, `375px`, `430px`, `768px` и `1280px+`: дельта не должна перекрывать основное число баланса, обрезаться или ломать выравнивание карточек.

### 3.4. Cache-busting, уборка и обязательный деплой на VPS
- Проверить текущие значения `ASSET_VERSION` (в `web/static/index.html` и `web/static/app.js`) и имени кэша Service Worker (в `web/static/sw.js`) и синхронно увеличить их на следующую версию (например, `20261126_03` / `prisonbot-assets-v15`, строго выше текущих в репозитории).
- Удалить любые временные скрипты агента в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).
- Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`) и перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую верификацию на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`, старт `127.0.0.1:8085` за `<= 5` секунд.
  2. Проверить через `curl` отдачу свежей статики (`index.html`, `app.js`, `styles.css`, `sw.js`) на `127.0.0.1:8085` и `https://zvezdoed.space/prison/`.
  3. Сделать авторизованный запрос к эндпоинту профиля/состояния на VPS и убедиться, что `resource_deltas` присутствует в ответе, содержит все 5 ключей (`cigarettes`, `sugar`, `rubles`, `paper`, `soap`), валидный `day_msk` по Москве и реальную запись в таблице `daily_resource_snapshots` в `/opt/prisonbot/storage/prison_bot.db`.
  4. Проверить `journalctl -u prisonbot.service -n 60 --no-pager` на отсутствие `Traceback`.
  5. Подтвердить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Добавить и обновить автотесты в `tests/test_state_hub.py`, `tests/test_web_api.py` и `tests/test_web_endpoints.py`:

1. **SQLite-персистентность и расчет суточных дельт (`tests/test_state_hub.py` / `tests/test_web_api.py`)**:
   - **Фиксация базы и пересчет дельт**: первый снимок дня фиксирует базу (`cigarettes=5000, sugar=30000, rubles=200, paper=100, soap=10`), последующее обновление (`5225, 29800, 208, 100, 12`) возвращает дельты `(+225, -200, +8, 0, +2)`.
   - **Устойчивость к перезапуску**: повторное открытие БД / новый экземпляр `Database` в те же московские сутки сохраняет исходную базу и возвращает ту же накопленную дельту (не сбрасывает в `0`).
   - **Смена московских суток (`00:00 МСК`)**: при `23:55 МСК` используется база дня `D`, а при `00:05 МСК` (хотя в UTC еще `21:05` дня `D`!) автоматически создается новая база для дня `D+1`, и дельта считается от нее.
   - **Защита от битых/пустых данных**: незагруженный/ошибочный профиль не перезаписывает и не создает ложный нулевой базовый снимок.
2. **API и фронтенд-рендер (`tests/test_web_api.py`, `tests/test_web_endpoints.py`)**:
   - Проверить наличие `resource_deltas` в JSON-ответе эндпоинта Главной страницы (`/api/v1/state` или `/api/v1/profile`).
   - Проверить наличие 5 элементов дельт (`#res-*-delta`) в `web/static/index.html` внутри блока «Валюты и Ресурсы».
   - Runtime-тест через `node` для `formatResourceDelta` и `renderResourceDeltas` в `web/static/app.js`:
     - положительные числа форматируются как `+1 250` с классом `is-positive`;
     - отрицательные как `-340` с классом `is-negative`;
     - нули как `0` с классом `is-zero`;
     - заполняется tooltip `title`.
   - Актуализировать проверки версий кэша (`ASSET_VERSION` и `sw.js`).
3. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и полный прогон `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Baseline VPS и аудит текущих роутов/разметки Главной страницы**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Изучить текущую реализацию блока «Валюты и Ресурсы» в `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, а также поток обновления профиля в `core/state_hub.py`, `core/database.py` и `web/routes.py`.
- [ ] **Шаг 2. Реализация суточных снимков и расчета дельт на бэкенде (`core/database.py`, `core/state_hub.py`, `web/routes.py`)**:
  - Создать таблицу `daily_resource_snapshots` и методы фиксации базы/вычисления дельт по `MSK_TZ` (`Europe/Moscow`) с защитой от невалидных/пустых профилей.
  - Подключить автоматическую фоновую фиксацию базы в `core/state_hub.py` и отдачу `resource_deltas` в API Главной страницы в `web/routes.py`.
- [ ] **Шаг 3. Отображение дельт в блоке «Валюты и Ресурсы» (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)**:
  - Добавить элементы дельт для всех 5 ресурсов (`Папиросы`, `Сахар`, `Рубли`, `Бумага`, `Мыло`) с цветовой индикацией (`+` зеленый, `-` красный, `0` нейтральный), форматированием разрядов, tooltip и чистой мобильной/десктопной версткой.
- [ ] **Шаг 4. Cache-busting, автотесты и уборка временных файлов**:
  - Синхронно поднять `ASSET_VERSION` (`index.html`, `app.js`) и версию кэша SW (`sw.js`) на следующую версию выше текущей.
  - Добавить автотесты (БД, рестарт, смена суток по МСК, API и `node` runtime-тест рендера дельт) и прогнать `node --check` + полный `pytest -q tests/`.
  - Удалить временные скрипты в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 5. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ЖИВАЯ ВЕРИФИКАЦИЯ**:
  - Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Подтвердить быстрый старт `127.0.0.1:8085` (`<= 5s`), отдачу свежих версий статики на `https://zvezdoed.space/prison/`, наличие `resource_deltas` в живом API и записи в `daily_resource_snapshots` в БД VPS, отсутствие `Traceback` в `journalctl -u prisonbot.service -n 60` и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_state_hub.py tests/test_web_api.py tests/test_web_endpoints.py
python -m pytest -q tests/
```