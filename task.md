# ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ЧАСТЬ 2 ИЗ 2): СТАТЫ РАДАРА (АВТОРИТЕТ + 3 ОРУЖИЯ), ФИКС ИКОНКИ РАЗВОРОТА, РЕВИЗИЯ НОВЫХ ЭЛЕМЕНТОВ UI «КОРЕША» И КОМПЛЕКСНАЯ ОПТИМИЗАЦИЯ СКОРОСТИ

Ты выступаешь в роли Senior Full-Stack Python & Frontend разработчика. Твоя задача - исправить отображение характеристик игроков в Радаре активных дамагеров (реальные авторитет и уровень, убрать бицуху, добавить урон всех трех видов оружия), починить битую иконку стрелочек разворота персонажа в Примерочной, провести полную ревизию и восстановить живое отображение всех новых элементов интерфейса (включая счетчик друзей, дельту за 24 часа, таблицу конверсии и аудит на вкладке «Кореша»), а также выполнить системную оптимизацию скорости работы бэкенда, SQLite и фронтенда.

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Исправление статов игроков в Радаре активных дамагеров (`#sec-raids`):**
   - Полностью убрать отображение **бицухи** (`💪 0`) из карточек игроков Радара (игра не отдает чужую бицуху в открытом API).
   - Устранить баг с `Ур. 1` и `👑 0` у игроков из `weekly-top` и бригад: отображать **реальный Авторитет** (`/static/assets/icons/authority.webp`) и корректно рассчитанный **Уровень** (`Ур. N`).
   - Добавить в каждую карточку игрока Радара показатели **урона всех трех видов оружия** с оригинальными иконками игры:
     - **Яд** (`/static/assets/icons/poison.webp`);
     - **Самопал** (`/static/assets/icons/gunshot.webp`);
     - **Финка** (`/static/assets/icons/knife.webp`).
   - Обеспечить кэшируемое автообогащение отображаемых игроков Радара (TTL 24ч в `TrackedCandidate`), чтобы статы загружались быстро и не создавали лишних повторных запросов к `/api/player/view/{userId}`.
2. **Исправление битой иконки стрелочек разворота в Примерочной:**
   - Выяснить и устранить причину, по которой кнопка `#btn-fitting-rotate` отображается как битая картинка с текстом `Разверн...`.
   - Проверить файл `web/static/assets/icons/back_poworot.webp` (целостность, размер, формат, права/путь) и атрибуты `<img>` в `index.html` / `app.js`. Если файл поврежден или пустой - восстановить корректный ассет (из кэша/CDN игры или четкую валидную иконку желтых круговых стрелок) и подтвердить загрузку (`complete === true && naturalWidth > 0`) в живом браузере.
3. **Полная ревизия и восстановление отображения всех новых элементов в веб-интерфейсе:**
   - Выяснить, почему в браузере на вкладке **«Кореша» (`#sec-friends`)** не видны новые элементы (счетчик `Кореша: N`, цветная дельта за 24ч `(+N)/(-N)/(0)`, таблица конверсии источников, переключатель режима фильтра `Все пороги (И)` / `Любой порог (ИЛИ)`, блок «Аудит урона и чистка корешей»), а также проверить все новые элементы на вкладке `#sec-raids`.
   - Устранить все найденные причины:
     - кэширование старых `app.js` / `styles.css` / `index.html` браузером -> внедрить в `web/app.py` заголовки `Cache-Control: no-cache, must-revalidate` для HTML/JS/CSS и автоматическое версионирование статики `?v=<mtime>`;
     - пропущенные вызовы `loadFriendsSummary()` / `loadFriendsAudit()` при открытии вкладки или несовпадающие ID/селекторы в DOM;
     - отсутствие первого снимка `FriendsCountSnapshot` в БД -> в `GET /api/v1/friends/summary` автоматически запрашивать актуальное число друзей и создавать первичный снимок на лету, если снимков еще нет, чтобы `Кореша: N` и `Дельта 24ч` отображались сразу при первом открытии.
