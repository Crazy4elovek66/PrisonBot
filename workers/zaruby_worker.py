"""
Независимый реальновременной воркер Зарубов:
автозапуск выбранного тира, сбор наград и выполнение ТОЛЬКО безопасных бесплатных задач.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from core.database import get_or_create_config, is_worker_active
from core.drop_parser import DropParser
from core.server_health import GameMaintenanceError, server_health_monitor
from client.api.zaruby import ZarubyAPI, parse_zaruby_state

logger = logging.getLogger(__name__)


class ZarubyWorker:
    def __init__(
        self,
        account_id: int,
        zaruby_api: ZarubyAPI,
        player_api: Optional[Any] = None,
        fartovy_worker: Optional[Any] = None,
        db_engine: Optional[Any] = None,
        notifier: Optional[Any] = None,
        on_wakeup_schedule: Optional[Callable[[str, datetime], Any]] = None,
    ) -> None:
        self.account_id = account_id
        self.zaruby_api = zaruby_api
        self.player_api = player_api
        self.fartovy_worker = fartovy_worker
        self.db_engine = db_engine
        self.notifier = notifier
        self.on_wakeup_schedule = on_wakeup_schedule
        self._lock = asyncio.Lock()

    async def run_cycle(self, config: Optional[Any] = None) -> Dict[str, Any]:
        if server_health_monitor.is_maintenance:
            return {"status": "skipped", "reason": "maintenance"}

        async with self._lock:
            if config is None and self.db_engine is not None:
                config = await get_or_create_config(self.account_id, self.db_engine)
            if config is not None and not is_worker_active(config):
                return {"status": "skipped", "reason": "paused"}
            if config is not None and not getattr(config, "auto_zaruby_enabled", False):
                return {"status": "skipped", "reason": "disabled"}

            try:
                raw_st = await self.zaruby_api.get_state()
                parsed = parse_zaruby_state(raw_st, config=config)

                claimed = False
                started = False
                safe_actions_done = 0

                # 1. Забор награды за завершенный заруб
                if parsed.get("pending_reward") or (
                    parsed["active"] and (parsed["finished_success"] or parsed["finished_fail"] or parsed["seconds_left"] == 0)
                ):
                    try:
                        c_res = await self.zaruby_api.claim_reward()
                        claimed = True
                        if self.notifier is not None:
                            await self.notifier.notify(
                                f"<b>Зарубы: награда собрана!</b>\nРежим: {parsed['tier_title']}"
                            )
                        if self.db_engine is not None:
                            await DropParser.save_notification(
                                self.account_id,
                                {
                                    "category": "business",
                                    "event_type": "zaruby_claim",
                                    "title": "Зарубы: награда собрана",
                                    "body": f"Режим: {parsed['tier_title']}",
                                    "meta_json": c_res if isinstance(c_res, dict) else {},
                                },
                                self.db_engine,
                            )
                        raw_st = await self.zaruby_api.get_state()
                        parsed = parse_zaruby_state(raw_st, config=config)
                    except Exception as ce:
                        logger.debug("Zaruby claim error: %s", ce)

                # 2. Старт нового заруба, если активного нет
                if not parsed["active"]:
                    tier = str(getattr(config, "auto_zaruby_tier", "pacan") or "pacan")
                    await self.zaruby_api.start_zarub(tier=tier)
                    started = True
                    raw_st = await self.zaruby_api.get_state()
                    parsed = parse_zaruby_state(raw_st, config=config)

                # 3. Выполнение только safe_auto задач (без урона, платных и конфликта энергии)
                for task in parsed.get("tasks") or []:
                    if task.get("completed"):
                        continue
                    if task.get("classification") != "safe_auto":
                        continue
                    t_type = int(task.get("type") or 0)
                    if t_type == 13 and self.fartovy_worker is not None:
                        fw_res = await self.fartovy_worker.run_cycle(config=config)
                        if (fw_res.get("spins_done") or 0) > 0:
                            safe_actions_done += 1

                # 4. Планируем точный real-time wake-up на окончание 24ч окна заруба
                if self.on_wakeup_schedule is not None and parsed.get("end_unix", 0) > 0:
                    wake_dt = datetime.fromtimestamp(int(parsed["end_unix"]) + 5, tz=timezone.utc)
                    self.on_wakeup_schedule("zaruby", wake_dt)

                if claimed or started or safe_actions_done > 0:
                    try:
                        from core.state_hub import state_hub
                        state_hub.notify_mutation(self.account_id, "zarub_updated", reason="zaruby_worker")
                    except Exception:
                        pass

                return {
                    "status": "ok",
                    "claimed": claimed,
                    "started": started,
                    "safe_actions_done": safe_actions_done,
                    "summary_label": parsed["summary_label"],
                    "active": parsed["active"],
                }
            except GameMaintenanceError:
                return {"status": "skipped", "reason": "maintenance"}
            except Exception as e:
                logger.warning("ZarubyWorker error: %s", e)
                return {"status": "error", "error": str(e)}
