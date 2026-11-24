# Контракты Ежедневных Действий: Туалетка, Подогревы, Катала и Месячные Делюги

Документ содержит точные API-контракты, структуры данных и правила бизнес-логики ежедневных игровых действий, извлеченные из `bundle.js`, дампов и референс-архива.

---

## 1. «Щипануть туалетку» у барыги (Бесплатная туалетная бумага)

### 1.1. Эндпоинт и протокол
* **Метод:** `POST /api/daily/toilet-paper`
* **Тело запроса:** `{}`
* **Заголовки:** `Authorization: Bearer <token>`
* **Ответ сервера (успех):**
  ```json
  {
    "success": true,
    "balance": 142
  }
  ```
* **Ответ сервера (уже получено сегодня или ошибка):**
  ```json
  {
    "success": false,
    "message": "Туалетная бумага уже получена сегодня"
  }
  ```

### 1.2. Проверка доступности и подтвержденный механизм сброса (00:00 МСК)
* Флаг `canClaimToiletPaper` в `PlayerDataStore` / ответе `POST /api/player/init`.
* **Механизм сброса (подтверждено по `bundle.js` и живому API):** календарный сброс ежедневно в **00:00 МСК (UTC+3)** (`Europe/Moscow`). При повторном запросе в те же московские сутки сервер возвращает `200 OK` с `{"success": false, "message": "Ещё рано! Приходи завтра.", "canClaimToiletPaper": false}`.
* **Автоматизация и таймер:** `core/scheduler.py` регистрирует cron-триггер на `00:01 Europe/Moscow`, а `RoutineWorker` дополнительно проверяет `canClaimToiletPaper` в каждом цикле (учитывая режим сна и мастер-переключатель) и возвращает точный `secondsUntilReset` / `nextResetAt` в `/api/v1/live/profile`.

---

## 1.3. Контракт извлечения боевых характеристик других игроков (`extract_player_combat_stats`)
* **Проверено по живому API игры, `parsed_js/bundle.js` и `@pro_prison_bot`:**
  * `GET /api/boss/check-session` (только свой аккаунт) возвращает точный объект `weaponStatsEffective` (`poisonDamage`, `gunshotDamage`, `knifeDamage`).
  * `GET /api/friendship/requests` — единственный эндпоинт для других игроков, отдающий серверный `weaponDamage` (`{"poison": ..., "gunshot": ..., "knife": ...}`) и `talentsCount` напрямую (примеры из живого API: `TheCheesechddr` — `{"poison": 895, "gunshot": 246, "knife": 432}`, `КЛ МАТАДОРА` — `{"poison": 2280, "gunshot": 1353, "knife": 864}`).
  * `GET /api/player/view/{userId}` (проверено на `RV ГАРИК` `9000000000179416` и `ОПГ I Бубен` `9000000000193390`) возвращает ключи верхнего уровня: `userId`, `nickname`, `photoUrl`, `face` (`eyes`, `nose`, `mouth`), `tattooZones` (`1..42`), `clothingZones`, `clothingBackZones`, `clothingFrontIds`, `beardStartTime`, `beardPhase`, `roomCameraUrl`, `authority`, `wishlist`, `cooldowns`, `statusMessage`, `isFriend`, `vpiTier`, `guildId`, `guildEmblem` (`pattern`, `texture`, `textureColor`, `icon`, `iconColor`, `lvl`), `cameraFriends`. Поля `weaponDamage` или полного инвентаря (`ownedTattoos`/`ownedClothing`) сервер здесь не отдает.
  * `GET /api/summary/{userId}` возвращает `success`, `data.overview` (`achievementsUnlockedReward`, `achievementsTotalReward`, `talentPointsTotal`, `bossWins`), `data.unlockedAchievements` (где `poison_*`, `gunshot_*`, `knife_*` — кумулятивные достижения по сбору/использованию, например «Собери 50.000 доз яда», а не разовый урон с удара).
  * `GET /api/player/brief/{userId}`, `/api/friendship/profiles`, `/api/weekly-top/top`, `/api/friend/top100` и `/api/guild/{id}/members` не содержат поля `weaponDamage`.
