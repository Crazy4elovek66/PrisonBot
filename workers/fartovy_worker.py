"""
Независимый реальновременной воркер Фартового (строго по зеленым спичкам и бесплатным бонусам).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from core.database import get_game_guard_state, get_or_create_config, is_worker_active, trip_game_guard
from core.drop_parser import DropParser
from core.server_health import GameMaintenanceError, server_health_monitor
from client.api.fartovy import FartovyAPI, analyze_spin_bonuses, parse_fartovy_state

logger = logging.getLogger(__name__)


async def _fetch_rubles_safe(player_api: Any) -> Optional[int]:
    if not player_api or not hasattr(player_api, "init_player"):
        return None
    try:
        d = await player_api.init_player()
        cur = (d.get("currencies") if isinstance(d, dict) else None) or {}
        if cur.get("rubles") is not None:
            return int(cur["rubles"])
    except Exception:
        pass
    return None


class FartovyWorker:
    def __init__(
        self,
        account_id: int,
        fartovy_api: FartovyAPI,
        player_api: Optional[Any] = None,
        db_engine: Optional[Any] = None,
        notifier: Optional[Any] = None,
        on_wakeup_schedule: Optional[Callable[[str, datetime], Any]] = None,
        enable_jitter: bool = True,
    ) -> None:
        self.account_id = account_id
        self.fartovy_api = fartovy_api
        self.player_api = player_api
        self.db_engine = db_engine
        self.notifier = notifier
        self.on_wakeup_schedule = on_wakeup_schedule
        self.enable_jitter = enable_jitter
        self._lock = asyncio.Lock()

    async def _notify_bonus(self, title: str, body: str, event_type: str, meta: Dict[str, Any]) -> None:
        if self.notifier is not None:
            try:
                await self.notifier.notify(f"<b>{title}</b>\n{body}")
            except Exception:
                pass
        if self.db_engine is not None:
            try:
                await DropParser.save_notification(
                    self.account_id,
                    {"category": "business", "event_type": event_type, "title": title, "body": body, "meta_json": meta},
                    self.db_engine,
                )
            except Exception:
                pass

    async def run_cycle(self, config: Optional[Any] = None) -> Dict[str, Any]:
        if server_health_monitor.is_maintenance:
            return {"status": "skipped", "reason": "maintenance"}

        async with self._lock:
            if config is None and self.db_engine is not None:
                config = await get_or_create_config(self.account_id, self.db_engine)
            if config is not None and not is_worker_active(config):
                return {"status": "skipped", "reason": "paused"}
            if config is not None and not getattr(config, "auto_fartovy_enabled", False):
                return {"status": "skipped", "reason": "disabled"}

            if self.db_engine is not None:
                guard = await get_game_guard_state(self.account_id, "fartovy", engine=self.db_engine)
                if guard.get("guard_tripped"):
                    return {"status": "skipped", "reason": "guard_tripped"}

            try:
                rubles_before = await _fetch_rubles_safe(self.player_api)
                spins_done = 0
                free_spins_done = 0
                bonuses_triggered = 0

                for _ in range(30):
                    raw_info = await self.fartovy_api.get_state()
                    st = parse_fartovy_state(raw_info)

                    # 1. Активная бонус-игра «Козёл»
                    if st["bonus_active"] or st["bonus_boxes_remaining"] > 0:
                        box_res = await self.fartovy_api.open_bonus_box(side="left", super_game=True)
                        bonuses_triggered += 1
                        b_data = (box_res.get("data") if isinstance(box_res, dict) else None) or box_res or {}
                        win_amt = int(b_data.get("win") or b_data.get("redWin") or 0)
                        await self._notify_bonus(
                            "Фартовый: бонус-игра «Козёл»!",
                            f"Бонус пройден автоматически. Получено красных спичек: +{win_amt}",
                            "fartovy_goat",
                            box_res if isinstance(box_res, dict) else {},
                        )
                        if self.enable_jitter:
                            await asyncio.sleep(0.8)
                        continue

                    # 2. Фриспины «Колокол воли» или зеленые спички
                    if st["free_spins_left"] > 0 or st["green_matches"] >= 1:
                        is_free_spin = st["free_spins_left"] > 0
                        spin_res = await self.fartovy_api.spin(bet=1, allow_paid=False)
                        if isinstance(spin_res, dict) and spin_res.get("skipped"):
                            break
                        if is_free_spin:
                            free_spins_done += 1
                        else:
                            spins_done += 1

                        bon = analyze_spin_bonuses(spin_res)
                        if bon["is_stalin_jackpot"]:
                            bonuses_triggered += 1
                            await self._notify_bonus(
                                "Фартовый: выпал «Отец народов»!",
                                f"Получено: +{bon['win_red'] or 1000} красных спичек",
                                "fartovy_stalin",
                                spin_res if isinstance(spin_res, dict) else {},
                            )
                        if self.enable_jitter:
                            await asyncio.sleep(1.0)
                        continue

                    # Спички закончились -> ставим точный real-time wake-up
                    if self.on_wakeup_schedule is not None and st.get("next_green_match_at"):
                        try:
                            wake_dt = datetime.fromisoformat(st["next_green_match_at"]) + timedelta(seconds=3)
                            self.on_wakeup_schedule("fartovy", wake_dt.astimezone(timezone.utc))
                        except Exception:
                            pass
                    break

                rubles_after = await _fetch_rubles_safe(self.player_api)
                if rubles_before is not None and rubles_after is not None and rubles_after < rubles_before:
                    cb_msg = f"rubles {rubles_before}->{rubles_after}"
                    logger.critical("CRITICAL: Фартовый списал рубли! %s", cb_msg)
                    if self.db_engine is not None:
                        await trip_game_guard(self.account_id, "fartovy", cb_msg, engine=self.db_engine)

                return {
                    "status": "ok",
                    "spins_done": spins_done,
                    "free_spins_done": free_spins_done,
                    "bonuses_triggered": bonuses_triggered,
                }
            except GameMaintenanceError:
                return {"status": "skipped", "reason": "maintenance"}
            except Exception as e:
                logger.warning("FartovyWorker error: %s", e)
                return {"status": "error", "error": str(e)}
