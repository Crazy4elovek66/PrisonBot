import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from client.http_client import GameHttpClient

logger = logging.getLogger(__name__)

CATEGORY_NAMES = {
    1: "Беспредельщики",
    2: "Надзиратели",
    3: "Рецидивисты",
}

CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "storage" / "bosses_catalog.json"

# Правила склонения русского языка (соответствуют fS и bS из parsed_js/bundle.js)
NEED_DAY = ["Нужна", "Нужно", "Нужно"]
RUNS_DAY = ["дневная ходка", "дневные ходки", "дневных ходок"]
NEED_NIGHT = ["Нужен", "Нужно", "Нужно"]
RUNS_NIGHT = ["ночной бунт", "ночных бунта", "ночных бунтов"]


def decline_ru(count: int, forms: List[str]) -> str:
    """Склонение числительных русского языка (1 ходка, 2 ходки, 5 ходок)."""
    n = abs(int(count or 0))
    r = n % 100
    a = n % 10
    if 11 <= r <= 14:
        return forms[2]
    if a == 1:
        return forms[0]
    if 2 <= a <= 4:
        return forms[1]
    return forms[2]


def _load_bosses_catalog() -> List[Dict[str, Any]]:
    """Загружает полный эталонный каталог 58 боссов игры из storage/bosses_catalog.json."""
    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Ошибка чтения bosses_catalog.json: %s", e)
    return []


FALLBACK_BOSSES = _load_bosses_catalog()


