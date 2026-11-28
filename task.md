# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ПОЧИНКА 33 ПАДЕНИЙ ТЕСТОВ В GITHUB ACTIONS CI И ФИНАЛЬНЫЙ АУДИТ / ОЧИСТКА VPS ДЛЯ ПЕРВОГО АВТОДЕПЛОЯ

Ты выступаешь в роли Senior DevOps / Full-Stack разработчика (Python / FastAPI / SQLite / GitHub Actions / Linux systemd) на проекте PrisonBot.

**Анализ текущего состояния проекта и выявленные проблемы:**
- Пайплайн `.github/workflows/deploy.yml` уже подключен и успешно запускается при `push` в `main`.
- На чистом Linux-раннере GitHub Actions прошли 287 из 320 тестов, а **33 теста упали** строго по 5 конкретным причинам:
  1. **Отсутствие 3 статических JSON-справочников игры в Git (24 падения)**: правило игнорирования папки `storage/` скрыло не только БД и сессии, но и статические справочники `storage/bosses_catalog.json`, `storage/collections_catalog.json`, `storage/tattoo_clothing_cache.json`. В чистом CI каталог боссов оказался пустым (`0` вместо `58`), пропали 48 хат и бонусы вещей (`test_boss_worker.py`, `test_web_api.py`, `test_improvements_v2.py`, `test_drop_parser.py`, `test_wardrobe_api.py`, `test_raids_api.py`, `test_asset_cache.py`).
  2. **6 тестов в `tests/test_prison_worker.py` ходили в реальную БД**: при создании `AuthProvider(account_id=acc_id)` не передан `db_engine=engine`, из-за чего в CI без локальной БД возникает `sqlite3.OperationalError: no such table: sessions`.
  3. **Отсутствует `Pillow` (`PIL`) в окружении CI (1 падение)**: `tests/test_web_api.py::test_back_poworot_icon_integrity` падает с `ModuleNotFoundError: No module named 'PIL'`. Также нужно закрепить `greenlet` / `sqlalchemy[asyncio]` в `requirements.txt`.
  4. **Проверка `parsed_js/` в `tests/test_reference_archive.py::test_code_dump_completeness` (1 падение)**: папка `reference_archive/pro_prison_bot/parsed_js/` намеренно исключена из Git (чтобы не раздувать репозиторий), но тест жестко требует ее наличия.
  5. **Недетерминированный порядок выборки в SQLite на Linux (1 падение)**: в `tests/test_friend_outreach_worker.py::test_run_profile_enrichment_pass_and_429_backoff_and_coverage` при равных полях сортировки у `6001` и `6002` SQLite в Linux вернул первым `6002`, а не `6001`, из-за отсутствия вторичного ключа сортировки `user_id ASC`.
- **Дополнительно требуется финальная инспекция и уборка VPS (`178.17.60.16:/opt/prisonbot`)** перед первым реальным автодеплоем из GitHub Actions: проверить, что на сервере нет конфликтующих неотслеживаемых файлов, временного мусора от старых ручных деплоев, что Deploy Key реально работает с GitHub (`git fetch origin main`), и что первый `git reset --hard origin/main` пройдет чисто и безопасно для `.env`, `storage/` и `prisonbot.service`.

Твоя задача - исправить все 5 причин падения тестов в CI, провести инспекцию и безопасную уборку `/opt/prisonbot` на VPS, проверить готовность Git/SSH-связки на сервере и убедиться, что все тесты проходят на 100%.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

### 1.1. Исправление всех 5 причин падения тестов в GitHub Actions CI
1. **Включить 3 статических JSON-справочника в Git (`.gitignore`)**:
   - Проверить `.gitignore` и настроить исключения для `storage/` так, чтобы:
     - секреты, БД, сессии и тяжелый кэш картинок (`storage/*.db*`, `storage/*.session*`, `storage/asset_cache/`) оставались строго в `.gitignore`;
     - 3 статических справочника игры (`storage/bosses_catalog.json`, `storage/collections_catalog.json`, `storage/tattoo_clothing_cache.json`) были явно разрешены (`!storage/`, `!storage/bosses_catalog.json`, `!storage/collections_catalog.json`, `!storage/tattoo_clothing_cache.json`) и добавлены в индекс Git (`git add`).
   - Убедиться через `git status` и `git ls-files storage/`, что в Git попадают **только** эти 3 справочника и ни один `.db` / `.session` / `asset_cache` файл.
2. **Изолировать `tests/test_prison_worker.py` от реальной БД**:
   - Во всех 6 упавших тестах (`test_prison_worker_energy_drain_cycle`, `test_prison_worker_skip_low_energy`, `test_prison_worker_night_mode`, `test_prison_worker_single_hit_energy_drain`, `test_prison_worker_checkpoint_claim`, `test_prison_drain_all_energy_across_circle_completion`) передать `db_engine=engine` в `AuthProvider(account_id=acc_id, db_engine=engine)` (проверить остальные тесты в файле, чтобы ни один не создавал `AuthProvider` без `db_engine=engine`).
