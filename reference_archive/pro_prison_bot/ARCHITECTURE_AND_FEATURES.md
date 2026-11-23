# Архитектура, технологии и функциональные модули `@pro_prison_bot`

Документ представляет собой системный архитектурный разбор фронтенда, бэкенда и игровой интеграции референсного бота **`@pro_prison_bot`** (`pro-prison-bot.003220.xyz`), основанный на 100% дампе его исходных JS-чанков (`parsed_js/`), сетевых контрактах (`api_snapshots/`) и исследовании пользовательского интерфейса (`screenshots/`, `ui_dom/`).

---

## 1. Технологический стек

### 1.1. Фронтенд
- **Фреймворк:** Next.js (версия App Router / Pages с бандлером **Turbopack**). Build ID: `FmH16ITs5FViI3gHxEMSK`.
- **UI-библиотека:** React 18/19, Radix UI Primitives (компоненты `@radix-ui/react-dialog`, `@radix-ui/react-accordion`, `@radix-ui/react-tabs`, `@radix-ui/react-tooltip`, `@radix-ui/react-dropdown-menu`).
- **Стилизация:** Tailwind CSS со специализированной темной темой под Telegram Dark Theme (211 переменных в `:root`, бандл `css/2xz4eq8hsmei2.css`).
- **Иконки:** Библиотека Lucide React (`lucide-react`) + уникальные растровые и векторные игровые ассеты в каталоге `assets/`.
- **Интеграция с Telegram:** Telegram WebApp SDK (`telegram-web-app.js`), использующий глобальный объект `window.Telegram.WebApp` для управления темой, виброоткликом (`HapticFeedback`), закрытием/раскрытием на весь экран и передачей `initData`.

### 1.2. Архитектура Single Page Application (SPA)
В отличие от классических многостраничных сайтов, `@pro_prison_bot` загружается как единый SPA-бандл по корневому маршруту `/`.
Навигация между экранами осуществляется через URL-параметр `?v=2&tab=<section_id>`:
- `tab=main` — Главная страница профиля;
- `tab=combo` — Комбо-система;
- `tab=bosses` — Боссы;
- `tab=prisons` — Ходки и тюрьмы;
- `tab=zaruba` — Зарубы;
- `tab=delyugi` — Делюги;
- `tab=monthly` — Ежемесячные события;
- `tab=baryaga` — Барыга;
- `tab=friends` — Друзья;
- `tab=requests` — Заявки в друзья;
- `tab=brigade` — Бригада;
- `tab=slots` — Катала (Слоты / Наперстки);
- `tab=poker` — Покер;
- `tab=wheel` — Колесо фортуны;
- `tab=custom` — Фартовый;
- `tab=dice` — Кости;
- `tab=calc` — Калькулятор урона;
- `tab=wardrobe` — Тату и Шмот;
- `tab=giveaways` — Розыгрыши;
- `tab=subscription` — Подписка;
- `tab=settings` — Настройки автоматизации;
- `tab=news` — Новости и рейды.

---

## 2. Модель аутентификации и клиентское состояние

### 2.1. Поток авторизации
1. Telegram клиент открывает WebApp iframe с хешем `#tgWebAppData_<REDACTED>`.
2. Клиентский скрипт бота извлекает параметры инициализации, сохраняет их в `localStorage.getItem('telegramInitData')` и отправляет на эндпоинт `/api/auth/telegram`.
3. Бэкенд верифицирует криптографическую подпись HMAC-SHA256 по токену Telegram-бота.
4. При успешной проверке клиент получает JWT-токены:
   - `accessToken` — короткоживущий токен для вызовов внутренних API бота;
   - `miniappToken` — токен авторизации мини-аппа;
   - `gameRefreshToken` — токен для продления игровой сессии оригинальной «Тюряги».
5. Для админ-панели используется флаг `_isAdmin` в `localStorage`, открывающий доступ к роутам `/admin/*`.

