import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from core.config import settings
from core.database import get_session, get_or_create_config, is_worker_active
from core.models import PlayerSnapshot, ActionLog
from client.api.player import PlayerAPI
from bot.notifier import TelegramNotifier
from core.drop_parser import DropParser

logger = logging.getLogger(__name__)


def parse_iso_utc(ts_str: Optional[str]) -> Optional[datetime]:
    """Безопасный парсинг временной метки ISO в UTC datetime."""
    if not ts_str:
        return None
    try:
        clean_ts = str(ts_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class RoutineWorker:
    """
    Воркер ежедневных и регулярных игровых активностей:
    1. Синхронизация профиля и фиксация снапшота в БД (POST /api/player/init).
    2. Сбор ежедневной туалетной бумаги (POST /api/daily/toilet-paper).
    3. Сбор прибыли с бизнесов (POST /api/player/business/collect).
    4. Проверка и бритье бороды (POST /api/beard/update).
    5. Сбор подогревов от друзей (POST /api/podogrev/collect/all).
    """

    def __init__(
        self,
        account_id: int,
        player_api: PlayerAPI,
        notifier: Optional[TelegramNotifier] = None,
        db_engine: Optional[Any] = None,
        enable_jitter: bool = True,
        prison_worker: Optional[Any] = None,
    ):
        self.account_id = account_id
        self.api = player_api
        self.notifier = notifier
        self.db_engine = db_engine
        self.enable_jitter = enable_jitter
        self.prison_worker = prison_worker

    async def _jitter(self) -> None:
        if self.enable_jitter:
            delay = random.uniform(settings.JITTER_MIN_SEC, settings.JITTER_MAX_SEC)
            await asyncio.sleep(delay)

    async def _log_action(
        self,
        action_type: str,
        endpoint: str,
        status_code: int = 200,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            async with get_session(self.db_engine) as session:
                log_entry = ActionLog(
                    account_id=self.account_id,
                    action_type=action_type,
                    endpoint=endpoint,
                    status_code=status_code,
                    success=success,
                    details=details or {},
                )
                session.add(log_entry)
        except Exception as e:
            logger.error(f"Не удалось записать ActionLog ({action_type}): {e}")

    async def run_cycle(self) -> Dict[str, Any]:
        """Выполняет один полный цикл рутинных задач."""
        logger.info(f"=== [Аккаунт {self.account_id}] Запуск цикла рутинных задач ===")

        # Проверка живого BotConfig
        config = await get_or_create_config(self.account_id, self.db_engine)
        if not is_worker_active(config):
            logger.info("Планировщик на паузе или активен режим сна. Пропуск рутины.")
            return {"status": "skipped", "reason": "paused_or_sleep"}

        results: Dict[str, Any] = {
            "account_id": self.account_id,
            "snapshot_saved": False,
            "toilet_paper_claimed": False,
            "business_collected": False,
            "beard_updated": False,
            "podogrev_collected": False,
            "kolsik_rolled": False,
            "errors": [],
        }

        # 1. Синхронизация профиля (POST /api/player/init)
        try:
            player_data = await self.api.init_player()
            currencies = player_data.get("currencies", {})
            can_claim_paper = bool(player_data.get("canClaimToiletPaper", False))

            async with get_session(self.db_engine) as session:
                snapshot = PlayerSnapshot(
                    account_id=self.account_id,
                    level=int(player_data.get("level", 0)),
                    authority=int(player_data.get("authority", 0)),
                    biceps=int(player_data.get("biceps", 0)),
                    energy=int(player_data.get("energy", 0)),
                    max_energy=int(player_data.get("maxEnergy", 0)),
                    cigarettes=int(currencies.get("cigarettes", 0)),
                    sugar=int(currencies.get("sugar", 0)),
                    rubles=int(currencies.get("rubles", 0)),
                    paper=int(currencies.get("paper", 0)),
                    soap=int(currencies.get("soap", 0)),
                    can_claim_toilet_paper=can_claim_paper,
                    last_business_collect_time=str(player_data.get("lastBusinessCollectTime", "")),
                    raw_payload=player_data,
                )
                session.add(snapshot)

            results["snapshot_saved"] = True
            await self._log_action("init_player", "/api/player/init", 200, True, {
                "level": player_data.get("level"),
                "authority": player_data.get("authority"),
                "can_claim_paper": can_claim_paper,
            })
            logger.info(
                f"Профиль синхронизирован: Уровень {player_data.get('level')}, "
                f"Авторитет: {player_data.get('authority')}, Энергия: {player_data.get('energy')}/{player_data.get('maxEnergy')}"
            )
        except Exception as e:
            logger.error(f"Ошибка при синхронизации профиля: {e}")
            results["errors"].append(f"init_player: {str(e)}")
            await self._log_action("init_player", "/api/player/init", 500, False, {"error": str(e)})
            can_claim_paper = False

        await self._jitter()

        # 2. Сбор ежедневной туалетной бумаги
        if can_claim_paper and getattr(config, "auto_toilet_paper", False):
            try:
                paper_res = await self.api.claim_toilet_paper()
                results["toilet_paper_claimed"] = True
                await self._log_action("claim_toilet_paper", "/api/daily/toilet-paper", 200, True, paper_res)
                logger.info(f"Туалетная бумага успешно собрана! Новый баланс: {paper_res.get('balance')}")
                # Сохранение уведомления
                await DropParser.save_notification(
                    self.account_id,
                    DropParser.parse_other(
                        "Ежедневная бумага",
                        "Сбор рулона",
                        rewards=[{"currency": "paper", "label": "Бумага", "amount": 1}],
                    ),
                    self.db_engine,
                )
            except Exception as e:
                logger.error(f"Ошибка при сборе туалетной бумаги: {e}")
                results["errors"].append(f"claim_toilet_paper: {str(e)}")
                await self._log_action("claim_toilet_paper", "/api/daily/toilet-paper", 500, False, {"error": str(e)})

        await self._jitter()

        # 3. Проверка и сбор прибыли с бизнесов
        if getattr(config, "auto_business", False):
            try:
                biz_data = await self.api.get_businesses()
                player_biz = biz_data.get("playerBusinesses", [])
                has_active_biz = any(isinstance(b, dict) and b.get("level", 0) > 0 for b in player_biz)

                last_collect_str = biz_data.get("lastCollectTime")
                last_collect_dt = parse_iso_utc(last_collect_str)
                can_collect_by_timer = True

                if last_collect_dt:
                    now_utc = datetime.now(timezone.utc)
                    elapsed_minutes = (now_utc - last_collect_dt).total_seconds() / 60.0
                    if elapsed_minutes < settings.BUSINESS_COLLECT_MIN_MINUTES:
                        can_collect_by_timer = False
                        logger.info(
                            f"Бизнесы еще не накопили прибыль (прошло {elapsed_minutes:.1f} мин из {settings.BUSINESS_COLLECT_MIN_MINUTES} мин). Пропуск сбора."
                        )

                if not has_active_biz:
                    logger.info("Нет активных бизнесов (level > 0). Пропуск сбора прибыли.")
                elif not can_collect_by_timer:
                    pass
                else:
                    try:
                        biz_res = await self.api.collect_business_rewards()
                        results["business_collected"] = True
                        await self._log_action("collect_business", "/api/player/business/collect", 200, True, biz_res)
                        logger.info(f"Прибыль с бизнесов собрана: {biz_res.get('rewards')}")
                        # Сохранение уведомления о сборе с бизнесов
                        await DropParser.save_notification(
                            self.account_id,
                            DropParser.parse_business_collect(biz_res),
                            self.db_engine,
                        )
                    except httpx.HTTPStatusError as err:
                        err_text = err.response.text
                        status_code = err.response.status_code
                        logger.warning(f"Сервер отклонил сбор прибыли с бизнесов (HTTP {status_code}): {err_text}")
                        results["errors"].append(f"collect_business (HTTP {status_code}): {err_text}")
                        await self._log_action(
                            "collect_business",
                            "/api/player/business/collect",
                            status_code,
                            False,
                            {"error": err_text},
                        )
            except Exception as e:
                logger.error(f"Ошибка при проверке бизнесов: {e}")
                results["errors"].append(f"get_businesses: {str(e)}")
                await self._log_action("get_businesses", "/api/player/business/all", 500, False, {"error": str(e)})

        await self._jitter()

        # 4. Проверка и бритье бороды
        if getattr(config, "auto_beard", False):
            try:
                beard_res = await self.api.update_beard()
                results["beard_updated"] = True
                await self._log_action("update_beard", "/api/beard/update", 200, True, beard_res)
                logger.info(f"Борода обновлена: фаза {beard_res.get('beardPhase')}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении бороды: {e}")
                results["errors"].append(f"update_beard: {str(e)}")
                await self._log_action("update_beard", "/api/beard/update", 500, False, {"error": str(e)})

        await self._jitter()

        # 5. Сбор подогревов от друзей
        if getattr(config, "auto_podogrev", False):
            try:
                podogrev_res = await self.api.collect_all_podogrev()
                results["podogrev_collected"] = True
                await self._log_action("collect_podogrev", "/api/podogrev/collect/all", 200, True, podogrev_res)
                applied_energy = podogrev_res.get("appliedEnergy", 0)
                logger.info(f"Подогревы собраны: добавлено энергии {applied_energy}")
                if applied_energy > 0:
                    await DropParser.save_notification(
                        self.account_id,
                        DropParser.parse_other(
                            "Подогревы от друзей",
                            f"+{applied_energy} энергии",
                            rewards=[{"currency": "energy", "label": "Энергия", "amount": applied_energy}],
                        ),
                        self.db_engine,
                    )
            except Exception as e:
                logger.error(f"Ошибка при сборе подогревов: {e}")
                results["errors"].append(f"collect_podogrev: {str(e)}")
                await self._log_action("collect_podogrev", "/api/podogrev/collect/all", 500, False, {"error": str(e)})

        await self._jitter()

        # 6. Кольщик (автопокупка наколок за туалетную бумагу или рубли)
        if getattr(config, "auto_kolsik", False):
            currency = str(getattr(config, "kolsik_currency", "paper")).lower().strip()
            cur_balance = int(currencies.get(currency, 0)) if "currencies" in locals() and isinstance(currencies, dict) else 0
            cost = 15
            if cur_balance >= cost:
                try:
                    kolsik_res = await self.api.roll_kolsik(currency)
                    results["kolsik_rolled"] = True
                    endpoint = "/api/kolsik/roll" if currency == "rubles" else "/api/kolsik/roll-paper"
                    await self._log_action("kolsik_roll", endpoint, 200, True, kolsik_res)
                    await DropParser.save_notification(
                        self.account_id,
                        DropParser.parse_kolsik_roll(kolsik_res, currency),
                        self.db_engine,
                    )
                    logger.info("Успешно набита наколка у Кольщика за %s: %s", currency, kolsik_res)
                except httpx.HTTPStatusError as err:
                    status_code = err.response.status_code
                    logger.warning("Кольщик отклонил покупку (HTTP %s): %s", status_code, err.response.text)
                    results["errors"].append(f"roll_kolsik (HTTP {status_code})")
                    endpoint = "/api/kolsik/roll" if currency == "rubles" else "/api/kolsik/roll-paper"
                    await self._log_action("kolsik_roll", endpoint, status_code, False, {"error": err.response.text})
                except Exception as ke:
                    logger.warning("Ошибка при автопрокрутке кольщика: %s", ke)
                    results["errors"].append(f"roll_kolsik: {str(ke)}")
            else:
                logger.info(
                    "Недостаточно средств для Кольщика (%s: %s при стоимости %s). Пропуск.",
                    currency, cur_balance, cost
                )

        # 7. Уведомление владельца при наличии сборов
        if self.notifier is not None:
            applied_energy = podogrev_res.get("appliedEnergy", 0) if results["podogrev_collected"] and "podogrev_res" in locals() and isinstance(podogrev_res, dict) else 0
            kolsik_info = results.get("kolsik_rolled", False)
            if results["toilet_paper_claimed"] or results["business_collected"] or applied_energy > 0 or kolsik_info:
                lines = ["📦 <b>Рутинные сборы:</b>"]
                if results["toilet_paper_claimed"]:
                    lines.append("🧻 Собрана ежедневная туалетная бумага")
                if results["business_collected"]:
                    lines.append("💼 Собрана прибыль с бизнесов")
                if applied_energy > 0:
                    lines.append(f"⚡️ Подогревы от друзей: +{applied_energy} энергии")
                if kolsik_info:
                    lines.append("🎨 Набита новая татуировка у Кольщика")
                await self.notifier.notify("\n".join(lines))

        # 8. Если получена энергия из подогревов или рулона - сразу триггерим PrisonWorker для мгновенного слива энергии
        if (results["toilet_paper_claimed"] or (results["podogrev_collected"] and "applied_energy" in locals() and applied_energy > 0)) and self.prison_worker:
            asyncio.create_task(self.prison_worker.run_cycle())

        logger.info(f"=== [Аккаунт {self.account_id}] Цикл рутинных задач завершен ===")
        return results
        return results
