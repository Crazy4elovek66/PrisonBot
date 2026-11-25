# Документация API-контрактов: Гардероб, Слепой кольщик, Хаты, Профиль игроков, Коллекции, Таланты, Баулы и Ассеты

Данный документ фиксирует точные контракты, выявленные в ходе анализа `parsed_js/bundle.js`, живого сетевого трафика и DOM оригинальной игры «Тюряга» и референсного мини-аппа `@pro_prison_bot` (`https://pro-prison-bot.003220.xyz/?v=2`).

---

## 1. Гардероб («Тату и Шмот»), «Слепой кольщик» и «Хаты»

### 1.1. Каталог татуировок, одежды и камер
- **Эндпоинт кэша / справочников игры:**
  - `GET /api/tattoo/by-zone?zone={1..42}` — получение татуировок по зонам (зоны 1–42).
  - `GET /api/clothing/by-zone?zone={1..8}` — получение одежды по зонам (зоны 1–8).
  - `GET /api/camera/all` — получение полного списка камер игры (Хаты).
    Ответ: `{"success": true, "cameras": [{"id": int, "name": str, "price": int, "currency": str, "imageUrl": str, "owned": bool, "currencyIconUrl": str}]}`.
  - Полнофункциональный агрегированный кэш базы данных:
    `GET https://pro-prison-bot.003220.xyz/api/game/tattoo-clothing-cache`
    Возвращает 8,126 татуировок, 506 предметов одежды и 48 камер:
    - `id`: уникальный числовой ID предмета.
    - `name`: название части (например, "Череп", "Шляпа", "Наколка").
    - `setName`: название сета (например, `Комплект "Череп"`, `Биомеханика`, `Мафия`).
    - `zone`: номер зоны надевания (для тату 1..42, для одежды 1..8).
    - `isSet`: булев флаг вхождения в сет.
    - `rarity`: `A3`, `B2`, `P1` и т.д.
    - `price`: стоимость покупки (0, если нельзя купить за валюту или падает в бою/квестах).
    - `currency`: валюта покупки (`rubles`, `sugar`, `paper` и т.д.).
    - `imageUrl`: путь спрайта на CDN (например, `assets/PrisonV3/Tattoos/Skull/T/Skull_Zone1.png`).
    - `cardPreviewUrl`: превью-изображение (например, `assets/PrisonV3/Tattoos/Skull/P/prev_Skull_Zone1.webp`).
    - `description`: источник/описание части (например, `"Можно получить за убийство \"Сизый\" в пацанском режиме"`).
    - `sourceDescription`: дополнительное описание источника.
    - `setDescription`: описание эффекта сета (например, `"Увеличивает урон атаки \"Шмальнуть из самопала\" на 25 (эффект за 20 татуировок)"`).
    - `combat_stats_bonus`: словарь боевых бонусов части (например, `{"poison": 6}`, `{"gunshot": 5}`, `{"knife": 15}`).
    - `authorityValue`: даваемый авторитет при получении/покупке.

### 1.2. Критерий строгого разделения «Слепого кольщика» и «Сетов»
Предметы относятся к пулу **«Слепого кольщика»** (`blind_kolsik`) строго по условию:
1. `description` или `sourceDescription` содержит `"слепого кольщика"` или `"кольщик"`.
2. `imageUrl` содержит `"Tattoos/Kolsik/"` или `"Tattoos/Skull/"`.
3. `rewardPreviewUrl` содержит `"kolsik.png"`.
4. `setName` равен `Комплект "Череп"` или начинается с `Комплект "` и его части добываются у кольщика.
5. `is_kolsik` полностью изолирует ровно 707 татуировок кольщика.
Все остальные 7,419 татуировок и 506 предметов одежды относятся к разделу **«Сеты»** (`regular`).
**Пересечение ID между разделами строго равно 0.**

### 1.3. Инвентарь игрока
- `GET /api/clothing/inventory`
  Ответ:
  ```json
  {
    "success": true,
    "ownedClothing": [13, 25, 48, ...],
    "ownedTattoos": [1, 92, 113, 360, ...],
    "ownedCameras": [1, 2, 5, ...]
  }
  ```

### 1.4. Надевание, снятие и покупка
- **Надевание/снятие отдельной татуировки или комплекта татуировок:**
  - `POST /api/tattoo/apply`
    Payload: `{"tattooZones": { "<zoneId>": { "tattooId": int, "imageUrl": str }, ... } }`
    - Передаются только изменяемые зоны (1..42). `imageUrl` — оригинальный путь игры (например `assets/PrisonV3/Tattoos/biomechanics/T/bone_Zone2.png`), **без** обёртки `/api/v1/assets/proxy`.
    - Отсутствие `tattooId` (или `tattooId: 0` / пустой `imageUrl`) трактуется сервером игры как **снятие** татуировки в указанной зоне.
    - Для надевания полного или частичного комплекта передаётся словарь всех собранных зон с валидными `tattooId > 0` и `imageUrl`.
    - Особенность игры (`bundle.js`): при надевании татуировки в зону `14` (кисть) клиент сбрасывает зону `6` одежды на дефолтную кисть (`clothingId: 0`).
