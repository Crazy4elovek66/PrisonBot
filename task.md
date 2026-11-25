# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ДОРАБОТКА ЛОГИКИ ОПРЕДЕЛЕНИЯ И ОТОБРАЖЕНИЯ ОСТАВШЕГОСЯ HP БОССА ПРИ ПОРАЖЕНИИ (WEB + TELEGRAM) И ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack & Backend инженера (Python / AsyncIO / FastAPI / SQLite / Vanilla JS / Telegram Bot / Linux systemd). Твоя задача - провести аудит всей цепочки обработки поражения от босса по тайм-ауту (`client/api/boss.py` -> `workers/boss_worker.py` -> `core/state_hub.py` -> `core/database.py` -> `bot/notifier.py` -> `web/routes.py` -> `web/static/app.js`), устранить баг, из-за которого при поражении от босса и в веб-панели, и в Telegram отображается нулевой остаток здоровья (`Осталось HP: 0 / 1` и `0%` - как на скриншоте поражения от `Воркута (Пацанский)` в `13:27`), реализовать надежный каскад вычисления и сохранения реального оставшегося HP и максимального HP босса (включая устойчивость к сбросу поля боя сервером игры и перезапускам воркера), корректно оформлять уведомления в Web и Telegram (включая честный fallback для случаев, когда точный остаток действительно неизвестен), покрыть все сценарии автотестами и **обязательно задеплоить и верифицировать изменения на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Устранение ложного `Осталось HP: 0 / 1 (0%)` при поражении от босса в Web и Telegram**:
   - При поражении от босса (`Время боя вышло, босс не повержен`) босс физически не был добит - его реальный остаток HP строго больше `0`, а `max_hp` равен полному запасу здоровья выбранного босса в данном режиме (например, `Воркута` в режиме `Пацанский`), а не `1`.
   - Недопустимо, чтобы и в Telegram-уведомлении, и в ленте уведомлений веб-панели выводилось `0` / `0 / 1` (`0%`) из-за того, что игровой сервер после истечения таймера обнулил объект активного боя или не вернул поля `hp`/`max_hp` в ответе о завершении боя.
2. **Единый достоверный источник данных об остатке HP на момент поражения**:
   - Бэкенд обязан определять пару `(remaining_hp, max_hp)` по строгому приоритетному каскаду:
     1. Реальные поля результата боя с сервера игры (если сервер возвращает ненулевой остаток HP или суммарный урон рейда при известном `max_hp`).
     2. Последний зафиксированный живой снимок активного боя (`last_active_battle_snapshot`) для того же `(boss_id, mode)`, сохраненный в памяти воркера, `StateHub` и SQLite (чтобы данные не терялись даже при рестарте сервиса или при мгновенном сбросе боя на сервере игры в секунду истечения таймера).
     3. Каталог боссов (`storage/bosses_catalog.json` / метаданные боссов в `client/api/boss.py` и `core/models.py`) для восстановления точного `max_hp` по `(boss_id, mode)` и расчета `remaining_hp = max_hp - total_damage`, если известен суммарный урон.
3. **Честное и наглядное отображение в Web-интерфейсе и Telegram**:
   - При наличии валидных `remaining_hp > 0` и `max_hp > 1`:
     - В **Telegram** (`bot/notifier.py` / `workers/boss_worker.py`): показывать отформатированный остаток HP, полный запас HP и процент (например: `Осталось HP: 12 450 / 50 000 (24.9%)`, а при остатке `< 1%` - `<1%` или `0.1%`, а не `0%`), плюс нанесенный личный урон (если есть).
     - В **Web-уведомлениях** (`web/static/app.js` / `web/routes.py`): показывать `Осталось HP: 12 450 / 50 000`, процент справа и визуально заполненный красный/оранжевый прогресс-бар, пропорциональный оставшемуся HP (с минимальной видимой шириной при `remaining_hp > 0`, чтобы бар не выглядел пустым).
   - Если реальный остаток HP достоверно неизвестен (например, бот был выключен до конца боя и сервер игры не прислал ни остаток HP, ни общий урон, а также для старых уже сохраненных в БД записей с битыми `0 / 1` или `0 / 0`):
     - Никогда не показывать `Осталось HP: 0 / 1 (0%)` - выводить честный текст `Осталось HP: нет данных` (или `неизвестно`) без фейкового `0%` прогресс-бара.
