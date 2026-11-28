# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: НАСТРОЙКА АВТОМАТИЧЕСКОГО CI/CD ДЕПЛОЯ PRISONBOT ЧЕРЕЗ GITHUB ACTIONS (ТЕСТЫ + АВТООБНОВЛЕНИЕ VPS)

Ты выступаешь в роли Senior DevOps / Full-Stack разработчика (Python / FastAPI / GitHub Actions / Linux systemd / SSH) на проекте PrisonBot.

**Анализ текущего состояния проекта:**
- Боевой сервис работает на VPS `178.17.60.16` в директории `/opt/prisonbot` (`prisonbot.service`, статика `20261127_16`, SW `prisonbot-assets-v37`, 317 тестов зеленые).
- Локальный репозиторий подключен к GitHub (ветка `main`), данные подключения к VPS находятся в `.env_server` и `vps_audit.md`.
- Сейчас деплой выполняется вручную через одноразовые скрипты `deploy_*.py`, которые копируют отдельные файлы на сервер. Владелец хочет перейти на полноценный автоматический цикл: при каждом `git push` в `main` GitHub Actions сначала прогоняет все проверки и тесты в чистом Linux, и только если они прошли - сам подключается к VPS по SSH, делает резервную копию БД, обновляет код через `git pull`, при необходимости обновляет зависимости и перезапускает `prisonbot.service` с проверкой работоспособности.

**Твоя задача:**
1. Безопасно подготовить репозиторий (`.gitignore`, аудит трекинга секретов/БД) и создать готовый workflow `.github/workflows/deploy.yml`.
2. Полностью подготовить VPS `178.17.60.16:/opt/prisonbot` к работе через Git и SSH-деплой (бэкап БД и `.env`, генерация отдельных SSH-ключей для чтения репозитория и для входа GitHub Actions, безопасная привязка `/opt/prisonbot` к GitHub без остановки/потери данных).
3. Сохранить все готовые ключи и значения для ручного добавления на GitHub в локальный игнорируемый файл `github_setup_keys.txt` (который НИКОГДА не попадет в Git), покрыть конфигурацию автотестом и проверить, что боевой `prisonbot.service` продолжает стабильно работать.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

### 1.1. Безопасность секретов и данных БД (КРИТИЧНО)
- Провести аудит `.gitignore` и `git ls-files` в локальном репозитории:
  - убедиться, что `.env`, `.env_server`, `github_setup_keys.txt`, `storage/*.db`, `storage/*.db-wal`, `storage/*.db-shm`, `storage/*.session*`, `storage/asset_cache/`, `repomix-output*.xml`, `__pycache__/`, `.pytest_cache/` и временные отладочные скрипты/логи надежно закрыты в `.gitignore`;
  - проверить через `git ls-files`, не отслеживаются ли сейчас в Git файлы `.env`, `.env_server`, `storage/prison_bot.db`, `storage/prison.db`, `storage/user_session.session` (если какой-то из них случайно отслеживается - аккуратно убрать из индекса через `git rm --cached`, не удаляя сам файл с диска, чтобы при `git reset --hard` на VPS боевые данные никогда не затерлись).
- Ни один приватный SSH-ключ, пароль или токен не должен попадать в `.github/workflows/deploy.yml` или в коммит.