- **Покупка татуировки:**
  - `POST /api/tattoo/buy`
    Payload: `{"tattooId": int}`
- **Надевание/снятие одежды или комплекта одежды:**
  - `POST /api/clothing/apply`
    Payload: `{"clothingZones": { "<zoneId>": { "clothingId": int, "imageUrl": str }, ... } }`
    - Для снятия передаётся `clothingId: 0` и `imageUrl: ""`.
    - При надевании комплекта передаётся словарь собранных зон с `clothingId > 0` и оригинальным `imageUrl`.
- **Покупка одежды:**
  - `POST /api/clothing/buy`
    Payload: `{"clothingId": int}`
- **Выбор активной камеры (Хаты):**
  - `POST /api/camera/select`
    Payload: `{"cameraId": int}`
    Ответ: `{"success": true, "roomCameraUrl": str}`
- **Покупка камеры:**
  - `POST /api/camera/buy`
    Payload: `{"cameraId": int}`

---

## 2. Послойный рендер персонажа («Примерочная»)

Визуальная примерочная отображает персонажа на Canvas (пропорция 755:562, 1510x1124px при retina 2x).
Порядок наложения слоев (снизу вверх, Z-Index):
1. **Фон хаты (Camera Background):**
   - URL из `roomCameraUrl` (например, `assets/PrisonV3/RoomCameraUrl/1/1.png`).
2. **Задний слой одежды (Back Clothing):**
   - Одежда с `imageBackUrl` или задние слои зон (пояс, плащ, крылья).
3. **Базовое тело персонажа (Base Body):**
   - Спрайт тела `assets/PlayerSprite.png` (или `assets/PrisonV3/HUD/PlayerSprite.png`).
4. **Лицо персонажа (`face`):**
   - Глаза (`eyes`): `assets/PrisonV3/Face/EyesAnim/...`
   - Нос (`nose`): `assets/PrisonV3/Face/Nose/...`
   - Рот (`mouth`): `assets/PrisonV3/Face/Mouth/...`
5. **Татуировки по зонам (Tattoos):**
   - 42 зоны татуировок поверх базового тела.
6. **Передний слой одежды (Front Clothing):**
   - Зоны 1..8 (головной убор, торс/рубаха, штаны, обувь, аксессуары, кисти рук).
7. **Борода (`beard`):**
   - Фаза бороды `assets/Beard/BeardDay/{phase}.png`.

---

## 3. Профиль кандидатов в заявках в друзья (`GET /api/friendship/requests`)

В ответе `GET /api/friendship/requests` каждый кандидат `t` содержит:
- `userId`: числовой ID кандидата.
- `nickname`: никнейм.
- `photoUrl`: аватарка.
- `talentsCount` или `TalentsCount`: сумма талантов.
- `weaponDamage` или `WeaponDamage`: объект урона оружия:
  - `knife` / `Knife`: урон финки (`knifeDamage`).
  - `poison` / `Poison`: урон яда (`poisonDamage`).
  - `gunshot` / `Gunshot`: урон самопала (`gunshotDamage`).
- `totalDamage`: сумма `knife + poison + gunshot`.

### Расчет `level`, `authority` и `biceps`:
В профиле кандидата из `GET /api/player/view/{userId}`:
- `authority` возвращается в `resources.authority` или `authority`.
- Уровень игрока вычисляется игровым алгоритмом (Module 415 в `bundle.js`):
  $$D = 1600 + 80 \times \text{authority}$$
  $$\text{level} = \max\left(1, \left\lfloor \frac{-40 + \sqrt{D}}{40} \right\rfloor\right)$$
- **Особенность показателя `biceps` чужих игроков:**
  В результате декомпиляции `parsed_js/bundle.js` (компоненты `FriendRequestsTab` и `class jo` — просмотр чужого профиля) установлено, что игровой сервер принципиально не отдает `biceps` других игроков в открытом API (в `class jo` поле `biceps` отсутствует вовсе, рендерятся только `authority`, `nickname`, `photoUrl`, `tattooZones`, `clothingZones`).
  Поэтому бэкенд возвращает `biceps: None`, если сервер игры не передал ненулевое значение. На фронтенде вместо вводящего в заблуждение `0` отображается прочерк `-`, а `SocialWorker` при значении `None` и дефолтном фильтре `friend_min_biceps == 0` не блокирует и не отсекает кандидатов.