* **Игровая формула расчета урона (подтверждена на живом аккаунте `9000000000466709`: `302 / 122 / 40` совпали с точностью до 1):**
  * Базовый урон (`bundle.js`, модуль `607`, константа `l`): `poisonDamage = 250`, `gunshotDamage = 60`, `knifeDamage = 30`.
  * К базе суммируются бонусы из `/api/clothing/by-zone` & `/api/tattoo/by-zone` (`combat_stats_bonus` по `storage/tattoo_clothing_cache.json`) и плоские бонусы талантов (`TalentsTab`, модуль `999` в `bundle.js` + `/api/talent/status` config: последовательная ветка `0..34` -> `[35, 36, 37]` -> `38..41`, всего `1035` очков по дереву, максимум `+850 poison / +570 gunshot / +612 knife`).
  * Для игроков из Радара/Топа без записи в `/api/friendship/requests` `extract_player_combat_stats(payload, summary_payload)` при наличии данных профиля (`player/view` и/или `summary`) рассчитывает достоверный минимум урона из реальных игровых источников: `база (250/60/30) + надетые шмотки (clothingFrontIds / clothingZones) + набитые на персонаже тату (tattooZones 1..42) + гарантированные плоские бонусы дерева талантов по talentPointsTotal` (и помечает `weaponDamageEstimated: true`). Если по игроку вообще нет профильных данных, возвращается `0` (без подстановки пустых фиктивных констант).

---

## 2. Умные Подогревы (Сбор после слива энергии + Отправка корешам)

### 2.1. Эндпоинты
1. **Проверка входящих подогревов:**
   * `GET /api/podogrev/status?page=1&pageSize=20`
   * Возвращает список готовых к сбору посылок от друзей.
2. **Массовый сбор входящих подогревов:**
   * `POST /api/podogrev/collect/all`
   * Тело: `{}`
   * Увеличивает текущую энергию игрока на сумму энергии из подогревов.
3. **Список друзей для отправки подогревов:**
   * `GET /api/podogrev/friends?page=1&pageSize=50`
   * Ответ:
     ```json
     {
       "friends": [
         { "userId": 882585344, "nickname": "ОПГ I Химик", "photoUrl": "..." }
       ],
       "page": 1,
       "hasMore": false,
       "total": 42
     }
     ```
4. **Отправка бесплатных подогревов:**
   * `POST /api/podogrev/send`
   * Тело:
     ```json
     {
       "sendToAll": false,
       "recipientIds": [882585344, 9000000000179416]
     }
     ```
   * **Строгий запрет:** вызов `/api/gifts/send` (платные подарки за рубли/мыло) категорически запрещен. Разрешена только отправка бесплатного подогрева через `/api/podogrev/send`.

### 2.2. Умная связка «Слив энергии -> Сбор подогревов -> Дослив энергии»
* **Проблема сгорания энергии:** если собрать подогревы при полной или частично заполненной шкале энергии, излишек сгорает сверх лимита `max_energy`.
* **Реализация в `PrisonWorker`:**
  1. Бот сначала полностью тратит доступную энергию на ходки в целевой тюрьме или обучение у мастера (пока `energy >= action_cost`).
  2. Если после слива энергии включен `auto_podogrev == True` и шкала энергии не полна (`energy < max_energy`), бот запрашивает статус входящих подогревов и вызывает `collect_all_podogrev()`.
  3. Если в результате сбора энергия пополнилась до стоимости хотя бы 1 действия (`energy >= action_cost`), бот не ждет следующего интервала, а **немедленно запускает второй проход слива энергии** в ходки или мастеров.

---

## 3. Мини-игра «Катала» (Бесплатная партия + Шульмовки + Солвер)

### 3.1. Эндпоинты
* `GET /api/card/state` — текущее состояние стола Каталы (`level`, `progress`, `freeGameAvailable`, `lastGameTime`).
* `POST /api/card/start` — запуск бесплатной игры. Возвращает стартовую руку из 2-х карт:
  ```json
  {
    "success": true,
    "card1": "A_h",
    "card2": "K_d"
  }
  ```
