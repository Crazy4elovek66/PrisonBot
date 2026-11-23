# Реестр API-контрактов и сетевой протокол `@pro_prison_bot`

Настоящий документ содержит спецификацию всех API-эндпоинтов бэкенда референсного бота `pro-prison-bot.003220.xyz`, составленную на основе объединения живых перехваченных сетевых запросов ([network_summary.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/api_snapshots/network_summary.json)) и статического анализа всех 178 JS-чанков ([api_registry.json](file:///d:/Projects/PrisonBot/reference_archive/pro_prison_bot/api_snapshots/api_registry.json) — 592 эндпоинта).

---

## 1. Общие принципы сетевого взаимодействия

### 1.1. Базовые URL и заголовки
- **Базовый URL бэкенда:** `https://pro-prison-bot.003220.xyz/api`
- **Обязательные заголовки клиентских запросов:**
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `Authorization: Bearer <REDACTED_JWT>`
  - `X-Telegram-Init-Data: <REDACTED_TG_DATA>` (при первичной авторизации или обновлении токена)
  - `X-Client-Version: 2.0.0` (Next.js build: `FmH16ITs5FViI3gHxEMSK`)

---

## 2. Категории API-эндпоинтов

### 2.1. Аутентификация и сессия (`/api/auth/*`)

#### `POST /api/auth/telegram`
- **Назначение:** Обмен Telegram WebApp `initData` на сессионные JWT-токены бота.
- **Тело запроса (Request Body):**
  ```json
  {
    "initData": "<REDACTED_TG_DATA>"
  }
  ```
- **Схема ответа (Response Body 200 OK):**
  ```json
  {
    "success": true,
    "user": {
      "id": "<REDACTED_USER_ID>",
      "username": "<REDACTED_USERNAME>",
      "firstName": "<REDACTED_NAME>",
      "isAdmin": false,
      "subscription": {
        "active": true,
        "expiresAt": "2026-12-31T23:59:59.000Z",
        "daysLeft": 39
      }
    },
    "tokens": {
      "accessToken": "<REDACTED_TOKEN>",
      "refreshToken": "<REDACTED_TOKEN>",
      "miniappToken": "<REDACTED_TOKEN>"
    }
  }
  ```

---

### 2.2. Комбо-система (`/api/combo/*`)

#### `GET /api/combo/daily`
- **Назначение:** Получение информации о текущем дневном комбо (секретная последовательность ударов по боссу).
- **Ответ (200 OK):**
  ```json
  {
    "date": "2026-11-22",
    "isGuessed": true,
    "combo": [1, 3, 2, 4, 1],
    "bossId": 5,
    "bossName": "Шайба",
    "guessedBy": "<REDACTED_USERNAME>",
    "guessedAt": "2026-11-22T04:12:00.000Z"
  }
  ```

#### `GET /api/combo/auto-stream` (Server-Sent Events)
- **Назначение:** Реалтайм-стриминг разгаданных ударов комбо для автоматического выполнения ботом.
- **Формат:** `text/event-stream`
- **События:** `data: {"type": "combo_update", "combo": [...], "status": "active"}`

#### `POST /api/combo/prize/claim`
- **Назначение:** Клейм награды за разгаданное комбо.
- **Ответ (200 OK):**
  ```json
  {
    "success": true,
    "reward": {
      "sugar": 50,
      "rubles": 5,
      "authority": 1000
    }
  }
  ```

---

### 2.3. Игровые операции и автоматизация (`/api/game/*`)

#### `GET /api/game/user-info`
- **Назначение:** Полный снимок игрового состояния персонажа из игры «Тюряга».
- **Маппинг на API Тюряги:** метод `get_user_info`.
- **Ответ (200 OK):**
  ```json
  {
    "id": "<REDACTED_USER_ID>",
    "authority": 852000,
    "energy": 50,
    "maxEnergy": 50,
    "sugar": 302,
    "soap": 122,
    "toiletPaper": 40,
    "rubles": 14,
    "talents": 11,
    "beardDays": 7,
    "achievementsCount": 199
  }
  ```

#### `POST /api/game/boss/hit`
- **Назначение:** Нанесение удара по активному боссу.
- **Маппинг на API Тюряги:** метод `boss_hit`.
- **Тело запроса:**
  ```json
  {
    "bossId": 1,
    "hitType": "combo",
    "weapons": {
      "knife": 0,
      "poison": 1,
      "gunshot": 0
    }
  }
  ```
- **Ответ (200 OK):**
  ```json
  {
    "success": true,
    "damageDealt": 15000,
    "bossHpRemaining": 35000,
    "crit": true
  }
  ```

#### `POST /api/game/prisons/walk`
- **Назначение:** Прохождение ходки в тюрьме.
- **Маппинг на API Тюряги:** метод `prison_job`.
- **Тело запроса:**
  ```json
  {
    "prisonId": 2,
    "jobId": 3,
    "energySpent": 5
  }
  ```

#### `POST /api/game/business/collect`
- **Назначение:** Сбор прибыли с бизнесов персонажа.
- **Маппинг на API Тюряги:** метод `collect_business`.
- **Ответ (200 OK):**
  ```json
  {
    "success": true,
    "collectedRubles": 12,
    "collectedSugar": 45
  }
  ```

#### `POST /api/game/monthly/claim`
- **Назначение:** Забор ежедневной награды календаря событий (День 22).
- **Маппинг на API Тюряги:** метод `monthly_event_claim`.
- **Тело запроса:**
  ```json
  {
    "day": 22
  }
  ```
- **Ответ (200 OK):**
  ```json
  {
    "success": true,
    "claimed": true,
    "rewards": [
      { "type": "rubles", "amount": 10 },
      { "type": "weapon_poison", "amount": 5 }
    ]
  }
  ```

---

### 2.4. Бригада, Лагеря и Сходняк (`/api/brigade/*`, `/api/game/shodnyak/*`)

#### `GET /api/brigade/overview`
- **Назначение:** Информация о текущей бригаде игрока, общаке и рейдах.
- **Ответ (200 OK):**
  ```json
  {
    "brigadeId": 86,
    "name": "ОПГ ХМАО 86",
    "rank": 14,
    "membersCount": 50,
    "obshchak": {
      "rubles": 45000,
      "sprats": 128000
    }
  }
  ```

#### `POST /api/game/shodnyak/cells/buy`
- **Назначение:** Покупка клеток сходняка за бригадные ресурсы.
- **Тело запроса:**
  ```json
  {
    "cellIndex": 4,
    "shodnyakId": 12
  }
  ```

#### `POST /api/brigade/camps/attack`
- **Назначение:** Атака вражеского бригадного лагеря (подземелья).
- **Тело запроса:**
  ```json
  {
    "campId": 3,
    "mode": "auto",
    "batchSize": 10,
    "dailyDamageCap": 5000000
  }
  ```

---

### 2.5. Социалка и Подогревы (`/api/game/friends/*`, `/api/game/podogrev/*`)

#### `POST /api/game/podogrev/friends`
- **Назначение:** Массовая отправка или сбор подогревов (подарков).
- **Тело запроса:**
  ```json
  {
    "action": "send_all",
    "friendIds": ["<REDACTED_ID_1>", "<REDACTED_ID_2>"]
  }
  ```

#### `POST /api/game/friends/requests/filter`
- **Назначение:** Пакетный прием/отклонение заявок по критериям авто-фильтра.
- **Тело запроса:**
  ```json
  {
    "minTalents": 10,
    "strictProfile": true,
    "declineUnqualified": true
  }
  ```

---

### 2.6. Мини-игры Двора (`/api/games/*`)

- `POST /api/games/dice/roll` — бросок костей с указанием ставки;
- `POST /api/games/poker/turn` — ход в партии тюремного покера;
- `POST /api/games/wheel/spin` — запуск колеса фортуны;
- `POST /api/games/katala/play` — раунд в наперстки каталы.

---

### 2.7. Телеметрия и Метрики (`/api/client-metrics`)

#### `POST /api/client-metrics`
- **Назначение:** Пассивный сбор клиентских метрик (задержка сети, ошибки рендера).
- **Статус ответа:** `204 No Content`
- **Тело запроса:**
  ```json
  {
    "latency": 49,
    "screen": "08_events_main",
    "timestamp": 1795353100
  }
  ```
