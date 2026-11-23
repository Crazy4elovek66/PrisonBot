# Логика автоматизации, алгоритмы и конфигурация `@pro_prison_bot`

Документ описывает полный набор механизмов автоматизации референсного бота **`@pro_prison_bot`**, извлеченный из статического анализа 178 JS-чанков (`parsed_js/`), 60 специализированных конфигурационных ключей `auto*` и структуры формы настроек (`24_settings.json`).

---

## 1. Схема конфигурационного объекта автоматизации

Объект настроек бота хранится в клиентском состоянии и синхронизируется с бэкендом через эндпоинт `/api/settings`.
Полная схема включает 60 проверенных ключей:

| Ключ конфигурации | Тип | Дефолтное значение | Допустимый диапазон | Описание алгоритма |
|---|---|---|---|---|
| **Подземелья и Рейды Бригады** | | | | |
| `autoDungeonAttack` | `boolean` | `true` | `true / false` | Главный тумблер авто-атаки лагерей и подземелий бригады |
| `autoDungeonAttackMode` | `string` | `"balanced"` | `"safe" / "balanced" / "aggressive"` | Режим расхода оружия в подземельях |
| `autoDungeonAttackBatch` | `boolean` | `true` | `true / false` | Пакетная отправка ударов для снижения нагрузки на сеть |
| `autoDungeonAttackBatchSize` | `number` | `10` | `1 - 50` | Количество ударов в одной пачке |
| `autoDungeonAttackDailyDamageCap` | `number` | `10000000` | `0 - 50000000` | Дневной лимит суммарного урона персонажа в рейдах |
| `autoDungeonAttackDailyCapFinishNode` | `boolean` | `true` | `true / false` | Добивать ли текущий узел при исчерпании дневного капа |
| `autoDungeonAttackAfterDailyCap` | `boolean` | `false` | `true / false` | Продолжать атаковать после капа только бесплатными ударами |
| `autoDungeonAttackHitImmediately` | `boolean` | `false` | `true / false` | Наносить удар мгновенно без рандомизации задержки |
| `autoDungeonAttackSyncPlan` | `boolean` | `true` | `true / false` | Синхронизация тактического плана атаки с бригадным штабом |
| `autoDungeonAttackWeaponDamageCap` | `number` | `5000000` | `0 - 20000000` | Порог урона, после которого прекращается трата платного оружия |
| `autoDungeonAttackVpi` | `boolean` | `true` | `true / false` | Использование ВПИ в боях подземелий |
| `autoDungeonAttackVpiReserve` | `number` | `5` | `0 - 50` | Неснижаемый остаток ВПИ |
| `autoDungeonArmband` | `boolean` | `true` | `true / false` | Авто-надевание повязки лагеря для бонуса к урону |
| `autoDungeonDefense` | `boolean` | `true` | `true / false` | Авто-защита лагеря бригады при нападении врагов |
| `autoDungeonDefenseUsePaid` | `boolean` | `false` | `true / false` | Использовать платное оружие при защите лагеря |
| `autoDungeonClaim` | `boolean` | `true` | `true / false` | Авто-сбор сундуков и наград за зачищенные узлы лагеря |
| **Баулы** | | | | |
| `autoBaulEnabled` | `boolean` | `true` | `true / false` | Автоматическое вскрытие баулов по кулдауну |
| `autoBaulLevel` | `number` | `3` | `1 - 5` | Минимальный уровень вскрываемых баулов |
| `autoBaulRequireAll` | `boolean` | `false` | `true / false` | Требовать наличие всех компонентов перед вскрытием |
| `autoBaulKnife` | `boolean` | `true` | `true / false` | Разрешить вскрытие заточками |
| `autoBaulGunshot` | `boolean` | `true` | `true / false` | Разрешить вскрытие самопалами |
| `autoBaulPoison` | `boolean` | `true` | `true / false` | Разрешить вскрытие ядом |
| `autoBaulRubles` | `boolean` | `false` | `true / false` | Разрешить трату рублей на докупку недостающих отмычек |
| `autoBaulOnTattoo` | `boolean` | `true` | `true / false` | Вскрывать баул при набивке целевых наколок |
| `autoBaulTattooCount` | `number` | `5` | `1 - 20` | Количество наколок, требуемых для триггера баула |
| **Друзья и Социалка** | | | | |
| `autoAcceptFriends` | `boolean` | `true` | `true / false` | Автоматический прием заявок в друзья |
| `autoAcceptFriendRequests` | `boolean` | `true` | `true / false` | Мониторинг входящей очереди запросов |
| `autoAcceptQualified` | `boolean` | `true` | `true / false` | Принимать только подходящих под фильтр игроков |
| `autoDeclineUnqualified` | `boolean` | `true` | `true / false` | Автоматически отклонять заявки игроков ниже порога |
| `autoAddFilterEnabled` | `boolean` | `true` | `true / false` | Активация фильтров при поиске и приеме |
| `autoAddMinTalents` | `number` | `8` | `1 - 25` | Минимальное число очков талантов у кандидата |
| `autoAddStrictProfile` | `boolean` | `true` | `true / false` | Проверка наличия аватарки, авторитета и непустой хаты |
| `autoAddWeeklyTop` | `boolean` | `false` | `true / false` | Добавление кандидатов из еженедельного топа |
| `autoFriendBossKillers` | `boolean` | `true` | `true / false` | Авто-добавление игроков с высоким дамагом по боссам |
| `autoPodogrevSend` | `boolean` | `true` | `true / false` | Ежедневная автоматическая рассылка подогревов друзьям |
| `autoPodogrevAccept` | `boolean` | `true` | `true / false` | Авто-сбор входящих подогревов от корешей |
| `autoRemoveBlacklisted` | `boolean` | `true` | `true / false` | Удаление из друзей игроков из персонального черного списка |
| `autoRemoveBrigadeBlacklisted` | `boolean` | `true` | `true / false` | Удаление врагов клана по общебригадному черному списку |
| **Экономика и Рутина** | | | | |
| `autoCollectBusiness` | `boolean` | `true` | `true / false` | Сбор прибыли с бизнесов каждые N часов |
| `autoCollectToilet` | `boolean` | `true` | `true / false` | Сбор туалетной бумаги в хате |
| `autoCollectToiletPaper` | `boolean` | `true` | `true / false` | Синоним сбора бумаги |
| `autoCollectKatala` | `boolean` | `true` | `true / false` | Сбор выигрышей у каталы |
| `autoBarygaSpin` | `boolean` | `true` | `true / false` | Автоматическая прокрутка барыги |
| `autoBarygaSpinReserve` | `number` | `100` | `10 - 1000` | Резерв сахара/рублей, ниже которого прокрутка стопится |
| `autoContributeSprats` | `boolean` | `true` | `true / false` | Авто-взнос килек в бригадный общак |
| `autoShaveBeard` | `boolean` | `true` | `true / false` | Сбривание бороды по достижении максимальной длины (бонус) |
| `autoClaimVpi` | `boolean` | `true` | `true / false` | Клейм ежедневных очков ВПИ |
| `autoMenyalaOpenBags` | `boolean` | `true` | `true / false` | Авто-открытие мешков менялы во время ивентов |
| `autoOpenVbox` | `boolean` | `true` | `true / false` | Вскрытие посылок при поступлении в инвентарь |
| `autocombo` | `boolean` | `true` | `true / false` | Авто-пробитие ежедневного комбо по расписанию |

