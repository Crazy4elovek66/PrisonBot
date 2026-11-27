import logging
from typing import Dict, Any, List, Optional
from core.database import get_session
from core.models import Notification

logger = logging.getLogger(__name__)

CURRENCY_LABELS = {
    "authority": "Авторитет",
    "respect": "Уважение",
    "cigarettes": "Папиросы",
    "sugar": "Сахар",
    "rubles": "Рубли",
    "paper": "Туалетная бумага",
    "soap": "Мыло",
    "keys": "Ключи",
    "energy": "Энергия",
    "biceps": "Бицуха",
    "intellect": "Интеллект",
    "rating": "Уважение",
    "stash": "Нычка",
    "talents": "Очки талантов",
    "poison": "Яд",
    "knife": "Финка",
    "gunshot": "Самопал",
    "experience": "Опыт",
    "signet": "Печатки",
    "signets": "Печатки",
    "chips": "Фишки",
    "votes": "Голоса",
    "stew": "Тушенка",
}

MODE_TITLES = {
    "pacansky": "Пацанский",
    "patsansky": "Пацанский",
    "normal": "Пацанский",
    "1": "Пацанский",
    "blotnoy": "Блатной",
    "blatnoy": "Блатной",
    "hard": "Блатной",
    "2": "Блатной",
    "avtoritetny": "Авторитетный",
    "epic": "Авторитетный",
    "3": "Авторитетный",
    "vorovskoy": "Воровской",
    "odin": "В одного",
    "solo": "В одного",
    "alone": "В одного",
    "brigade": "Бригадный",
}