3. **Зафиксировать зависимости (`requirements.txt` и `.github/workflows/deploy.yml`)**:
   - Убедиться, что в `requirements.txt` присутствуют `greenlet` (или `sqlalchemy[asyncio]`) и все нужные рантайм-зависимости.
   - В `.github/workflows/deploy.yml` в шаге установки зависимостей для тестов добавить `pillow` (либо добавить `pillow` в `requirements.txt`), чтобы `from PIL import Image` гарантированно работал в CI.
4. **Адаптировать `tests/test_reference_archive.py::test_code_dump_completeness` под CI**:
   - В `test_code_dump_completeness` проверять наличие `raw_js` и `css` всегда, а `parsed_js` проверять только если директория присутствует (либо пропускать проверку `parsed_js` в CI через проверку `os.environ.get("GITHUB_ACTIONS")` / `if parsed_dir.exists():`), не удаляя сам тест и не добавляя тяжелый `parsed_js/` в Git.
5. **Детерминированная сортировка в `get_candidates_needing_profile_enrichment()` (`core/database.py`)**:
   - Добавить явный вторичный ключ сортировки `TrackedCandidate.user_id.asc()` (в конец `order_by(...)`), чтобы порядок выдачи кандидатов с одинаковым приоритетом был 100% одинаковым на Windows и Linux.

