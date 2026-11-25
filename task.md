# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: УСТАНОВКА ФИРМЕННОГО ЛОГОТИПА БОТА И FAVICON В ВЕБ-ПАНЕЛИ + ДЕПЛОЙ НА VPS

Ты выступаешь в роли Senior Front-End & DevOps инженера (HTML / CSS / Vanilla JS / FastAPI / Pillow / Linux systemd). Твоя задача - заменить желтый квадрат с эмодзи цепи в блоке логотипа веб-панели на подготовленную иконку `web/static/assets/icons/bot_logo.png`, установить ее же в качестве иконки вкладки браузера (`favicon` + `apple-touch-icon`), оптимизировать размеры ассетов под UI и вкладку, покрыть отдачу автотестами и **обязательно задеплоить и верифицировать изменения на VPS (`178.17.60.16`, `prisonbot.service`)** без какого-либо влияния на соседние Docker-контейнеры (`autoclip_service`, `crayfish_omni_hub`)[cite: 45, 63, 64].

---

## 1. ЦЕЛЬ И БИЗНЕС-ТРЕБОВАНИЯ

1. **Замена логотипа в интерфейсе веб-панели**:
   - Заменить текущий желтый квадрат с эмодзи цепи рядом с заголовком `PrisonBot` / `Автономный клиент v3.0` в сайдбаре (а также во всех остальных местах, где дублируется этот значок бренда - мобильная шапка, экран входа и т.д.) на новый графический логотип с колючей проволокой из `web/static/assets/icons/bot_logo.png`[cite: 63, 64].
   - Убрать желтый фон у контейнера логотипа и аккуратно оформить его под темную тему панели (темная подложка, скругление, тонкая нейтральная рамка).
2. **Иконка вкладки браузера (`favicon`)**:
   - Установить новый логотип как основную иконку вкладки браузера (`favicon.ico`, `favicon-32x32.png`) и иконку для мобильных закладок (`apple-touch-icon.png`).
3. **Оптимизация веса ассетов**:
   - Исходник `web/static/assets/icons/bot_logo.png` сохранить без изменений, но для реального отображения в UI и вкладке сгенерировать легкие уменьшенные версии под нужные разрешения (чтобы браузер не загружал тяжелый полноразмерный PNG ради иконки `32x32` / `40x40`).