### 2.2. Схема клиентского хранилища (`storage_schema.json`)
- **`localStorage`:**
  - `accessToken` — текущий JWT авторизации API бота;
  - `miniappToken` — токен сессии Telegram WebApp;
  - `gameRefreshToken` — токен сессии игрового сервера;
  - `telegramInitData` — санитизированная строка инициализации;
  - `telegramUser` — JSON-объект пользователя Telegram (id, username, first_name);
  - `currentUserId` — цифровой ID игрока в Тюряге;
  - `_isAdmin` — булев флаг прав администратора;
  - `startTabCache` — сохраненная вкладка по умолчанию;
  - `giveawaySeenAt` — метка времени последнего просмотра розыгрышей;
  - `gameEventsActive` — кэш флага активности игровых событий.
- **`IndexedDB`:**
  - База `prison-bot-cache` (версия 1) — локальный кэш тяжелых справочников (предметы гардероба, наколки, списки боссов, текстуры).

---

## 3. Детальный разбор всех 17 функциональных модулей

### 3.1. Главная (HUD & Профиль)
- **Скриншот:** [01_home_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/01_home_main.png)
- **Код:** `parsed_js/1roro0q1bvazd.js`, `parsed_js/0zev-6heomamn.js`
- **Функционал:**
  - Верхний статус-бар: авторитет, текущая задержка сети (мс), статус активной подписки;
  - Профиль игрока: аватар, никнейм, статус, уровень авторитета, топ-100;
  - Виджеты ресурсов: Энергия (50/50), Сахар, Мыло, Рубли, Туалетная бумага;
  - Прогресс-бары: Таланты (#23383, 11 очков), Достижения (199/29 404), Борода (рост в днях);
  - История ресурсов (модальное окно с графиками притока/оттока ресурсов);
  - Быстрый доступ к покупке общака и активным боссам.

### 3.2. Комбо (Ежедневное комбо и Автокомбо)
- **Скриншоты:** [03_combo.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo.png), [03_combo_auto.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo_auto.png), [03_combo_rating.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo_rating.png)
- **Код:** `parsed_js/3zreb_5w18fd8.js`, `parsed_js/0zpci8mldv7f0.js`
- **Эндпоинты:** `/api/combo/daily`, `/api/combo/status`, `/api/combo/auto-stream`, `/api/combo/guess-stream`, `/api/combo/leaderboard`, `/api/combo/prize/claim`
- **Функционал:**
  - Отображение текущего дневного комбо-удара (последовательность ударов по боссу);
  - Банк комбо: совместный сбор средств игроками на покупку и разгадку комбо;
  - `autocombo`: стриминг разгаданных комбинаций через Server-Sent Events (SSE) `/api/combo/auto-stream`;
  - Автоматическое пробитие комбо при смене суток без участия пользователя;
  - Таблица лидеров игроков, быстрее всех разгадавших комбо.

### 3.3. Боссы (Боевой модуль)
- **Скриншот:** [04_bosses.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/04_bosses.png)
- **Код:** `parsed_js/1am_i-bcrgxg_.js`, `parsed_js/1ohk_du8t8ozu.js`
- **Эндпоинты:** `/api/game/bosses/*`, `/api/game/boss-presets/*`
- **Функционал:**
  - Разделение боссов по категориям: «Беспредельщики», «Надзиратели», «Рецидивисты»;
  - Отображение детальной информации: Кирпич (7/7, 2ч 55м), Сизый, Махно, Лютый, Шайба, Бурят, Дядя Миша, Бандяк, Абу, Гризли, Феня, Север, Мазай, Хирург, Пресс, Немой, Бидон, Воркута, Старшой, Полтос, Бугор, Змей, Гвоздь, Тротил;
  - Таймеры вызова и кулдауны ключей;
  - Пресеты оружия: связки ударов (кулаки, заточки, яд, самопалы);
  - Автобой: пороги урона, ограничения по оружию (`autoDungeonAttackWeaponDamageCap`).

### 3.4. Ходки и Тюрьмы
- **Скриншот:** [05_prisons.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/05_prisons.png)
- **Код:** `parsed_js/2p-gruifay5-q.js`
- **Функционал:**
  - Список всех доступных тюрем (Бутырка, Кресты, Матросская тишина, Владимирский централ, Белый лебедь и др.);
  - Мастера и выполнение заданий за энергию;
  - Автоматическое расходование энергии на ходки с максимальным КПД опыта/авторитета;
  - Дневной и ночной режим ходок (по расписанию).

### 3.5. Зарубы (PvP)
- **Скриншот:** [06_zaruby.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/06_zaruby.png)
- **Код:** `parsed_js/14c1gzjsrr3sa.js`
- **Эндпоинты:** `/api/game/zaruba/*`
- **Функционал:**
  - Участие в ежедневных зарубах стенка на стенку;
  - Выбор тактики (атака, защита, поддержка);
  - Автоматический сбор наград по итогам раундов зарубы.

### 3.6. Делюги, Бизнесы и Баулы
- **Скриншот:** [07_delyugi.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/07_delyugi.png)
- **Код:** `parsed_js/3_uqbz4gqx812.js`
- **Функционал:**
  - Автоматический сбор прибыли с бизнесов (`autoCollectBusiness`);
  - Сбор туалетной бумаги (`autoCollectToilet`, `autoCollectToiletPaper`);
  - Прокачка талантов и сбор нычек;
  - Авто-вскрытие баулов (`autoBaulEnabled`, `autoBaulLevel`, `autoBaulKnife`, `autoBaulGunshot`, `autoBaulPoison`, `autoBaulRubles`).

### 3.7. События и Ежемесячный календарь
- **Скриншоты:** [08_events_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/08_events_main.png), [09_events_changer.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/09_events_changer.png), [10_events_settings.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/10_events_settings.png)
- **Код:** `parsed_js/3a4wko0h_su9d.js`
- **Эндпоинты:** `/api/game/monthly/claim`, `/api/game/events/*`
- **Функционал:**
  - Сетка ежедневных наград за вход (Ноябрь 2026, дни 1–30);
  - Модуль «Меняла»: обмен ивентовой валюты на призы и мешки;
  - Настройка автоматического клейма ежедневных подарков (`autoClaimVpi`, `autoMenyalaOpenBags`).

### 3.8. Барыга
- **Скриншот:** [11_bariga.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/11_bariga.png)
- **Код:** `parsed_js/2nhwoaz3lu1a4.js`
- **Функционал:**
  - Обмен рублей, сахара и мыла на оружие и расходники;
  - Авто-прокрутка у барыги (`autoBarygaSpin`) с сохранением неснижаемого резерва (`autoBarygaSpinReserve`).

### 3.9. Друзья и Социальная автоматизация
- **Скриншот:** [12_friends.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/12_friends.png)
- **Код:** `parsed_js/0fl4wey_7fjtb.js`
- **Эндпоинты:** `/api/game/friends/*`, `/api/game/podogrev/*`
- **Функционал:**
  - Мониторинг входящих заявок в друзья;
  - Авто-прием корешей по критериям (`autoAcceptQualified`, `autoAddMinTalents`, `autoAddStrictProfile`);
  - Авто-отклонение слабых игроков (`autoDeclineUnqualified`);
  - Автоматическая отправка и прием подогревов (`autoPodogrevSend`, `autoPodogrevAccept`);
  - Черный список (`autoRemoveBlacklisted`).

### 3.10. Бригада (Клан, Лагеря, Сходняк)
- **Скриншоты:** [13_brigade.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade.png), [13_brigade_roster.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_roster.png), [13_brigade_camps.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_camps.png), [13_brigade_shodnyak.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_shodnyak.png)
- **Код:** `parsed_js/1byu6xllnqky0.js`, `parsed_js/3bpzgsgig4vb5.js`
- **Эндпоинты:** `/api/brigade/*`, `/api/game/shodnyak/*`
- **Функционал:**
  - Обзор бригады: общак, авторитет, позиция в топе;
  - Ростер («Состав»): вклад каждого участника, онлайн-статусы;
  - «Лагеря»: захват лагерей, подземелья бригады (`autoDungeonAttack`, `autoDungeonDefense`, `autoDungeonAttackDailyDamageCap`);
  - «Сходняк»: покупка клеток сходняка (`/api/game/shodnyak/cells/buy`), взносы килек (`autoContributeSprats`).

### 3.11. Мини-игры Двора
- **Скриншоты:** [14_games_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/14_games_main.png), [15_games_katala.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/15_games_katala.png), [16_games_poker.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/16_games_poker.png), [17_games_wheel.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/17_games_wheel.png), [18_games_fartovy.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/18_games_fartovy.png), [19_games_dice.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/19_games_dice.png)
- **Код:** `parsed_js/36g-417s98p40.js`, `parsed_js/16_pr73k-dtvl.js`
- **Функционал:**
  - «Катала»: наперстки, авто-сбор (`autoCollectKatala`);
  - «Покер»: партии в тюремный покер против ИИ;
  - «Колесо фортуны»: ежедневные бесплатные вращения и покупка спинов;
  - «Фартовый»: карточная игра на удвоение;
  - «Кости»: игра в кости со ставками на сахар/рубли.

### 3.12. Калькулятор урона
- **Скриншот:** [20_damage_calc.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/20_damage_calc.png)
- **Код:** `parsed_js/3476ir6uihri8.js`
- **Функционал:**
  - Интерактивный калькулятор суммарного урона по любому боссу;
  - Учет прокачки всех веток талантов (Ударник, Защитник, Беспредельщик);
  - Учет сетов шмота и татуировок;
  - Оптимизация расхода оружия для нанесения ровно 100% урона без перерасхода.

### 3.13. Тату и Шмот (Гардероб и Примерочная)
- **Скриншот:** [21_wardrobe.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/21_wardrobe.png)
- **Код:** `parsed_js/1aaea4hunfv7f.js`
- **Функционал:**
  - Полный каталог всех наколок и вещей с фильтрацией по слотам и бонусам;
  - Калькулятор бонусов к авторитету и урону;
  - Симулятор «Слепой кольщик»;
  - Каталог обустройства хат.

### 3.14. Розыгрыши
- **Скриншот:** [22_giveaways.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/22_giveaways.png)
- **Код:** `parsed_js/1mpp9dce_l5tx.js`
- **Эндпоинты:** `/api/giveaways/*`
- **Функционал:**
  - Список активных и завершенных розыгрышей подписок и валюты;
  - Автоматическая проверка условий участия (подписка на канал, активность).

### 3.15. Подписка и Платежная система
- **Скриншот:** [23_subscription.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/23_subscription.png)
- **Код:** `parsed_js/2u-42xez2tfos.js`
- **Эндпоинты:** `/api/subscriptions/*`
- **Функционал:**
  - Оплата через Telegram Stars (150 ⭐) или банковские карты;
  - Покупка подписки себе или в подарок корешу;
  - История транзакций и проверка статуса платежа.

### 3.16. Настройки автоматизации
- **Скриншот:** [24_settings.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/24_settings.png)
- **Код:** `parsed_js/13ru_942tnq-4.js`
- **Функционал:**
  - Главные тумблеры автоматизации;
  - Расписание сна бота (часы покоя, имитирующие живого игрока);
  - Настройка прокси-серверов и сессий;
  - Настройка Telegram-уведомлений о событиях бота.

### 3.17. Новости и Рейды
- **Скриншот:** [02_news_raids.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/02_news_raids.png)
- **Код:** `parsed_js/0324-p2oqpwmu.js`
- **Функционал:**
  - Официальные новости разработчиков;
  - Расписание межбригадных рейдов и глобальных битв.