4. **Комплексная оптимизация скорости всей системы (Backend + SQLite + Frontend):**
   - **Backend & Сеть (`web/app.py`, `web/routes.py`, `core/database.py`):**
     - подключить `GZipMiddleware(minimum_size=500)` для сжатия JSON, JS и CSS на 70-85%;
     - настроить длинное кэширование (`Cache-Control: public, max-age=86400`) для неизменяемых иконок и комнат в `/static/assets/*`;
     - внедрить `_SingleFlightCache` (TTL 3-15 сек + `asyncio.Lock` на ключ для дедупликации параллельных запросов к игровому серверу + мгновенная инвалидация после любых `POST/PATCH/DELETE` мутаций);
     - распараллелить все оставшиеся последовательные вызовы к внешнему API в `/api/v1/live/*`, `/api/v1/friends/*`, `/api/v1/raids/*` через `asyncio.gather()`;
     - добавить SQLite PRAGMA-настройки (`busy_timeout=5000`, `cache_size=-16000`, `temp_store=MEMORY`) при инициализации файловой БД.
   - **Frontend (`web/static/app.js`):**
     - внедрить **Stale-While-Revalidate (SWR)** кэш (`Map` + `sessionStorage`) для мгновенного (`0 мс`) переключения между вкладками с тихим фоновым обновлением;
     - на старте загружать только HUD/конфиг + текущую активную вкладку (убрать лишние стартовые запросы скрытых разделов);
     - приостанавливать фоновые `setInterval`-поллинги, когда вкладка браузера свернута (`document.hidden` / `visibilitychange`);
     - добавить `loading="lazy" decoding="async"` на списки изображений и избегать полной перерисовки DOM, если полученные JSON-данные не изменились.

---

## 2. КОНФИГУРАЦИЯ

Обновляемые файлы проекта:

```text
PrisonBot/
├── core/
│   └── database.py                       # SQLite PRAGMA-оптимизации (busy_timeout=5000, cache_size=-16000, temp_store=MEMORY)
├── client/
│   └── api/
│       └── raids.py                      # Возврат authority, level, poisonDamage, gunshotDamage, knifeDamage в get_active_players_radar + быстрое кэшируемое обогащение (24ч TTL)
├── web/
│   ├── app.py                            # GZipMiddleware, дифференцированные заголовки Cache-Control (no-cache для HTML/JS/CSS, max-age=86400 для /static/assets/*), автоматическая подстановка ?v=<mtime> в index.html
│   ├── routes.py                         # _SingleFlightCache с авто-инвалидацией, параллельный asyncio.gather(), автоинициализация FriendsCountSnapshot в GET /api/v1/friends/summary, отдача 3-х оружейных статов и authority в GET /api/v1/raids/active-players
│   └── static/
│       ├── assets/icons/back_poworot.webp # Проверка целостности и восстановление валидного изображения стрелок разворота
│       ├── index.html                    # Проверка всех контейнеров и ID на #sec-friends и #sec-raids, версионированные ссылки на styles.css и app.js
│       ├── styles.css                    # Стили компактных оружейных бейджей (Яд/Самопал/Финка) и авторитета в Радаре, проверка стилей плашки друзей и кнопки #btn-fitting-rotate
│       └── app.js                        # Обновление renderRadarPlayers (без бицухи, реальный авторитет + 3 оружия), фикс загрузки #friends (счетчик + дельта 24ч + конверсия + аудит), SWR-кэш, lazy-load вкладок, visibilitychange пауза поллингов и пропуск лишних перерисовок
└── tests/
    ├── test_raids_api.py                 # Тесты возврата authority, level, poisonDamage, gunshotDamage, knifeDamage и автообогащения кандидатов в Радаре
    └── test_web_api.py                   # Тесты /api/v1/friends/summary (первичный снимок + delta24h), GZipMiddleware, Cache-Control заголовков, _SingleFlightCache и валидности back_poworot.webp
```

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Диагностика перед внесением правок
1. Проверить живой ответ `GET /api/player/view/{userId}` для 1-2 игроков из `weekly-top` (например `9000000000179416`), чтобы точно подтвердить ключи JSON, по которым сервер отдает `authority`, `level` и `weaponDamage` (`poison`, `gunshot`, `knife`) или `combatStats`.
2. Проверить бинарный файл `web/static/assets/icons/back_poworot.webp` (сигнатура `RIFF....WEBP`, размеры) и все места использования `back_poworot` в `index.html`, `styles.css`, `app.js`.
3. Открыть текущий `http://127.0.0.1:8080/#friends` в Chrome через `chrome-devtools` MCP и зафиксировать точную причину отсутствия счетчика друзей и дельты за 24ч (ошибка в Console, старый кэш JS/HTML, пустой ответ API или ошибка DOM-привязки).