class BossAPI:
    """
    Методы взаимодействия с боссами и боевой системой:
    - /api/boss/bootstrap (состояние активного боя, сессия, награды, статы)
    - /api/boss/weapons (инвентарь, время последних ударов, экипированные слоты)
    - /api/boss/use-weapon (нанесение удара оружием / рукопашной атакой)
    - /api/boss/claim (получение награды за поверженного босса)
    - /api/boss/friend-damage (получение урона друзей)
    """

    def __init__(self, http_client: GameHttpClient):
        self.http = http_client

    async def get_bootstrap(self) -> Dict[str, Any]:
        """Получение текущего состояния босса, сессии боя и наград."""
        resp = await self.http.get("/api/boss/bootstrap")
        resp.raise_for_status()
        return resp.json()

    async def get_weapons(self) -> Dict[str, Any]:
        """Получение состояния оружия, таймеров ударов и экипированных слотов."""
        resp = await self.http.get("/api/boss/weapons")
        resp.raise_for_status()
        return resp.json()

    async def hit_boss(self, weapon: str, count: int = 1) -> Dict[str, Any]:
        """
        Нанесение удара по боссу.
        :param weapon: Название оружия / рукопашной атаки (punchChest, kickBalls, pokeEyes, kneeEar)
        :param count: Количество атак (по умолчанию 1)
        """
        payload = {"weapon": weapon, "count": count}
        resp = await self.http.post("/api/boss/use-weapon", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def claim_reward(self, claim_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Сбор награды за победу над боссом.
        :param claim_id: Идентификатор конкретной награды (при наличии)
        """
        payload = {"claimId": claim_id} if claim_id else {}
        resp = await self.http.post("/api/boss/claim", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_friend_damage(self) -> Dict[str, Any]:
        """Получение урона, нанесенного друзьями."""
        resp = await self.http.get("/api/boss/friend-damage")
        resp.raise_for_status()
        return resp.json()

    async def get_boss_list(self, category_id: int = 1) -> Dict[str, Any]:
        """Получение списка боссов выбранной категории."""
        resp = await self.http.get(f"/api/boss/list?categoryId={category_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_all_bosses(self) -> List[Dict[str, Any]]:
        """
        Загрузка всех 58 боссов игры по всем трем категориям (1: Беспредельщики, 2: Надзиратели, 3: Рецидивисты).
        Использует эталонный каталог storage/bosses_catalog.json с реальным HP (без выдуманных множителей),
        опрашивает категории API игры для обновления живого статуса и возвращает точные контракты ключей.
        """
        # Базовый эталонный каталог всех боссов
        catalog = _load_bosses_catalog()
        bosses_by_id = {b["id"]: dict(b) for b in catalog}

        # Опрос API игры для живых данных сессий/наград
        categories = [1, 2, 3]
        tasks = [self.get_boss_list(category_id=cid) for cid in categories]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for cid, res in zip(categories, results):
            if isinstance(res, Exception) or not isinstance(res, dict):
                continue
            raw_list = res.get("bosses") or res.get("items") or []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                boss_data = item.get("boss") if isinstance(item.get("boss"), dict) else item
                b_id = boss_data.get("id") or boss_data.get("bossId")
                if not b_id:
                    continue

                if b_id in bosses_by_id:
                    target = bosses_by_id[b_id]
                    if "baseHp" in boss_data and boss_data["baseHp"]:
                        target["baseHp"] = int(boss_data["baseHp"])
                    if "keysRequired" in boss_data:
                        kr = boss_data["keysRequired"]
                        target["requiredKeyBossId"] = kr.get("bossId")
                        target["requiredKeyBossName"] = kr.get("bossName")
                        target["requiredKeysCount"] = kr.get("count", 0)
                        target["keyLabel"] = f"от {kr.get('bossName')}" if kr.get("bossName") else "Без ключей"
                    # Извлечение объекта access (из item или boss_data)
                    acc_obj = item.get("access") or boss_data.get("access")
                    if acc_obj:
                        target["access"] = acc_obj
                    if "isLocked" in boss_data:
                        target["isLocked"] = bool(boss_data["isLocked"])
                    elif "locked" in boss_data:
                        target["isLocked"] = bool(boss_data["locked"])
                    elif "available" in boss_data:
                        target["isLocked"] = not bool(boss_data["available"])
                    if "unlockReason" in boss_data and boss_data["unlockReason"]:
                        target["unlockReason"] = str(boss_data["unlockReason"])
                    if "cooldownSeconds" in boss_data and boss_data["cooldownSeconds"] is not None:
                        target["cooldownSeconds"] = int(boss_data["cooldownSeconds"])
                else:
                    base_hp = int(boss_data.get("hp") or boss_data.get("baseHp") or 0)
                    kr = boss_data.get("keysRequired") or {}
                    acc_obj = item.get("access") or boss_data.get("access")
                    bosses_by_id[b_id] = {
                        "id": b_id,
                        "name": boss_data.get("name") or boss_data.get("title") or f"Босс #{b_id}",
                        "title": boss_data.get("title") or boss_data.get("name") or f"Босс #{b_id}",
                        "categoryId": cid,
                        "categoryName": CATEGORY_NAMES.get(cid, "Прочие"),
                        "baseHp": base_hp,
                        "hp": base_hp,
                        "modes": {"pacansky": {"hp": base_hp}, "odin": {"hp": base_hp}},
                        "requiredKeyBossId": kr.get("bossId"),
                        "requiredKeyBossName": kr.get("bossName"),
                        "requiredKeysCount": kr.get("count", 0),
                        "keyLabel": f"от {kr.get('bossName')}" if kr.get("bossName") else "Без ключей",
                        "dailyLimit": 7,
                        "access": acc_obj,
                        "isLocked": bool(boss_data.get("isLocked") or boss_data.get("locked") or (boss_data.get("available") is False)),
                        "unlockReason": boss_data.get("unlockReason"),
                        "cooldownSeconds": int(boss_data.get("cooldownSeconds") or 0),
                    }

        all_bosses = list(bosses_by_id.values())
        all_bosses.sort(key=lambda x: (x.get("categoryId", 1), x.get("sortOrder", 999), x.get("id", 0)))
        return all_bosses

    @staticmethod
    def evaluate_bosses_availability(
        bosses: List[Dict[str, Any]],
        bootstrap: Optional[Dict[str, Any]] = None,
        prisons_data: Optional[Any] = None,
        player_init: Optional[Dict[str, Any]] = None,
        arrivals_data: Optional[Dict[str, Any]] = None,
        guild_status: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Точная серверная оценка доступности и блокировок для всех 58 боссов игры и каждого режима боя.
        Проверяет по приоритету:
        1. Серверный запрет (access.available === false, unavailableReason);
        2. Требования по дневным ходкам и ночным бунтам (с реальным прогрессом X из Y и склонением);
        3. Требование победы над предыдущим боссом (requiredBossId);
        4. Ивентовые окна прихода (arrivals: Тротил, Гастролёр, Конвой, Воркута);
        5. Нехватка ключей (requiredKeyBossId / requiredKeysCount против инвентаря игрока);
        6. Кулдауны (cooldownSeconds > 0) и суточные лимиты (dailyWins >= dailyLimit);
        7. Раздельный статус каждого режима боя (modesAccess).
        """
        bootstrap = bootstrap or {}
        player_init = player_init or {}

        # 1. Построение карты прогресса тюрем
        prisons_map: Dict[int, Dict[str, Any]] = {}
        raw_prisons = []
        if isinstance(prisons_data, dict):
            raw_prisons = prisons_data.get("prisons") or []
        elif isinstance(prisons_data, list):
            raw_prisons = prisons_data

        if not raw_prisons:
            raw_prisons = player_init.get("prisons") or bootstrap.get("prisons") or []

        for p in raw_prisons:
            if not isinstance(p, dict):
                continue
            pid = p.get("id") or p.get("prisonId")
            if pid:
                try:
                    pid_int = int(pid)
                    day_val = (
                        p.get("dayRuns")
                        if p.get("dayRuns") is not None
                        else (p.get("dayCount") or p.get("dayCompletions") or p.get("completedDay") or p.get("runs") or 0)
                    )
                    night_val = (
                        p.get("nightRuns")
                        if p.get("nightRuns") is not None
                        else (p.get("nightCount") or p.get("nightCompletions") or p.get("completedNight") or 0)
                    )
                    prisons_map[pid_int] = {
                        "name": p.get("name") or p.get("title") or f"тюрьме {pid_int}",
                        "dayRuns": int(day_val or 0),
                        "nightRuns": int(night_val or 0),
                    }
                except (ValueError, TypeError):
                    pass

        # 2. Карты игрока: ключи, суточные победы, общие победы, arrivals
        p_stats = bootstrap.get("playerStats") or {}
        keys_map: Dict[str, int] = {}
        raw_keys = p_stats.get("keys")
        if isinstance(raw_keys, dict):
            keys_map = {str(k): int(v) for k, v in raw_keys.items() if str(v).isdigit()}

        daily_wins_map: Dict[str, int] = {}
        raw_dw = p_stats.get("dailyWins")
        if isinstance(raw_dw, dict):
            daily_wins_map = {str(k): int(v) for k, v in raw_dw.items() if str(v).isdigit()}

        wins_map: Dict[str, int] = {}
        raw_w = p_stats.get("wins")
        if isinstance(raw_w, dict):
            wins_map = {str(k): int(v) for k, v in raw_w.items() if str(v).isdigit()}

        arrivals_map: Dict[int, Dict[str, Any]] = {}
        raw_arr = arrivals_data or bootstrap.get("arrivals") or {}
        if isinstance(raw_arr, dict):
            for ak, av in raw_arr.items():
                if isinstance(av, dict):
                    try:
                        arrivals_map[int(ak)] = av
                    except (ValueError, TypeError):
                        pass

        # Гильдия / бригада
        g_data = guild_status or bootstrap.get("guild") or player_init.get("guild") or {}
        in_guild = bool(g_data.get("inGuild", False) or g_data.get("guildId"))

        for boss in bosses:
            b_id = int(boss.get("id") or 0)
            is_locked = False
            unlock_reason = None
            progress_text = None

            # А. Проверка серверного объекта access
            acc = boss.get("access")
            if isinstance(acc, dict):
                if acc.get("available") is False:
                    reason_code = acc.get("unavailableReason")
                    if reason_code == "prison_runs_required" and isinstance(acc.get("prison"), dict):
                        p_info = acc["prison"]
                        shift = p_info.get("shift", "day")
                        req_runs = int(p_info.get("requiredRuns") or p_info.get("requiredNightRuns") or 0)
                        cur_runs = int(p_info.get("runs") or p_info.get("nightRuns") or 0)
                        p_name = p_info.get("prisonName") or f"тюрьме {p_info.get('prisonId')}"
                        s_need = decline_ru(req_runs, NEED_DAY if shift == "day" else NEED_NIGHT)
                        s_runs = decline_ru(req_runs, RUNS_DAY if shift == "day" else RUNS_NIGHT)
                        progress_text = f"{cur_runs} из {req_runs}"
                        unlock_reason = f"{s_need} {req_runs} {s_runs} в {p_name}, пройдено {cur_runs} ({progress_text})"
                        is_locked = True
                    elif reason_code == "guild_level_too_low":
                        req_lvl = acc.get("requiredGuildLevel", 50)
                        unlock_reason = f"Нужен уровень бригады {req_lvl}"
                        is_locked = True
                    elif reason_code == "not_in_guild":
                        unlock_reason = "Бригадный режим доступен только участникам бригады"
                        is_locked = True
                    elif reason_code == "boss_not_open":
                        unlock_reason = "Босс сейчас недоступен"
                        is_locked = True
                    else:
                        unlock_reason = str(acc.get("message") or reason_code or "Босс недоступен")
                        is_locked = True
                elif acc.get("available") is True:
                    is_locked = False

            # Б. Проверка требований по тюрьмам из каталога
            req_p_id = boss.get("requiredPrisonId")
            if req_p_id and not is_locked:
                shift = boss.get("requiredShift", "day")
                req_runs = int(boss.get("requiredRuns") or 0)
                p_name = boss.get("requiredPrisonName") or f"тюрьме {req_p_id}"
                p_stat = prisons_map.get(int(req_p_id), {})
                cur_runs = int(p_stat.get("dayRuns" if shift == "day" else "nightRuns", 0))
                if cur_runs < req_runs:
                    s_need = decline_ru(req_runs, NEED_DAY if shift == "day" else NEED_NIGHT)
                    s_runs = decline_ru(req_runs, RUNS_DAY if shift == "day" else RUNS_NIGHT)
                    progress_text = f"{cur_runs} из {req_runs}"
                    unlock_reason = f"{s_need} {req_runs} {s_runs} в {p_name}, пройдено {cur_runs} ({progress_text})"
                    is_locked = True
                else:
                    progress_text = f"{cur_runs} из {req_runs}"

            # В. Проверка требования победы над предыдущим боссом
            req_boss_id = boss.get("requiredBossId")
            if req_boss_id and not is_locked:
                prev_wins = int(wins_map.get(str(req_boss_id), 0))
                if prev_wins < 1:
                    req_name = boss.get("requiredBossName") or f"Босс #{req_boss_id}"
                    unlock_reason = f"Победите босса «{req_name}»"
                    is_locked = True

            # Г. Проверка ивентовых окон прихода (arrivals)
            if (boss.get("isArrival") or b_id in (19, 20, 39, 56)) and not is_locked:
                arr = arrivals_map.get(b_id)
                if arr and arr.get("isOpen") is False:
                    is_locked = True
                    unlock_reason = "Босс сейчас недоступен (вне окна прихода)"

            # Д. Проверка ключей
            req_key_boss_id = boss.get("requiredKeyBossId")
            req_keys_count = int(boss.get("requiredKeysCount") or 0)
            owned_keys = int(keys_map.get(str(req_key_boss_id), 0)) if req_key_boss_id else 0
            missing_keys = max(0, req_keys_count - owned_keys) if (req_key_boss_id and req_keys_count > 0) else 0
            key_boss_name = boss.get("requiredKeyBossName") or (f"#{req_key_boss_id}" if req_key_boss_id else "")

            # Е. Проверка кулдауна и дневного лимита
            cooldown_seconds = int(boss.get("cooldownSeconds") or 0)
            daily_wins = int(daily_wins_map.get(str(b_id), 0))
            daily_limit = int(boss.get("dailyLimit") or 7)

            if is_locked:
                can_attack = False
                attack_block_reason = unlock_reason
            elif missing_keys > 0:
                can_attack = False
                attack_block_reason = f"Не хватает ключей от {key_boss_name} ({owned_keys}/{req_keys_count})"
            elif cooldown_seconds > 0:
                can_attack = False
                attack_block_reason = f"Кулдаун {cooldown_seconds} сек."
            elif daily_wins >= daily_limit:
                can_attack = False
                attack_block_reason = f"Достигнут дневной лимит побед ({daily_wins}/{daily_limit})"
            else:
                can_attack = True
                attack_block_reason = None

            # Ж. Раздельная оценка режимов боя (modesAccess)
            raw_modes = boss.get("modes") or {"pacansky": {"hp": boss.get("baseHp", 1000)}, "odin": {"hp": boss.get("baseHp", 1000)}}
            modes_access: Dict[str, Any] = {}

            for mode_name, m_info in raw_modes.items():
                m_hp = m_info.get("hp", boss.get("baseHp", 1000))
                m_acc = m_info.get("access") if isinstance(m_info.get("access"), dict) else {}

                if is_locked:
                    modes_access[mode_name] = {
                        "available": False,
                        "canAttack": False,
                        "reason": unlock_reason,
                        "hp": m_hp,
                    }
                elif m_acc.get("available") is False:
                    m_reason = m_acc.get("unavailableReason")
                    if m_reason == "guild_level_too_low":
                        m_msg = f"Нужен уровень бригады {m_acc.get('requiredGuildLevel', 50)}"
                    elif m_reason == "not_in_guild":
                        m_msg = "Бригадный режим доступен только участникам бригады"
                    else:
                        m_msg = "Режим сейчас недоступен"
                    modes_access[mode_name] = {
                        "available": False,
                        "canAttack": False,
                        "reason": m_msg,
                        "hp": m_hp,
                    }
                elif mode_name == "brigade" and not in_guild:
                    modes_access[mode_name] = {
                        "available": False,
                        "canAttack": False,
                        "reason": "Бригадный режим доступен только участникам бригады",
                        "hp": m_hp,
                    }
                elif not can_attack:
                    modes_access[mode_name] = {
                        "available": True,
                        "canAttack": False,
                        "reason": attack_block_reason,
                        "hp": m_hp,
                    }
                else:
                    modes_access[mode_name] = {
                        "available": True,
                        "canAttack": True,
                        "reason": None,
                        "hp": m_hp,
                    }

            boss["isLocked"] = is_locked
            boss["canAttack"] = can_attack
            boss["unlockReason"] = unlock_reason
            boss["attackBlockReason"] = attack_block_reason
            boss["progressText"] = progress_text
            boss["missingKeysCount"] = missing_keys
            boss["modesAccess"] = modes_access

        return bosses

    async def start_battle(
        self,
        boss_id: int,
        mode: str = "pacansky",
        combo_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Призыв / запуск боя с боссом.
        :param boss_id: ID босса
        :param mode: Режим боя (pacansky, blotnoy, avtoritetny, vorovskoy, odin)
        :param combo_mode: Опциональный комбо-режим
        """
        payload = {
            "bossId": boss_id,
            "mode": mode,
            "comboMode": combo_mode,
        }
        resp = await self.http.post("/api/boss/start-attack", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_boss_buffs(self) -> Dict[str, Any]:
        """Получение списка доступных баффов на боссах."""
        resp = await self.http.get("/api/boss-buffs")
        resp.raise_for_status()
        return resp.json()

    async def get_guild_status(self) -> Dict[str, Any]:
        """Получение статуса гильдии / бригады игрока (членство, уровень, ранг, полномочия)."""
        resp = await self.http.get("/api/guild/status")
        resp.raise_for_status()
        return resp.json()

    async def activate_boss_buff(self, buff_id: str) -> Dict[str, Any]:
        """Активация выбранного баффа босса по строковому идентификатору (напр. 'buff_skuns')."""
        resp = await self.http.post("/api/boss-buffs/activate", json={"buffId": str(buff_id)})
        resp.raise_for_status()
        return resp.json()

    async def get_guild_buffs(self) -> Dict[str, Any]:
        """Получение баффов гильдии / бригады."""
        resp = await self.http.get("/api/guild/buff")
        resp.raise_for_status()
        return resp.json()

    async def activate_guild_buff(self, guild_id: int, buff_id: str) -> Dict[str, Any]:
        """Активация баффа бригады."""
        payload = {"guildId": guild_id, "buffId": buff_id}
        resp = await self.http.post("/api/guild/buff/activate", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_shodnyak_buffs(self) -> Dict[str, Any]:
        """Получение баффов сходняка."""
        resp = await self.http.get("/api/shodnyak/buffs")
        resp.raise_for_status()
        return resp.json()

    async def activate_shodnyak_buff(self, buff_id: str) -> Dict[str, Any]:
        """Активация баффа сходняка."""
        payload = {"buffId": buff_id}
        resp = await self.http.post("/api/shodnyak/buffs/activate", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def buy_weapon(self, weapon_type: str, count: int = 1) -> Dict[str, Any]:
        """Покупка оружия у барыги."""
        payload = {"weaponType": weapon_type, "count": count}
        resp = await self.http.post("/api/boss/weapon/buy", json=payload)
        resp.raise_for_status()
        return resp.json()