4. **Автотесты и обязательный деплой на VPS**:
   - Покрыть юнит- и интеграционными тестами все ветки определения `remaining_hp` / `max_hp` (ответ сервера, кэш последнего живого снимка, восстановление после рестарта, вычисление через `total_damage`, отсутствие данных), форматирование Telegram-сообщения и рендер Web-уведомления.
   - Обновить cache-busting (если правилась статика `app.js`/`styles.css`/`index.html`/`sw.js`), задеплоить на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service` и подтвердить 0 рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Ключевые файлы проекта под аудит и доработку
- Игровой API и контракты боссов: `client/api/boss.py`, `docs/boss_and_render_contracts.md`, `reference_archive/pro_prison_bot/API_CONTRACTS.md`, `storage/bosses_catalog.json`.
- Воркер боссов, модели и хранилище состояния: `workers/boss_worker.py`, `core/models.py`, `core/state_hub.py`, `core/database.py`.
- Уведомления Telegram и Web API: `bot/notifier.py`, `web/routes.py`.
- Фронтенд уведомлений: `web/static/app.js`, `web/static/index.html`, `web/static/styles.css`, `web/static/sw.js`.
- Автотесты: `tests/test_boss_worker.py`, `tests/test_web_api.py`, `tests/test_web_endpoints.py`.
- Продакшен VPS: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), публичный URL `https://zvezdoed.space/prison/`.
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Диагностика первопричины `Осталось HP: 0 / 1` (код + логи VPS за `13:27`)
- Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
- Проверить логи `journalctl -u prisonbot.service` на VPS за период вокруг `13:27` (момент поражения от `Воркута (Пацанский)`), а также проверить саму запись этого уведомления в SQLite (`storage/prison_bot.db`) на VPS: какие именно сырые поля были записаны в `meta`/`data` уведомления и что вернул игровой сервер при финализации/опросе боя.
- Провести сквозной аудит кода:
  1. `client/api/boss.py` - какие поля возвращают методы проверки/завершения/получения награды боя (`get_battle`, `finish_battle`, `claim_reward`, `get_boss_info` и др.) при поражении по тайм-ауту, как парсятся `hp`, `current_hp`, `max_hp`, `health`, `max_health`, `boss_hp`, `total_damage`, `damage`.
  2. `workers/boss_worker.py` - в какой момент фиксируется поражение, откуда берутся `remaining_hp` и `max_hp` при формировании уведомления в БД и Telegram, почему `max_hp` схлопывается в `1` (вероятно, `max(max_hp, 1)` при `max_hp == 0`), и не перезаписывается ли последний живой снимок боя нулями до генерации уведомления о поражении.
  3. `core/state_hub.py` и `core/database.py` - сохраняется ли последнее живое состояние активного боя (`boss_id`, `mode`, `current_hp`, `max_hp`, `total_damage`, `personal_damage`, `updated_at`) так, чтобы пережить сброс ответа сервера и/или рестарт `prisonbot.service`.
  4. `web/routes.py`, `bot/notifier.py` и `web/static/app.js` - как сериализуются и рендерятся поля `remaining_hp`, `hp`, `max_hp`, `hp_percent` в карточке уведомления о поражении.

### 3.2. Надежный трекинг живого HP и каскад расчета при поражении (`workers/boss_worker.py`, `client/api/boss.py`, `core/state_hub.py`, `core/database.py`)
- **Сохранение последнего живого снимка боя (`last_live_battle_snapshot`)**:
  - При каждом успешном опросе активного боя (и после каждой атаки/обновления урона в `workers/boss_worker.py`, `web/routes.py` и `core/state_hub.py`), когда `max_hp > 1` и `current_hp > 0`, сохранять актуальный снимок `(boss_id, mode, current_hp, max_hp, total_damage, personal_damage, battle_id/started_at, updated_at)`:
    - в памяти `BossWorker` / `StateHub`;
    - и персистентно в SQLite (`core/database.py` - например, в таблице состояния/настроек или отдельной легкой записи), чтобы при перезапуске бота во время боя снимок не пропадал.
  - **Критично**: никогда не перезаписывать валидный `last_live_battle_snapshot` (с `current_hp > 0, max_hp > 1`) пустым или обнуленным ответом (`current_hp == 0` / `max_hp == 0`), когда бой переходит в статус `defeat` / `timeout` / `expired` / `missing`! Очищать снимок только после того, как уведомление о завершении боя (победе или поражении) уже сформировано и отправлено (либо при старте нового боя).
