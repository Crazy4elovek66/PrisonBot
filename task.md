# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: ОБНОВЛЕНИЕ ИКОНОК БОССОВ, НЫЧЕК, ХАТ И НАВИГАЦИОННОГО МЕНЮ ИЗ REFERENCE_ARCHIVE + CACHE-BUSTING И ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Full-Stack & Front-End инженера (Python / FastAPI / Vanilla JS / CSS / Service Worker / Linux systemd). Твоя задача - обновить и внедрить во всей веб-системе 6 качественных игровых иконок из `reference_archive/pro_prison_bot/assets/` (`боссы`, `нычки`, `хаты`, `комплекты / тату и шмот`, `делюги / подогрев`, `авторитет / кореша`), заменить ими старые файлы в `web/static/assets/icons/` и все соответствующие эмодзи в выпадающем/боковом меню навигации (`Боссы`, `Ходки и Мастера`, `Тату и Шмот`, `Делюги`, `Кореша`), в блоке активного боя с боссом, на нычках и на всех иконках хат, обеспечить единообразную верстку и надежный cache-busting (HTML + JS + Service Worker), покрыть изменения автотестами и **обязательно задеплоить и верифицировать побайтовую отдачу новых иконок на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`).

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Побайтовое обновление и добавление 6 целевых ассетов в `web/static/assets/icons/`**:
   - `reference_archive/pro_prison_bot/assets/PrisonV3_bosses_all_bosses.webp` -> `web/static/assets/icons/boss.webp`
   - `reference_archive/pro_prison_bot/assets/poker_hidesicon.webp` -> `web/static/assets/icons/stash.webp`
   - `reference_archive/pro_prison_bot/assets/PrisonV3_bosses_all_camerReward.webp` -> `web/static/assets/icons/room_reward.webp`
   - `reference_archive/pro_prison_bot/assets/PrisonV3_bosses_all_complectReward.webp` -> `web/static/assets/icons/complect.webp`
   - `reference_archive/pro_prison_bot/assets/podogrev_pagePodogrev.webp` -> `web/static/assets/icons/podogrev.webp`
   - `reference_archive/pro_prison_bot/assets/Avtoritet.webp` -> `web/static/assets/icons/authority.webp`[cite: 32]
2. **Точечная замена эмодзи и старых иконок по всей системе (строго по ТЗ)**:
   - **Боссы (`boss.webp`)**:
     - Поставить новую иконку `boss.webp` вместо emoji в **блоке активного боя с боссом** (заголовок/статус/карточка активного боя в `index.html` и динамическом рендере `app.js`).
     - Заменить emoji у пункта **`Боссы`** (сейчас `⚔️`) в выпадающем/боковом меню навигации (и мобильном, и десктопном меню, если есть дубли)[cite: 31].
   - **Нычки (`stash.webp`)**:
     - Поставить новую иконку `stash.webp` на **нычки** во всех местах системы (профиль/HUD, награды тюрем и боссов, уведомления, карточки обмена/барыги, каталог дропа), убрав любые оставшиеся текстовые эмодзи нычек в веб-UI.
   - **Хаты и «Ходки и Мастера» (`room_reward.webp`)**:
     - Заменить новой иконкой `room_reward.webp` **все иконки хат** в системе (награды хат у боссов, переключение/карточки хат в гардеробе/примерочной, уведомления о выпадении хаты, сводки прогресса).
     - Заменить emoji у пункта **`Ходки и Мастера`** (сейчас цепи) в выпадающем/боковом меню навигации на `room_reward.webp`[cite: 31].
   - **«Тату и Шмот» (`complect.webp`)**:
     - Заменить emoji у пункта **`Тату и Шмот`** в выпадающем/боковом меню навигации на `complect.webp`, а также убедиться, что везде для комплектов используется обновленный `complect.webp`[cite: 31].
   - **«Делюги» (`podogrev.webp`)**:
     - Заменить emoji у пункта **`Делюги`** (сейчас портфель `💼`) в выпадающем/боковом меню навигации на `podogrev.webp`[cite: 31].
   - **«Кореша» (`authority.webp`)**:
     - Заменить emoji у пункта **`Кореша`** (сейчас рукопожатие `🤝`) в выпадающем/боковом меню навигации на `authority.webp`, сохранив корректное отображение красного счетчика-бейджа справа (например `13`)[cite: 31].
