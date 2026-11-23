# Каталог экранов, компонентов и дизайн-токенов `@pro_prison_bot`

Документ содержит полный каталог всех 30 экранов, подвкладок и модальных окон референсного бота **`@pro_prison_bot`**, детальный разбор UI-компонентов, состояний элементов и вычисленных дизайн-токенов CSS.

---

## 1. Дизайн-токены и тема (:root)

Вся визуальная система `@pro_prison_bot` построена на CSS-переменных, адаптированных под цветовую палитру Telegram WebApp Dark Theme (211 переменных в [css/variables.css](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/css/variables.css)):

### 1.1. Базовая палитра
- `--background`: `hsl(0, 0%, 13%)` (`#212121` — темный базовый фон)
- `--foreground`: `hsl(0, 0%, 98%)` (`#fafafa` — белый основной текст)
- `--card`: `hsl(0, 0%, 9%)` (`#181818` — подложка карточек и списков)
- `--card-foreground`: `hsl(0, 0%, 98%)`
- `--popover`: `hsl(0, 0%, 13%)`
- `--primary`: `hsl(251, 63%, 67%)` (`#8774e1` — фиолетовый акцент Telegram)
- `--primary-foreground`: `hsl(0, 0%, 100%)`
- `--secondary`: `hsl(0, 0%, 18%)` (`#2e2e2e` — нейтральные кнопки и чипы)
- `--muted`: `hsl(0, 0%, 20%)`
- `--muted-foreground`: `hsl(0, 0%, 65%)` (`#aaaaaa` — подсказки и второстепенный текст)
- `--accent`: `hsl(251, 63%, 67%)`
- `--destructive`: `hsl(359, 100%, 68%)` (`#ff595a` — опасные действия, отмена, ошибки)
- `--border`: `hsl(0, 0%, 22%)` (`#383838` — тонкие разделители карточек)
- `--radius`: `0.5rem` (скругление кнопок и карточек 8px)

---

## 2. Каталог экранов со ссылками на скриншоты и DOM

### 2.1. Главная страница (HUD и Профиль)
- **Скриншот:** [01_home_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/01_home_main.png)
- **DOM-снимок:** [01_home_main.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/01_home_main.json)
- **Элементы интерфейса:**
  - Шапка: иконка меню-гамбургера (слева), текущий авторитет (852k), пинг сети (50 мс, зеленый бейдж);
  - Блок подписки: градиентная плашка «Подписка активна • Осталось 0 дней»;
  - Карточка бригады: название «ОПГ ХМАО 86», ссылка в чат клана;
  - Кнопка «Топ-100 по авторитету»;
  - Панель ресурсов: 4 горизонтальных карточки (Энергия 50/50, Таланты #23383 11, Достижения 199/29k, Борода 7 дней);
  - Инвентарь оружия: Сахар (302), Мыло (122), Бумага (40), Рубли (14);
  - Список доступных боссов: Кирпич, Сизый, Махно, Лютый и др. со счетчиками побед за 1 час.

---

### 2.2. Комбо (3 экрана)
1. **Обзор комбо:** [03_combo.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/03_combo.json)) — текущая комбинация ударов, кнопка «Банк комбо», таймер до смены суток.
2. **Автокомбо:** [03_combo_auto.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo_auto.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/03_combo_auto.json)) — настройки автоматического пробития, тумблеры отслеживания SSE-потока.
3. **Рейтинг комбо:** [03_combo_rating.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/03_combo_rating.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/03_combo_rating.json)) — лидерборд пользователей по скорости разгадывания.

---

### 2.3. Боссы
- **Скриншот:** [04_bosses.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/04_bosses.png)
- **DOM-снимок:** [04_bosses.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/04_bosses.json)
- **Элементы:**
  - Вкладки фильтрации: «Беспредельщики», «Надзиратели», «Рецидивисты»;
  - Сетка карточек боссов со статусом (доступен/в бою/кулдаун);
  - Карточка активного боя: HP босса, нанесенный дамаг, кнопки выбора связок ударов;
  - Кнопка быстрого запуска автобоя.

---

