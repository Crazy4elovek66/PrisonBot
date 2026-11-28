# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ПОЛНАЯ ПЕРЕЗАПИСЬ ТАБЛИЦЫ МЕСЯЧНЫХ ДЕЛЮГ ПРИ СМЕНЕ МЕСЯЦА (ОЧИСТКА ПРОШЛЫХ МЕСЯЦЕВ В SQLITE) + ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Backend-разработчика (Python / FastAPI / Asyncio / SQLite) на проекте PrisonBot.

**Контекст:**
- В релизе `20261127_11` / `prisonbot-assets-v32` был реализован полный парсинг календаря «Месячных делюг» (`client/api/monthly.py`) и таблица `monthly_tasks_schedule` в `core/database.py`.
- Сейчас при переходе на новый месяц строки предыдущих месяцев (`2026-11`, `2026-10` и т.д.) остаются накапливаться в таблице `monthly_tasks_schedule`.
- Твоя задача - перевести `monthly_tasks_schedule` на режим **полной перезаписи при смене месяца**, чтобы в базе всегда хранился строго один актуальный месяц (`28-31` строка) без складирования старых месяцев, защитив при этом таблицу от случайной очистки при сетевых сбоях, обновить тесты и выгрузить изменения на VPS.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

- В таблице `monthly_tasks_schedule` в SQLite должен храниться **только текущий активный месяц** (`year_month`).
- При поступлении валидных данных за новый месяц (например, при переходе с `2026-11` на `2026-12`) все записи за любые другие месяцы (`year_month != current_year_month`) должны автоматически удаляться в рамках одной транзакции.
- **Защита от сетевых сбоев:** если игровой API вернул пустой список дней, ошибку или невалидный `year_month`, существующие записи в `monthly_tasks_schedule` **не должны удаляться**.
- **Сохранность внутри текущего месяца:** при повторных обновлениях внутри того же `year_month` уже сохраненные непустые формулировки (`task_title`, `task_description`) по-прежнему не должны затираться пустыми строками.
- **Важное организационное требование:** НЕ удалять временные скрипты деплоя (`deploy_release_*.py`) из корня локального репозитория - владелец оставляет их специально для прозрачного аудита действий агента.

---

## 2. КОНФИГУРАЦИЯ

