# Оглавление и навигатор по эталонному архиву `@pro_prison_bot`

Данный каталог содержит полный, 100% автономный офлайн-архив референсного бота **`@pro_prison_bot`** (`pro-prison-bot.003220.xyz`), полученный в рамках сессии реверс-инжиниринга при активной подписке.

Все секретные токены, сессионные данные, JWT и хеши санитизированы (`<REDACTED>`), что делает архив безопасным для хранения в репозитории и автономной работы любых ИИ-агентов без подключения к Chrome CDP или внешним серверам.

---

## 1. Структура архива

```text
reference_archive/pro_prison_bot/
├── INDEX.md                           # Данный навигационный документ
├── ARCHITECTURE_AND_FEATURES.md       # Полная архитектура, стек, авторизация и 17 модулей
├── API_CONTRACTS.md                   # 592 API-маршрута, схемы запросов/ответов, сопоставление с игрой
├── AUTOMATION_LOGIC.md                # 60 ключей автоматизации, формулы, очереди, кулдауны, рейды
├── UI_CATALOG.md                      # Каталог всех 30 экранов со ссылками на скриншоты и DOM
├── GAP_ANALYSIS.md                    # Сопоставление с текущим PrisonBot и бэклог фич
├── manifest.json                      # Машиночитаемый манифест всех 470 файлов архива
├── index.html                         # Оригинальный HTML-документ SPA приложения
├── next_data.json                     # Дегидрированное состояние Next.js (__NEXT_DATA__)
├── raw_js/                            # 178 оригинальных минифицированных JS-чанков и манифестов
│   ├── _buildManifest.js              # Манифест сборки Next.js (роуты и бандлы)
│   ├── _ssgManifest.js                # SSG-манифест
│   ├── _clientMiddlewareManifest.js   # Middleware-манифест
│   └── *.js                           # Все 178 JS-чанков приложения
├── parsed_js/                         # 178 отформатированных (beautified) JS-чанков для grep/поиска
│   └── *.js                           # Читаемый код с отступами и разбиением строк
├── css/                               # Стили приложения и дизайн-токены
│   ├── 2xz4eq8hsmei2.css              # Основной Tailwind/Next.js CSS-бандл (215 КБ)
│   ├── 3ppd9b3x4__1s.css              # Вспомогательные стили
│   ├── variables.json                 # 211 вычисленных CSS-переменных (:root) в формате JSON
│   └── variables.css                  # CSS-переменные в формате чистого CSS (:root { ... })
├── api_snapshots/                     # Сетевые контракты и снимки данных
│   ├── api_registry.json              # Реестр всех 592 эндпоинтов (/api/...) со статическим анализом
│   ├── storage_schema.json            # Схема localStorage, sessionStorage и IndexedDB
│   ├── network_summary.json           # Лог всех 52 перехваченных живых сетевых запросов
│   └── *.json                         # Санитизированные JSON-ответы бэкенда
├── ui_dom/                            # 30 структурированных DOM-снимков экранов
│   └── *.json                         # Заголовки, кнопки, инпуты, бейджи и состояния
├── screenshots/                       # 30 PNG-скриншотов высокого разрешения (600x800)
│   └── *.png                          # Скриншот каждого экрана, меню и модалки
└── assets/                            # 47 графических ассетов и иконок бота
    └── *                              # SVG, WebP, PNG иконки игры и интерфейса
```

---

## 2. Инвентарь экранов и скриншотов

В архиве сохранены 30 экранов, полностью покрывающих все разделы и модальные окна бота:

| № | Раздел / Экран | Скриншот | DOM-снимок | Описание экрана |
|---|---|---|---|---|
| 01 | Главная (HUD) | [01_home_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/01_home_main.png) | [01_home_main.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/01_home_main.json) | Профиль игрока, авторитет, энергия, борода, таланты, боссы |
| 02 | Новости и Рейды | [02_news_raids.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/02_news_raids.png) | [02_news_raids.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/02_news_raids.json) | Лента новостей, анонсы глобальных рейдов и объявлений |
| 03 | Комбо | [03_combo.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo.png) | [03_combo.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/03_combo.json) | Дневное комбо, статус подбора, банк комбо |
| 04 | Автокомбо | [03_combo_auto.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo_auto.png) | [03_combo_auto.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/03_combo_auto.json) | Настройки автоматического подбора и пробития комбо |
| 05 | Рейтинг комбо | [03_combo_rating.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo_rating.png) | [03_combo_rating.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/03_combo_rating.json) | Таблица лидеров по разгадыванию комбо |
| 06 | Боссы | [04_bosses.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/04_bosses.png) | [04_bosses.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/04_bosses.json) | Список боссов, таймеры вызова, выбор режима боя |
| 07 | Ходки | [05_prisons.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/05_prisons.png) | [05_prisons.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/05_prisons.json) | Тюрьмы, мастера, авто-энергия, дневной/ночной режим |
| 08 | Зарубы | [06_zaruby.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/06_zaruby.png) | [06_zaruby.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/06_zaruby.json) | PvP-зарубы, статистика побед, награды |
| 09 | Делюги | [07_delyugi.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/07_delyugi.png) | [07_delyugi.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/07_delyugi.json) | Сбор бизнесов, таланты, нычки, баулы |
| 10 | События | [08_events_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/08_events_main.png) | [08_events_main.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/08_events_main.json) | Ежемесячный календарь событий, прогресс за месяц |
| 11 | Меняла | [09_events_changer.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/09_events_changer.png) | [09_events_changer.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/09_events_changer.json) | Обмен валюты событий, открытие мешков менялы |
| 12 | Настройка событий | [10_events_settings.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/10_events_settings.png) | [10_events_settings.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/10_events_settings.json) | Автоматизация сбора наград событий и мешков |
| 13 | Барыга | [11_bariga.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/11_bariga.png) | [11_bariga.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/11_bariga.json) | Прокрутка у барыги, курсы обмена, авто-прокрутка |
| 14 | Друзья | [12_friends.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/12_friends.png) | [12_friends.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/12_friends.json) | Списочный состав корешей, поиск, фильтры |
| 15 | Бригада (Обзор) | [13_brigade.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade.png) | [13_brigade.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade.json) | Обзор бригады, общак, взносы килек |
| 16 | Бригада: Состав | [13_brigade_roster.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_roster.png) | [13_brigade_roster.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade_roster.json) | Ростер соклановцев, авторитет, взносы |
| 17 | Бригада: Лагеря | [13_brigade_camps.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_camps.png) | [13_brigade_camps.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade_camps.json) | Бригадные лагеря, захваты, авто-атака |
| 18 | Бригада: Сходняк | [13_brigade_shodnyak.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_shodnyak.png) | [13_brigade_shodnyak.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade_shodnyak.json) | Сходняки бригады, клетки, прокачка |
| 19 | Игры (Обзор) | [14_games_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/14_games_main.png) | [14_games_main.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/14_games_main.json) | Раздел мини-игр двора |
| 20 | Катала | [15_games_katala.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/15_games_katala.png) | [15_games_katala.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/15_games_katala.json) | Наперстки каталы, авто-сбор выигрышей |
| 21 | Покер | [16_games_poker.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/16_games_poker.png) | [16_games_poker.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/16_games_poker.json) | Тюремный покер, партии, ставки |
| 22 | Колесо фортуны | [17_games_wheel.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/17_games_wheel.png) | [17_games_wheel.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/17_games_wheel.json) | Колесо фортуны, сектора, бесплатные спины |
| 23 | Фартовый | [18_games_fartovy.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/18_games_fartovy.png) | [18_games_fartovy.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/18_games_fartovy.json) | Игра «Фартовый», ставки, коэффициенты |
| 24 | Кости | [19_games_dice.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/19_games_dice.png) | [19_games_dice.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/19_games_dice.json) | Броски костей, таблица результатов |
| 25 | Калькулятор урона | [20_damage_calc.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/20_damage_calc.png) | [20_damage_calc.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/20_damage_calc.json) | Расчет урона по боссам с учетом талантов и сетов |
| 26 | Тату и Шмот | [21_wardrobe.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/21_wardrobe.png) | [21_wardrobe.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/21_wardrobe.json) | Гардероб, наколки, слепой кольщик, хаты |
| 27 | Розыгрыши | [22_giveaways.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/22_giveaways.png) | [22_giveaways.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/22_giveaways.json) | Розыгрыши призов и подписок среди пользователей |
| 28 | Подписка | [23_subscription.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/23_subscription.png) | [23_subscription.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/23_subscription.json) | Тарифы, Telegram Stars, оплата, статус подписки |
| 29 | Настройки | [24_settings.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/24_settings.png) | [24_settings.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/24_settings.json) | Автоматизация, таймеры сна, лимиты, уведомления |
| 30 | Главная (Стартовая) | [01_home.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/01_home.png) | [01_home.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/01_home.json) | Стартовое состояние при первом открытии мини-аппа |

---

## 3. Инструкции по поиску в архиве для разработчиков и ИИ-агентов

### 3.1. Как найти логику конкретной функции или компонента
Все JS-чанки в каталоге `parsed_js/` отформатированы с отступами в 2 пробела и разбиты по строкам.
Для поиска по архиву используйте `grep` или скрипты Python:

```powershell
# Поиск компонента или настройки (например, autoDungeonAttack)
Get-ChildItem reference_archive\pro_prison_bot\parsed_js\*.js | Select-String -Pattern "autoDungeonAttack"

# Поиск формулы урона или расчета талантов
Get-ChildItem reference_archive\pro_prison_bot\parsed_js\*.js | Select-String -Pattern "calcDamage|talentDamage"

# Поиск констант таймеров и интервалов
Get-ChildItem reference_archive\pro_prison_bot\parsed_js\*.js | Select-String -Pattern "checkInterval|pollInterval"
```

### 3.2. Как найти эндпоинт и его параметры
В файле [api_snapshots/api_registry.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/api_snapshots/api_registry.json) содержится список всех 592 эндпоинтов с указанием JS-файлов, где они вызываются.
Для поиска эндпоинта по ключевому слову (например `shodnyak`):
```powershell
python -c "import json; reg = json.load(open('reference_archive/pro_prison_bot/api_snapshots/api_registry.json', encoding='utf-8')); print([r for r in reg if 'shodnyak' in r['route']])"
```

### 3.3. Как проверить стили и UI-токены
В файле [css/variables.css](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/css/variables.css) и [css/variables.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/css/variables.json) содержатся все 211 вычисленных CSS-переменных темы бота (цвета фона, текста, акцентов, скругления, тени).