3. **Аккуратная верстка навигационного меню и адаптивность**:
   - Иконки в выпадающем/боковом меню навигации должны иметь единый ровный размер и выравнивание по вертикали с текстом и соседними пунктами (`Главная`, `Рейды и Новости`, `Уведомления`, `Настройки (Мозг)`), не сжиматься (`flex-shrink: 0`), сохранять пропорции (`object-fit: contain`) и одинаково четко выглядеть как в активном, так и в неактивном состоянии пункта меню[cite: 31].
4. **Сброс кэша и обязательный деплой на VPS**:
   - Обновить версию cache-busting `?v=...` в `web/static/index.html`, `web/static/app.js` и имя кэша в `web/static/sw.js`, чтобы обновленные `.webp`-файлы и новый `podogrev.webp` мгновенно подтянулись у всех пользователей.
   - Задеплоить изменения на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`, проверить `SHA256` всех 6 ассетов через `127.0.0.1:8085` и `https://zvezdoed.space/prison/` и подтвердить 0 рестартов у `autoclip_service` и `crayfish_omni_hub`.

---

## 2. КОНФИГУРАЦИЯ

### Карта замены и добавления ассетов
- `reference_archive/pro_prison_bot/assets/PrisonV3_bosses_all_bosses.webp` -> `web/static/assets/icons/boss.webp`
- `reference_archive/pro_prison_bot/assets/poker_hidesicon.webp` -> `web/static/assets/icons/stash.webp`
- `reference_archive/pro_prison_bot/assets/PrisonV3_bosses_all_camerReward.webp` -> `web/static/assets/icons/room_reward.webp`
- `reference_archive/pro_prison_bot/assets/PrisonV3_bosses_all_complectReward.webp` -> `web/static/assets/icons/complect.webp`
- `reference_archive/pro_prison_bot/assets/podogrev_pagePodogrev.webp` -> `web/static/assets/icons/podogrev.webp`
- `reference_archive/pro_prison_bot/assets/Avtoritet.webp` -> `web/static/assets/icons/authority.webp`[cite: 32]