### 1.2. Автоматический пайплайн `.github/workflows/deploy.yml`
- Создать рабочий пайплайн GitHub Actions `.github/workflows/deploy.yml`, состоящий из двух последовательных джоб:
  1. **`test` (Проверка кода и автотесты на `ubuntu-latest`)**:
     - запуск при `push` в ветку `main` и по ручной кнопке `workflow_dispatch`;
     - настроить `paths-ignore`, чтобы правки только в `task.md`, `docs/**`, `screenshots/**`, `inf/**`, `ref/**`, `reference_archive/**`, `scratch/**`, `*.md` не запускали лишние перезапуски боевого сервера;
     - настроить `concurrency` (`group: deploy-prisonbot-main`, `cancel-in-progress: false`), чтобы два параллельных пуша не перебивали друг друга на сервере;
     - установить Python (версия как на VPS, например `3.11` / `3.12`) с кэшированием `pip`, установить Node.js (`20`), установить зависимости из `requirements.txt` (и `pytest`, если его нет в `requirements.txt`);
     - выполнить проверки:
       - `node --check web/static/app.js`
       - `node --check web/static/sw.js`
       - `python -m pytest -q tests/`
     - если хотя бы один тест упал - пайплайн немедленно завершается с ошибкой, шаг `deploy` НЕ запускается, боевой сервер остается на предыдущей стабильной версии.
  2. **`deploy` (Автоматическое обновление VPS, `needs: test`)**:
     - запускается строго после успешного прохождения `test`;
     - подключается к VPS через `appleboy/ssh-action@v1` с использованием секретов GitHub:
       - `host: ${{ secrets.VPS_HOST }}`
       - `username: ${{ secrets.VPS_USER }}`
       - `key: ${{ secrets.VPS_SSH_KEY }}`
     - выполняет на сервере в `/opt/prisonbot` безопасный и идемпотентный скрипт обновления (с `set -euo pipefail`):
       1. создает бэкап SQLite базы `/opt/prisonbot/storage/prison_bot.db` в `/opt/prisonbot/backups/` с датой и оставляет последние 5 бэкапов;
       2. забирает свежий код с GitHub (`git fetch origin main` и `git reset --hard origin/main`, не трогая неотслеживаемые `.env`, `storage/`, `venv/`, `backups/`);
       3. устанавливает/обновляет пакеты из `requirements.txt` в фактический `venv`, который использует `prisonbot.service` (определить точный путь к python/pip из `systemctl cat prisonbot.service`);
       4. перезапускает `prisonbot.service` (`systemctl restart prisonbot.service`);
       5. ждет 4 секунды и выполняет живой health-check (`systemctl is-active --quiet prisonbot.service` + HTTP-проверка локального порта `127.0.0.1:8085` и отсутствия падения процесса); если сервис не поднялся - выводит последние 40 строк `journalctl -u prisonbot.service` и завершает шаг с ненулевым кодом ошибки.

### 1.3. Полная подготовка VPS (`178.17.60.16:/opt/prisonbot`) агентом
- Проверить конфигурацию `prisonbot.service` (`systemctl cat prisonbot.service`) и текущий статус папки `/opt/prisonbot`.
- Сделать полную резервную копию `.env` и всей папки `/opt/prisonbot/storage` (`prison_bot.db*`, `user_session.session` и др.) в `/opt/prisonbot/backups/pre_cicd_backup_<timestamp>/`.
- Сгенерировать на VPS две отдельные SSH-пары (`ed25519`, без парольной фразы):
  1. **Ключ для чтения GitHub с VPS (Deploy Key)**: `/root/.ssh/prisonbot_github_deploy` (и `.pub`):
     - добавить `github.com` в `/root/.ssh/known_hosts` через `ssh-keyscan -H github.com`;
     - настроить для репозитория `/opt/prisonbot` явную команду `git config core.sshCommand "ssh -i /root/.ssh/prisonbot_github_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"`.
  2. **Ключ для входа GitHub Actions на VPS**: `/root/.ssh/prisonbot_gha_access` (и `.pub`):
     - аккуратно дописать публичную часть (`/root/.ssh/prisonbot_gha_access.pub`) в `/root/.ssh/authorized_keys` (проверив права `700` на `/root/.ssh` и `600` на `authorized_keys`, НЕ удаляя существующие ключи!).
