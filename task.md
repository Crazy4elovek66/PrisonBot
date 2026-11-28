# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ 2 ОСТАВШИХСЯ ПАДЕНИЙ ТЕСТОВ В GITHUB ACTIONS CI (320/320 GREEN)

Ты выступаешь в роли Senior Python / DevOps разработчика на проекте PrisonBot.

**Анализ текущего состояния проекта:**
- После прошлого фикса в GitHub Actions CI (`ubuntu-latest`, Python 3.11) уже проходят **318 из 320 тестов**.
- Остались ровно **2 падения**, оба вызваны особенностями изоляции тестов в чистой Linux-среде без локальной БД:
  1. `tests/test_improvements_v2.py::test_boss_victory_notification_web_and_telegram_formatting` - `BossWorker` создается без параметра `db_engine`, поэтому в чистом CI без локального `storage/prison_bot.db` падает с `sqlite3.OperationalError: no such table: action_logs` и `no such table: notifications`, из-за чего `worker._notified_victory_keys` остается пустым `set()`.
  2. `tests/test_friend_outreach_worker.py::test_run_profile_enrichment_pass_and_429_backoff_and_coverage` - при добавлении кандидатов `6001` и `6002` подряд без явных значений `last_seen` / `total_damage` в Linux (микросекундная точность часов) `6002` получает чуть более свежую метку времени, сортировка по свежести ставит `6002` перед `6001`, в результате `authority = 90000` записывается в `6002`, а `6001` попадает на замоканный `RuntimeError("429 Too Many Requests")` и остается с `c1.authority == 0`.

Твоя задача - исправить оба теста (и проверить детерминированность сортировки в `core/database.py`), убедиться в отсутствии других тестов без `db_engine` и довести пакет `pytest` до гарантированных 100% в чистом Linux, чтобы следующий `git push` пользователя из VS Code впервые успешно провел автодеплой на VPS.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Изолировать `test_boss_victory_notification_web_and_telegram_formatting` (`tests/test_improvements_v2.py`)**:
   - Добавить фикстуру `tmp_path` в сигнатуру теста.
   - Создать временную SQLite БД через `get_engine(f"sqlite+aiosqlite:///{(tmp_path / 'boss_victory_notif.db').as_posix()}")`, вызвать `await init_db(engine)` и при необходимости создать тестовый `Account(id=1, ...)`.
   - Передать `db_engine=engine` в `BossWorker(...)`.
   - Корректно закрыть движок (`await engine.dispose()`) в `finally`.
2. **Сделать детерминированным `test_run_profile_enrichment_pass_and_429_backoff_and_coverage` (`tests/test_friend_outreach_worker.py`)**:
   - Проверить точный `order_by` в `get_candidates_needing_profile_enrichment()` (`core/database.py`).
   - В тесте явно задать для `6001` и `6002` одинаковые (или более высокий приоритет для `6001`, например фиксированный `last_seen` / `total_damage`) поля сортировки, чтобы на любой ОС (`Windows` и `Linux`) первым гарантированно выбирался `6001`, а вторым - `6002`.
   - Корректно закрыть `await engine.dispose()` в конце теста.
3. **Быстрый аудит остальных тестов на скрытую зависимость от локальной БД**:
   - Проверить `tests/test_improvements_v2.py` и остальные файлы в `tests/` на создание `BossWorker`, `PrisonWorker`, `SocialWorker`, `FriendOutreachWorker`, `RoutineWorker`, `AuthProvider` без передачи `db_engine=engine` в тестах, которые дергают методы с записью в SQLite.

---

## 2. КОНФИГУРАЦИЯ

### 2.1. Файлы для изменения
- `tests/test_improvements_v2.py` - изолировать `test_boss_victory_notification_web_and_telegram_formatting` с временной БД (`tmp_path`, `init_db`, `db_engine=engine`).
- `tests/test_friend_outreach_worker.py` - задать явные детерминированные поля сортировки (`last_seen`, `total_damage`) для `6001` и `6002` в `test_run_profile_enrichment_pass_and_429_backoff_and_coverage`.
- `core/database.py` - только при необходимости уточнить tie-breaker в `get_candidates_needing_profile_enrichment()`.

### 2.2. Ограничения
- **НЕ запускать ручной деплой на VPS** и не трогать боевые файлы на сервере - выкатку выполнит сам GitHub Actions после `git push` пользователя из VS Code.
- **НЕ удалять** `reference_archive/`, скрипты `deploy_*.py` и не изменять правила `.gitignore` для `storage/*.json`.

---

## 3. ЛОГИКА / АРХИТЕКТУРА

1. В `tests/test_improvements_v2.py::test_boss_victory_notification_web_and_telegram_formatting`:
   - использовать ту же схему создания временной БД, что и в `tests/test_boss_worker.py::test_boss_defeat_hp_cascade_all_cases` (`get_engine` -> `init_db` -> `Account` -> `BossWorker(..., db_engine=engine)` -> `finally: await engine.dispose()`);
   - убедиться, что `ActionLog` и `Notification` успешно записываются во временную БД, `boss_claim_sess_39` попадает в `worker._notified_victory_keys`, а уведомление в `sent_msgs` формируется корректно.
2. В `tests/test_friend_outreach_worker.py::test_run_profile_enrichment_pass_and_429_backoff_and_coverage`:
   - явно передать одинаковый `now_dt = datetime.utcnow()` (или `last_seen` для `6001` на 10 секунд свежее, чем для `6002`) и явный `total_damage`, чтобы `get_candidates_needing_profile_enrichment()` при любом разрешении таймера ОС (включая `ubuntu-latest`) всегда возвращал `[6001, 6002]`;
   - проверить, что `c1.authority == 90000`, `c1.obshak_type == "vor"`, `c1.brigade_name == "TopClan"`, а `6002` остается `"unknown"` после `429`.

---

## 4. ТЕСТИРОВАНИЕ

1. Проверить оба исправленных теста в изоляции (и убедиться, что тест в `test_improvements_v2.py` проходит даже при отсутствии/недоступности дефолтного `storage/prison_bot.db`).
2. Проверить синтаксис JS (`node --check web/static/app.js`, `node --check web/static/sw.js`).
3. Прогнать весь пакет `python -m pytest -q tests/` - ожидается `320 passed` (0 failed).

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

### Чеклист выполнения
- [ ] 1. Исправить `tests/test_improvements_v2.py::test_boss_victory_notification_web_and_telegram_formatting` - подключить временную БД через `tmp_path`, `init_db(engine)` и передать `db_engine=engine` в `BossWorker(...)`.
- [ ] 2. Исправить `tests/test_friend_outreach_worker.py::test_run_profile_enrichment_pass_and_429_backoff_and_coverage` - задать явные детерминированные значения `last_seen` / `total_damage` для `6001` и `6002` (и проверить `order_by` в `core/database.py::get_candidates_needing_profile_enrichment`).
- [ ] 3. Быстро проверить остальные тесты в `tests/` на отсутствие обращений к дефолтной БД без `db_engine`.
- [ ] 4. Запустить целевые тесты, `node --check` и полный `python -m pytest -q tests/`, убедиться в `0 failed`.
- [ ] 5. Проверить `git status` (убедиться, что в изменениях только нужные файлы и нет временного мусора) и сообщить пользователю, что можно делать **Фиксация + Push** в VS Code для запуска зеленого CI/CD автодеплоя.

### Команды проверки
```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest tests/test_friend_outreach_worker.py tests/test_improvements_v2.py -v
python -m pytest -q tests/
git status
```