### 1.2. Финальная инспекция и безопасная очистка VPS (`178.17.60.16:/opt/prisonbot`)
- Подключиться к VPS `178.17.60.16` и провести полный аудит директории `/opt/prisonbot`:
  1. **Проверка Git и Deploy Key**:
     - выполнить `ssh -i /root/.ssh/prisonbot_github_deploy -o IdentitiesOnly=yes -T git@github.com` и `git fetch origin main` в `/opt/prisonbot` - убедиться, что VPS уже авторизован на GitHub и успешно видит ветку `main`;
     - проверить `git status` в `/opt/prisonbot` - выявить все неотслеживаемые (`untracked`) и измененные файлы.
  2. **Безопасная очистка лишнего мусора на VPS**:
     - удалить на VPS только очевидный временный мусор от прошлых ручных сессий/деплоев (например, временные `audit_*.py`, `test_guild_*.py`, `*.bak`, `__pycache__`, `.pytest_cache`, если они завалялись в `/opt/prisonbot`);
     - **СТРОГО НЕ ТРОГАТЬ** на VPS: `.env`, всю папку `storage/` (`prison_bot.db*`, `user_session.session`, `asset_cache/`), `venv/`, `backups/`, а также соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`);
     - проверить, не вызовет ли предстоящий `git reset --hard origin/main` конфликта с уже лежащими на VPS файлами `storage/bosses_catalog.json`, `storage/collections_catalog.json`, `storage/tattoo_clothing_cache.json` (если нужно - убедиться, что `git fetch` + `git reset --hard origin/main` в `deploy.yml` корректно их обновит без ошибки `untracked working tree files would be overwritten`).
  3. **Проверка сервиса и автобэкапа**:
     - проверить, что `prisonbot.service` активен (`active`), нет ошибок в `journalctl -u prisonbot.service -n 50`;
     - проверить наличие свежих данных фонового обогащения общака (`obshak_coverage`) и подтвердить в отчете, что фоновый сбор на VPS работает штатно.

---

## 2. КОНФИГУРАЦИЯ

### 2.1. Файлы для изменения
- `.gitignore` - разрешить `storage/bosses_catalog.json`, `storage/collections_catalog.json`, `storage/tattoo_clothing_cache.json`, сохранив жесткий игнор для `storage/*.db*`, `storage/*.session*`, `storage/asset_cache/`, `.env`, `.env_server`, `github_setup_keys.txt`.
- `requirements.txt` и/или `.github/workflows/deploy.yml` - закрепить `greenlet` и `pillow`.
- `core/database.py` - добавить `TrackedCandidate.user_id.asc()` в `order_by` метода `get_candidates_needing_profile_enrichment()`.
- `tests/test_prison_worker.py` - передать `db_engine=engine` в `AuthProvider(...)` во всех тестах файла.
- `tests/test_reference_archive.py` - сделать проверку `parsed_js/` совместимой с чистой средой CI (GitHub Actions).

### 2.2. Ограничения сохранности файлов и сервисов
- **НЕ удалять** локально `reference_archive/pro_prison_bot/`, `tests/test_reference_archive.py` и скрипты `deploy_*.py`.
- **НЕ коммитить** `.env`, `.env_server`, `storage/*.db*`, `storage/*.session*`, `github_setup_keys.txt`.
- На VPS **НЕ затрагивать** `.env`, `storage/`, `venv/`, `backups/`, `crayfish_omni_hub`, `autoclip_service`.

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Проверка чистоты CI-среды локально
- Проверить, что в `git ls-files storage/` присутствуют ровно 3 JSON-справочника:
  - `storage/bosses_catalog.json`
  - `storage/collections_catalog.json`
  - `storage/tattoo_clothing_cache.json`
- Проверить, что все тесты в `tests/` проходят без обращения к локальным `.db` / `.env` файлам (имитация чистого Linux-раннера GitHub Actions).

### 3.2. Безопасный `git reset --hard` на VPS при первом автодеплое
- Поскольку 3 JSON-файла в `storage/` раньше не отслеживались в Git, а на VPS они уже существуют на диске, при первом `git reset --hard origin/main` Git может выдать ошибку `untracked working tree files would be overwritten`.
- Чтобы первый и все последующие автодеплои из GitHub Actions прошли гарантированно без сбоев:
  - при инспекции VPS убедиться, что `/opt/prisonbot` синхронизирован с текущим `origin/main` (или аккуратно убрать конфликтные неотслеживаемые копии этих 3 JSON-файлов / забэкапить их перед `git reset --hard`), а остальные важные файлы (`.env`, `storage/prison_bot.db*`, `storage/user_session.session`, `storage/asset_cache/`) остались полностью нетронутыми.

---

## 4. ТЕСТИРОВАНИЕ

1. Прогнать точечно все ранее упавшие тестовые модули:
   - `tests/test_asset_cache.py`
   - `tests/test_boss_worker.py`
   - `tests/test_drop_parser.py`
   - `tests/test_friend_outreach_worker.py`
   - `tests/test_improvements_v2.py`
   - `tests/test_prison_worker.py`
   - `tests/test_raids_api.py`
   - `tests/test_reference_archive.py`
   - `tests/test_wardrobe_api.py`
   - `tests/test_web_api.py`
   - `tests/test_ci_workflow.py`
2. Прогнать синтаксис JS (`node --check web/static/app.js && node --check web/static/sw.js`) и полный пакет `python -m pytest -q tests/`.
3. Проверить `git status` и `git ls-files storage/` на отсутствие утечки секретов и БД.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

### Чеклист выполнения
- [ ] 1. Обновить `.gitignore`, чтобы 3 справочника (`storage/bosses_catalog.json`, `storage/collections_catalog.json`, `storage/tattoo_clothing_cache.json`) отслеживались в Git, а все `.db*`, `.session*`, `asset_cache/`, `.env*` оставались строго игнорируемыми; выполнить `git add` для этих 3 справочников и проверить `git ls-files storage/`.
- [ ] 2. Добавить `greenlet` и `pillow` в `requirements.txt` / `.github/workflows/deploy.yml`.
- [ ] 3. Передать `db_engine=engine` в `AuthProvider(...)` во всех тестах `tests/test_prison_worker.py`.
- [ ] 4. Добавить `TrackedCandidate.user_id.asc()` в `order_by` функции `get_candidates_needing_profile_enrichment()` в `core/database.py`.
- [ ] 5. Адаптировать `tests/test_reference_archive.py::test_code_dump_completeness` под отсутствие `parsed_js/` в GitHub Actions.
- [ ] 6. Прогнать `node --check` и `python -m pytest -q tests/` - убедиться, что все 320+ тестов зеленые.
- [ ] 7. Провести инспекцию и безопасную уборку VPS (`178.17.60.16:/opt/prisonbot`):
  - проверить работу Deploy Key (`ssh -i /root/.ssh/prisonbot_github_deploy -T git@github.com`) и `git fetch origin main`;
  - проверить `git status` в `/opt/prisonbot`, удалить только временный отладочный мусор (НЕ трогая `.env`, `storage/`, `venv/`, `backups/` и соседние контейнеры), устранить возможные конфликты `untracked` для первого `git reset --hard origin/main`;
  - проверить `systemctl is-active prisonbot.service`, логи `journalctl -u prisonbot.service -n 50` и актуальный `obshak_coverage` на VPS;
  - в финальном отчете кратко указать, что было почищено на VPS, подтвердить готовность к `git push` из VS Code и привести текущий статус `prisonbot.service` и `obshak_coverage`.

### Команды проверки
```bash
node --check web/static/app.js
node --check web/static/sw.js
git ls-files storage/
python -m pytest tests/test_prison_worker.py tests/test_friend_outreach_worker.py tests/test_reference_archive.py tests/test_ci_workflow.py -v
python -m pytest -q tests/
git status
```