- **Единый helper разрешения HP при поражении (`resolve_defeat_boss_hp`)**:
  - Вынести чистую детерминированную функцию расчета `(remaining_hp: Optional[int], max_hp: Optional[int], hp_percent: Optional[float], hp_known: bool)` со следующим порядком приоритетов:
    1. **Сырой ответ сервера о поражении/результате боя**: если ответ содержит валидные `max_hp > 1` и `remaining_hp > 0` (и `remaining_hp <= max_hp`) - использовать их напрямую.
    2. **Расчет через каталог + суммарный урон из ответа сервера**: если `max_hp` не пришел или `<= 1`, восстановить `max_hp` из каталога боссов (`storage/bosses_catalog.json` / `client/api/boss.py`) по `(boss_id, mode)` (или имени босса + режиму). Если при этом в ответе сервера есть суммарный нанесенный урон `total_damage` (`0 <= total_damage < max_hp`), вычислить `remaining_hp = max_hp - total_damage`.
    3. **Последний живой снимок активного боя (`last_live_battle_snapshot`)**: если снимок совпадает по `(boss_id, mode)` (и актуален по времени боя) и содержит `current_hp > 0` и `max_hp > 1` - взять `(current_hp, max_hp)` оттуда (если в ответе поражения пришел более свежий `total_damage`, уточнить `remaining_hp = min(snapshot.current_hp, max(1, max_hp - total_damage))`, не давая уйти в `0` при поражении).
    4. **Защитный инвариант при поражении**:
       - При поражении `remaining_hp` **не может** быть `0` (если `0` - это невалидные/сброшенные данные, значит `hp_known = False`, `remaining_hp = None`).
       - `max_hp` **никогда** не подменяется на `1` для отображения (использовать реальный `max_hp` из каталога, а если и он неизвестен - `max_hp = None`, `hp_known = False`).
       - Процент считать как `round((remaining_hp / max_hp) * 100, 1)` (или с сохранением ненулевого минимума при `remaining_hp > 0`: например, `hp_percent = round(remaining_hp * 100 / max_hp, 1)`, а при форматировании если `remaining_hp > 0` и `hp_percent < 0.1`, выводить `<0.1%` / `<1%`, но не `0%`).

### 3.3. Единообразное отображение в Telegram (`workers/boss_worker.py`, `bot/notifier.py`) и Web (`web/routes.py`, `web/static/app.js`, `web/static/styles.css`)
- **Payload уведомления в БД (`core/database.py` / `workers/boss_worker.py`)**:
  - Сохранять структурированные поля в `meta` уведомления о поражении:
    - `remaining_hp` (`int | None`), `max_hp` (`int | None`), `hp_percent` (`float | None`), `hp_known` (`bool`), `personal_damage` (`int | None`, если известно).
  - Сохранить обратную совместимость ключей (`boss_hp` / `remaining_hp` / `max_hp`), чтобы существующие тесты и старые записи не ломались.
- **Telegram-уведомление (`workers/boss_worker.py`, `bot/notifier.py`)**:
  - При `hp_known == True`: форматировать числа с пробелами-разделителями разрядов (например: `❤️ Осталось HP: 12 450 / 50 000 (24.9%)`).
  - При `hp_known == False`: вместо `0 / 1 (0%)` выводить аккуратную строку `❤️ Осталось HP: нет данных` (если известен `max_hp` из каталога - можно указать `из 50 000`, но без фейкового `0`).
- **Web-уведомление (`web/static/app.js`, `web/routes.py`, `web/static/styles.css`)**:
  - В рендере карточки поражения от босса (`Поражение от босса: ...`):
    - Проверять валидность: `remaining_hp > 0 && max_hp > 1` (и `hp_known !== false`).
    - Если данные валидны - отображать `Осталось HP: <formatNumber(remaining_hp)> / <formatNumber(max_hp)>`, процент справа (`24.9%` или `<0.1%`, никогда не `0%` при `remaining_hp > 0`) и реально заполненный прогресс-бар шириной `Math.max(pct, 1)%` (в цвете поражения/остатка HP).
    - Если данные невалидны или это старая историческая запись из БД с `0 / 1` или `0 / 0` - НЕ рендерить `Осталось HP: 0 / 1` и `0%`, а показывать компактный текст `Осталось HP: нет данных` без пустого фейкового прогресс-бара.

### 3.4. Cache-busting, уборка и обязательный деплой на VPS
- Если менялась статика (`web/static/app.js`, `web/static/styles.css`, `web/static/index.html`), синхронно поднять `ASSET_VERSION` до `20261125_17` в `web/static/index.html` и `web/static/app.js` и имя кэша в `web/static/sw.js` до `prisonbot-assets-v12`.
- Удалить любые временные скрипты агента в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).
- Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую верификацию на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`, старт `127.0.0.1:8085` за `<= 5` секунд.
  2. Проверить через `curl` свежую статику (`20261125_17` / `prisonbot-assets-v12`) на `127.0.0.1:8085` и `https://zvezdoed.space/prison/`, а также ответ эндпоинта уведомлений `/api/v1/notifications`.
  3. Проверить `journalctl -u prisonbot.service -n 80 --no-pager` на отсутствие `Traceback`.
  4. Подтвердить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Расширить автотесты в `tests/test_boss_worker.py`, `tests/test_web_api.py` и `tests/test_web_endpoints.py`:

1. **Каскад определения оставшегося HP при поражении (`tests/test_boss_worker.py`)**:
   - **Кейс 1 (сервер прислал нули/пустой объект после таймаута)**: во время боя зафиксирован живой снимок `Воркута (Пацанский)` с `current_hp = 18500`, `max_hp = 50000`; при таймауте сервер вернул `hp = 0, max_hp = 0` (или `battle = None`). Уведомление в БД и сообщение в Telegram должны содержать `18 500 / 50 000` (`37%`), а НЕ `0 / 1 (0%)`.
   - **Кейс 2 (сервер вернул `total_damage` без `hp`/`max_hp`)**: `max_hp` берется из каталога боссов, `remaining_hp = max_hp - total_damage` рассчитывается точно.
   - **Кейс 3 (перезапуск воркера во время боя)**: живой снимок восстановлен из SQLite/хранилища и корректно использован при поражении.
   - **Кейс 4 (малый остаток HP, например `5 / 100 000`)**: процент не схлопывается в `0%` (выводится `<0.1%` / `<1%`).
   - **Кейс 5 (данных нет вообще - бот не видел бой и сервер не прислал HP)**: `hp_known = False`, `remaining_hp = None`, в Telegram и Web выводится `нет данных`, без `0 / 1` и `0%`.
2. **Web API и runtime-рендер карточки уведомления (`tests/test_web_api.py`, `tests/test_web_endpoints.py`)**:
   - Проверить сериализацию уведомления о поражении в `/api/v1/notifications`.
   - Через `node` прогнать рендер уведомления о поражении в `web/static/app.js` на трех кейсах: валидные `remaining_hp / max_hp`, малый остаток HP и битая/старая запись `0 / 1` (подтвердить отсутствие строки `0 / 1` и корректную ширину прогресс-бара).
   - Актуализировать проверки версий кэша (`20261125_17` / `prisonbot-assets-v12`).
3. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и полный прогон `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Диагностика первопричины (код + логи и БД VPS за `13:27`)**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Посмотреть логи `prisonbot.service` на VPS вокруг `13:27` и запись поражения `Воркута (Пацанский)` в SQLite, а также разобрать цепочку `client/api/boss.py` -> `workers/boss_worker.py` -> `core/state_hub.py` -> `core/database.py` -> `bot/notifier.py` -> `web/static/app.js`.
  - Зафиксировать точную причину, почему при поражении записалось и отобразилось `0 / 1 (0%)` в Web и `0` в Telegram.
- [ ] **Шаг 2. Реализация надежного трекинга живого HP и каскада `resolve_defeat_boss_hp`**:
  - Обеспечить сохранение последнего живого снимка активного боя (память + SQLite) без затирания нулями при таймауте.
  - Реализовать приоритетный расчет `(remaining_hp, max_hp, hp_percent, hp_known)` с использованием ответа сервера, последнего живого снимка и каталога боссов (`storage/bosses_catalog.json`), исключив подмену `max_hp` на `1` и вывод `0` при поражении.
- [ ] **Шаг 3. Обновление форматирования уведомлений в Telegram и Web (`workers/boss_worker.py`, `bot/notifier.py`, `web/routes.py`, `web/static/app.js`, `web/static/styles.css`)**:
  - Выводить реальные `remaining_hp / max_hp` и процент (с прогресс-баром в Web и читаемым форматированием чисел в Web и Telegram).
  - Реализовать честный fallback `нет данных` (включая корректную обработку старых записей `0 / 1` в БД).
- [ ] **Шаг 4. Cache-busting, автотесты и уборка временных файлов**:
  - При изменении статики поднять версии до `20261125_17` (`index.html`, `app.js`) и `prisonbot-assets-v12` (`sw.js`).
  - Добавить тесты в `tests/test_boss_worker.py`, `tests/test_web_api.py` и `tests/test_web_endpoints.py` (включая runtime-тест рендера карточки поражения через `node`).
  - Прогнать `node --check web/static/app.js`, `node --check web/static/sw.js` и полный `python -m pytest -q tests/`.
  - Удалить временные скрипты в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 5. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ЖИВАЯ ВЕРИФИКАЦИЯ**:
  - Загрузить все измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Проверить быстрый старт `127.0.0.1:8085` (`<= 5s`), отдачу свежих версий статики и `/api/v1/notifications`, отсутствие `Traceback` в `journalctl -u prisonbot.service -n 80` и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_boss_worker.py tests/test_web_api.py tests/test_web_endpoints.py
python -m pytest -q tests/
```