### 3.2. Статы игроков Радара (`client/api/raids.py`, `web/routes.py`, `web/static/app.js`)
1. В `RaidsAPI.get_active_players_radar(...)`:
   - возвращать для каждого кандидата поля: `authority`, `level` (вычисленный через `calculate_level_from_authority(authority)`, если `level == 0`), `poisonDamage`, `gunshotDamage`, `knifeDamage`;
   - если у кандидатов из видимой выборки (`limit`) `enriched_at is None` или старше 24 часов (или `authority == 0` и оружейные статы по нулям), вызывать `enrich_candidates_batch(..., max_enrich=min(limit, 25))` с точным разбором полей из Шага 3.1 и сохранять результат в `TrackedCandidate` (так повторные открытия Радара отдаются мгновенно из SQLite без единого запроса к `/api/player/view/{userId}`).
2. В `renderRadarPlayers()` (`web/static/app.js`):
   - **полностью удалить** вывод бицухи (`💪`);
   - вывести уровень `Ур. N` (если `level > 0`), **Авторитет** с `/static/assets/icons/authority.webp` и форматированным числом (`1.2кк` / `450к`);
   - вывести три компактных бейджа оружейного урона:
     - Яд: `<img src="/static/assets/icons/poison.webp"> ${poisonDamage}`
     - Самопал: `<img src="/static/assets/icons/gunshot.webp"> ${gunshotDamage}`
     - Финка: `<img src="/static/assets/icons/knife.webp"> ${knifeDamage}`
   - сохранить все существующие бейджи (`Score`, источник, `🔥 Активен`, название бригады, кнопка `+ В друзья`).

### 3.3. Починка иконки разворота и ревизия UI «Кореша» (`web/static/`, `web/routes.py`)
1. **Иконка `#btn-fitting-rotate`:**
   - убедиться, что `web/static/assets/icons/back_poworot.webp` является валидным изображением (при повреждении восстановить из `storage/asset_cache/` / CDN игры `https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/...` или сгенерировать четкую прозрачную желтую иконку круговых стрелок);
   - проверить путь `src="/static/assets/icons/back_poworot.webp"` в `index.html` и `app.js`, убедиться, что кнопка имеет прозрачный фон и контрастную `drop-shadow` обводку.
2. **Вкладка «Кореша» (`#sec-friends`):**
   - в `GET /api/v1/friends/summary`: если `friends_count_snapshots` пуста, синхронно получить текущее число друзей через `social_api.get_all_friend_ids()`, записать первый снимок в БД и вернуть `{"friendsCount": N, "delta24h": 0, "snapshotAt": ..., "conversionBySource": [...]}`;
   - проверить в `index.html` и `app.js` отображение:
     - плашки `Кореша: N` и цветной дельты `(+N)` / `(-N)` / `(0)` с тултипом времени замера;
     - таблицы конверсии источников;
     - сегментного переключателя `Все пороги (И)` / `Любой порог (ИЛИ)`;
     - блока «Аудит урона и чистка корешей» (`Топ помощников (7д)` / `Неактивные (кик)`, белый список, предпросмотр, удаление).

