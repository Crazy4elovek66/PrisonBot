import asyncio
import logging
import math
from typing import Dict, Any, List, Optional, Set
from client.http_client import GameHttpClient

logger = logging.getLogger(__name__)


def calculate_level_from_authority(authority: int) -> int:
    """
    Расчет игрового уровня арестанта по формуле оригинальной игры (Module 415 bundle.js):
    D = 1600 + 80 * max(0, authority)
    level = max(1, floor((-40 + sqrt(D)) / 40))
    """
    auth = max(0, int(authority or 0))
    disc = 1600 + 80 * auth
    if disc < 0:
        return 1
    lvl = int((-40 + math.sqrt(disc)) / 40)
    return max(1, lvl)


class SocialAPI:
    """
    Методы взаимодействия с социальными функциями и регулярными событиями:
    - Подарки (GET /api/gifts/inbox, POST /api/gifts/claim, POST /api/gifts/send)
    - Друзья (GET /api/friendship/requests, GET /api/friendship/accept-request, GET /api/friendship/list)
    - Ежемесячный календарь (GET /api/monthly/state, POST /api/monthly/claim)
    - Дворовые игры (GET /api/yard/games, POST /api/kolsik/roll-paper)
    """

    def __init__(self, http_client: GameHttpClient):
        self.http = http_client

    async def get_gifts_inbox(self) -> Dict[str, Any]:
        """Получение списка входящих подарков."""
        resp = await self.http.get("/api/gifts/inbox")
        resp.raise_for_status()
        return resp.json()

    # Псевдоним для совместимости
    get_inbox_gifts = get_gifts_inbox

    async def claim_gift(self, gift_id: Any) -> Dict[str, Any]:
        """Сбор входящего подарка."""
        resp = await self.http.post("/api/gifts/claim", json={"giftId": gift_id})
        resp.raise_for_status()
        return resp.json()

    async def get_gifts_stats(self) -> Dict[str, Any]:
        """Получение статистики подарков."""
        resp = await self.http.get("/api/gifts/stats")
        resp.raise_for_status()
        return resp.json()

    async def send_gift(
        self,
        to_user_id: int,
        tier: int = 1,
        kind: str = "chips",
        message: str = "",
    ) -> Dict[str, Any]:
        """Отправка подарка другу."""
        payload = {
            "toUserId": to_user_id,
            "tier": tier,
            "kind": kind,
            "message": message,
        }
        resp = await self.http.post("/api/gifts/send", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_friend_requests(self, page: int = 0, page_size: int = 50) -> Any:
        """Получение списка входящих заявок в друзья."""
        url = f"/api/friendship/requests?page={page}&pageSize={page_size}"
        resp = await self.http.get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_enriched_friend_requests(
        self,
        page: int = 0,
        page_size: int = 50,
        player_api: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Запрашивает список входящих заявок в друзья (GET /api/friendship/requests)
        и обогащает профили кандидатов ключевыми характеристиками:
        level, authority, biceps, talents, knifeDamage, poisonDamage, gunshotDamage, totalDamage.
        """
        raw_res = await self.get_friend_requests(page=page, page_size=page_size)
        raw_list = (
            raw_res
            if isinstance(raw_res, list)
            else raw_res.get("requests", [])
            if isinstance(raw_res, dict)
            else []
        )

        sem = asyncio.Semaphore(5)

        async def _enrich_candidate(c: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(c, dict):
                return {}

            uid = c.get("userId") or c.get("fromUserId") or c.get("id")
            nick = c.get("nickname") or c.get("name") or (f"Игрок {uid}" if uid else "Арестант")
            photo = c.get("photoUrl") or c.get("avatarUrl") or c.get("photo")

            wep_dmg = c.get("weaponDamage") or c.get("WeaponDamage") or {}
            poi_dmg = int(wep_dmg.get("poison") or wep_dmg.get("Poison") or c.get("poisonDamage") or 0)
            gun_dmg = int(wep_dmg.get("gunshot") or wep_dmg.get("Gunshot") or c.get("gunshotDamage") or 0)
            kni_dmg = int(wep_dmg.get("knife") or wep_dmg.get("Knife") or c.get("knifeDamage") or 0)
            tot_dmg = int(c.get("totalDamage") or (kni_dmg + poi_dmg + gun_dmg) or 0)

            talents = int(
                c.get("talents")
                or c.get("talentsCount")
                or c.get("TalentsCount")
                or 0
            )
            level = int(c.get("level") or c.get("lvl") or 0)
            authority = int(c.get("authority") or 0)
            biceps_raw = c.get("biceps")
            biceps: Optional[int] = int(biceps_raw) if (biceps_raw is not None and int(biceps_raw) > 0) else None

            # Если базовые характеристики (уровень, авторитет, бицуха, таланты или урон) не заданы в заявке,
            # дозагружаем через /api/player/view/{userId}
            if uid and (level == 0 or authority == 0 or biceps is None or talents == 0 or tot_dmg == 0):
                try:
                    async with sem:
                        if player_api:
                            p_view = await player_api.get_player_view(uid)
                        else:
                            resp = await self.http.get(f"/api/player/view/{uid}")
                            p_view = resp.json() if resp.status_code == 200 else {}

                        p_data = p_view.get("data") if isinstance(p_view.get("data"), dict) else p_view
                        if isinstance(p_data, dict):
                            if not authority:
                                authority = int(
                                    p_data.get("resources", {}).get("authority")
                                    or p_data.get("authority")
                                    or 0
                                )
                            if not level:
                                level = int(
                                    p_data.get("level")
                                    or p_data.get("lvl")
                                    or p_data.get("resources", {}).get("level")
                                    or 0
                                )
                            if biceps is None:
                                raw_b = (
                                    p_data.get("biceps")
                                    or p_data.get("stats", {}).get("biceps")
                                    or p_data.get("resources", {}).get("biceps")
                                    or p_data.get("profile", {}).get("biceps")
                                    or p_data.get("user", {}).get("biceps")
                                )
                                if raw_b is not None and int(raw_b) > 0:
                                    biceps = int(raw_b)
                            if not talents:
                                talents = int(
                                    p_data.get("talents")
                                    or p_data.get("talentsCount")
                                    or p_data.get("TalentsCount")
                                    or p_data.get("stats", {}).get("talents")
                                    or 0
                                )
                            ext_wep = (
                                p_data.get("weaponDamage")
                                or p_data.get("WeaponDamage")
                                or p_data.get("stats", {}).get("weaponDamage")
                                or {}
                            )
                            if not poi_dmg:
                                poi_dmg = int(
                                    ext_wep.get("poison")
                                    or ext_wep.get("Poison")
                                    or p_data.get("poisonDamage")
                                    or 0
                                )
                            if not gun_dmg:
                                gun_dmg = int(
                                    ext_wep.get("gunshot")
                                    or ext_wep.get("Gunshot")
                                    or p_data.get("gunshotDamage")
                                    or 0
                                )
                            if not kni_dmg:
                                kni_dmg = int(
                                    ext_wep.get("knife")
                                    or ext_wep.get("Knife")
                                    or p_data.get("knifeDamage")
                                    or 0
                                )
                            ext_tot = int(
                                p_data.get("totalDamage")
                                or p_data.get("TotalDamage")
                                or (kni_dmg + poi_dmg + gun_dmg)
                                or 0
                            )
                            if not tot_dmg or tot_dmg == 0:
                                tot_dmg = ext_tot
                            if not nick or nick.startswith("Игрок"):
                                ext_nick = p_data.get("nickname") or p_data.get("name")
                                if ext_nick:
                                    nick = ext_nick
                            if not photo:
                                photo = p_data.get("photoUrl") or p_data.get("avatarUrl") or p_data.get("photo")
                except Exception as e:
                    logger.debug(f"Не удалось обогатить профиль игрока {uid}: {e}")

            # Если уровень не пришел напрямую, рассчитываем по игровому алгоритму от авторитета
            if level == 0 and authority > 0:
                level = calculate_level_from_authority(authority)

            return {
                "userId": uid,
                "nickname": nick,
                "photoUrl": photo,
                "level": level,
                "authority": authority,
                "biceps": biceps,
                "talents": talents,
                "knifeDamage": kni_dmg,
                "poisonDamage": poi_dmg,
                "gunshotDamage": gun_dmg,
                "totalDamage": tot_dmg if tot_dmg > 0 else (kni_dmg + poi_dmg + gun_dmg),
            }

        tasks = [_enrich_candidate(c) for c in raw_list]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for item in enriched:
            if isinstance(item, dict) and item.get("userId") is not None:
                results.append(item)
        return results

    async def accept_friend(self, from_user_id: int) -> Dict[str, Any]:
        """Принятие заявки в друзья (POST /api/friendship/accept-request?fromUserId={from_user_id})."""
        url = f"/api/friendship/accept-request?fromUserId={from_user_id}"
        resp = await self.http.post(url)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"success": True}

    async def decline_friend(self, from_user_id: int) -> Dict[str, Any]:
        """Отклонение заявки в друзья (POST /api/friendship/decline-request?fromUserId={from_user_id})."""
        url = f"/api/friendship/decline-request?fromUserId={from_user_id}"
        resp = await self.http.post(url)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"success": True}

    async def get_friend_profiles(self, page: int = 0, page_size: int = 50) -> Any:
        """Получение профилей друзей."""
        url = f"/api/friendship/profiles?page={page}&pageSize={page_size}"
        resp = await self.http.get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_friends_list(self) -> Any:
        """Получение списка друзей."""
        resp = await self.http.get("/api/friendship/list")
        resp.raise_for_status()
        return resp.json()

    async def get_all_friend_ids(self) -> Set[int]:
        """
        Корректно разбирает все возможные форматы ответа GET /api/friendship/list:
        - массив int: [9000000000147562, ...]
        - массив dict: [{"userId": ...}, {"id": ...}]
        - объект: {"friends": [...], "total": N} или {"items": [...]}
        Возвращает множество int ID друзей.
        """
        try:
            raw = await self.get_friends_list()
        except Exception as e:
            logger.warning(f"Ошибка получения списка друзей: {e}")
            return set()

        items = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("friends") or raw.get("items") or raw.get("userIds") or []

        friend_ids: Set[int] = set()
        for item in items:
            if isinstance(item, (int, str)):
                try:
                    friend_ids.add(int(item))
                except (ValueError, TypeError):
                    pass
            elif isinstance(item, dict):
                uid = item.get("userId") or item.get("id") or item.get("friendUserId")
                if uid is not None:
                    try:
                        friend_ids.add(int(uid))
                    except (ValueError, TypeError):
                        pass
        return friend_ids

    async def get_all_friend_profiles(self, page_size: int = 100, max_pages: int = 50) -> List[Dict[str, Any]]:
        """
        Итерируется по page = 0, 1, ... через GET /api/friendship/profiles?page={page}&pageSize={page_size}
        до получения пустой страницы или < page_size элементов (с паузой 0.15-0.3с между страницами),
        возвращая полный список всех профилей друзей.
        """
        all_profiles: List[Dict[str, Any]] = []
        for page in range(max_pages):
            try:
                res = await self.get_friend_profiles(page=page, page_size=page_size)
            except Exception as e:
                logger.warning(f"Ошибка пагинации профилей друзей на странице {page}: {e}")
                break

            items = (
                res
                if isinstance(res, list)
                else res.get("profiles") or res.get("items") or []
                if isinstance(res, dict)
                else []
            )

            if not items:
                break

            for p in items:
                if isinstance(p, dict) and p.get("userId") is not None:
                    all_profiles.append(p)

            if len(items) < page_size:
                break

            await asyncio.sleep(0.15)

        return all_profiles

    async def send_friend_request(self, to_user_id: int) -> Dict[str, Any]:
        """Отправка заявки в друзья (POST /api/friendship/send-request?toUserId={to_user_id})."""
        url = f"/api/friendship/send-request?toUserId={to_user_id}"
        resp = await self.http.post(url)
        if resp.status_code in (200, 204):
            try:
                return resp.json()
            except Exception:
                return {"success": True}
        resp.raise_for_status()
        return resp.json()

    async def remove_friend(self, friend_user_id: int) -> Dict[str, Any]:
        """Удаление из друзей (POST /api/friendship/remove-friend?friendUserId={friend_user_id})."""
        url = f"/api/friendship/remove-friend?friendUserId={friend_user_id}"
        resp = await self.http.post(url)
        if resp.status_code in (200, 204):
            try:
                return resp.json()
            except Exception:
                return {"success": True}
        resp.raise_for_status()
        return resp.json()

    async def get_weekly_top(self, limit: int = 100) -> Dict[str, Any]:
        """Получение еженедельного топа игроков по урону (GET /api/weekly-top/top?limit={limit})."""
        resp = await self.http.get(f"/api/weekly-top/top?limit={limit}")
        resp.raise_for_status()
        return resp.json()

    async def get_top_achievements(self, limit: int = 100) -> Dict[str, Any]:
        """Получение топа игроков по достижениям (GET /api/weekly-top/achievements?limit={limit})."""
        resp = await self.http.get(f"/api/weekly-top/achievements?limit={limit}")
        resp.raise_for_status()
        return resp.json()

    async def get_guild_members(self, guild_id: int) -> Dict[str, Any]:
        """Получение состава бригады (GET /api/guild/{guild_id}/members)."""
        resp = await self.http.get(f"/api/guild/{guild_id}/members")
        resp.raise_for_status()
        return resp.json()

    async def get_recruitment_list(self, limit: int = 100) -> Dict[str, Any]:
        """Получение объявлений о наборе в бригады (GET /api/guild/recruitment/list?limit={limit})."""
        resp = await self.http.get(f"/api/guild/recruitment/list?limit={limit}")
        resp.raise_for_status()
        return resp.json()

    async def get_monthly_state(self) -> Dict[str, Any]:
        """Получение состояния ежемесячного календаря наград."""
        resp = await self.http.get("/api/monthly/state")
        resp.raise_for_status()
        return resp.json()

    async def claim_monthly_reward(self, tier: int) -> Dict[str, Any]:
        """Сбор награды ежемесячного календаря."""
        resp = await self.http.post("/api/monthly/claim", json={"Tier": tier})
        resp.raise_for_status()
        return resp.json()

    async def get_yard_games(self) -> Dict[str, Any]:
        """Получение состояния дворовых игр."""
        resp = await self.http.get("/api/yard/games")
        resp.raise_for_status()
        return resp.json()

    async def roll_paper_kolsik(self) -> Dict[str, Any]:
        """Бесплатное вращение кольщика за туалетную бумагу (если доступно)."""
        resp = await self.http.post("/api/kolsik/roll-paper", json={})
        resp.raise_for_status()
        return resp.json()