4. **Обязательный деплой на VPS**:
   - Обновить cache-busting `?v=...` в `web/static/index.html` (и версию кэша в `web/static/sw.js`, если используется), задеплоить изменения на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service` и проверить, что соседние контейнеры `autoclip_service` и `crayfish_omni_hub` не затрагивались[cite: 45, 60].

---

## 2. КОНФИГУРАЦИЯ

### Исходный файл и целевые модули
- Исходный логотип (уже добавлен в проект): `web/static/assets/icons/bot_logo.png` (квадрат `1:1`, металлическая колючая проволока на темно-графитовом фоне)[cite: 63].
- Файлы веб-интерфейса и роутинга: `web/static/index.html`, `web/static/styles.css`, `web/static/app.js`, `web/static/sw.js`, `web/app.py`[cite: 60].
- Тесты: `tests/test_web_endpoints.py` (или `tests/test_improvements_v2.py`)[cite: 60].
- Cache-busting: обновить параметр версии в `web/static/index.html` на `?v=20261125_08`.
- Продакшен VPS: `178.17.60.16` (через `vps.py` / SSH), `/opt/prisonbot`, `prisonbot.service` (`127.0.0.1:8085`).
- Соседние Docker-контейнеры (**НЕ ТРОГАТЬ**): `autoclip_service` (`8080`) и `crayfish_omni_hub` (`8081`)[cite: 45].

---

## 3. ЛОГИКА / АРХИТЕКТУРА

### 3.1. Генерация оптимизированных размеров из `bot_logo.png`
- Используя `Pillow` (одноразовой командой Python, не оставляя временных скриптов в корне репозитория), нарезать из `web/static/assets/icons/bot_logo.png` (с качественным ресемплингом `Image.Resampling.LANCZOS`) следующие файлы:
  - `web/static/assets/icons/bot_logo_128.webp` (`128x128`, quality `90`) - легкий и четкий ассет для отображения в шапке/сайдбаре (`36-44px` CSS с запасом под Retina 2x/3x).
  - `web/static/assets/icons/favicon-32x32.png` (`32x32`, PNG optimize) - для вкладки браузера.
  - `web/static/assets/icons/favicon-16x16.png` (`16x16`, PNG optimize) - для компактных вкладок.
  - `web/static/assets/icons/apple-touch-icon.png` (`180x180`, PNG optimize) - для iOS / Android закладок.
  - `web/static/favicon.ico` (мультиразмерный `.ico` с кадрами `16x16`, `32x32`, `48x48`) - для стандартных запросов `/favicon.ico`.
- Исходный `web/static/assets/icons/bot_logo.png` оставить нетронутым.

### 3.2. Замена блока логотипа в сайдбаре и UI (`web/static/index.html`, `web/static/styles.css`)
- Найти в `web/static/index.html` (и проверить `web/static/app.js`) блок логотипа рядом с `PrisonBot` / `Автономный клиент v3.0`, где сейчас отрисован желтый квадрат с эмодзи цепи (`⛓` / `⛓️`)[cite: 64], а также все остальные места с этим значком бренда (например, мобильная верхняя панель или модалка входа).
- Заменить текстовый эмодзи на изображение с относительным путем (строго в том же стиле, что и остальные `assets/icons/...`, чтобы корректно работать под префиксом `/prison/` за Nginx):

```html
<img src="assets/icons/bot_logo_128.webp?v=20261125_08" alt="PrisonBot" class="brand-logo-img" width="40" height="40">
```

- Обновить стили контейнера логотипа и класса `.brand-logo-img` в `web/static/styles.css`:
  - Убрать желтый фон (`background` / `linear-gradient`) у контейнера иконки бренда.
  - Задать аккуратную темную рамку и пропорции: `background: #111316; border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 10px; overflow: hidden; padding: 0; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);`.
  - Для `.brand-logo-img`: `width: 100%; height: 100%; object-fit: cover; display: block;`.
  - Проверить отображение и на десктопе, и на мобильном вьюпорте (иконка ровно центрирована, не искажается, не съезжает).

### 3.3. Установка Favicon и проверка роутинга (`web/static/index.html`, `web/app.py`, `web/static/sw.js`)
- В `<head>` файла `web/static/index.html` удалить старые `<link rel="icon" ...>` / `<link rel="shortcut icon" ...>` (включая возможные inline SVG data-URI с эмодзи) и подключить новые иконки относительными путями с cache-busting:

```html
<link rel="icon" type="image/png" sizes="32x32" href="assets/icons/favicon-32x32.png?v=20261125_08">
<link rel="icon" type="image/png" sizes="16x16" href="assets/icons/favicon-16x16.png?v=20261125_08">
<link rel="icon" href="favicon.ico?v=20261125_08" sizes="any">
<link rel="apple-touch-icon" sizes="180x180" href="assets/icons/apple-touch-icon.png?v=20261125_08">
```

- Проверить `web/app.py` (и при наличии `web/routes.py`): убедиться, что `/favicon.ico`, `/assets/icons/favicon-32x32.png`, `/assets/icons/bot_logo_128.webp` и `/assets/icons/apple-touch-icon.png` гарантированно отдаются с `HTTP 200` и правильным `Content-Type` (если нужен явный `@app.get("/favicon.ico")` -> вернуть `FileResponse` на `web/static/favicon.ico`).
- Проверить `web/static/sw.js`: инкрементировать имя/версию кэша (если есть), чтобы Service Worker сбросил старый `index.html` и старую иконку.

### 3.4. Обязательный деплой на VPS и живая верификация
- Снять baseline `StartedAt` контейнеров `autoclip_service` и `crayfish_omni_hub` на VPS.
- Загрузить на VPS (`178.17.60.16`, `/opt/prisonbot`) все новые и измененные файлы:
  - `web/static/assets/icons/bot_logo.png`
  - `web/static/assets/icons/bot_logo_128.webp`
  - `web/static/assets/icons/favicon-32x32.png`
  - `web/static/assets/icons/favicon-16x16.png`
  - `web/static/assets/icons/apple-touch-icon.png`
  - `web/static/favicon.ico`
  - `web/static/index.html`, `web/static/styles.css`, `web/static/sw.js`, `web/app.py` (если менялся)