### 3.4. Системная оптимизация скорости (`web/app.py`, `web/routes.py`, `core/database.py`, `web/static/app.js`)
1. **Middleware и версионирование статики (`web/app.py`):**
   - добавить `app.add_middleware(GZipMiddleware, minimum_size=500)`;
   - добавить HTTP-middleware кэширования:
     - для `/` и `*.html`, `*.js`, `*.css` -> `Cache-Control: no-cache, must-revalidate`;
     - для `/static/assets/*` -> `Cache-Control: public, max-age=86400`;
   - при отдаче `/` (`index.html`) автоматически подставлять `?v=<max_mtime>` к `styles.css` и `app.js` (чтобы браузер гарантированно подхватывал обновления после каждого перезапуска сервера).
2. **Single-Flight TTL-кэш (`web/routes.py`):**
   - реализовать класс `_SingleFlightCache`:
     - хранит `(expires_at, value)` и `asyncio.Lock` по ключу;
     - предотвращает дублирующие параллельные запросы к `oldprison-prod.luckygem.online` при одновременных вызовах с фронта;
     - применяет короткие TTL: `profile` (5с), `boss` (3с), `prisons` (5с), `friends_summary` (15с), `wardrobe_overview` (30с);
     - предоставляет `invalidate(*prefixes)` и автоматически сбрасывает затронутые ключи после любого мутирующего `POST /api/v1/actions/*` или `PATCH /api/v1/config`.
3. **SQLite PRAGMAs (`core/database.py`):**
   - при инициализации файловой БД выставлять `PRAGMA busy_timeout=5000; PRAGMA cache_size=-16000; PRAGMA temp_store=MEMORY;` в дополнение к `WAL` и `synchronous=NORMAL`.
4. **Оптимизация фронтенда (`web/static/app.js`):**
   - добавить обертку `fetchWithSWR(cacheKey, fetcher, onData)` для ключевых вкладок (`home`, `bosses`, `prisons`, `friends`, `raids`): мгновенный рендер из кэша при клике по меню + фоновое обновление;
   - на `DOMContentLoaded` загружать только HUD/конфиг и данные **текущей активной вкладки**;
   - добавить обработчик `visibilitychange`: ставить на паузу фоновые таймеры (пинг, автообновление), когда `document.hidden === true`, и мягко обновлять активную вкладку при возвращении;
   - добавить `loading="lazy" decoding="async"` на списки изображений и сравнение хеша/JSON перед тяжелой перерисовкой списков.

---

## 4. ТЕСТИРОВАНИЕ

1. Дополнить `tests/test_raids_api.py`:
   - Тест `get_active_players_radar`: проверяет наличие и корректные значения `authority`, `level`, `poisonDamage`, `gunshotDamage`, `knifeDamage` и автообогащение кандидатов с сохранением `enriched_at` (повторный вызов не дергает `get_player_view` повторно).
2. Дополнить `tests/test_web_api.py`:
   - Тест `GET /api/v1/friends/summary`: на пустой таблице `friends_count_snapshots` возвращает реальный `friendsCount > 0`, создает первичный снимок и корректно считает `delta24h`.
   - Тест `web/app.py`: проверка `GZip` сжатия (`Accept-Encoding: gzip`), заголовков `Cache-Control` (`no-cache` для `/static/app.js` и `max-age=86400` для `/static/assets/icons/...`) и версионирования `?v=` в `/`.
   - Тест `_SingleFlightCache`: два параллельных запроса вызывают внешнюю корутину ровно 1 раз; после мутирующего действия кэш сбрасывается.
   - Тест целостности `web/static/assets/icons/back_poworot.webp` (существует, непустой, валидный формат изображения).