---

## 2. Планировщик задач и управление очередями

### 2.1. Приоритеты выполнения фоновых задач
Бот использует приоритетную очередь задач (`PriorityQueue`), где задачи ранжируются по срочности:
1. **Приоритет 1 (Критический):** `autocombo` (пробитие комбо сразу при наступлении игровых суток или получении сигнала SSE);
2. **Приоритет 2 (Высокий):** `autoDungeonDefense` (защита бригадного лагеря при тревоге);
3. **Приоритет 3 (Средний):** `autoDungeonAttack` (плановые рейдовые удары пакетами по расписанию);
4. **Приоритет 4 (Регулярный):** `autoCollectBusiness`, `autoCollectToilet`, `autoClaimVpi`;
5. **Приоритет 5 (Фоновый):** `autoPodogrevSend`, `autoAcceptFriends`, `autoBaulEnabled`, `autoShaveBeard`.

### 2.2. Расписание сна («Режим человека»)
Для маскировки под живого игрока в настройках бота задаются окна покоя:
- Дефолтное время сна: `01:00 — 07:00` (по МСК).
- Во время окна сна:
  - Все рутинные сборы (бизнесы, ходки, друзья) полностью приостанавливаются;
  - Исключение составляют только критические события бригадных тревог (если включена опция `wakeOnBrigadeAlarm`).
- К каждому действию добавляется случайный джиттер (`jitter`): `BaseDelay + random(-15%, +25%)`.

---

## 3. Формулы и алгоритмы

### 3.1. Формула оптимизации урона калькулятора (`calcDamage`)
При расчете урона по боссу используется формула:
$$\text{TotalDamage} = \sum (\text{HitBase} \times (1 + \text{TalentBonus} + \text{SetBonus} + \text{TattooBonus})) \times \text{CritMultiplier}$$

Где:
- $\text{TalentBonus}$ — сумма процентов из ветки «Ударник» (до +120%);
- $\text{SetBonus}$ — бонус от надетых сетов шмота (до +45%);
- $\text{TattooBonus}$ — авторитетный множитель наколок;
- $\text{CritMultiplier}$ — шанс и сила крита (дефолт 2.0x).

### 3.2. Алгоритм фильтрации заявок в друзья
Заявка одобряется только при выполнении логического предиката:
$$\text{IsApproved} = (\text{Talents} \ge \text{autoAddMinTalents}) \land (\text{Authority} \ge \text{Threshold}) \land (\neg \text{IsBlacklisted})$$
Если `autoDeclineUnqualified == true` и предикат ложен, бот автоматически отправляет вызов на отклонение заявки, освобождая очередь.