- Перезапустить `systemctl restart prisonbot.service`.
- Выполнить живую проверку на VPS:
  1. `systemctl is-active prisonbot.service` -> `active`.
  2. `curl -sI http://127.0.0.1:8085/favicon.ico`, `curl -sI http://127.0.0.1:8085/assets/icons/favicon-32x32.png`, `curl -sI http://127.0.0.1:8085/assets/icons/bot_logo_128.webp` -> все `200 OK`.
  3. `curl -s http://127.0.0.1:8085/ | grep -E "bot_logo_128|favicon-32x32|20261125_08"` -> подтвердить свежий HTML.
  4. Проверить через публичный/Nginx URL `/prison/assets/icons/bot_logo_128.webp` и `/prison/assets/icons/favicon-32x32.png` -> `200 OK`.
  5. Проверить неизменность `StartedAt` и статуса `running` у `autoclip_service` и `crayfish_omni_hub` (0 рестартов)[cite: 45].

---

## 4. ТЕСТИРОВАНИЕ

Добавить или расширить автотесты в `tests/test_web_endpoints.py`:
1. `GET /` возвращает `200 OK`, содержит ссылки на `favicon-32x32.png`, `favicon.ico`, `apple-touch-icon.png` и `bot_logo_128.webp`, и не содержит старый эмодзи цепи в блоке логотипа.
2. Запросы к `/favicon.ico`, `/assets/icons/favicon-32x32.png`, `/assets/icons/bot_logo_128.webp`, `/assets/icons/apple-touch-icon.png` возвращают `200 OK` с непустым телом и корректным MIME-типом (`image/x-icon` или `image/vnd.microsoft.icon`, `image/png`, `image/webp`).
3. Проверить синтаксис JS (`node --check web/static/app.js`) и прогнать весь пакет `pytest`.

---

## 5. ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ АГЕНТА

- [ ] **Шаг 1. Подготовка иконок из `web/static/assets/icons/bot_logo.png`**:
  - Сгенерировать через Pillow `bot_logo_128.webp`, `favicon-32x32.png`, `favicon-16x16.png`, `apple-touch-icon.png` и `web/static/favicon.ico`, сохранив исходник `bot_logo.png`.
- [ ] **Шаг 2. Обновление верстки, стилей и фавикона (`web/static/index.html`, `web/static/styles.css`, `web/static/sw.js`, `web/app.py`)**:
  - Заменить желтый блок с эмодзи цепи на новый логотип во всех местах бренда (сайдбар, мобильная шапка и т.д.), убрать желтый фон контейнера.
  - Прописать `<link rel="icon">` и `<link rel="apple-touch-icon">` в `<head>`, обновить `?v=20261125_08` и кэш `sw.js`.
  - Убедиться, что `/favicon.ico` и все новые иконки корректно отдаются FastAPI.
- [ ] **Шаг 3. Автотесты и проверка**:
  - Добавить тесты отдачи нового логотипа и фавикона в `tests/test_web_endpoints.py`.
  - Прогнать `node --check web/static/app.js` и `python -m pytest -q tests/`.
- [ ] **Шаг 4. ОБЯЗАТЕЛЬНЫЙ ДЕПЛОЙ НА VPS И ЖИВАЯ ВЕРИФИКАЦИЯ**:
  - Снять baseline `autoclip_service` и `crayfish_omni_hub` (`StartedAt`).
  - Загрузить измененные и новые файлы на VPS (`178.17.60.16`, `/opt/prisonbot`), перезапустить `prisonbot.service`.
  - Проверить `systemctl is-active prisonbot.service`, `200 OK` на все новые ассеты и свежий `index.html`, а также 0 рестартов у соседних Docker-контейнеров.
  - Убедиться в чистоте корня локального репозитория (без временных `.py` скриптов) и очистить `.pytest_cache` / `__pycache__`.

### Команды верификации

```bash
node --check web/static/app.js
python -m pytest -v tests/test_web_endpoints.py
python -m pytest -q tests/
```