### Ключевые файлы проекта под аудит и доработку
- Ассеты и фронтенд: `web/static/assets/icons/`, `web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/static/sw.js`.
- Бэкенд и скрипты: `web/routes.py`, `core/drop_parser.py`, `scripts/fetch_game_icons.py`.
- Автотесты: `tests/test_asset_cache.py`, `tests/test_web_endpoints.py`, `tests/test_web_api.py`[cite: 32].
- Продакшен VPS: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`), публичный URL `https://zvezdoed.space/prison/`.
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`).

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Побайтовое копирование и проверка валидности 6 ассетов
- Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
- Проверить наличие, валидность заголовка (`RIFF....WEBP`) и размеры всех 6 исходных файлов в `reference_archive/pro_prison_bot/assets/`:
  - `PrisonV3_bosses_all_bosses.webp`
  - `poker_hidesicon.webp`
  - `PrisonV3_bosses_all_camerReward.webp`
  - `PrisonV3_bosses_all_complectReward.webp`
  - `podogrev_pagePodogrev.webp`
  - `Avtoritet.webp`[cite: 32]
- Выполнить побайтовое копирование в целевые пути `web/static/assets/icons/{boss,stash,room_reward,complect,podogrev,authority}.webp` и сверить `SHA256`-хеши с эталонами (6 из 6 должны совпадать на 100%).

### 3.2. Замена эмодзи в выпадающем/боковом меню навигации и блоке активного боя (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)
- **Навигационное меню (выпадающий список / сайдбар / мобильное меню)**:
  - Найти все определения пунктов меню в `web/static/index.html` и (если есть динамическая генерация/обновление заголовков/кнопок) в `web/static/app.js`.
  - Заменить эмодзи на `<img class="nav-icon-img" src="assets/icons/<file>.webp?v=<ASSET_VERSION>" alt="" loading="eager">` для 5 пунктов:
    1. `Боссы` -> `assets/icons/boss.webp`
    2. `Ходки и Мастера` -> `assets/icons/room_reward.webp`
    3. `Тату и Шмот` -> `assets/icons/complect.webp`
    4. `Делюги` -> `assets/icons/podogrev.webp`
    5. `Кореша` -> `assets/icons/authority.webp`
  - Добавить/уточнить стили для `.nav-icon-img` (и контейнера иконки пункта меню) в `web/static/styles.css`: фиксированная ширина/высота (`20px x 20px` или совпадающая с шириной колонки остальных иконок меню, чтобы все названия пунктов шли строго по одной вертикальной линии), `object-fit: contain`, `flex-shrink: 0`, `display: inline-block`, `vertical-align: middle`.
  - Убедиться, что при переключении активной вкладки, обновлении бейджей (`Кореша 13`, `Уведомления 8`) или выборе пункта в выпадающем мобильном меню иконка НЕ затирается через `textContent` и корректно отображается и в кнопке-триггере текущего раздела (если она отображает иконку активной вкладки)[cite: 31].
- **Блок активного боя с боссом**:
  - Найти в `web/static/index.html` и `web/static/app.js` рендер блока активного боя с боссом (баннер/карточка активного боя, заголовок статуса боя, мини-индикатор в шапке/дашборде, если есть).
  - Заменить эмодзи босса/боя (`⚔️`, `👹`, `💀` и т.п.) в блоке активного боя на `<img class="boss-battle-icon" src="assets/icons/boss.webp?v=<ASSET_VERSION>" alt="Босс">` (через единый helper `resolveAppAssetUrl` в `app.js`) с аккуратным размером и `object-fit: contain`.

### 3.3. Сквозной аудит иконок нычек (`stash.webp`) и всех иконок хат (`room_reward.webp`) по системе
- **Нычки (`stash.webp`)**:
  - Проверить по всему `web/static/index.html`, `web/static/app.js` и `web/routes.py` все места отображения нычек (`stash`, `nyachki`, `нычки`, `hides`, `poker_hides`, эмодзи нычек в веб-UI): профиль, дроп/награды с тюрем и боссов, уведомления, рутина, Барыга/обмен, мини-игры.
  - Везде в веб-интерфейсе гарантировать использование локальной `assets/icons/stash.webp` с cache-busting (без остаточных эмодзи или внешних URL; текстовые эмодзи в Telegram-боте `bot/` не трогать).
- **Все иконки хат (`room_reward.webp`)**:
  - Проверить по всему `web/static/index.html`, `web/static/app.js` и `web/routes.py` все места отображения иконок хат (награды хат на карточках боссов, вкладка/фильтр хат в Примерочной/Гардеробе, уведомления о получении хаты, статусы/эмодзи `🏠`/`🏚️`/`🚪` у хат в веб-UI).
  - Заменить все иконки/эмодзи хат на единую `assets/icons/room_reward.webp` с cache-busting (реальные полноразмерные фоны комнат `web/static/assets/rooms/room_*.webp` НЕ трогать - менять именно иконки хат!).
- Проверить `scripts/fetch_game_icons.py`: обновить маппинг/приоритет, чтобы повторный запуск скрипта не откатил `boss.webp`, `stash.webp`, `room_reward.webp`, `complect.webp`, `podogrev.webp`, `authority.webp` на старые версии[cite: 32].

### 3.4. Надежный cache-busting (HTML + JS + Service Worker) и уборка
- Инкрементировать `ASSET_VERSION` в `web/static/index.html` и `web/static/app.js` (например, `20261125_15`) и поднять имя кэша в `web/static/sw.js` (следующая версия `prisonbot-assets-v*`).
- Убедиться, что:
  1. Все новые и обновленные `<img src="assets/icons/...">` в `web/static/index.html` содержат новый `?v=<ASSET_VERSION>`.
  2. В `web/static/app.js` `resolveAppAssetUrl` автоматически и идемпотентно добавляет `?v=<ASSET_VERSION>` ко всем локальным `assets/icons/*.webp` (включая новый `podogrev.webp`), не ломая префикс `/prison/` и прокси `api/v1/assets/proxy?path=...`.
  3. В `web/static/sw.js` корректно отрабатывает очистка старых кэшей на `activate`.
- Удалить любые временные скрипты агента в корне локального репозитория (`diag_*.py`, `deploy_*.py`, `verify_*.py`, `fix_*.py` - не трогая `vps.py` и `vps_audit.md`).

### 3.5. Обязательный деплой на VPS и SHA256-верификация на проде
- Загрузить на VPS (`178.17.60.16`, `/opt/prisonbot`) все 6 иконок (`boss.webp`, `stash.webp`, `room_reward.webp`, `complect.webp`, `podogrev.webp`, `authority.webp`) и все измененные файлы (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`, `web/static/sw.js`, `scripts/fetch_game_icons.py` и др.).
- Перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую верификацию на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`, старт `127.0.0.1:8085` за `<= 5` секунд.
  2. Скачать все 6 иконок по `http://127.0.0.1:8085/assets/icons/{boss,stash,room_reward,complect,podogrev,authority}.webp?v=<ASSET_VERSION>` и через публичный URL `https://zvezdoed.space/prison/assets/icons/...`:
     - Подтвердить `HTTP 200`, `Content-Type: image/webp`.
     - Сверить `SHA256` каждого файла с эталоном из `reference_archive/pro_prison_bot/assets/` - должно быть 100% совпадение 6 из 6.
  3. Проверить отдачу свежего `index.html`, `app.js`, `styles.css` и `sw.js` на `https://zvezdoed.space/prison/` (наличие нового `ASSET_VERSION`, новых `<img>` в пунктах меню и блоке активного боя).
  4. Проверить `journalctl -u prisonbot.service -n 60 --no-pager` на отсутствие `Traceback`.
  5. Подтвердить неизменность `StartedAt` и статуса `running` у соседних Docker-контейнеров `autoclip_service` и `crayfish_omni_hub` (0 рестартов).

---

## 4. ТЕСТИРОВАНИЕ

Расширить автотесты в `tests/test_asset_cache.py` и `tests/test_web_endpoints.py`[cite: 32]:

1. **Побайтовая целостность 6 обновленных иконок (`tests/test_asset_cache.py`)**:
   - Для всех 6 файлов (`boss.webp`, `stash.webp`, `room_reward.webp`, `complect.webp`, `podogrev.webp`, `authority.webp`) проверить:
     - файл существует в `web/static/assets/icons/` и является валидным WebP (`RIFF....WEBP`);
     - `SHA256` файла совпадает с соответствующим эталоном в `reference_archive/pro_prison_bot/assets/` (если архив доступен).
2. **HTTP-отдача, верстка меню и блока активного боя (`tests/test_web_endpoints.py`)**:
   - `GET /assets/icons/{boss,stash,room_reward,complect,podogrev,authority}.webp` возвращает `200 OK`, `Content-Type: image/webp` и побайтово совпадает с локальными файлами.
   - В `web/static/index.html` пункты меню `Боссы`, `Ходки и Мастера`, `Тату и Шмот`, `Делюги`, `Кореша` используют соответствующие `<img ... assets/icons/*.webp>` без старых эмодзи, и в блоке активного боя с боссом используется `boss.webp`.
   - Версии `ASSET_VERSION` синхронизированы между `web/static/index.html`, `web/static/app.js` и `web/static/sw.js`.
   - Через `node -e` проверить `resolveAppAssetUrl` на `assets/icons/podogrev.webp` и остальных 5 иконках (идемпотентность `?v=...` и сохранение `/prison/` и `assets/proxy`).
3. **Синтаксис JS и полный прогон**:
   - `node --check web/static/app.js`, `node --check web/static/sw.js` и полный прогон `python -m pytest -q tests/`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Baseline VPS и копирование 6 иконок**:
  - Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
  - Проверить валидность (`RIFF....WEBP`) и `SHA256` исходников в `reference_archive/pro_prison_bot/assets/` и побайтово скопировать их в `web/static/assets/icons/{boss,stash,room_reward,complect,podogrev,authority}.webp`.
- [ ] **Шаг 2. Обновление меню навигации и блока активного боя (`web/static/index.html`, `web/static/app.js`, `web/static/styles.css`)**:
  - Заменить эмодзи на `<img>` в выпадающем/боковом меню (все экземпляры - десктоп и мобилка): `Боссы` -> `boss.webp`, `Ходки и Мастера` -> `room_reward.webp`, `Тату и Шмот` -> `complect.webp`, `Делюги` -> `podogrev.webp`, `Кореша` -> `authority.webp` (сохранив бейдж-счетчик у `Кореша`).
  - Заменить эмодзи на `boss.webp` в блоке активного боя с боссом.
  - Настроить единые размеры и выравнивание `.nav-icon-img` и иконки активного боя в `web/static/styles.css`.
- [ ] **Шаг 3. Сквозной аудит нычек (`stash.webp`), всех иконок хат (`room_reward.webp`) и `scripts/fetch_game_icons.py`**:
  - Убедиться, что во всех экранах веб-панели нычки рендерят `stash.webp`, а все иконки хат (не трогая фоны комнат `assets/rooms/`) рендерят `room_reward.webp`, без остаточных эмодзи и внешних URL.
  - Синхронизировать `scripts/fetch_game_icons.py`.
- [ ] **Шаг 4. Cache-busting (`web/static/index.html`, `web/static/app.js`, `web/static/sw.js`)**:
  - Поднять `ASSET_VERSION` в `index.html` и `app.js`, инкрементировать версию кэша в `sw.js`.
- [ ] **Шаг 5. Автотесты и уборка временных файлов**:
  - Обновить `tests/test_asset_cache.py` и `tests/test_web_endpoints.py`.
  - Прогнать `node --check web/static/app.js`, `node --check web/static/sw.js` и весь `python -m pytest -q tests/`.
  - Удалить временные скрипты в корне локального репозитория (не трогая `vps.py` и `vps_audit.md`).
- [ ] **Шаг 6. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И SHA256-ВЕРИФИКАЦИЯ НА ПРОДЕ**:
  - Загрузить все 6 иконок и измененные файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Проверить быстрый старт `127.0.0.1:8085` (`<= 5s`), скачать все 6 иконок с `127.0.0.1:8085` и `https://zvezdoed.space/prison/assets/icons/...`, подтвердить `HTTP 200`, `image/webp` и 100% совпадение `SHA256` с эталонами из `reference_archive`.
  - Проверить чистый `journalctl -u prisonbot.service -n 60` и 100% неизменность `StartedAt` у `autoclip_service` и `crayfish_omni_hub`.
  - Очистить локальные кэши `.pytest_cache` и `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
node --check web/static/sw.js
python -m pytest -v tests/test_asset_cache.py tests/test_web_endpoints.py tests/test_web_api.py
python -m pytest -q tests/
```