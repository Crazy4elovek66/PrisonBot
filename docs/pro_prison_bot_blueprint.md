# Master Blueprint: Офлайн-база знаний и эталонный архив `@pro_prison_bot`

Данный документ является **главной точкой входа** для разработчиков и автономных ИИ-агентов. Он описывает эталонную архитектуру, алгоритмы и интерфейс бота **`@pro_prison_bot`** (`pro-prison-bot.003220.xyz`), сохраненные в локальном архиве `reference_archive/pro_prison_bot/`.

Архив получен методом глубокого реверс-инжиниринга сессии Chrome CDP при активной подписке. Все данные полностью санитизированы (Zero Secret Leaks) и готовы к автономному использованию без подключения к сети.

---

## 1. Карта документов архива

Вся подробная техническая документация структурирована по специализированным файлам:

1. [INDEX.md](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/INDEX.md) — Общий навигатор по каталогам архива, правила поиска компонентов и сводная таблица всех 30 экранов;
2. [ARCHITECTURE_AND_FEATURES.md](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ARCHITECTURE_AND_FEATURES.md) — Полный стек (Next.js Turbopack, Tailwind, Radix UI), жизненный цикл Telegram WebApp сессии, модель хранилищ и детальное описание всех 17 модулей;
3. [API_CONTRACTS.md](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/API_CONTRACTS.md) — Реестр 592 API-эндпоинтов, методы (GET/POST/SSE), параметры запросов, санитизированные схемы ответов и связь с оригинальным API «Тюряги»;
4. [AUTOMATION_LOGIC.md](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/AUTOMATION_LOGIC.md) — Спецификация всех 60 параметров автоматизации (`auto*`), алгоритмы планировщика, очереди, капы дамага в подземельях, фильтры корешей и формулы расчета урона;
5. [UI_CATALOG.md](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/UI_CATALOG.md) — Каталог всех 30 экранов, подвкладок и модалок со ссылками на скриншоты (`screenshots/*.png`) и DOM-деревья (`ui_dom/*.json`), дизайн-токены темы (:root);
6. [GAP_ANALYSIS.md](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/GAP_ANALYSIS.md) — Сравнительная матрица «`@pro_prison_bot` vs `PrisonBot`», статус модулей (Готово / Частично / Отсутствует) и приоритизированный бэклог внедрения (P0 / P1 / P2 / P3);
7. [manifest.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/manifest.json) — Машиночитаемый индекс всех 470 файлов архива с размерами и категориями.

---

## 2. Исходные файлы и артефакты дампа

- **Отформатированный JS-код:** [parsed_js/](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/parsed_js/) — 178 отформатированных файлов (beautified) для мгновенного поиска через `grep`;
- **Оригинальные чанки:** [raw_js/](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/raw_js/) — исходные минифицированные бандлы и манифесты (`_buildManifest.js`, `_ssgManifest.js`);
- **Стили и тема:** [css/variables.css](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/css/variables.css) — 211 вычисленных CSS-переменных темы бота;
- **Скриншоты экранов:** [screenshots/](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/) — 30 PNG-изображений высокого разрешения (600x800);
- **DOM-карты:** [ui_dom/](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/) — 30 структурированных JSON-снимков интерактивных элементов;
- **Сетевые контракты:** [api_snapshots/](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/api_snapshots/) — 52 живых ответа API, схема хранилищ [storage_schema.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/api_snapshots/storage_schema.json) и реестр [api_registry.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/api_snapshots/api_registry.json);
- **Графические ассеты:** [assets/](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/assets/) — 47 уникальных иконок игры и интерфейса.

---

## 3. Ключевые архитектурные выводы для PrisonBot

1. **SPA-маршрутизация через единый параметр `?v=2&tab=...`:**
   Вся навигация строится вокруг единого корневого документа и бокового меню-гамбургера с аккордеонами. Это предотвращает перезагрузку страницы в Telegram WebApp и обеспечивает плавный нативный UX.
2. **Многоуровневая автоматизация подземелий бригады (`autoDungeon*`):**
   Эталонный бот поддерживает пакетные удары (`autoDungeonAttackBatch`), жесткие лимиты дамага (`autoDungeonAttackDailyDamageCap`), контроль остатка ВПИ и автоматическую защиту лагерей при атаках противников.
3. **Реалтайм комбо-стрим через SSE (`/api/combo/auto-stream`):**
   Вместо медленного периодического опроса polling используется непрерывный поток событий (Server-Sent Events), позволяющий наносить комбо-удары в первые секунды после их отгадки сообществом.
4. **Умный фильтр входящих заявок в друзья:**
   Автоматический отсев кандидатов по числу талантов (`autoAddMinTalents`), строгости профиля и отсутствию в клановых черных списках.
