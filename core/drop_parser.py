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
        if k in ("paper", "toiletpaper"):
            return "paper"
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
            kind = str(dr.get("kind") or "").lower()
            em = "📦" if kind == "stash" else ("🎒" if kind == "stashed_gear" else ("🏠" if kind == "room" else ("🧩" if kind in ("tattoo", "clothing", "complect") else "🎁")))
            title = dr.get("title") or dr.get("name") or "Предмет"
            sub = dr.get("subtitle")
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

        # 3. Валюты внутри payload.get("currencies") / data / result / globalReward / personalReward / loot
        data_sub = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        result_sub = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        containers = [
            payload,
            data_sub,
            result_sub,
            raw_rewards if isinstance(raw_rewards, dict) else {},
            payload.get("globalReward") if isinstance(payload.get("globalReward"), dict) else {},
            payload.get("personalReward") if isinstance(payload.get("personalReward"), dict) else {},
            payload.get("loot") if isinstance(payload.get("loot"), dict) else {},
        ]
        consumed_keys = {
            "success", "result", "status", "outcome", "win", "isWin", "isDefeat",
            "bossId", "bossName", "title", "mode", "solo", "isSolo", "sessionId", "claimId",
            "rewards", "reward", "currencies", "globalReward", "personalReward", "loot", "drops", "items",
            "rewardSets", "soloSetReward", "tattoo", "tattoos", "clothing", "clothes", "wardrobe",
            "complect", "complects", "room", "rooms", "camera", "chambers", "hata",
            "collectionDrop", "collections", "stashes", "nyachki", "caches",
            "hiddenItems", "stashedGear", "stashGear", "zanykanny", "chests", "bauls",
            "boss", "player", "message", "error", "time", "startedAt", "endsAt", "hp", "maxHp", "currentHp",
        }
        for container in containers:
            if not container:
                continue
            cur_block = container.get("currencies")
            if isinstance(cur_block, dict):
                for k, v in cur_block.items():
                    c_key = cls._normalize_currency(k)
                    if c_key and isinstance(v, (int, float)) and v > 0:
                        if not any(r["currency"] == c_key for r in rewards):
                            rewards.append({
                                "currency": c_key,
                                "label": CURRENCY_LABELS.get(c_key, c_key),
                                "amount": int(v),
                            })
            elif isinstance(cur_block, list):
                for item in cur_block:
                    if isinstance(item, dict):
                        t = item.get("type") or item.get("currency")
                        amt = item.get("amount") or item.get("value") or 0
                        c_key = cls._normalize_currency(str(t))
                        if c_key and isinstance(amt, (int, float)) and amt > 0:
                            if not any(r["currency"] == c_key for r in rewards):
                                rewards.append({
                                    "currency": c_key,
                                    "label": CURRENCY_LABELS.get(c_key, c_key),
                                    "amount": int(amt),
                                })
            for k in (
                "authority", "cigarettes", "rubles", "sugar", "toiletPaper", "paper",
                "soap", "keys", "respect", "energy", "talents", "talentPoints",
                "poison", "knife", "gunshot",
            ):
                val = container.get(k)
                if isinstance(val, (int, float)) and val > 0:
                    c_key = cls._normalize_currency(k)
                    if c_key and not any(r["currency"] == c_key for r in rewards):
                        rewards.append({
                            "currency": c_key,
                            "label": CURRENCY_LABELS.get(c_key, c_key),
                            "amount": int(val),
                        })

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

            for gear_key in ("hiddenItems", "stashedGear", "stashGear", "zanykanny", "chests", "bauls"):
                raw_gr = c_src.get(gear_key)
                if not raw_gr:
                    continue
                gr_list = raw_gr if isinstance(raw_gr, list) else [raw_gr]
                for gr in gr_list:
                    if isinstance(gr, dict):
                        g_name = gr.get("name") or gr.get("title") or "Трофей"
                        g_cnt = gr.get("count") or gr.get("amount") or 1
                        prefix = "Баул / Сундук" if gear_key in ("chests", "bauls") else "Заныканный шмот"
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

        # 4. Разбор дропов татуировок и сетов (rewardSets, soloSetReward, tattoo, clothing, room)
        cosmetic_drops: List[Dict[str, Any]] = []
        reward_sets = payload.get("rewardSets") or (raw_rewards.get("rewardSets") if isinstance(raw_rewards, dict) else None)
        if isinstance(reward_sets, list):
            for r_set in reward_sets:
                if isinstance(r_set, dict):
                    title = r_set.get("title") or r_set.get("name") or "Комплект татуировок"
                    tattoo_name = r_set.get("tattoo") or r_set.get("item") or "Элемент тату"
                    owned = r_set.get("owned", 1)
                    total = r_set.get("total", 20)
                    r_kind = str(r_set.get("kind") or r_set.get("type") or "tattoo")
                    c_item = {
                        "kind": r_kind,
                        "type": "clothing" if "cloth" in r_kind.lower() else ("room" if "room" in r_kind.lower() or "cam" in r_kind.lower() else "tattoo"),
                        "itemId": r_set.get("itemId") or r_set.get("id"),
                        "setId": r_set.get("setId") or title,
                        "name": tattoo_name if tattoo_name != "Элемент тату" else title,
                        "imageUrl": r_set.get("imageUrl") or r_set.get("previewUrl") or "",
                        "title": title if title.startswith("Комплект") else f'Комплект "{title}"',
                        "subtitle": f"{tattoo_name} ({owned}/{total} сета)",
                    }
                    drops.append(c_item)
                    cosmetic_drops.append(c_item)
                elif isinstance(r_set, str):
                    c_item = {
                        "kind": "tattoo",
                        "type": "tattoo",
                        "setId": r_set,
                        "name": r_set,
                        "title": r_set,
                        "subtitle": "Новая татуировка",
                    }
                    drops.append(c_item)
                    cosmetic_drops.append(c_item)

        solo_set = payload.get("soloSetReward") or (raw_rewards.get("soloSetReward") if isinstance(raw_rewards, dict) else None)
        if isinstance(solo_set, dict):
            title = solo_set.get("title") or solo_set.get("name") or 'Комплект "Биомеханика"'
            tattoo_name = solo_set.get("tattoo") or solo_set.get("item") or "Элемент сета"
            owned = solo_set.get("owned", 1)
            total = solo_set.get("total", 20)
            c_item = {
                "kind": "tattoo",
                "type": "tattoo",
                "itemId": solo_set.get("itemId") or solo_set.get("id"),
                "setId": solo_set.get("setId") or title,
                "name": tattoo_name if tattoo_name != "Элемент сета" else title,
                "imageUrl": solo_set.get("imageUrl") or solo_set.get("previewUrl") or "",
                "title": title if title.startswith("Комплект") else f'Комплект "{title}"',
                "subtitle": f"{tattoo_name} ({owned}/{total} сета)",
            }
            drops.append(c_item)
            cosmetic_drops.append(c_item)

        tattoo_item = payload.get("tattoo") or (raw_rewards.get("tattoo") if isinstance(raw_rewards, dict) else None)
        if isinstance(tattoo_item, dict):
            t_title = tattoo_item.get("set") or tattoo_item.get("title") or 'Комплект "Биомеханика"'
            t_name = tattoo_item.get("name") or "Татуировка"
            c_item = {
                "kind": "tattoo",
                "type": "tattoo",
                "itemId": tattoo_item.get("id") or tattoo_item.get("tattooId"),
                "setId": tattoo_item.get("setId") or t_title,
                "name": t_name,
                "imageUrl": tattoo_item.get("imageUrl") or tattoo_item.get("previewUrl") or "",
                "title": t_title if t_title.startswith("Комплект") else f'Комплект "{t_title}"',
                "subtitle": t_name,
            }
            drops.append(c_item)
            cosmetic_drops.append(c_item)
        elif isinstance(tattoo_item, str):
            c_item = {
                "kind": "tattoo",
                "type": "tattoo",
                "setId": tattoo_item,
                "name": tattoo_item,
                "title": tattoo_item if tattoo_item.startswith("Комплект") else f'Комплект "{tattoo_item}"',
                "subtitle": "Татуировка",
            }
            drops.append(c_item)
            cosmetic_drops.append(c_item)

        for cos_key, cos_type, cos_label in (
            ("clothing", "clothing", "Шмот"),
            ("room", "room", "Хата"),
            ("camera", "room", "Хата"),
        ):
            cos_obj = payload.get(cos_key) or (raw_rewards.get(cos_key) if isinstance(raw_rewards, dict) else None)
            if isinstance(cos_obj, dict):
                nm = cos_obj.get("name") or cos_obj.get("title") or cos_label
                c_item = {
                    "kind": cos_type,
                    "type": cos_type,
                    "itemId": cos_obj.get("id"),
                    "setId": cos_obj.get("setName") or cos_obj.get("setId"),
                    "name": nm,
                    "imageUrl": cos_obj.get("imageUrl") or cos_obj.get("previewUrl") or "",
                    "title": nm,
                    "subtitle": cos_label,
                }
                drops.append(c_item)
                cosmetic_drops.append(c_item)

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
        subtitle = "Босс повержен" if reward_lines else "Награда получена"
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
