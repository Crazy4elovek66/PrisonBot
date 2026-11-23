import logging
from typing import Dict, Any, List, Optional
from core.database import get_session
from core.models import Notification

logger = logging.getLogger(__name__)

CURRENCY_LABELS = {
    "authority": "Авторитет",
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
}


class DropParser:
    """
    Универсальный парсер наград, валют, нычек, татуировок и предметов
    из сырых JSON-ответов сервера.
    """

    @staticmethod
    def _normalize_currency(key: str) -> Optional[str]:
        k = key.lower().strip()
        if k.startswith("reward"):
            k = k[6:].strip()
        if k in ("authority", "auth"):
            return "authority"
        if k in ("cigarettes", "cigs"):
            return "cigarettes"
        if k in ("sugar",):
            return "sugar"
        if k in ("rubles", "rub"):
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

        # 3. Валюты внутри payload.get("currencies")
        currencies = payload.get("currencies") or (raw_rewards.get("currencies") if isinstance(raw_rewards, dict) else None)
        if isinstance(currencies, dict):
            for k, v in currencies.items():
                c_key = cls._normalize_currency(k)
                if c_key and isinstance(v, (int, float)) and v > 0:
                    if not any(r["currency"] == c_key for r in rewards):
                        rewards.append({
                            "currency": c_key,
                            "label": CURRENCY_LABELS.get(c_key, c_key),
                            "amount": int(v),
                        })

        # 4. Разбор дропов татуировок и сетов (rewardSets, soloSetReward, tattoo)
        reward_sets = payload.get("rewardSets") or (raw_rewards.get("rewardSets") if isinstance(raw_rewards, dict) else None)
        if isinstance(reward_sets, list):
            for r_set in reward_sets:
                if isinstance(r_set, dict):
                    title = r_set.get("title") or r_set.get("name") or "Комплект татуировок"
                    tattoo_name = r_set.get("tattoo") or r_set.get("item") or "Элемент тату"
                    owned = r_set.get("owned", 1)
                    total = r_set.get("total", 20)
                    drops.append({
                        "kind": "tattoo",
                        "title": title if title.startswith("Комплект") else f'Комплект "{title}"',
                        "subtitle": f"{tattoo_name} ({owned}/{total} сета)",
                    })
                elif isinstance(r_set, str):
                    drops.append({
                        "kind": "tattoo",
                        "title": r_set,
                        "subtitle": "Новая татуировка",
                    })

        solo_set = payload.get("soloSetReward") or (raw_rewards.get("soloSetReward") if isinstance(raw_rewards, dict) else None)
        if isinstance(solo_set, dict):
            title = solo_set.get("title") or solo_set.get("name") or 'Комплект "Биомеханика"'
            tattoo_name = solo_set.get("tattoo") or solo_set.get("item") or "Элемент сета"
            owned = solo_set.get("owned", 1)
            total = solo_set.get("total", 20)
            drops.append({
                "kind": "tattoo",
                "title": title if title.startswith("Комплект") else f'Комплект "{title}"',
                "subtitle": f"{tattoo_name} ({owned}/{total} сета)",
            })

        tattoo_item = payload.get("tattoo") or (raw_rewards.get("tattoo") if isinstance(raw_rewards, dict) else None)
        if isinstance(tattoo_item, dict):
            t_title = tattoo_item.get("set") or tattoo_item.get("title") or 'Комплект "Биомеханика"'
            t_name = tattoo_item.get("name") or "Татуировка"
            drops.append({
                "kind": "tattoo",
                "title": t_title if t_title.startswith("Комплект") else f'Комплект "{t_title}"',
                "subtitle": t_name,
            })
        elif isinstance(tattoo_item, str):
            drops.append({
                "kind": "tattoo",
                "title": tattoo_item if tattoo_item.startswith("Комплект") else f'Комплект "{tattoo_item}"',
                "subtitle": "Татуировка",
            })

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
        }
        mode_str = mode_titles.get(mode, mode) if mode else ""
        b_name = boss_name or "Босс"
        title = f"Босс повержен: {b_name}" + (f" - {mode_str}" if mode_str else "")

        return {
            "category": "bosses",
            "title": title,
            "subtitle": "Победа в бою",
            "rewards": rewards,
            "drops": drops,
        }

    @classmethod
    def parse_prison_work(
        cls,
        payload: Dict[str, Any],
        prison_name: Optional[str] = None,
        works_count: int = 1,
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

        rating = payload.get("rewardRating") or payload.get("rating") or 0
        if rating > 0:
            rewards.append({
                "currency": "rating",
                "label": "Уважение",
                "amount": int(rating),
            })

        # Дропы нычек и предметов
        if payload.get("stash") or payload.get("stashes") or payload.get("stashDrop"):
            drops.append({
                "kind": "stash",
                "title": "Нычка",
                "subtitle": "Работа в тюрьме",
            })

        if payload.get("collectionDrop"):
            c_drop = payload["collectionDrop"]
            c_name = c_drop.get("title") or c_drop.get("name") or "Коллекционный предмет"
            drops.append({
                "kind": "item",
                "title": c_name,
                "subtitle": "Предмет коллекции",
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
        return {
            "category": "prisons",
            "title": f"Ходки: {p_name}",
            "subtitle": f"Кликов: {works_count}",
            "rewards": rewards,
            "drops": drops,
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
                event_key=event_key,
                is_read=False,
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)
            return notif
