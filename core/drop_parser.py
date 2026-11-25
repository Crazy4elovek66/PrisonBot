import logging
from typing import Dict, Any, List, Optional
from core.database import get_session
from core.models import Notification

logger = logging.getLogger(__name__)

CURRENCY_LABELS = {
    "authority": "Авторитет",
    "respect": "Уважение",
    "cigarettes": "Сигареты",
    "sugar": "Сахар",
    "rubles": "Рубли",
    "paper": "Бумага",
    "soap": "Мыло",
    "keys": "Ключи",
    "energy": "Энергия",
    "biceps": "Бицуха",
    "intellect": "Интеллект",
    "rating": "Уважение",
    "stash": "Нычка",
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
        return None

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

        # 3. Валюты внутри payload.get("currencies") / globalReward / personalReward (dict или list)
        for container in (
            payload,
            raw_rewards if isinstance(raw_rewards, dict) else {},
            payload.get("globalReward") if isinstance(payload.get("globalReward"), dict) else {},
            payload.get("personalReward") if isinstance(payload.get("personalReward"), dict) else {},
            payload.get("loot") if isinstance(payload.get("loot"), dict) else {},
        ):
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
            for k in ("authority", "cigarettes", "rubles", "sugar", "toiletPaper", "paper", "soap", "keys", "respect", "energy"):
                val = container.get(k)
                if isinstance(val, (int, float)) and val > 0:
                    c_key = cls._normalize_currency(k)
                    if c_key and not any(r["currency"] == c_key for r in rewards):
                        rewards.append({
                            "currency": c_key,
                            "label": CURRENCY_LABELS.get(c_key, c_key),
                            "amount": int(val),
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

        # Заголовок
        mode_titles = {
            "pacansky": "Пацанский",
            "blotnoy": "Блатной",
            "avtoritetny": "Авторитетный",
            "vorovskoy": "Воровской",
            "odin": "В одного",
            "brigade": "Бригадный",
        }
        mode_str = mode_titles.get(mode, mode) if mode else ""
        b_name = cls._resolve_boss_name(payload, boss_name)
        title = f"Босс повержен: {b_name}" + (f" - {mode_str}" if mode_str else "")

        return {
            "category": "bosses",
            "title": title,
            "subtitle": "Победа в бою",
            "rewards": rewards,
            "drops": drops,
            "meta_json": {
                "type": "boss_victory",
                "outcome": "victory",
                "boss_name": b_name,
                "mode": mode_str or mode,
                "cosmetic_drops": cosmetic_drops,
            },
        }

    @classmethod
    def parse_boss_defeat(
        cls,
        boss_name: Optional[str] = None,
        mode: Optional[str] = None,
        remaining_hp: int = 0,
        max_hp: int = 1,
    ) -> Dict[str, Any]:
        """Формирует структурированное уведомление о поражении от босса с полоской остатка HP."""
        mode_titles = {
            "pacansky": "Пацанский",
            "blotnoy": "Блатной",
            "avtoritetny": "Авторитетный",
            "vorovskoy": "Воровской",
            "odin": "В одного",
            "brigade": "Бригадный",
        }
        mode_str = mode_titles.get(mode, mode) if mode else ""
        b_name = boss_name.strip() if boss_name and boss_name.strip() else "Босс"
        title = f"Поражение от босса: {b_name}" + (f" - {mode_str}" if mode_str else "")
        rem = max(0, int(remaining_hp or 0))
        mx = max(1, int(max_hp or rem or 1))
        return {
            "category": "bosses",
            "title": title,
            "subtitle": "Бой завершен без победы",
            "rewards": [],
            "drops": [],
            "meta_json": {
                "type": "boss_defeat",
                "outcome": "defeat",
                "boss_name": b_name,
                "mode": mode_str or mode,
                "remaining_hp": rem,
                "max_hp": mx,
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
                    "kind": "item",
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