- Подготовить директорию `/opt/prisonbot` как Git-репозиторий:
  - узнать точный URL репозитория из локального `git remote -v` и преобразовать в SSH-формат `git@github.com:<owner>/<repo>.git`;
  - если `/opt/prisonbot/.git` еще не существует - аккуратно выполнить `git init -b main` и `git remote add origin git@github.com:<owner>/<repo>.git` + настроить `core.sshCommand` (при этом НЕ удалять `.env`, `storage/`, `venv/` и не ломать работающий сервис).
  - проверить, что `prisonbot.service` активен (`active`) и соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`) не затронуты.

### 1.4. Удобная выдача ключей владельцу (`github_setup_keys.txt`)
- Создать локально в корне проекта временный файл `github_setup_keys.txt` (строго добавленный в `.gitignore`!) с аккуратно отформатированными и готовыми к копированию блоками:
  - `DEPLOY_KEY_PUB` - содержимое `/root/.ssh/prisonbot_github_deploy.pub` (для GitHub -> Settings -> Deploy keys);
  - `VPS_HOST` - IP сервера `178.17.60.16`;
  - `VPS_USER` - имя пользователя SSH (из `.env_server`, например `root`);
  - `VPS_SSH_KEY` - полное содержимое приватного ключа `/root/.ssh/prisonbot_gha_access` (от `-----BEGIN OPENSSH PRIVATE KEY-----` до `-----END OPENSSH PRIVATE KEY-----`).
- Проверить через `git status --ignored`, что `github_setup_keys.txt` точно игнорируется Git и не попадет в коммит.

---

## 2. КОНФИГУРАЦИЯ

### 2.1. Файлы для создания и изменения
- `.gitignore` - убедиться в защите `.env`, `.env_server`, `github_setup_keys.txt`, `storage/*.db*`, `storage/*.session*`, `storage/asset_cache/`, `repomix-output*.xml`, `__pycache__/`, `.pytest_cache/`.
- `.github/workflows/deploy.yml` (новый файл) - CI/CD пайплайн тестирования и автодеплоя на VPS.
- `tests/test_ci_workflow.py` (новый файл) - автотесты валидности `.github/workflows/deploy.yml` и правил `.gitignore`.
- `github_setup_keys.txt` (локальный временный игнорируемый файл) - ключи для разовой вставки на сайте GitHub.
- `requirements.txt` - проверить, все ли пакеты, нужные для запуска приложения и `pytest` в чистом Linux, присутствуют (при необходимости указать установку `pytest` / `pytest-asyncio` / `httpx` прямо в шаге CI, если они dev-зависимости).

### 2.2. Ограничения сохранности файлов и сервисов
- **НЕ удалять** `reference_archive/pro_prison_bot/`, `tests/test_reference_archive.py` и существующие скрипты `deploy_*.py`.
- **НЕ коммитить** и не выводить в публичные логи содержимое `.env` или `.env_server`.
- На VPS **НЕ затрагивать** соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`) и не удалять файлы из `/opt/prisonbot/storage/`.

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Проверка совместимости тестов с чистой средой Linux (GitHub Actions)
- Перед завершением проанализировать тесты в `tests/`: убедиться, что ни один тест не зависит от:
  - жестких Windows-путей (`d:\...` или `\` вместо `Path`);
  - наличия локального `.env`, `.env_server`, `storage/prison_bot.db` или `storage/user_session.session`;
  - реального сетевого доступа к VPS или игровому серверу.
- Если найдется тест, который в чистой среде Linux без `.env` / локальной БД может упасть - аккуратно поправить его (добавить мок/временную фикстуру), чтобы в GitHub Actions гарантированно проходили 100% тестов.

### 3.2. Идемпотентность скрипта деплоя на VPS
- Внутри `.github/workflows/deploy.yml` шаг деплоя должен корректно работать при каждом последующем пуше:
  ```bash
  set -euo pipefail
  cd /opt/prisonbot
  mkdir -p /opt/prisonbot/backups
  if [ -f /opt/prisonbot/storage/prison_bot.db ]; then
    cp /opt/prisonbot/storage/prison_bot.db "/opt/prisonbot/backups/prison_bot_$(date +%Y%m%d_%H%M%S).db"
    ls -1t /opt/prisonbot/backups/prison_bot_*.db | tail -n +6 | xargs -r rm -f
  fi
  git fetch origin main
  git reset --hard origin/main
  <ACTUAL_VENV_PIP> install -q -r requirements.txt
  systemctl restart prisonbot.service
  sleep 4
  systemctl is-active --quiet prisonbot.service
  curl -fsS [http://127.0.0.1:8085/prison/](http://127.0.0.1:8085/prison/) > /dev/null
  ```
- Заменить `<ACTUAL_VENV_PIP>` на реальный путь к `pip` из `systemctl cat prisonbot.service` (и проверить точный URL локального health-check эндпоинта на VPS).
- Убедиться, что если в `/opt/prisonbot` лежат старые локальные файлы-конфликты (например, неотслеживаемые файлы, которые теперь есть в Git), первый `git reset --hard` пройдет без ошибки `untracked working tree files would be overwritten by checkout` (для этого на этапе подготовки VPS аккуратно проверить пересечения или сделать бэкап и синхронизировать).

---

## 4. ТЕСТИРОВАНИЕ

Создать `tests/test_ci_workflow.py` и прогнать весь пакет тестов:
1. Проверка наличия и синтаксической валидности `.github/workflows/deploy.yml` (парсинг YAML, наличие джоб `test` и `deploy`, `needs: test`, триггер `push` в `main`, `workflow_dispatch`, игнорирование `task.md`, использование `secrets.VPS_HOST`, `secrets.VPS_USER`, `secrets.VPS_SSH_KEY`, отсутствие захардкоженных IP/паролей/приватных ключей).
2. Проверка `.gitignore`: содержит правила для `.env`, `.env_server`, `github_setup_keys.txt`, `*.db`, `*.session`.
3. Полный прогон `node --check web/static/app.js`, `node --check web/static/sw.js` и `python -m pytest -q tests/` (проверить, что все тесты проходят даже при запуске без локальных секретов).

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

### Чеклист выполнения
- [ ] 1. Проверить локальный `git remote -v`, `git ls-files` и `.gitignore` (убрать из индекса любые случайно отслеживаемые секреты/БД через `git rm --cached`, добавить `github_setup_keys.txt` в `.gitignore`).
- [ ] 2. Проинспектировать на VPS (`178.17.60.16`) `systemctl cat prisonbot.service` (точный путь к Python/venv и локальный порт), сделать бэкап `.env` и `storage/` в `/opt/prisonbot/backups/`.
- [ ] 3. Сгенерировать на VPS две SSH-пары (`prisonbot_github_deploy` для GitHub Deploy Key и `prisonbot_gha_access` для GitHub Actions), добавить `prisonbot_gha_access.pub` в `/root/.ssh/authorized_keys`, добавить `github.com` в `/root/.ssh/known_hosts`, привязать `/opt/prisonbot` к GitHub remote `origin` (`git@github.com:...`) с настроенным `core.sshCommand`.
- [ ] 4. Записать готовые значения (`DEPLOY_KEY_PUB`, `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`) в локальный игнорируемый файл `github_setup_keys.txt` и проверить через `git status`, что он не попадает в отслеживаемые файлы.
- [ ] 5. Создать `.github/workflows/deploy.yml` с джобами `test` и `deploy`, настроенным `paths-ignore`, автобэкапом БД на VPS и health-check после рестарта `prisonbot.service`.
- [ ] 6. Проверить совместимость всех тестов в `tests/` с чистым Linux (GitHub Actions), написать `tests/test_ci_workflow.py` и прогнать `node --check` + `python -m pytest -q tests/`.
- [ ] 7. Проверить состояние VPS после подготовки: `systemctl is-active prisonbot.service` (`active`), отсутствие ошибок в `journalctl -u prisonbot.service -n 50`, соседние контейнеры (`crayfish_omni_hub`, `autoclip_service`) не затронуты. В финальном отчете кратко подтвердить готовность и сообщить пользователю, что файл `github_setup_keys.txt` создан локально и готов для переноса ключей в GitHub.

### Команды проверки
```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest tests/test_ci_workflow.py -v
python -m pytest -q tests/
git status
```