---

## 4. Контракты Талантов, Коллекций и Баулов

1. **Таланты (`GET /api/talent/status`):**
   - Возвращает `{ "state": { "spentPoints": int, "unspentPoints": int, "currentDamage": int, "talentLevels": { ... } }, "config": { ... }, "requiredDamage": int, "biceps": int }`.
   - `totalPoints = state.spentPoints + state.unspentPoints`.
   - `currentDamage` и `requiredDamage` определяют шкалу прогресса до следующего очка.
2. **Коллекции и Нычки:**
   - Подтвержденный эндпоинт: `GET /api/collection/player/full?userId={user_id}`.
   - Двухуровневая структура ответа:
     - Внешний массив `collections` содержит тюрьмы:
       `[{"prisonid": 1, "prison": "Бутырка", "collections": [{"id": 1, "name": "...", "items": [...], "rewards": {...}}]}]`
     - Прогресс игрока по предметам хранится в `playerProgress.data[str(prisonid)][str(collectionId)] = {"1": 2, "2": 1, ...}`.
   - Для каждого предмета коллекции количество $> 0$ означает, что предмет собран.
   - Если собраны все 7 предметов (`collected == total` и каждый $\ge 1$), коллекция готова к обмену (`canExchange = True`).
   - Обмен: `POST /api/collection/player/vparit` с телом `{"userId": user_id, "prisonId": prison_id, "collectionId": collection_id}`.
   - Нычки: массив `stashes` из `init_player` и инвентарь `GET /api/stashgear/all`.
3. **Баулы (`GET /api/bauls/stat`):**
   - Возвращает вложенный объект `stats`:
     - `active`: булево состояние активности.
     - `level`: текущий уровень баула.
     - `maxLevel`: максимальный уровень.
     - `currentExp`: текущий опыт.
     - `expToNext`: опыт для следующего уровня.
     - `pendingRewards`: массив накопленных наград.
   - Покупка/открытие: `POST /api/bauls/buy` с `{"baulId": int}`.

---

## 5. Реестр оригинальных иконок игры на CDN

Базовый CDN игры: `https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/` и мини-аппа `https://pro-prison-bot.003220.xyz/game-icons/`:
- **Валюты:**
  - Рубли: `/static/assets/icons/rubles.webp` (источник `PrisonV3/BARIGA/img/icon_B_rubles.webp`)
  - Мыло: `/static/assets/icons/soap.webp` (источник `HUD_soap.webp`)
  - Сахар: `/static/assets/icons/sugar.webp` (источник `PrisonV3/BARIGA/img/icon_B_sugar.webp`)
  - Папиросы: `/static/assets/icons/cigarettes.webp` (источник `PrisonV3/BARIGA/img/icon_B_cigarettes.webp`)
  - Бумага: `/static/assets/icons/paper.webp` (источник `PrisonV3/BARIGA/img/icon_B_paper.webp`)
- **Оружие и удары:**
  - Финка: `/static/assets/icons/knife.webp` (`PrisonV3_Friend_knifeIcon.webp`)
  - Яд: `/static/assets/icons/poison.webp` (`PrisonV3_Friend_poisonIcon.webp`)
  - Самопал: `/static/assets/icons/gunshot.webp` (`PrisonV3_Friend_gunIcon.webp`)
  - В грудину: `/static/assets/icons/punchChest.webp` (`PrisonV3_WeaponsScene_icon_4_1.webp`)
  - По бубенцам: `/static/assets/icons/kickBalls.webp` (`PrisonV3_WeaponsScene_icon_4_2.webp`)
  - В глаза: `/static/assets/icons/pokeEyes.webp` (`PrisonV3_WeaponsScene_icon_4_3.webp`)
  - В ухо: `/static/assets/icons/kneeEar.webp` (`PrisonV3_WeaponsScene_icon_4_4.webp`)
- **Характеристики и UI:**
  - Авторитет: `/static/assets/icons/authority.webp` (`PrisonV3/All/AvtoritetDamage.webp`)
  - Бицуха: `/static/assets/icons/biceps.webp` (`PrisonV3/interaction/bitsepsAdd.png`)
  - Энергия: `/static/assets/icons/energy.webp` (`Energy.webp`)
  - Ключи боссов: `/static/assets/icons/keys.webp` (`PrisonV3/bossKeyDrop.webp`)
  - Таланты: `/static/assets/icons/talents.webp` (`PrisonV3/talents/image/all/tallent.png` или `PrisonV3/talents/image/all/icon_jurnal.png`)
  - Боссы: `/static/assets/icons/boss.webp` (`PrisonV3/All/bossWine.png`)
  - Голосование / лайк: `/static/assets/icons/vote.webp` (`PrisonV3_interaction_iconVote3.webp`)
