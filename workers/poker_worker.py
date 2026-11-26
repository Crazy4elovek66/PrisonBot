"""
Независимый реальновременной воркер Покера (строго бесплатно за красную фишку).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from core.config import MSK_TZ
from core.database import get_or_create_config, is_worker_active
from core.drop_parser import DropParser
from core.server_health import GameMaintenanceError, server_health_monitor
from client.api.poker import PokerAPI, play_free_poker_game

logger = logging.getLogger(__name__)


class PokerWorker:
    def __init__(
        self,
        account_id: int,
        poker_api: PokerAPI,
        player_api: Optional[Any] = None,
        db_engine: Optional[Any] = None,
        notifier: Optional[Any] = None,
        on_wakeup_schedule: Optional[Callable[[str, datetime], Any]] = None,
        enable_jitter: bool = True,
    ) -> None:
        self.account_id = account_id
        self.poker_api = poker_api
        self.player_api = player_api
        self.db_engine = db_engine
        self.notifier = notifier
        self.on_wakeup_schedule = on_wakeup_schedule
        self.enable_jitter = enable_jitter
        self._lock = asyncio.Lock()

    async def run_cycle(self, config: Optional[Any] = None) -> Dict[str, Any]:
        if server_health_monitor.is_maintenance:
            return {"status": "skipped", "reason": "maintenance"}

        async with self._lock:
            if config is None and self.db_engine is not None:
                config = await get_or_create_config(self.account_id, self.db_engine)
            if config is not None and not is_worker_active(config):
                return {"status": "skipped", "reason": "paused"}
            if config is not None and not getattr(config, "auto_poker_enabled", False):
                return {"status": "skipped", "reason": "disabled"}

            try:
                played = 0
                last_res: Dict[str, Any] = {"status": "no_chips"}
                for _ in range(10):
                    res = await play_free_poker_game(
                        self.poker_api,
                        player_api=self.player_api,
                        account_id=self.account_id,
                        allow_paid=False,
                        mode="chips",
                        db_engine=self.db_engine,
                    )
                    last_res = res
                    if not res.get("success"):
                        break
                    played += 1
                    rw_list = res.get("rewards_formatted") or ["без ресурсов"]
                    msg_lines = [
                        "<b>Покер (бесплатно, 1 фишка)</b>",
                        f"Комбинация: <b>{res.get('combo_title')}</b>",
                        f"Получено: {', '.join(rw_list)}",
                        f"Осталось красных фишек: {res.get('chips_left', 0)}",
                    ]
                    if self.notifier is not None:
                        try:
                            await self.notifier.notify("\n".join(msg_lines))
                        except Exception:
                            pass
                    if self.db_engine is not None:
                        try:
                            await DropParser.save_notification(
                                self.account_id,
                                {
                                    "category": "business",
                                    "event_type": "poker_game",
                                    "title": f"Покер: {res.get('combo_title')}",
                                    "body": f"Получено: {', '.join(rw_list)} (фишек: {res.get('chips_left', 0)})",
                                    "meta_json": res,
                                },
                                self.db_engine,
                            )
                        except Exception:
                            pass
                    if int(res.get("chips_left") or 0) <= 0:
                        break
                    if self.enable_jitter:
                        await asyncio.sleep(0.8)

                # Планируем wake-up на 00:00:05 МСК (суточный сброс/проверка)
                if self.on_wakeup_schedule is not None:
                    now_msk = datetime.now(MSK_TZ)
                    next_midnight_msk = (now_msk.replace(hour=0, minute=0, second=5, microsecond=0) + timedelta(days=1)).astimezone(timezone.utc)
                    self.on_wakeup_schedule("poker", next_midnight_msk)

                if played > 0:
                    try:
                        from core.state_hub import state_hub
                        state_hub.notify_mutation(self.account_id, "poker_played", reason="poker_worker")
                    except Exception:
                        pass

                return {"status": "ok", "played": played, "last_result": last_res}
            except GameMaintenanceError:
                return {"status": "skipped", "reason": "maintenance"}
            except Exception as e:
                logger.warning("PokerWorker error: %s", e)
                return {"status": "error", "error": str(e)}