### 2.4. Ходки
- **Скриншот:** [05_prisons.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/05_prisons.png)
- **DOM-снимок:** [05_prisons.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/05_prisons.json)
- **Элементы:**
  - Список тюремных зон с прогресс-барами завершения заданий;
  - Индикатор доступной энергии и кнопка авто-слива энергии;
  - Список мастеров тюрьмы и статусы их побед.

---

### 2.5. Зарубы
- **Скриншот:** [06_zaruby.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/06_zaruby.png)
- **DOM-снимок:** [06_zaruby.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/06_zaruby.json)
- **Элементы:**
  - Статус активного раунда зарубы;
  - Выбор тактики (атака/оборона);
  - Рейтинг участников зарубы и таймер окончания.

---

### 2.6. Делюги
- **Скриншот:** [07_delyugi.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/07_delyugi.png)
- **DOM-снимок:** [07_delyugi.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/07_delyugi.json)
- **Элементы:**
  - Секция бизнесов со счетчиками времени до следующего сбора прибыли;
  - Секция нычек и коллекций (прогресс сбора сетов);
  - Блок баулов с кнопками вскрытия и выбором инструментов.

---

### 2.7. События (3 экрана)
1. **Календарь событий:** [08_events_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/08_events_main.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/08_events_main.json)) — сетка дней месяца (1–30), отметки забранных наград.
2. **Меняла:** [09_events_changer.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/09_events_changer.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/09_events_changer.json)) — витрина обмена ивентовой валюты на сундуки.
3. **Настройка событий:** [10_events_settings.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/10_events_settings.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/10_events_settings.json)) — тумблеры авто-сбора подарков и мешков.

---

### 2.8. Барыга
- **Скриншот:** [11_bariga.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/11_bariga.png)
- **DOM-снимок:** [11_bariga.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/11_bariga.json)
- **Элементы:**
  - Таблица текущих курсов обмена сахара/мыла на рубли;
  - Колесо барыги и счетчик бесплатных прокруток.

---

### 2.9. Друзья
- **Скриншот:** [12_friends.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/12_friends.png)
- **DOM-снимок:** [12_friends.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/12_friends.json)
- **Элементы:**
  - Список корешей с аватарами, авторитетом и онлайном;
  - Кнопка «Отправить подогревы всем»;
  - Вкладка входящих заявок с фильтрами по талантам.

---

### 2.10. Бригада (4 экрана)
1. **Обзор бригады:** [13_brigade.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade.json)) — карточка клана, общак, авторитет.
2. **Состав:** [13_brigade_roster.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_roster.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade_roster.json)) — список соклановцев, вклад килек.
3. **Лагеря:** [13_brigade_camps.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_camps.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade_camps.json)) — карта лагерей, статус контроля, кнопка атаки.
4. **Сходняк:** [13_brigade_shodnyak.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/13_brigade_shodnyak.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/13_brigade_shodnyak.json)) — поле сходняка, покупка клеток за ресурсы общака.

---

### 2.11. Мини-игры Двора (6 экранов)
1. **Обзор игр:** [14_games_main.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/14_games_main.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/14_games_main.json))
2. **Катала:** [15_games_katala.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/15_games_katala.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/15_games_katala.json))
3. **Покер:** [16_games_poker.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/16_games_poker.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/16_games_poker.json))
4. **Колесо фортуны:** [17_games_wheel.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/17_games_wheel.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/17_games_wheel.json))
5. **Фартовый:** [18_games_fartovy.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/18_games_fartovy.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/18_games_fartovy.json))
6. **Кости:** [19_games_dice.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/19_games_dice.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/19_games_dice.json))

---

### 2.12. Вспомогательные сервисы (5 экранов)
1. **Калькулятор урона:** [20_damage_calc.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/20_damage_calc.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/20_damage_calc.json))
2. **Тату и Шмот:** [21_wardrobe.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/21_wardrobe.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/21_wardrobe.json))
3. **Розыгрыши:** [22_giveaways.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/22_giveaways.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/22_giveaways.json))
4. **Подписка:** [23_subscription.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/23_subscription.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/23_subscription.json))
5. **Настройки:** [24_settings.png](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/screenshots/24_settings.png) ([DOM](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/ui_dom/24_settings.json))