### 2.1. Файлы для аудита и изменений
- `core/database.py` - метод `upsert_monthly_tasks()` (и при необходимости хелпер валидации `year_month` / `purge_old_monthly_tasks()`).
- `workers/routine_worker.py` и `web/routes.py` - проверить все точки вызова `upsert_monthly_tasks()`, убедиться, что туда передается валидный `year_month` (формат `YYYY-MM`) и непустой `schedule`, и что при сбое API очистка не вызывается.
- `tests/test_daily_actions.py`, `tests/test_web_api.py` (и любые другие тесты, проверяющие `monthly_tasks_schedule`) - обновить старые проверки изоляции нескольких месяцев и добавить тесты полной перезаписи и защиты от пустого ответа.
- Фронтенд (`web/static/index.html`, `app.js`, `styles.css`, `sw.js`) не меняется - версии статики `20261127_11` и SW `prisonbot-assets-v32` трогать не нужно.
- Инфраструктура VPS: `.env_server`, `vps_audit.md` (`178.17.60.16`, `/opt/prisonbot`, `prisonbot.service`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Транзакционная перезапись в `core/database.py`
В методе `upsert_monthly_tasks(self, year_month: str, days: list[dict])` реализовать следующий безопасный алгоритм:
1. Валидация входных данных до начала изменений в БД:
   - проверить, что `year_month` соответствует строго формату `YYYY-MM` (например, через regex `^\d{4}-\d{2}$`);
   - отфильтровать валидные записи в `days` (имеющие корректный `day_num` в диапазоне `1..31`);
   - если `year_month` невалиден или список валидных записей пуст - немедленно вернуть `0` (или `False`), **не выполняя `DELETE`** и не трогая таблицу.
2. В рамках одной атомарной SQLite-транзакции:
   - удалить все записи за другие месяцы:
     ```sql
     DELETE FROM monthly_tasks_schedule WHERE year_month != ?
     ```
   - выполнить `INSERT INTO monthly_tasks_schedule ... ON CONFLICT(year_month, day_num) DO UPDATE SET ...` для всех записей текущего месяца, сохраняя защиту от перезаписи непустых `task_title` / `task_description` пустыми значениями:
     ```sql
     task_title = CASE
       WHEN excluded.task_title != '' THEN excluded.task_title
       ELSE monthly_tasks_schedule.task_title
     END,
     task_description = CASE
       WHEN excluded.task_description != '' THEN excluded.task_description
       ELSE monthly_tasks_schedule.task_description
     END
     ```
   - зафиксировать транзакцию (`commit`).

### 3.2. Проверка точек вызова (`workers/routine_worker.py`, `web/routes.py`)
- Убедиться, что при ответе `GET /api/monthly/state` с ошибкой или пустым `schedule` не вызывается очистка БД и корректно работает fallback на сохраненный в SQLite актуальный месяц.
- Убедиться, что `get_monthly_tasks(year_month)` корректно возвращает данные только запрошенного месяца.

---

## 4. ТЕСТИРОВАНИЕ

Обновить и добавить unit-тесты в `tests/test_daily_actions.py` (и при необходимости в `tests/test_web_api.py`):
1. **Полная очистка старых месяцев при смене месяца:**
   - сохранить в БД записи за `2026-10` и/или `2026-11`;
   - вызвать `upsert_monthly_tasks("2026-12", [...])` с валидными днями декабря;
   - проверить через `get_monthly_tasks("2026-11")` (пусто), `get_monthly_tasks("2026-12")` (все новые записи) и прямой SQL-запрос `SELECT DISTINCT year_month FROM monthly_tasks_schedule` (в таблице строго `["2026-12"]`).
2. **Защита от очистки при пустых или битых данных:**
   - при существующих записях за `2026-11` вызвать `upsert_monthly_tasks("2026-12", [])` и `upsert_monthly_tasks("invalid", [{"day_num": 1, ...}])`;
   - проверить, что записи за `2026-11` остались нетронутыми.
3. **Защита от затирания текстов внутри текущего месяца:**
   - сохранить день `1` за `2026-12` с непустым `task_title`;
   - повторно вызвать `upsert_monthly_tasks("2026-12", [...])`, передав пустой `task_title` и обновленный `status="completed"`;
   - проверить, что статус обновился, а прежний `task_title` сохранился.
4. Проверить, что все ранее написанные тесты не конфликтуют с новым поведением, и прогнать весь пакет `pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

### Чеклист выполнения
- [ ] 1. Изучить текущую реализацию `upsert_monthly_tasks` / `get_monthly_tasks` в `core/database.py` и все места их вызова в `workers/routine_worker.py` и `web/routes.py`.
- [ ] 2. Внедрить атомарную очистку прошлых месяцев (`DELETE FROM monthly_tasks_schedule WHERE year_month != ?`) внутри `upsert_monthly_tasks()` с валидацией `year_month` (`YYYY-MM`) и непустого списка дней, сохранив защиту от затирания формулировок внутри текущего месяца.
- [ ] 3. Обновить/добавить тесты в `tests/test_daily_actions.py` (и смежных тестовых файлах) на полную перезапись при смене месяца, защиту от пустых/невалидных вызовов и сохранность текстов внутри текущего месяца.
- [ ] 4. Прогнать полный пакет тестов `python -m pytest -q tests/` и убедиться в отсутствии ошибок; очистить `.pytest_cache` / `__pycache__`, но **не удалять** скрипты `deploy_release_*.py` из корня проекта.
- [ ] 5. **ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS**: выгрузить обновленные файлы (`core/database.py` и др. измененные модули) на `178.17.60.16` (`/opt/prisonbot`), перезапустить `prisonbot.service`, не затрагивая соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`).
- [ ] 6. **ОБЯЗАТЕЛЬНАЯ ЖИВАЯ ПРОВЕРКА НА VPS**:
  - проверить `systemctl is-active prisonbot.service` и отсутствие traceback в `journalctl -u prisonbot.service -n 80`;
  - дернуть `GET /api/v1/monthly/state?force=true` локально на VPS (`HTTP 200`);
  - выполнить SQL-проверку в базе `/opt/prisonbot/storage/prison_bot.db` (`SELECT year_month, COUNT(*) FROM monthly_tasks_schedule GROUP BY year_month`) и подтвердить в отчете, что в таблице присутствует строго один актуальный месяц (`2026-11`, `30` записей).

### Команды проверки
```bash
python -m pytest tests/test_daily_actions.py tests/test_routine_worker.py tests/test_web_api.py -v
python -m pytest -q tests/
```