3. **Обязательная живая визуальная проверка в Chrome (`http://127.0.0.1:8080`) через `chrome-devtools` MCP:**
   - **Вкладка `#raids` -> «Радар»:** скриншот и проверка DOM - у игроков отображаются реальный **Авторитет** и **Уровень** (не `Ур. 1` и `👑 0`), **нет бицухи** и отображены **3 оружейных показателя** (Яд, Самопал, Финка).
   - **Вкладка `#wardrobe` -> Примерочная:** открыть Примерочную, проверить через `evaluate_script` и скриншот, что у `#btn-fitting-rotate img` значения `complete === true && naturalWidth > 0`, нет битой картинки и клик переворачивает персонажа на спину и обратно.
   - **Вкладка `#friends` («Кореша»):** скриншот и проверка DOM - видны счетчик друзей (`Кореша: N`), дельта за 24ч, таблица конверсии, переключатель `И / ИЛИ` и блок «Аудит урона и чистка корешей».
   - **Проверка оптимизации и чистоты:** подтвердить в Network наличие `content-encoding: gzip`, версий `?v=`, мгновенное переключение между уже открытыми вкладками за счет SWR, 0 JS-ошибок в Console и 0 битых ресурсов (`status >= 400`) в Network.
4. Прогон полного набора автотестов:
   ```bash
   python -m pytest -v tests/
   ```

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

Выполняй задачи последовательно, отмечая прогресс:

- [ ] **Шаг 1:** Выполнить диагностику: 1) проверить реальные ключи `authority` / `level` / `weaponDamage` в живом ответе `GET /api/player/view/{userId}`, 2) проверить целостность `web/static/assets/icons/back_poworot.webp` и его URL в HTML/JS, 3) открыть `http://127.0.0.1:8080/#friends` в Chrome через `chrome-devtools` MCP и зафиксировать точную причину отсутствия счетчика друзей и новых блоков.
- [ ] **Шаг 2:** Обновить `client/api/raids.py` и `web/routes.py` для возврата реальных `authority`, `level`, `poisonDamage`, `gunshotDamage`, `knifeDamage` в Радаре (с 24ч кэшем обогащения в `TrackedCandidate`) и гарантированной инициализации `FriendsCountSnapshot` в `GET /api/v1/friends/summary`.
- [ ] **Шаг 3:** Восстановить/исправить `web/static/assets/icons/back_poworot.webp` и его привязку в `#btn-fitting-rotate`.
- [ ] **Шаг 4:** Внедрить бэкенд-оптимизации: SQLite PRAGMAs в `core/database.py`, `GZipMiddleware` + дифференцированные `Cache-Control` + авто-версионирование `?v=` для `index.html` в `web/app.py`, а также `_SingleFlightCache` с авто-инвалидацией и `asyncio.gather()` в `web/routes.py`.
- [ ] **Шаг 5:** Обновить фронтенд (`web/static/index.html`, `styles.css`, `app.js`): переработать карточки Радара (убрать бицуху, показать реальный авторитет и 3 оружия), починить отображение всех новых элементов на `#friends` (счетчик, дельта 24ч, конверсия, фильтр `И / ИЛИ`, аудит/чистка), внедрить SWR-кэш, lazy-load вкладок, `visibilitychange` паузу поллингов и `loading="lazy" decoding="async"`.
- [ ] **Шаг 6:** Написать и прогнать тесты в `tests/test_raids_api.py` и `tests/test_web_api.py`, удалить любые временные файлы и выполнить полный прогон:
  ```bash
  python -m pytest -v tests/
  ```
- [ ] **Шаг 7:** Выполнить обязательную живую визуальную проверку в Chrome (`http://127.0.0.1:8080`) через `chrome-devtools` MCP со скриншотами `#raids` (Радар), `#wardrobe` (Примерочная + `#btn-fitting-rotate`), `#friends` (счетчик друзей, дельта 24ч, аудит), проверкой GZip/SWR и 0 ошибок в Console и Network.