class DropParser:
    """
    Универсальный парсер наград, валют, нычек, татуировок и предметов
    из сырых JSON-ответов сервера.
    """

    _cosmetic_cache_loaded: bool = False
    _tattoo_by_id: Dict[int, Dict[str, Any]] = {}
    _clothing_by_id: Dict[int, Dict[str, Any]] = {}
    _camera_by_id: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def load_cosmetic_catalog(cls) -> None:
        """Загружает справочник татуировок, шмота и камер из storage/tattoo_clothing_cache.json."""
        if cls._cosmetic_cache_loaded:
            return
        cls._cosmetic_cache_loaded = True
        try:
            import json
            from pathlib import Path
            cache_path = Path(__file__).resolve().parent.parent / "storage" / "tattoo_clothing_cache.json"
            if not cache_path.exists():
                return
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            for t in data.get("tattoos") or []:
                if isinstance(t, dict) and t.get("id") is not None:
                    try:
                        cls._tattoo_by_id[int(t["id"])] = t
                    except (TypeError, ValueError):
                        pass
            for c in data.get("clothing") or []:
                if isinstance(c, dict) and c.get("id") is not None:
                    try:
                        cls._clothing_by_id[int(c["id"])] = c
                    except (TypeError, ValueError):
                        pass
            for cam in data.get("cameras") or []:
                if isinstance(cam, dict) and cam.get("id") is not None:
                    try:
                        cls._camera_by_id[int(cam["id"])] = cam
                    except (TypeError, ValueError):
                        pass
        except Exception as e:
            logger.debug("Не удалось загрузить cosmetic catalog в DropParser: %s", e)

    @classmethod
    def _build_cosmetic_drop(cls, raw_item: Any, default_kind: str) -> Optional[Dict[str, Any]]:
        cls.load_cosmetic_catalog()
        kind = default_kind
        if kind in ("cloth", "wear", "clothing_set"):
            kind = "clothing"
        elif kind in ("camera", "chamber", "hata"):
            kind = "room"
        elif kind in ("tattoo_set",):
            kind = "tattoo"

        item_id: Optional[int] = None
        obj: Dict[str, Any] = {}
        if isinstance(raw_item, dict):
            obj = raw_item
            raw_id = obj.get("tattooId") or obj.get("clothingId") or obj.get("cameraId") or obj.get("roomId") or obj.get("itemId") or obj.get("id")
            if raw_id is not None and str(raw_id).strip().isdigit():
                item_id = int(str(raw_id).strip())
        elif isinstance(raw_item, (int, str)) and str(raw_item).strip().isdigit():
            item_id = int(str(raw_item).strip())
        elif isinstance(raw_item, str) and raw_item.strip():
            nm_str = raw_item.strip()
            if kind == "tattoo":
                title = f"Наколка: {nm_str}" if not nm_str.lower().startswith("наколка") else nm_str
                return {"kind": "tattoo", "type": "tattoo", "name": nm_str, "title": title, "subtitle": "Наколка", "count": 1, "icon": "/prison/assets/icons/complect.webp"}
            if kind == "clothing":
                title = f"Шмот: {nm_str}" if not nm_str.lower().startswith("шмот") else nm_str
                return {"kind": "clothing", "type": "clothing", "name": nm_str, "title": title, "subtitle": "Шмот", "count": 1, "icon": "/prison/assets/icons/complect.webp"}
            title = f"Хата «{nm_str}»" if not nm_str.lower().startswith("хата") else nm_str
            return {"kind": "room", "type": "room", "name": nm_str, "title": title, "subtitle": "Камера", "count": 1, "icon": "/prison/assets/icons/room_reward.webp"}
        else:
            return None

        if kind == "tattoo":
            meta = cls._tattoo_by_id.get(item_id) if item_id is not None else None
            name = obj.get("name") or obj.get("tattoo") or obj.get("item") or (meta.get("name") if meta else None)
            set_name = obj.get("setName") or obj.get("set") or obj.get("title") or (meta.get("setName") if meta else None)
            if obj.get("owned") is not None and obj.get("total") is not None and obj.get("title"):
                raw_title = str(obj["title"])
                title = raw_title if raw_title.startswith("Комплект") else f'Комплект "{raw_title}"'
                item_label = name or "Элемент сета"
                subtitle = f"{item_label} ({obj['owned']}/{obj['total']} сета)"
                name = item_label
            elif not name and set_name:
                title = f"Наколка из «{set_name}»"
                name = set_name
                subtitle = set_name
            elif name:
                title = f"Наколка: {name}" if not str(name).lower().startswith("наколка") else str(name)
                subtitle = set_name or "Наколка"
            else:
                name = f"Татуировка #{item_id}" if item_id is not None else "Татуировка"
                title = f"Наколка: {name}"
                subtitle = set_name or "Наколка"
            img = obj.get("imageUrl") or obj.get("previewUrl") or (meta.get("cardPreviewUrl") or meta.get("imageUrl") if meta else "") or ""
            return {
                "kind": "tattoo",
                "type": "tattoo",
                "id": item_id,
                "itemId": item_id,
                "set_name": set_name,
                "setId": obj.get("setId") or set_name,
                "name": name,
                "title": title,
                "subtitle": subtitle,
                "count": 1,
                "icon": "/prison/assets/icons/complect.webp",
                "imageUrl": img,
            }

        if kind == "clothing":
            meta = cls._clothing_by_id.get(item_id) if item_id is not None else None
            name = obj.get("name") or obj.get("title") or (meta.get("name") if meta else None) or (f"Шмотка #{item_id}" if item_id is not None else "Шмот")
            set_name = obj.get("setName") or obj.get("set") or (meta.get("setName") if meta else None)
            title = f"Шмот: {name}" if not str(name).lower().startswith("шмот") else str(name)
            img = obj.get("imageUrl") or obj.get("previewUrl") or (meta.get("cardPreviewUrl") or meta.get("imageUrl") if meta else "") or ""
            return {
                "kind": "clothing",
                "type": "clothing",
                "id": item_id,
                "itemId": item_id,
                "set_name": set_name,
                "setId": obj.get("setId") or set_name,
                "name": name,
                "title": title,
                "subtitle": set_name or "Шмот",
                "count": 1,
                "icon": "/prison/assets/icons/complect.webp",
                "imageUrl": img,
            }

        meta = cls._camera_by_id.get(item_id) if item_id is not None else None
        name = obj.get("name") or obj.get("title") or (meta.get("name") if meta else None) or (f"Камера #{item_id}" if item_id is not None else "Хата")
        title = f"Хата «{name}»" if not str(name).lower().startswith("хата") else str(name)
        img = obj.get("imageUrl") or obj.get("previewUrl") or (meta.get("imageUrl") if meta else "") or ""
        return {
            "kind": "room",
            "type": "room",
            "id": item_id,
            "itemId": item_id,
            "name": name,
            "title": title,
            "subtitle": "Камера",
            "count": 1,
            "icon": "/prison/assets/icons/room_reward.webp",
            "imageUrl": img,
        }

    @staticmethod
    def _resolve_boss_name(payload: Dict[str, Any], boss_name: Optional[str] = None) -> str:
        if boss_name and str(boss_name).strip() and str(boss_name).strip().lower() != "босс":
            return str(boss_name).strip()
        boss_obj = payload.get("boss") if isinstance(payload.get("boss"), dict) else {}
        for cand in (
            payload.get("bossName"),
            payload.get("title"),
            boss_obj.get("name"),
            boss_obj.get("title"),
        ):
            if cand and str(cand).strip() and str(cand).strip().lower() != "босс":
                return str(cand).strip()
        bid = payload.get("bossId") or boss_obj.get("id")
        if bid is not None:
            try:
                from client.api.boss import _load_bosses_catalog, FALLBACK_BOSSES
                for item in (_load_bosses_catalog() or FALLBACK_BOSSES):
                    if str(item.get("id")) == str(bid):
                        nm = item.get("name") or item.get("title")
                        if nm:
                            return str(nm)
            except Exception:
                pass
            return f"Босс #{bid}"
        return "Босс"

    @staticmethod
    def _normalize_currency(key: str) -> Optional[str]:
        k = key.lower().strip()
        if k.startswith("reward"):
            k = k[6:].strip()
        if k in ("authority", "auth"):
            return "authority"
        if k in ("respect",):
            return "respect"
        if k in ("cigarettes", "cigs"):
            return "cigarettes"
        if k in ("sugar",):
            return "sugar"
        if k in ("rubles", "rub", "coins"):
            return "rubles"
        if k in ("paper", "toiletpaper", "toilet_paper"):
            return "paper"
        if k in ("authority", "auth", "avtoritet"):
            return "authority"
        if k in ("soap",):
            return "soap"
        if k in ("keys", "key"):
            return "keys"
        if k in ("energy",):
            return "energy"
        if k in ("biceps", "bic"):
            return "biceps"
        if k in ("intellect", "intel"):
            return "intellect"
        if k in ("rating",):
            return "rating"
        if k in ("talents", "talentpoints", "talent_points", "freepoints"):
            return "talents"
        if k in ("poison", "yad"):
            return "poison"
        if k in ("knife", "finka"):
            return "knife"
        if k in ("gunshot", "samopal", "pistol"):
            return "gunshot"
        if k in ("experience", "exp"):
            return "experience"
        if k in ("signet", "signets"):
            return "signets"
        if k in ("chips",):
            return "chips"
        if k in ("votes", "vote"):
            return "votes"
        return None

    @staticmethod
    def format_boss_mode(mode: Optional[Any] = None, is_solo: bool = False) -> str:
        if is_solo:
            return "В одного"
        if mode is None:
            return ""
        raw = str(mode).strip()
        if not raw:
            return ""
        return MODE_TITLES.get(raw.lower(), raw)

    @staticmethod
    def format_boss_rewards_lines(parsed: Dict[str, Any]) -> List[str]:
        cur_emoji = {
            "cigarettes": "🚬",
            "authority": "🤘",
            "rubles": "💵",
            "sugar": "🍬",
            "paper": "🧻",
            "soap": "🧼",
            "keys": "🔑",
            "respect": "⭐",
            "energy": "⚡",
            "talents": "🧠",
            "poison": "☠️",
            "knife": "🔪",
            "gunshot": "🔫",
        }
        lines: List[str] = []
        for rw in parsed.get("rewards") or []:
            em = cur_emoji.get(rw.get("currency"), "🎁")
            lines.append(f"{em} {rw.get('label')}: +{rw.get('amount')}")
        for dr in parsed.get("drops") or []:
            kind = str(dr.get("kind") or dr.get("type") or "").lower()
            em = (
                "📦" if kind == "stash"
                else ("🎒" if kind == "stashed_gear"
                else ("🏠" if kind == "room"
                else ("👕" if kind == "clothing"
                else ("🧩" if kind in ("tattoo", "complect") else "🎁"))))
            )
            title = dr.get("title") or dr.get("name") or "Предмет"
            sub = dr.get("subtitle") or dr.get("set_name")
            if sub and sub.lower() not in title.lower():
                lines.append(f"{em} {title} ({sub})")
            else:
                lines.append(f"{em} {title}")
        return lines

    @staticmethod
    def format_boss_rewards_inline(parsed: Dict[str, Any]) -> str:
        """Форматирует награды и выпавшие предметы в одну строку для Telegram."""
        parts: List[str] = []
        for rw in parsed.get("rewards") or []:
            lbl = rw.get("label") or rw.get("name") or rw.get("currency") or "Ресурс"
            amt = rw.get("amount") or 0
            parts.append(f"{lbl} +{amt}")
        for dr in parsed.get("drops") or []:
            title = dr.get("title") or dr.get("name") or "Предмет"
            sub = dr.get("subtitle")
            if sub and sub.lower() not in title.lower():
                parts.append(f"{title} ({sub})")
            else:
                parts.append(str(title))
        return ", ".join(parts)

    @classmethod
    def parse_boss_claim(
        cls,
        payload: Dict[str, Any],
        boss_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Парсинг ответа при сборе награды за босса (POST /api/boss/claim)."""
        rewards: List[Dict[str, Any]] = []
        drops: List[Dict[str, Any]] = []

        raw_rewards = payload.get("rewards") or payload.get("reward") or {}

        # 1. Если награды в виде массива [{"type": "authority", "amount": 1000}, ...]
        if isinstance(raw_rewards, list):
            for item in raw_rewards:
                if isinstance(item, dict):
                    t = item.get("type") or item.get("currency")
                    amt = item.get("amount") or item.get("value") or 0
                    c_key = cls._normalize_currency(str(t))
                    if c_key and amt > 0:
                        rewards.append({
                            "currency": c_key,
                            "label": CURRENCY_LABELS.get(c_key, c_key),
                            "amount": int(amt),
                        })
                    elif str(t).lower() in ("keys", "key", "vbox", "chest"):
                        drops.append({
                            "kind": "item",
                            "title": "Ключи" if "key" in str(t).lower() else "Сундук",
                            "subtitle": f"+{amt} шт.",
                        })

        # 2. Если награды в виде словаря
        source_dict = raw_rewards if isinstance(raw_rewards, dict) and raw_rewards else payload
        for k, v in source_dict.items():
            c_key = cls._normalize_currency(k)
            if c_key and isinstance(v, (int, float)) and v > 0:
                # Избегаем дубликатов
                if not any(r["currency"] == c_key for r in rewards):
                    rewards.append({
                        "currency": c_key,
                        "label": CURRENCY_LABELS.get(c_key, c_key),
                        "amount": int(v),
                    })

        # Также проверяем сам payload на случай, если часть валют лежит на верхнем уровне
        if source_dict is not payload:
            for k, v in payload.items():
                c_key = cls._normalize_currency(k)
                if c_key and isinstance(v, (int, float)) and v > 0:
                    if not any(r["currency"] == c_key for r in rewards):
                        rewards.append({
                            "currency": c_key,
                            "label": CURRENCY_LABELS.get(c_key, c_key),
                            "amount": int(v),
                        })

        # 3. Валюты внутри payload / data / result / rewards / globalReward / personalReward / loot
        data_sub = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        result_sub = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        rw_dict = raw_rewards if isinstance(raw_rewards, dict) else {}
        containers = [
            payload,
            data_sub,
            result_sub,
            rw_dict,
            payload.get("globalReward") if isinstance(payload.get("globalReward"), dict) else {},
            payload.get("personalReward") if isinstance(payload.get("personalReward"), dict) else {},
            payload.get("loot") if isinstance(payload.get("loot"), dict) else {},
            rw_dict.get("globalReward") if isinstance(rw_dict.get("globalReward"), dict) else {},
            rw_dict.get("personalReward") if isinstance(rw_dict.get("personalReward"), dict) else {},
            rw_dict.get("loot") if isinstance(rw_dict.get("loot"), dict) else {},
            rw_dict.get("reward") if isinstance(rw_dict.get("reward"), dict) else {},
            rw_dict.get("garant") if isinstance(rw_dict.get("garant"), dict) else {},
            rw_dict.get("guaranteed") if isinstance(rw_dict.get("guaranteed"), dict) else {},
            rw_dict.get("chance") if isinstance(rw_dict.get("chance"), dict) else {},
            rw_dict.get("bonus") if isinstance(rw_dict.get("bonus"), dict) else {},
            rw_dict.get("resources") if isinstance(rw_dict.get("resources"), dict) else {},
            data_sub.get("globalReward") if isinstance(data_sub.get("globalReward"), dict) else {},
            result_sub.get("globalReward") if isinstance(result_sub.get("globalReward"), dict) else {},
        ]
        consumed_keys = {
            "success", "result", "status", "outcome", "win", "isWin", "isVictory", "victory", "won", "isDefeat",
            "bossId", "bossName", "title", "mode", "solo", "isSolo", "sessionId", "claimId",
            "rewards", "reward", "currencies", "globalReward", "personalReward", "loot", "drops", "items",
            "droppedItems", "newItems", "resources", "garant", "guaranteed", "chance", "bonus", "stats",
            "rewardSets", "soloSetReward", "tattoo", "tattoos", "clothing", "clothes", "wardrobe",
            "complect", "complects", "room", "rooms", "camera", "chambers", "hata",
            "collectionDrop", "collections", "stashes", "nyachki", "caches",
            "hiddenItems", "stashedGear", "stashGear", "stashGearReward", "bossChestDrop",
            "zanykanny", "chests", "bauls",
            "topDamage", "rublesByDamage", "authorityByDamage", "bonusKeysByDamage",
            "playerStats", "combosForBoss", "newAchievements", "lastKillers", "lastComboSolver",
            "boss", "player", "message", "error", "time", "startedAt", "endsAt", "hp", "maxHp", "currentHp",
        }
        def _add_reward_amt(c_key: str, amt_val: Any) -> None:
            try:
                amt_int = int(float(amt_val))
            except (TypeError, ValueError):
                return
            if amt_int <= 0:
                return
            for existing_rw in rewards:
                if existing_rw["currency"] == c_key:
                    return
            rewards.append({
                "currency": c_key,
                "label": CURRENCY_LABELS.get(c_key, c_key),
                "amount": amt_int,
            })

        def _add_or_sum_reward(c_key: str, amt_val: Any) -> None:
            try:
                amt_int = int(float(amt_val))
            except (TypeError, ValueError):
                return
            if amt_int <= 0:
                return
            for existing_rw in rewards:
                if existing_rw["currency"] == c_key:
                    existing_rw["amount"] = int(existing_rw["amount"]) + amt_int
                    return
            rewards.append({
                "currency": c_key,
                "label": CURRENCY_LABELS.get(c_key, c_key),
                "amount": amt_int,
            })

        for container in containers:
            if not container:
                continue
            for block_name in ("currencies", "resources"):
                cur_block = container.get(block_name)
                if isinstance(cur_block, dict):
                    for k, v in cur_block.items():
                        c_key = cls._normalize_currency(str(k))
                        if c_key:
                            _add_reward_amt(c_key, v)
                elif isinstance(cur_block, list):
                    for item in cur_block:
                        if isinstance(item, dict):
                            t = item.get("type") or item.get("currency") or item.get("key") or item.get("name")
                            amt = item.get("amount") or item.get("value") or item.get("count") or item.get("quantity") or 0
                            c_key = cls._normalize_currency(str(t))
                            if c_key:
                                _add_reward_amt(c_key, amt)
            for k in (
                "authority", "cigarettes", "rubles", "sugar", "toiletPaper", "paper",
                "soap", "keys", "respect", "energy", "talents", "talentPoints",
                "poison", "knife", "gunshot", "experience", "exp", "signet", "signets", "chips", "votes",
            ):
                val = container.get(k)
                if val is not None and not isinstance(val, (bool, dict, list)):
                    c_key = cls._normalize_currency(k)
                    if c_key:
                        _add_reward_amt(c_key, val)

        # Доп. бонусы за урон из rewards (rublesByDamage, authorityByDamage, bonusKeysByDamage)
        for dmg_src in (payload, rw_dict, data_sub, result_sub):
            if not dmg_src:
                continue
            if dmg_src.get("rublesByDamage"):
                _add_or_sum_reward("rubles", dmg_src.get("rublesByDamage"))
            if dmg_src.get("authorityByDamage"):
                _add_or_sum_reward("authority", dmg_src.get("authorityByDamage"))
            if dmg_src.get("bonusKeysByDamage"):
                _add_or_sum_reward("keys", dmg_src.get("bonusKeysByDamage"))

        # 3.1. Нычки / предметы коллекций, заныканный шмот, баулы
        if not cls._collection_item_map:
            cls.load_collection_catalog()
        for c_src in containers:
            if not c_src:
                continue
            for stash_key in ("collectionDrop", "collections", "stashes", "nyachki", "caches"):
                raw_st = c_src.get(stash_key)
                if not raw_st:
                    continue
                st_list = raw_st if isinstance(raw_st, list) else [raw_st]
                for st in st_list:
                    if isinstance(st, (int, str)):
                        st = {"itemId": st}
                    if not isinstance(st, dict):
                        continue
                    sid = st.get("itemId") or st.get("id")
                    s_img = str(st.get("imageUrl") or st.get("image") or "").strip()
                    col_lbl = (
                        (cls._collection_item_map.get(str(sid)) if sid is not None else None)
                        or (cls._collection_image_map.get(s_img) if s_img else None)
                        or (cls._collection_image_map.get(s_img.rsplit("/", 1)[-1]) if s_img else None)
                    )
                    s_name = st.get("name") or st.get("title") or (f"Нычка: {col_lbl}" if col_lbl else f"Нычка #{sid or ''}".strip())
                    drops.append({
                        "kind": "stash",
                        "type": "stash",
                        "title": s_name if str(s_name).startswith("Нычка") else f"Нычка: {s_name}",
                        "subtitle": f"Коллекция «{col_lbl}»" if col_lbl else "Предмет коллекции",
                        "itemId": sid,
                        "imageUrl": s_img or None,
                    })

            for gear_key in ("hiddenItems", "stashedGear", "stashGear", "stashGearReward", "bossChestDrop", "zanykanny", "chests", "bauls"):
                raw_gr = c_src.get(gear_key)
                if not raw_gr:
                    continue
                gr_list = raw_gr if isinstance(raw_gr, list) else [raw_gr]
                for gr in gr_list:
                    if isinstance(gr, dict):
                        g_name = gr.get("name") or gr.get("title") or "Трофей"
                        g_cnt = gr.get("count") or gr.get("amount") or 1
                        prefix = "Баул / Сундук" if gear_key in ("chests", "bauls", "bossChestDrop") else "Заныканный шмот"
                        drops.append({
                            "kind": "stashed_gear",
                            "type": "stashed_gear",
                            "title": f"{prefix}: {g_name}",
                            "subtitle": f"x{g_cnt}" if int(g_cnt or 1) > 1 else prefix,
                            "itemId": gr.get("id") or gr.get("itemId"),
                        })
                    elif isinstance(gr, (str, int)):
                        drops.append({
                            "kind": "stashed_gear",
                            "type": "stashed_gear",
                            "title": f"Заныканный шмот: {gr}",
                            "subtitle": "Заныканный шмот",
                        })

        # 4. Разбор дропов татуировок, шмота и хат по всем контейнерам (с дедупликацией)
        cosmetic_drops: List[Dict[str, Any]] = []
        seen_cosmetics: set = set()

        def _push_cosmetic(c_item: Optional[Dict[str, Any]]) -> None:
            if not c_item:
                return
            dedup_key = (str(c_item.get("kind")), str(c_item.get("itemId") or ""), str(c_item.get("title") or ""))
            if dedup_key in seen_cosmetics:
                return
            seen_cosmetics.add(dedup_key)
            drops.append(c_item)
            cosmetic_drops.append(c_item)

        for c_src in containers:
            if not c_src:
                continue
            r_sets = c_src.get("rewardSets")
            if isinstance(r_sets, list):
                for r_set in r_sets:
                    if isinstance(r_set, dict):
                        r_kind = str(r_set.get("kind") or r_set.get("type") or "tattoo").lower()
                        _push_cosmetic(cls._build_cosmetic_drop(r_set, r_kind))
                    elif isinstance(r_set, str):
                        _push_cosmetic(cls._build_cosmetic_drop(r_set, "tattoo"))

            s_set = c_src.get("soloSetReward")
            if isinstance(s_set, dict):
                _push_cosmetic(cls._build_cosmetic_drop(s_set, str(s_set.get("kind") or s_set.get("type") or "tattoo").lower()))

            for key_name, default_kind in (
                ("tattoo", "tattoo"), ("tattoos", "tattoo"), ("newTattoos", "tattoo"),
                ("tattooId", "tattoo"), ("tattooIds", "tattoo"),
                ("clothing", "clothing"), ("clothes", "clothing"), ("cloth", "clothing"),
                ("newClothes", "clothing"), ("clothingId", "clothing"), ("clothingIds", "clothing"),
                ("room", "room"), ("rooms", "room"), ("newRooms", "room"),
                ("camera", "room"), ("cameras", "room"), ("cameraId", "room"), ("roomId", "room"),
            ):
                raw_cos = c_src.get(key_name)
                if not raw_cos:
                    continue
                cos_list = raw_cos if isinstance(raw_cos, list) else [raw_cos]
                for entry in cos_list:
                    _push_cosmetic(cls._build_cosmetic_drop(entry, default_kind))

            for list_key in ("rewards", "items", "drops", "droppedItems", "newItems"):
                raw_items = c_src.get(list_key)
                if not isinstance(raw_items, list):
                    continue
                for entry in raw_items:
                    if not isinstance(entry, dict):
                        continue
                    e_type = str(entry.get("type") or entry.get("kind") or "").lower()
                    if e_type in ("tattoo", "tattoo_set", "clothing", "clothing_set", "cloth", "wear", "room", "camera", "chamber"):
                        _push_cosmetic(cls._build_cosmetic_drop(entry, e_type))
                    elif entry.get("tattooId") is not None:
                        _push_cosmetic(cls._build_cosmetic_drop(entry, "tattoo"))
                    elif entry.get("clothingId") is not None:
                        _push_cosmetic(cls._build_cosmetic_drop(entry, "clothing"))
                    elif entry.get("cameraId") is not None or entry.get("roomId") is not None:
                        _push_cosmetic(cls._build_cosmetic_drop(entry, "room"))

        # Ключи за победу
        keys_won = payload.get("keys") or (raw_rewards.get("keys") if isinstance(raw_rewards, dict) else None)
        if isinstance(keys_won, (int, float)) and keys_won > 0:
            if not any(r["currency"] == "keys" for r in rewards):
                rewards.append({
                    "currency": "keys",
                    "label": "Ключи",
                    "amount": int(keys_won),
                })

        # Zero-loss fallback для любых новых/нестандартных полей внутри raw_rewards / loot
        for extra_src in (raw_rewards if isinstance(raw_rewards, dict) else {}, payload.get("loot") if isinstance(payload.get("loot"), dict) else {}):
            for ek, ev in extra_src.items():
                if ek in consumed_keys or cls._normalize_currency(ek):
                    continue
                if isinstance(ev, (int, float)) and ev > 0:
                    logger.warning("DropParser zero-loss fallback numeric key=%s val=%s", ek, ev)
                    drops.append({"kind": "other", "type": "other", "title": str(ek), "subtitle": f"+{int(ev)}"})
                elif isinstance(ev, dict) and ev:
                    nm = ev.get("name") or ev.get("title") or str(ek)
                    logger.warning("DropParser zero-loss fallback dict key=%s", ek)
                    drops.append({"kind": "other", "type": "other", "title": str(nm), "subtitle": str(ek)})

        # Заголовок в едином формате: "Победа над боссом: <Имя> (<Режим>)"
        mode_str = cls.format_boss_mode(mode, is_solo=bool(payload.get("isSolo") or payload.get("solo")))
        b_name = cls._resolve_boss_name(payload, boss_name)
        title = f"Победа над боссом: {b_name}" + (f" ({mode_str})" if mode_str else "")
        reward_lines = cls.format_boss_rewards_lines({"rewards": rewards, "drops": drops})
        subtitle = "Босс повержен" if reward_lines else "Нет данных о наградах от сервера"
        meta_rewards = [
            {
                "type": "currency",
                "key": rw["currency"],
                "name": rw["label"],
                "amount": rw["amount"],
                "icon": f"assets/icons/{rw['currency']}.webp",
            }
            for rw in rewards
        ] + [
            {
                "type": dr.get("kind") or dr.get("type") or "item",
                "key": str(dr.get("itemId") or dr.get("setId") or dr.get("title") or "item"),
                "name": dr.get("title") or dr.get("name") or "Предмет",
                "amount": 1,
                "icon": dr.get("imageUrl") or "",
            }
            for dr in drops
        ]

        return {
            "category": "bosses",
            "title": title,
            "subtitle": subtitle,
            "rewards": rewards,
            "drops": drops,
            "meta_json": {
                "type": "boss_victory",
                "outcome": "victory",
                "boss_name": b_name,
                "mode": mode_str or mode,
                "rewards": meta_rewards,
                "cosmetic_drops": cosmetic_drops,
                "reward_lines": reward_lines,
            },
        }

    @classmethod
    def format_space_num(cls, value: int) -> str:
        """Форматирует целое число с пробелами-разделителями разрядов."""
        return f"{int(value):,}".replace(",", " ")

    @classmethod
    def format_hp_percent(cls, remaining_hp: int, max_hp: int) -> str:
        """Форматирует процент оставшегося HP, не схлопывая малые остатки > 0 в 0%."""
        pct = round((remaining_hp / max_hp) * 100.0, 1)
        if pct < 0.1:
            return "<0.1%"
        if pct.is_integer():
            return f"{int(pct)}%"
        return f"{pct:.1f}%"

    @classmethod
    def parse_boss_defeat(
        cls,
        boss_name: Optional[str] = None,
        mode: Optional[str] = None,
        remaining_hp: Optional[int] = None,
        max_hp: Optional[int] = None,
        reason: str = "Время боя вышло, босс не повержен",
        my_damage: Optional[int] = None,
        hp_percent: Optional[float] = None,
        hp_known: Optional[bool] = None,
        personal_damage: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Формирует структурированное уведомление о поражении от босса с достоверным остатком HP."""
        mode_str = cls.format_boss_mode(mode)
        b_name = boss_name.strip() if boss_name and boss_name.strip() else "Босс"
        title = f"Поражение от босса: {b_name}" + (f" ({mode_str})" if mode_str else "")

        raw_rem = int(remaining_hp) if remaining_hp is not None else 0
        raw_max = int(max_hp) if max_hp is not None else 0
        is_valid = raw_rem > 0 and raw_max > 1 and (hp_known is not False)
        rem: Optional[int] = raw_rem if is_valid else None
        mx: Optional[int] = raw_max if raw_max > 1 else None
        pct: Optional[float] = None
        if is_valid and rem is not None and mx is not None:
            pct = float(hp_percent) if hp_percent is not None else round((rem / mx) * 100.0, 1)

        p_dmg = personal_damage if personal_damage is not None else my_damage
        p_dmg_val = int(p_dmg) if p_dmg is not None and int(p_dmg) > 0 else None

        return {
            "category": "bosses",
            "title": title,
            "subtitle": reason,
            "rewards": [],
            "drops": [],
            "meta_json": {
                "type": "boss_defeat",
                "outcome": "defeat",
                "boss_name": b_name,
                "mode": mode_str or mode,
                "remaining_hp": rem,
                "max_hp": mx,
                "boss_hp": rem,
                "hp_percent": pct,
                "hp_known": bool(is_valid),
                "personal_damage": p_dmg_val,
            },
        }

    _collection_item_map: Dict[str, str] = {}
    _collection_image_map: Dict[str, str] = {}
    _collection_catalog_loaded: bool = False
    _last_prune_ts: float = 0.0

    @classmethod
    def load_collection_catalog(cls, path: Optional[str] = None) -> None:
        """Загружает локальный каталог коллекций из JSON-файла при холодном старте."""
        if cls._collection_catalog_loaded and path is None:
            return
        cls._collection_catalog_loaded = True
        try:
            import json
            from pathlib import Path
            p = Path(path) if path else (Path(__file__).resolve().parent.parent / "storage" / "collections_catalog.json")
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                cls.update_collection_cache(data)
        except Exception as e:
            logger.debug("Не удалось загрузить каталог коллекций %s: %s", path, e)

    @classmethod
    def update_collection_cache(cls, payload: Any) -> None:
        """Индексирует каталог коллекций (/api/collection/player/full) для точных названий дропов."""
        cols = payload.get("collections", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
        for p_group in cols:
            if not isinstance(p_group, dict):
                continue
            prison_title = str(p_group.get("prison") or "").strip()
            for col in p_group.get("collections") or []:
                if not isinstance(col, dict):
                    continue
                col_name = str(col.get("name") or col.get("title") or "").strip()
                if not col_name:
                    continue
                label = f"{col_name} ({prison_title})" if prison_title else col_name
                for itm in col.get("items") or []:
                    if not isinstance(itm, dict):
                        continue
                    iid = itm.get("id")
                    if iid is not None:
                        cls._collection_item_map[str(iid)] = f"{col_name}"
                    img = str(itm.get("image") or itm.get("imageUrl") or "").strip()
                    if img:
                        cls._collection_image_map[img] = label
                        cls._collection_image_map[img.rsplit("/", 1)[-1]] = label

    @classmethod
    def parse_prison_work(
        cls,
        payload: Dict[str, Any],
        prison_name: Optional[str] = None,
        works_count: int = 1,
        is_day: bool = True,
        stage_num: Optional[int] = None,
        prison_id: Optional[int] = None,
        collection_catalog: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Парсинг ответа выполнения ходки в тюрьме (POST /api/player/prison/{id}/work)."""
        rewards: List[Dict[str, Any]] = []
        drops: List[Dict[str, Any]] = []

        cigs = payload.get("rewardCigarettes") or payload.get("cigarettes") or 0
        if cigs > 0:
            rewards.append({
                "currency": "cigarettes",
                "label": "Сигареты",
                "amount": int(cigs),
            })

        auth = payload.get("rewardAuthority") or payload.get("authority") or 0
        if auth > 0:
            rewards.append({
                "currency": "authority",
                "label": "Авторитет",
                "amount": int(auth),
            })

        rating = payload.get("rewardRating") or payload.get("rating") or payload.get("respect") or 0
        if rating > 0:
            rewards.append({
                "currency": "respect" if payload.get("respect") else "rating",
                "label": "Уважение",
                "amount": int(rating),
            })

        rubles = payload.get("rewardRubles") or payload.get("rubles") or 0
        if rubles > 0:
            rewards.append({
                "currency": "rubles",
                "label": "Рубли",
                "amount": int(rubles),
            })

        # Дропы нычек и предметов
        if payload.get("stash") or payload.get("stashes") or payload.get("stashDrop"):
            drops.append({
                "kind": "stash",
                "title": "Нычка",
                "subtitle": "Работа в тюрьме",
            })

        if payload.get("collectionDrop"):
            if collection_catalog is not None:
                cls.update_collection_cache(collection_catalog)
            elif not cls._collection_item_map:
                cls.load_collection_catalog()
            raw_cd = payload["collectionDrop"]
            cd_list = raw_cd if isinstance(raw_cd, list) else [raw_cd]
            for c_drop in cd_list:
                if isinstance(c_drop, (int, str)):
                    c_drop = {"itemId": c_drop}
                elif not isinstance(c_drop, dict):
                    c_drop = {"title": str(c_drop)}
                c_id = c_drop.get("itemId") or c_drop.get("id")
                c_img = str(c_drop.get("imageUrl") or c_drop.get("image") or "").strip()
                col_label = (
                    (cls._collection_item_map.get(str(c_id)) if c_id is not None else None)
                    or (cls._collection_image_map.get(c_img) if c_img else None)
                    or (cls._collection_image_map.get(c_img.rsplit("/", 1)[-1]) if c_img else None)
                )
                c_name = (
                    c_drop.get("title")
                    or c_drop.get("name")
                    or c_drop.get("itemName")
                    or c_drop.get("collectionName")
                    or (f"Коллекция «{col_label}»" if col_label else None)
                    or (f"Предмет коллекции ({prison_name})" if prison_name else "Предмет коллекции")
                )
                sub_txt = f"Нычка: {col_label}" if col_label else (f"Нычка ({prison_name})" if prison_name else "Нычка")
                drops.append({
                    "kind": "stash",
                    "type": "stash",
                    "title": c_name,
                    "subtitle": sub_txt,
                    "itemId": c_id,
                    "imageUrl": c_img or None,
                })

        if payload.get("weaponDrop"):
            w_drop = payload["weaponDrop"]
            w_name = w_drop.get("title") or w_drop.get("weaponType") or "Оружие"
            drops.append({
                "kind": "weapon",
                "title": w_name,
                "subtitle": "Выпало оружие",
            })

        p_name = prison_name or "Тюрьма"
        shift_word = "День" if is_day else "Ночь"
        title = f"{p_name}: {shift_word} {stage_num}" if stage_num else f"{p_name}: {shift_word}"
        return {
            "category": "prisons",
            "title": title,
            "subtitle": f"Кликов: {works_count}",
            "rewards": rewards,
            "drops": drops,
            "meta_json": {
                "type": "prison_action",
                "prison_id": prison_id,
                "prison_name": p_name,
                "is_day": bool(is_day),
                "stage": stage_num,
                "clicks": int(works_count),
            },
        }

    @classmethod
    def parse_business_collect(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Парсинг ответа сбора прибыли бизнесов (POST /api/player/business/collect)."""
        rewards: List[Dict[str, Any]] = []

        rew = payload.get("rewards") or payload
        if isinstance(rew, dict):
            for k, v in rew.items():
                c_key = cls._normalize_currency(k)
                if c_key and isinstance(v, (int, float)) and v > 0:
                    rewards.append({
                        "currency": c_key,
                        "label": CURRENCY_LABELS.get(c_key, c_key),
                        "amount": int(v),
                    })

        return {
            "category": "business",
            "title": "Сбор с тюрем",
            "subtitle": "Прибыль с бизнесов",
            "rewards": rewards,
            "drops": [],
        }

    @classmethod
    def parse_kolsik_roll(cls, payload: Dict[str, Any], currency: str = "paper") -> Dict[str, Any]:
        """Парсинг результата прокрутки у Кольщика."""
        drops: List[Dict[str, Any]] = []
        reward = payload.get("reward") or payload.get("tattoo") or payload
        t_name = reward.get("name") or reward.get("title") or "Наколка"
        t_id = reward.get("id") or reward.get("tattooId")
        sub = f"ID тату: {t_id}" if t_id else "Новая татуировка"
        drops.append({
            "kind": "tattoo",
            "title": t_name,
            "subtitle": sub,
        })
        cur_name = "туалетную бумагу" if currency == "paper" else "рубли"
        return {
            "category": "other",
            "title": "Кольщик (Наколка)",
            "subtitle": f"Набита наколка за {cur_name}",
            "rewards": [],
            "drops": drops,
        }

    @classmethod
    def parse_monthly_claim(cls, payload: Dict[str, Any], tier: Optional[Any] = None) -> Dict[str, Any]:
        """Парсинг наград из ответа сбора Месячных делюг."""
        rewards: List[Dict[str, Any]] = []
        drops: List[Dict[str, Any]] = []

        raw_rewards = payload.get("rewards") or payload.get("reward") or payload
        if isinstance(raw_rewards, list):
            for item in raw_rewards:
                if isinstance(item, dict):
                    t = item.get("type") or item.get("currency")
                    amt = item.get("amount") or item.get("value") or 0
                    c_key = cls._normalize_currency(str(t))
                    if c_key and amt > 0:
                        rewards.append({
                            "currency": c_key,
                            "label": CURRENCY_LABELS.get(c_key, c_key),
                            "amount": int(amt),
                        })
                    else:
                        drops.append({
                            "kind": "item",
                            "title": item.get("name") or str(t),
                            "subtitle": f"+{amt}" if amt else "Награда",
                        })
        elif isinstance(raw_rewards, dict):
            for k, v in raw_rewards.items():
                c_key = cls._normalize_currency(k)
                if c_key and isinstance(v, (int, float)) and v > 0:
                    rewards.append({
                        "currency": c_key,
                        "label": CURRENCY_LABELS.get(c_key, c_key),
                        "amount": int(v),
                    })

        sub = f"Награда за этап {tier}" if tier is not None else "Сбор наград за выполненные этапы"
        return {
            "category": "other",
            "title": "Месячные делюги",
            "subtitle": sub,
            "rewards": rewards,
            "drops": drops,
        }

    @classmethod
    def parse_other(
        cls,
        title: str,
        subtitle: Optional[str] = None,
        rewards: Optional[List[Dict[str, Any]]] = None,
        drops: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Универсальное формирование карточки для категории 'other'."""
        return {
            "category": "other",
            "title": title,
            "subtitle": subtitle,
            "rewards": rewards or [],
            "drops": drops or [],
        }

    @classmethod
    async def save_notification(
        cls,
        account_id: int,
        parsed_data: Dict[str, Any],
        db_engine: Optional[Any] = None,
    ) -> Notification:
        """Сохранение уведомления в базу данных с дедупликацией по event_key."""
        event_key = parsed_data.get("event_key")
        async with get_session(db_engine) as session:
            if event_key:
                from sqlalchemy import select
                existing = await session.scalar(
                    select(Notification).where(
                        Notification.account_id == account_id,
                        Notification.event_key == event_key,
                    )
                )
                if existing:
                    logger.debug("Пропуск дубликата уведомления: event_key=%s", event_key)
                    return existing

            notif = Notification(
                account_id=account_id,
                category=parsed_data.get("category", "other"),
                title=parsed_data.get("title", "Событие"),
                subtitle=parsed_data.get("subtitle"),
                rewards=parsed_data.get("rewards", []),
                drops=parsed_data.get("drops", []),
                meta_json=parsed_data.get("meta_json") or {},
                event_key=event_key,
                is_read=False,
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)

        import time
        now_ts = time.monotonic()
        if db_engine is not None and (now_ts - cls._last_prune_ts) >= 600.0:
            cls._last_prune_ts = now_ts
            try:
                from core.config import settings
                from core.database import prune_old_notifications
                await prune_old_notifications(db_engine, days=settings.NOTIFICATIONS_RETENTION_DAYS)
            except Exception as pe:
                logger.debug("Ошибка фоновой очистки старых уведомлений: %s", pe)

        return notif