* `POST /api/card/reroll` — шульмовка (переворот одной карты):
  * Тело: `{"cardIndex": 0}` (для `card1`) или `{"cardIndex": 1}` (для `card2`).
  * Возвращает обновленную руку.
* `POST /api/card/finish` — завершение партии и зачисление выигрыша:
  ```json
  {
    "success": true,
    "result": { "reward": "cigarettes", "amount": 1000 }
  }
  ```

### 3.2. Количество бесплатных шульмовок от уровня игры
* **Уровень 1 .. 19:** 0 шульмовок (шульмовка недоступна).
* **Уровень 20 .. 59:** 1 бесплатная шульмовка.
* **Уровень 60+:** 2 бесплатные шульмовки.

### 3.3. Таблица комбинаций и их старшинство
Ранги карт: `Nk = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]`.
1. **AA (Пара Тузов / Двойной Туз):** 1000 папирос + Наколка + CartWinAA (Джекпот).
2. **KK (Пара Королей):** 700 папирос + Наколка + CartWinKK.
3. **QQ (Пара Дам):** 500 папирос + CartWinQQ.
4. **JJ (Пара Валетов):** 200 папирос.
5. **1010 (Пара Десяток):** 150 папирос.
6. **99 (Пара Девяток):** 100 авторитета.
7. **88 (Пара Восьмерок):** 100 папирос.
8. **77 (Пара Семерок):** 30 авторитета.
9. **default (Разнобой / Любая непарная комбинация):** 30 папирос.

### 3.4. Логика солвера `KatalaSolver`
* Если на руках уже пара (`card1 == card2`):
  * Комбинация уже выигрышная (от `77` до `AA`). Шульмовка не требуется — вызывается `finish` для гарантии приза.
* Если на руках разные карты (`card1 != card2`) и есть доступные шульмовки (`shulmovki_left > 0`):
  * Определяется старшая карта по индексу в `Nk`.
  * Старшая карта удерживается, а младшая карта отправляется на шульмовку (`reroll` с `cardIndex` младшей карты), чтобы попытаться собрать пару к старшей карте (с максимальным ожиданием `AA` или `KK`).
  * Если после шульмовки пара собрана — немедленный `finish`. Если нет и осталась еще 1 шульмовка — повтор для новой младшей карты.
* При `shulmovki_left == 0`: немедленный вызов `POST /api/card/finish`.
* **Безопасность:** бот играет строго **1 бесплатную суточную партию**, проверяя `freeGameAvailable` или 24 часа с `lastGameTime`. Любые платные партии и платные шульмовки за рубли/сахар строго заблокированы.

---

## 4. Месячные Делюги

### 4.1. Эндпоинты
* `GET /api/monthly/state?trackOpen=true` — получение структуры календаря, текущего активного дня (`activeDayId`), прогресса по дням и доступных тиров (`claimableTiers`).
* `POST /api/monthly/claim` — получение награды за этап/тир:
  * Тело: `{"Tier": 1}`.
  * Ответ: `{ "success": true, "reward": { ... } }`.

### 4.2. Маппинг заданий (`action` / `target`) на воркеры бота
* `PrisonRun` / `PrisonEarnAuthority` $\rightarrow$ ходки в `PrisonWorker`.
* `MasterSession` / `MasterEarnIntellect` $\rightarrow$ сессии у мастеров в `PrisonWorker`.
* `UseHomieHeat` $\rightarrow$ сбор подогревов в `RoutineWorker`.
* `ScamGambler` $\rightarrow$ игра у Каталы в `client/api/katala.py`.
* `BicepsTrain`, `SpitSoup`, `StressVictim`, `AddYeast` $\rightarrow$ делюги в `RoutineWorker`.
* `KillBoss` $\rightarrow$ победа/удары по боссу в `BossWorker`.
* После выполнения этапов бот автоматически собирает готовые тиры через `POST /api/monthly/claim`.
