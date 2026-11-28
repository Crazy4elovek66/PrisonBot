from contextlib import asynccontextmanager
from pathlib import Path
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text, event
from core.config import settings
from core.models import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def normalize_db_url(db_url: str) -> str:
    """
    Приводит относительный путь SQLite БД к единому абсолютному пути внутри <PROJECT_ROOT>/storage/prison_bot.db.
    In-memory и уже абсолютные пути оставляет без изменений.
    """
    if not db_url or ":memory:" in db_url:
        return db_url

    match = re.match(r"^(sqlite(?:\+[a-z0-9_]+)?):///(.+)$", db_url)
    if not match:
        return db_url

    scheme, raw_path = match.group(1), match.group(2)
    # Уже абсолютный путь (Unix /... или Windows C:/... или C:\...)
    if raw_path.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", raw_path):
        resolved = Path(raw_path)
    else:
        clean_rel = raw_path.lstrip("./\\")
        if clean_rel == "prison_bot.db":
            resolved = PROJECT_ROOT / "storage" / "prison_bot.db"
        else:
            resolved = (PROJECT_ROOT / clean_rel).resolve()

    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"{scheme}:///{resolved.as_posix()}"


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Оптимизация производительности SQLite: WAL, быстрые тайм-ауты, кэш 16MB и хранение temp в RAM."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA cache_size=-16000;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.close()
    except Exception:
        pass


def get_engine(db_url: Optional[str] = None) -> AsyncEngine:
    global _engine
    if _engine is None or db_url is not None:
        url = normalize_db_url(db_url or settings.DB_URL)
        # In-memory SQLite can't use pool_pre_ping or WAL mode
        is_memory = ":memory:" in url
        engine = create_async_engine(
            url,
            echo=False,
            future=True,
        )
        if "sqlite" in url:
            event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)
        if db_url is None:
            _engine = engine
        return engine
    return _engine


def get_session_factory(engine: Optional[AsyncEngine] = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None or engine is not None:
        eng = engine or get_engine()
        factory = async_sessionmaker(
            bind=eng,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        if engine is None:
            _session_factory = factory
        return factory
    return _session_factory


def _migrate_bot_configs(connection) -> None:
    """Автоматическая миграция новых колонок BotConfig при необходимости."""
    cursor = connection.execute(text("PRAGMA table_info(bot_configs);"))
    existing_cols = {row[1] for row in cursor.fetchall()}
    if not existing_cols:
        return

    col_defs = [
        ("friend_accept_all", "BOOLEAN DEFAULT 1 NOT NULL"),
        ("friend_min_level", "INTEGER DEFAULT 0 NOT NULL"),
        ("friend_min_authority", "BIGINT DEFAULT 0 NOT NULL"),
        ("friend_min_biceps", "INTEGER DEFAULT 0 NOT NULL"),
        ("friend_min_talents", "INTEGER DEFAULT 0 NOT NULL"),
        ("friend_min_poison_damage", "INTEGER DEFAULT 0 NOT NULL"),
        ("friend_min_total_damage", "INTEGER DEFAULT 0 NOT NULL"),
        ("last_notified_menyala_cycle", "VARCHAR(64) DEFAULT '' NOT NULL"),
        ("friend_auto_decline_below", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_kolsik", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("kolsik_currency", "VARCHAR(20) DEFAULT 'paper' NOT NULL"),
        ("auto_boss_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_friend_outreach", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("friend_outreach_daily_limit", "INTEGER DEFAULT 50 NOT NULL"),
        ("friend_outreach_min_damage", "BIGINT DEFAULT 0 NOT NULL"),
        ("friend_outreach_max_damage", "BIGINT DEFAULT 0 NOT NULL"),
        ("friend_outreach_only_active", "BOOLEAN DEFAULT 1 NOT NULL"),
        ("raid_tg_channels", "JSON DEFAULT '[]' NOT NULL"),
        ("guild_scan_cursor", "INTEGER DEFAULT 0 NOT NULL"),
        ("friend_filter_mode", "VARCHAR(10) DEFAULT 'and' NOT NULL"),
        ("auto_parse_news_raids", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_friend_cleanup", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("friend_cleanup_inactive_days", "INTEGER DEFAULT 14 NOT NULL"),
        ("friend_cleanup_daily_limit", "INTEGER DEFAULT 5 NOT NULL"),
        ("friend_cleanup_trigger_threshold", "INTEGER DEFAULT 10 NOT NULL"),
        ("auto_podogrev_send", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_katala", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_biceps", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_spit_balanda", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_throw_yeast", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_monthly_tasks", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("boss_auto_melee", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("friends_parser_tier", "VARCHAR(20) DEFAULT 'accessible' NOT NULL"),
        ("friends_parser_min_authority", "BIGINT DEFAULT 0 NOT NULL"),
        ("friends_parser_max_authority", "BIGINT DEFAULT 0 NOT NULL"),
        ("auto_poker_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_fartovy_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_zaruby_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("auto_zaruby_tier", "VARCHAR(32) DEFAULT 'pacan' NOT NULL"),
        ("outreach_criteria", "JSON DEFAULT '{}' NOT NULL"),
    ]

    for col_name, col_type in col_defs:
        if col_name not in existing_cols:
            connection.execute(text(f"ALTER TABLE bot_configs ADD COLUMN {col_name} {col_type};"))

    # Миграция старого дефолтного лимита 25 -> 50 (если не настраивался пользователем вручную)
    if "friend_outreach_daily_limit" in existing_cols:
        connection.execute(
            text("UPDATE bot_configs SET friend_outreach_daily_limit = 50 WHERE friend_outreach_daily_limit = 25;")
        )

    # XOR-нормализация взаимоисключающих целей энергии при миграции
    if "auto_prison" in existing_cols and "auto_masters" in existing_cols:
        connection.execute(
            text("UPDATE bot_configs SET auto_masters = 0 WHERE auto_prison = 1 AND auto_masters = 1;")
        )


def normalize_energy_target_flags(
    auto_prison: bool,
    auto_masters: bool,
    prev_auto_prison: bool = False,
    prev_auto_masters: bool = False,
) -> tuple[bool, bool, Optional[str]]:
    """
    Гарантирует XOR-инвариант целей энергии: одновременно активен максимум один режим
    (`auto_prison` или `auto_masters`). Возвращает `(auto_prison, auto_masters, disabled_conflict_target)`.
    """
    ap = bool(auto_prison)
    am = bool(auto_masters)
    if ap and am:
        if not prev_auto_masters and am and prev_auto_prison:
            return False, True, "auto_prison"
        if not prev_auto_prison and ap and prev_auto_masters:
            return True, False, "auto_masters"
        # Если оба пришли True одновременно (из старого клиента или БД) — приоритет auto_prison
        return True, False, "auto_masters"
    return ap, am, None


def _migrate_notifications(connection) -> None:
    """Автоматическая миграция новых колонок Notification при необходимости."""
    cursor = connection.execute(text("PRAGMA table_info(notifications);"))
    existing_cols = {row[1] for row in cursor.fetchall()}
    if not existing_cols:
        return

    if "event_key" not in existing_cols:
        connection.execute(text("ALTER TABLE notifications ADD COLUMN event_key VARCHAR(128);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_event_key ON notifications (event_key);"))
    if "meta_json" not in existing_cols:
        connection.execute(text("ALTER TABLE notifications ADD COLUMN meta_json JSON DEFAULT '{}' NOT NULL;"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications (created_at);"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications (is_read);"))


def _migrate_tracked_candidates(connection) -> None:
    """Автоматическая миграция новых колонок TrackedCandidate при необходимости."""
    cursor = connection.execute(text("PRAGMA table_info(tracked_candidates);"))
    existing_cols = {row[1] for row in cursor.fetchall()}
    if not existing_cols:
        return

    col_defs = [
        ("prev_total_damage", "BIGINT DEFAULT 0 NOT NULL"),
        ("damage_delta", "BIGINT DEFAULT 0 NOT NULL"),
        ("camp_activity", "INTEGER DEFAULT 0 NOT NULL"),
        ("talents", "INTEGER DEFAULT 0 NOT NULL"),
        ("score", "INTEGER DEFAULT 0 NOT NULL"),
        ("enriched_at", "DATETIME"),
    ]

    for col_name, col_type in col_defs:
        if col_name not in existing_cols:
            connection.execute(text(f"ALTER TABLE tracked_candidates ADD COLUMN {col_name} {col_type};"))

    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tracked_candidates_score ON tracked_candidates (score);"))

    # Сброс устаревших фиктивных значений урона 250/60/30, нулевых оружейных статов и нулевого авторитета для переобогащения реальными данными
    connection.execute(
        text(
            "UPDATE tracked_candidates "
            "SET poison_damage = 0, gunshot_damage = 0, knife_damage = 0, enriched_at = NULL "
            "WHERE poison_damage = 250 AND gunshot_damage = 60 AND knife_damage = 30;"
        )
    )
    connection.execute(
        text(
            "UPDATE tracked_candidates "
            "SET enriched_at = NULL "
            "WHERE authority = 0 OR (poison_damage = 0 AND gunshot_damage = 0 AND knife_damage = 0);"
        )
    )


def _migrate_sent_friend_requests(connection) -> None:
    """Автоматическая миграция новых колонок SentFriendRequest при необходимости."""
    cursor = connection.execute(text("PRAGMA table_info(sent_friend_requests);"))
    existing_cols = {row[1] for row in cursor.fetchall()}
    if not existing_cols:
        return

    if "resolved_at" not in existing_cols:
        connection.execute(text("ALTER TABLE sent_friend_requests ADD COLUMN resolved_at DATETIME;"))


def _migrate_boss_presets(connection) -> None:
    """Автоматическая миграция колонок таблицы boss_presets при необходимости."""
    cursor = connection.execute(text("PRAGMA table_info(boss_presets);"))
    existing_cols = {row[1] for row in cursor.fetchall()}
    if not existing_cols:
        return

    col_defs = [
        ("schedule_time_msk", "VARCHAR(5) DEFAULT '09:00' NOT NULL"),
        ("last_run_date_msk", "VARCHAR(10)"),
        ("is_running", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("current_step_index", "INTEGER DEFAULT 0 NOT NULL"),
        ("last_status", "VARCHAR(255)"),
    ]

    for col_name, col_type in col_defs:
        if col_name not in existing_cols:
            connection.execute(text(f"ALTER TABLE boss_presets ADD COLUMN {col_name} {col_type};"))


async def init_db(engine: Optional[AsyncEngine] = None) -> None:
    eng = engine or get_engine()
    
    # Configure WAL mode and performance PRAGMAs for file-based SQLite
    if "sqlite" in str(eng.url) and ":memory:" not in str(eng.url):
        async with eng.connect() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))
            await conn.execute(text("PRAGMA busy_timeout=5000;"))
            await conn.execute(text("PRAGMA cache_size=-16000;"))
            await conn.execute(text("PRAGMA temp_store=MEMORY;"))

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_bot_configs)
        await conn.run_sync(_migrate_notifications)
        await conn.run_sync(_migrate_tracked_candidates)
        await conn.run_sync(_migrate_sent_friend_requests)
        await conn.run_sync(_migrate_boss_presets)
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS daily_resource_snapshots (
                    day_msk TEXT PRIMARY KEY,
                    cigarettes INTEGER NOT NULL,
                    sugar INTEGER NOT NULL,
                    rubles INTEGER NOT NULL,
                    paper INTEGER NOT NULL,
                    soap INTEGER NOT NULL,
                    stew INTEGER NOT NULL DEFAULT 0,
                    match_red INTEGER DEFAULT NULL,
                    match_green INTEGER DEFAULT NULL,
                    match_blue INTEGER DEFAULT NULL,
                    wheel_tickets INTEGER DEFAULT NULL,
                    weapon_poison INTEGER DEFAULT NULL,
                    weapon_gunshot INTEGER DEFAULT NULL,
                    weapon_knife INTEGER DEFAULT NULL,
                    captured_at TEXT NOT NULL
                );
                """
            )
        )
        res_cols = await conn.execute(text("PRAGMA table_info(daily_resource_snapshots)"))
        existing_snapshot_cols = {row[1] for row in res_cols.fetchall()}
        if "stew" not in existing_snapshot_cols:
            await conn.execute(text("ALTER TABLE daily_resource_snapshots ADD COLUMN stew INTEGER NOT NULL DEFAULT 0"))
        for extra_col in (
            "match_red",
            "match_green",
            "match_blue",
            "wheel_tickets",
            "weapon_poison",
            "weapon_gunshot",
            "weapon_knife",
        ):
            if extra_col not in existing_snapshot_cols:
                await conn.execute(text(f"ALTER TABLE daily_resource_snapshots ADD COLUMN {extra_col} INTEGER DEFAULT NULL"))
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS monthly_tasks_schedule (
                    year_month TEXT NOT NULL,
                    day_num INTEGER NOT NULL,
                    date_iso TEXT NOT NULL,
                    task_key TEXT DEFAULT '',
                    task_title TEXT DEFAULT '',
                    task_description TEXT DEFAULT '',
                    target_value INTEGER DEFAULT 0,
                    progress_value INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'upcoming',
                    source TEXT DEFAULT 'api',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (year_month, day_num)
                );
                """
            )
        )


@asynccontextmanager
async def get_session(engine: Optional[AsyncEngine] = None) -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_or_create_config(account_id: int, engine: Optional[AsyncEngine] = None):
    """Получение или создание динамического конфига BotConfig для аккаунта."""
    from sqlalchemy import select
    from core.models import BotConfig

    async with get_session(engine) as session:
        stmt = select(BotConfig).where(BotConfig.account_id == account_id)
        res = await session.execute(stmt)
        cfg = res.scalar_one_or_none()
        if not cfg:
            cfg = BotConfig(account_id=account_id)
            session.add(cfg)
            await session.commit()
            await session.refresh(cfg)
        return cfg


_VALID_BOSS_MODES = {"pacansky", "blotnoy", "avtoritetny"}
_BOSS_MODE_ALIASES = {
    "pacansky": "pacansky",
    "pacan": "pacansky",
    "пацанский": "pacansky",
    "blotnoy": "blotnoy",
    "blatnoy": "blotnoy",
    "блатной": "blotnoy",
    "avtoritetny": "avtoritetny",
    "authority": "avtoritetny",
    "авторитетный": "avtoritetny",
}


def normalize_boss_mode(mode: Any, default: str = "pacansky") -> str:
    """Нормализует режим атаки босса к каноническому виду."""
    if not mode:
        return default
    key = str(mode).strip().lower()
    return _BOSS_MODE_ALIASES.get(key, default if default in _VALID_BOSS_MODES else "pacansky")


def normalize_boss_targets(raw_targets: Any) -> List[Dict[str, Any]]:
    """
    Нормализует и дедуплицирует очередь целей боссов.
    Гарантирует единый контракт элементов и синхронизированный монотонный priority (0..N-1).
    """
    if not isinstance(raw_targets, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()

    for item in raw_targets:
        if isinstance(item, dict):
            if item.get("enabled") is False:
                continue
            raw_id = (
                item.get("bossId")
                if item.get("bossId") is not None
                else (item.get("boss_id") if item.get("boss_id") is not None else item.get("id"))
            )
            if raw_id is None:
                continue
            try:
                boss_id = int(raw_id)
            except (ValueError, TypeError):
                continue
            if boss_id in seen_ids:
                continue
            seen_ids.add(boss_id)

            mode = normalize_boss_mode(item.get("mode"), default="pacansky")
            raw_limit = item.get("limit") if item.get("limit") is not None else item.get("daily_limit")
            try:
                limit_val = max(1, min(50, int(raw_limit if raw_limit is not None else 7)))
            except (ValueError, TypeError):
                limit_val = 7

            name_val = item.get("name") or item.get("bossName")
            entry: Dict[str, Any] = {
                "bossId": boss_id,
                "mode": mode,
                "limit": limit_val,
                "enabled": True,
                "priority": len(normalized),
            }
            if name_val:
                entry["name"] = str(name_val)
            normalized.append(entry)
        elif isinstance(item, (int, str)) and str(item).strip().isdigit():
            boss_id = int(str(item).strip())
            if boss_id in seen_ids:
                continue
            seen_ids.add(boss_id)
            normalized.append({
                "bossId": boss_id,
                "mode": "pacansky",
                "limit": 7,
                "enabled": True,
                "priority": len(normalized),
            })

    return normalized


def is_worker_active(config) -> bool:
    """Проверка глобальной активности воркера (без учета ночного режима боссов)."""
    return not bool(getattr(config, "is_paused", False))


def is_night_mode_active(config, now_utc=None) -> bool:
    """
    Проверка активности Ночного режима (строго по МСК, Europe/Moscow).
    Отключает ТОЛЬКО автопризыв и автоатаку боссов.
    """
    from datetime import datetime, timezone
    from core.config import MSK_TZ

    if not getattr(config, "sleep_mode_enabled", False):
        return False

    ref_utc = now_utc or datetime.now(timezone.utc)
    if ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=timezone.utc)
    now_msk = ref_utc.astimezone(MSK_TZ)
    current_hour = now_msk.hour

    start = int(getattr(config, "sleep_start_hour", 2) or 0) % 24
    end = int(getattr(config, "sleep_end_hour", 7) or 0) % 24

    if start == end:
        return False
    if start < end:
        return start <= current_hour < end
    return current_hour >= start or current_hour < end


async def prune_old_notifications(engine: Optional[AsyncEngine] = None, days: int = 7) -> int:
    """Удаляет уведомления старше `days` суток из таблицы notifications (политика ротации 7 дней)."""
    from datetime import datetime, timedelta
    from sqlalchemy import delete
    from core.models import Notification

    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    async with get_session(engine) as session:
        res = await session.execute(
            delete(Notification).where(Notification.created_at < cutoff)
        )
        await session.commit()
        return int(res.rowcount or 0)


_DAILY_RESOURCE_KEYS = ("cigarettes", "sugar", "rubles", "paper", "soap", "stew")
_REQUIRED_DAILY_RESOURCE_KEYS = ("cigarettes", "sugar", "rubles", "paper", "soap")
_OPTIONAL_DAILY_EXTRA_KEYS = (
    "match_red",
    "match_green",
    "match_blue",
    "wheel_tickets",
    "weapon_poison",
    "weapon_gunshot",
    "weapon_knife",
)
_last_known_resources: Optional[dict] = None


def _extract_optional_daily_extras(resources: object) -> Dict[str, int]:
    if not isinstance(resources, dict):
        return {}
    aliases = {
        "match_red": ("match_red", "fartovy_red", "red_matches", "pink_matches"),
        "match_green": ("match_green", "fartovy_green", "green_matches", "black_matches"),
        "match_blue": ("match_blue", "wheel_blue_matches", "blue_matches"),
        "wheel_tickets": ("wheel_tickets", "fortune_tickets"),
        "weapon_poison": ("weapon_poison", "poison_count", "poison"),
        "weapon_gunshot": ("weapon_gunshot", "gunshot_count", "gunshot"),
        "weapon_knife": ("weapon_knife", "knife_count", "knife"),
    }
    extras: Dict[str, int] = {}
    for canonical, cand_keys in aliases.items():
        for ck in cand_keys:
            raw = resources.get(ck)
            if raw is None or isinstance(raw, bool):
                continue
            try:
                val = int(raw)
            except (TypeError, ValueError):
                continue
            if val >= 0:
                extras[canonical] = val
                break
    return extras


def _validate_daily_resources(resources: object) -> Optional[dict]:
    """Проверяет, что словарь ресурсов содержит базовые ключи с целыми значениями >= 0 (stew и доп. ключи опциональны)."""
    if not isinstance(resources, dict):
        return None
    out = {}
    for k in _DAILY_RESOURCE_KEYS:
        raw = resources.get(k)
        if raw is None:
            if k in _REQUIRED_DAILY_RESOURCE_KEYS:
                return None
            raw = 0
        if isinstance(raw, bool):
            return None
        try:
            val = int(raw)
        except (TypeError, ValueError):
            return None
        if val < 0:
            return None
        out[k] = val
    out.update(_extract_optional_daily_extras(resources))
    return out


async def get_daily_resource_baseline(
    day_msk: str,
    engine: Optional[AsyncEngine] = None,
) -> Optional[dict]:
    """Возвращает сохранённый базовый снимок ресурсов за указанную московскую дату (YYYY-MM-DD)."""
    async with get_session(engine) as session:
        res = await session.execute(
            text(
                "SELECT day_msk, cigarettes, sugar, rubles, paper, soap, stew, "
                "match_red, match_green, match_blue, wheel_tickets, "
                "weapon_poison, weapon_gunshot, weapon_knife, captured_at "
                "FROM daily_resource_snapshots WHERE day_msk = :day_msk"
            ),
            {"day_msk": day_msk},
        )
        row = res.fetchone()
        if not row:
            return None
        return {
            "day_msk": row[0],
            "cigarettes": int(row[1]),
            "sugar": int(row[2]),
            "rubles": int(row[3]),
            "paper": int(row[4]),
            "soap": int(row[5]),
            "stew": int(row[6] or 0),
            "match_red": int(row[7]) if row[7] is not None else None,
            "match_green": int(row[8]) if row[8] is not None else None,
            "match_blue": int(row[9]) if row[9] is not None else None,
            "wheel_tickets": int(row[10]) if row[10] is not None else None,
            "weapon_poison": int(row[11]) if row[11] is not None else None,
            "weapon_gunshot": int(row[12]) if row[12] is not None else None,
            "weapon_knife": int(row[13]) if row[13] is not None else None,
            "captured_at": str(row[14]),
        }


async def ensure_daily_resource_baseline(
    day_msk: str,
    resources: dict,
    captured_at: Optional[str] = None,
    engine: Optional[AsyncEngine] = None,
) -> Optional[dict]:
    """
    Атомарно (INSERT OR IGNORE) фиксирует базовый снимок ресурсов за day_msk, если его ещё нет,
    и лениво инициализирует ранее отсутствовавшие (NULL) колонки текущим значением без ложной дельты.
    """
    global _last_known_resources
    from datetime import datetime, timedelta
    from core.config import MSK_TZ

    valid = _validate_daily_resources(resources)
    if valid is None:
        return None

    _last_known_resources = {k: valid[k] for k in _DAILY_RESOURCE_KEYS}
    cap_ts = captured_at or datetime.now(MSK_TZ).isoformat()
    cutoff_day = (datetime.now(MSK_TZ) - timedelta(days=90)).strftime("%Y-%m-%d")

    async with get_session(engine) as session:
        await session.execute(
            text(
                "INSERT OR IGNORE INTO daily_resource_snapshots "
                "(day_msk, cigarettes, sugar, rubles, paper, soap, stew, "
                "match_red, match_green, match_blue, wheel_tickets, "
                "weapon_poison, weapon_gunshot, weapon_knife, captured_at) "
                "VALUES (:day_msk, :cigarettes, :sugar, :rubles, :paper, :soap, :stew, "
                ":match_red, :match_green, :match_blue, :wheel_tickets, "
                ":weapon_poison, :weapon_gunshot, :weapon_knife, :captured_at)"
            ),
            {
                "day_msk": day_msk,
                "cigarettes": valid["cigarettes"],
                "sugar": valid["sugar"],
                "rubles": valid["rubles"],
                "paper": valid["paper"],
                "soap": valid["soap"],
                "stew": valid["stew"],
                "match_red": valid.get("match_red"),
                "match_green": valid.get("match_green"),
                "match_blue": valid.get("match_blue"),
                "wheel_tickets": valid.get("wheel_tickets"),
                "weapon_poison": valid.get("weapon_poison"),
                "weapon_gunshot": valid.get("weapon_gunshot"),
                "weapon_knife": valid.get("weapon_knife"),
                "captured_at": cap_ts,
            },
        )
        # Если строка уже существовала до миграции и новые колонки были NULL — инициализируем их текущим значением
        for extra_col in _OPTIONAL_DAILY_EXTRA_KEYS:
            if extra_col in valid:
                await session.execute(
                    text(
                        f"UPDATE daily_resource_snapshots SET {extra_col} = :val "
                        f"WHERE day_msk = :day_msk AND {extra_col} IS NULL"
                    ),
                    {"val": valid[extra_col], "day_msk": day_msk},
                )
        await session.execute(
            text("DELETE FROM daily_resource_snapshots WHERE day_msk < :cutoff_day"),
            {"cutoff_day": cutoff_day},
        )
        await session.commit()

    return await get_daily_resource_baseline(day_msk, engine=engine)


async def compute_daily_resource_deltas(
    current_resources: dict,
    now_msk=None,
    engine: Optional[AsyncEngine] = None,
) -> Optional[dict]:
    """
    Фиксирует/читает суточную базу по MSK_TZ (YYYY-MM-DD) и возвращает:
    {day_msk, captured_at, baseline: {...}, deltas: {...}}.
    """
    from datetime import datetime
    from core.config import MSK_TZ

    valid = _validate_daily_resources(current_resources)
    if valid is None:
        return None

    if now_msk is None:
        now_dt = datetime.now(MSK_TZ)
    elif now_msk.tzinfo is None:
        now_dt = now_msk.replace(tzinfo=MSK_TZ)
    else:
        now_dt = now_msk.astimezone(MSK_TZ)

    day_msk = now_dt.strftime("%Y-%m-%d")
    baseline_row = await ensure_daily_resource_baseline(
        day_msk,
        valid,
        captured_at=now_dt.isoformat(),
        engine=engine,
    )
    if not baseline_row:
        return None

    out_keys = list(_DAILY_RESOURCE_KEYS if (isinstance(current_resources, dict) and "stew" in current_resources) else _REQUIRED_DAILY_RESOURCE_KEYS)
    for extra_col in _OPTIONAL_DAILY_EXTRA_KEYS:
        if extra_col in valid and baseline_row.get(extra_col) is not None:
            out_keys.append(extra_col)

    baseline = {k: int(baseline_row[k]) for k in out_keys}
    deltas = {k: int(valid[k]) - baseline[k] for k in out_keys}
    return {
        "day_msk": day_msk,
        "captured_at": baseline_row["captured_at"],
        "baseline": baseline,
        "deltas": deltas,
    }


async def upsert_monthly_tasks(
    year_month: str,
    days_list: list,
    source: str = "api",
    engine: Optional[AsyncEngine] = None,
) -> int:
    """
    Атомарно сохраняет/обновляет расписание месячных делюг в monthly_tasks_schedule.
    При наступлении нового месяца очищает устаревшие месяцы (year_month != :year_month).
    Никогда не удаляет данные при пустом/невалидном списке и не затирает непустой task_title/task_description пустой строкой.
    """
    import re as _re
    import time as _time

    if not year_month or not isinstance(year_month, str) or not _re.fullmatch(r"\d{4}-\d{2}", year_month):
        return 0
    if not isinstance(days_list, list) or not days_list:
        return 0

    valid_items = []
    for item in days_list:
        if not isinstance(item, dict) or item.get("day_num") is None:
            continue
        try:
            day_num = int(item["day_num"])
        except (TypeError, ValueError):
            continue
        if not (1 <= day_num <= 31):
            continue
        valid_items.append((day_num, item))

    if not valid_items:
        return 0

    now_ts = _time.time()
    count = 0
    async with get_session(engine) as session:
        await session.execute(
            text("DELETE FROM monthly_tasks_schedule WHERE year_month != :year_month"),
            {"year_month": year_month},
        )
        for day_num, item in valid_items:
            date_iso = str(item.get("date_iso") or f"{year_month}-{day_num:02d}")
            task_key = str(item.get("task_key") or "").strip()
            task_title = str(item.get("title") or item.get("task_title") or "").strip()
            task_desc = str(item.get("task_description") or "").strip()
            target_val = int(item.get("target") or item.get("target_value") or 0)
            progress_val = int(item.get("progress") or item.get("progress_value") or 0)
            status_val = str(item.get("status") or "upcoming")

            await session.execute(
                text(
                    """
                    INSERT INTO monthly_tasks_schedule (
                        year_month, day_num, date_iso, task_key, task_title, task_description,
                        target_value, progress_value, status, source, updated_at
                    ) VALUES (
                        :year_month, :day_num, :date_iso, :task_key, :task_title, :task_description,
                        :target_value, :progress_value, :status, :source, :updated_at
                    )
                    ON CONFLICT(year_month, day_num) DO UPDATE SET
                        date_iso = excluded.date_iso,
                        task_key = CASE WHEN excluded.task_key != '' THEN excluded.task_key ELSE monthly_tasks_schedule.task_key END,
                        task_title = CASE WHEN excluded.task_title != '' THEN excluded.task_title ELSE monthly_tasks_schedule.task_title END,
                        task_description = CASE WHEN excluded.task_description != '' THEN excluded.task_description ELSE monthly_tasks_schedule.task_description END,
                        target_value = CASE WHEN excluded.target_value > 0 THEN excluded.target_value ELSE monthly_tasks_schedule.target_value END,
                        progress_value = excluded.progress_value,
                        status = excluded.status,
                        source = CASE WHEN excluded.task_title != '' THEN excluded.source ELSE monthly_tasks_schedule.source END,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "year_month": year_month,
                    "day_num": day_num,
                    "date_iso": date_iso,
                    "task_key": task_key,
                    "task_title": task_title,
                    "task_description": task_desc,
                    "target_value": target_val,
                    "progress_value": progress_val,
                    "status": status_val,
                    "source": source,
                    "updated_at": now_ts,
                },
            )
            count += 1
        await session.commit()
    return count


async def get_monthly_tasks(
    year_month: str,
    engine: Optional[AsyncEngine] = None,
) -> list:
    """Возвращает сохранённое расписание месячных делюг для указанного YYYY-MM."""
    async with get_session(engine) as session:
        res = await session.execute(
            text(
                "SELECT year_month, day_num, date_iso, task_key, task_title, task_description, "
                "target_value, progress_value, status, source, updated_at "
                "FROM monthly_tasks_schedule WHERE year_month = :ym ORDER BY day_num ASC"
            ),
            {"ym": year_month},
        )
        return [
            {
                "year_month": r[0],
                "day_num": int(r[1]),
                "date_iso": str(r[2]),
                "task_key": str(r[3] or ""),
                "task_title": str(r[4] or ""),
                "task_description": str(r[5] or ""),
                "target_value": int(r[6] or 0),
                "progress_value": int(r[7] or 0),
                "status": str(r[8] or "upcoming"),
                "source": str(r[9] or "api"),
                "updated_at": float(r[10] or 0.0),
            }
            for r in res.fetchall()
        ]


async def get_katala_guard_state(account_id: int = 1, engine: Optional[AsyncEngine] = None) -> dict:
    """Читает персистентное состояние суточного лимита МСК и Circuit Breaker Каталы."""
    from sqlalchemy import select
    from core.models import KatalaGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(KatalaGuardState).where(KatalaGuardState.account_id == account_id)
        )
        row = res.scalar_one_or_none()
        if not row:
            return {
                "account_id": account_id,
                "last_free_day_msk": None,
                "last_free_play_at": None,
                "rubles_guard_tripped": False,
                "guard_reason": None,
            }
        return {
            "account_id": row.account_id,
            "last_free_day_msk": row.last_free_day_msk,
            "last_free_play_at": row.last_free_play_at,
            "rubles_guard_tripped": bool(row.rubles_guard_tripped),
            "guard_reason": row.guard_reason,
        }


async def mark_katala_free_played_today(
    account_id: int,
    day_msk: str,
    last_play_at: Optional[str] = None,
    engine: Optional[AsyncEngine] = None,
) -> None:
    """Персистентно фиксирует сыгранную сегодня (МСК) бесплатную партию Каталы."""
    from sqlalchemy import select
    from core.models import KatalaGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(KatalaGuardState).where(KatalaGuardState.account_id == account_id)
        )
        row = res.scalar_one_or_none()
        if not row:
            row = KatalaGuardState(
                account_id=account_id,
                last_free_day_msk=day_msk,
                last_free_play_at=last_play_at,
                rubles_guard_tripped=False,
            )
            session.add(row)
        else:
            row.last_free_day_msk = day_msk
            if last_play_at:
                row.last_free_play_at = last_play_at
        await session.commit()


async def trip_katala_rubles_guard(
    account_id: int,
    reason: str,
    engine: Optional[AsyncEngine] = None,
) -> None:
    """Активирует персистентный Circuit Breaker при неожиданном списании рублей в Катале."""
    from sqlalchemy import select
    from core.models import KatalaGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(KatalaGuardState).where(KatalaGuardState.account_id == account_id)
        )
        row = res.scalar_one_or_none()
        if not row:
            row = KatalaGuardState(
                account_id=account_id,
                rubles_guard_tripped=True,
                guard_reason=reason,
            )
            session.add(row)
        else:
            row.rubles_guard_tripped = True
            row.guard_reason = reason
        await session.commit()


async def reset_katala_rubles_guard(
    account_id: int = 1,
    engine: Optional[AsyncEngine] = None,
) -> None:
    """Сбрасывает Circuit Breaker Каталы по явному запросу пользователя."""
    from sqlalchemy import select
    from core.models import KatalaGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(KatalaGuardState).where(KatalaGuardState.account_id == account_id)
        )
        row = res.scalar_one_or_none()
        if row:
            row.rubles_guard_tripped = False
            row.guard_reason = None
            await session.commit()


async def get_game_guard_state(account_id: int, game_key: str, engine: Optional[AsyncEngine] = None) -> dict:
    from sqlalchemy import select
    from core.models import GameGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(GameGuardState).where(
                GameGuardState.account_id == account_id,
                GameGuardState.game_key == game_key,
            )
        )
        row = res.scalar_one_or_none()
        if not row:
            return {"account_id": account_id, "game_key": game_key, "guard_tripped": False, "guard_reason": None}
        return {
            "account_id": row.account_id,
            "game_key": row.game_key,
            "guard_tripped": bool(row.guard_tripped),
            "guard_reason": row.guard_reason,
        }


async def trip_game_guard(account_id: int, game_key: str, reason: str, engine: Optional[AsyncEngine] = None) -> None:
    from sqlalchemy import select
    from core.models import GameGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(GameGuardState).where(
                GameGuardState.account_id == account_id,
                GameGuardState.game_key == game_key,
            )
        )
        row = res.scalar_one_or_none()
        if not row:
            session.add(GameGuardState(account_id=account_id, game_key=game_key, guard_tripped=True, guard_reason=reason))
        else:
            row.guard_tripped = True
            row.guard_reason = reason
        await session.commit()


async def reset_game_guard(account_id: int, game_key: str, engine: Optional[AsyncEngine] = None) -> None:
    from sqlalchemy import select
    from core.models import GameGuardState

    async with get_session(engine) as session:
        res = await session.execute(
            select(GameGuardState).where(
                GameGuardState.account_id == account_id,
                GameGuardState.game_key == game_key,
            )
        )
        row = res.scalar_one_or_none()
        if row:
            row.guard_tripped = False
            row.guard_reason = None
            await session.commit()


DEFAULT_OUTREACH_SOURCES = ["weekly_top", "achievements", "tg_channel", "guild"]


def normalize_outreach_criteria(raw: Any = None, cfg: Any = None) -> dict:
    """
    Нормализует и валидирует JSON-критерии авто-рассылки заявок в друзья,
    совмещая `BotConfig.outreach_criteria` и legacy-поля `BotConfig`.
    """
    base = {
        "enabled": bool(getattr(cfg, "auto_friend_outreach", False)) if cfg is not None else False,
        "daily_limit": int(getattr(cfg, "friend_outreach_daily_limit", 50) or 50) if cfg is not None else 50,
        "min_damage": int(getattr(cfg, "friend_outreach_min_damage", 0) or 0) if cfg is not None else 0,
        "max_damage": int(getattr(cfg, "friend_outreach_max_damage", 0) or 0) if cfg is not None else 0,
        "min_authority": 0,
        "max_authority": 0,
        "sources": list(DEFAULT_OUTREACH_SOURCES),
        "sort_by": "fresh",
        "batch_size": 5,
        "delay_between_requests_sec": 3.0,
        "cycle_interval_sec": 300,
        "exclude_keywords": "",
    }
    if isinstance(raw, dict):
        for k in base:
            if k in raw and raw[k] is not None:
                base[k] = raw[k]
    if cfg is not None and "auto_friend_outreach" in getattr(cfg, "__dict__", {}):
        # Синхронизируем enabled с legacy-флагом, если raw не переопределял его явно
        if not isinstance(raw, dict) or "enabled" not in raw:
            base["enabled"] = bool(getattr(cfg, "auto_friend_outreach", False))

    base["enabled"] = bool(base["enabled"])
    base["daily_limit"] = max(1, min(100, int(base["daily_limit"] or 50)))
    base["min_damage"] = max(0, int(base["min_damage"] or 0))
    base["max_damage"] = max(0, int(base["max_damage"] or 0))
    if base["max_damage"] > 0 and base["min_damage"] > base["max_damage"]:
        base["min_damage"], base["max_damage"] = base["max_damage"], base["min_damage"]

    base["min_authority"] = max(0, int(base["min_authority"] or 0))
    base["max_authority"] = max(0, int(base["max_authority"] or 0))
    if base["max_authority"] > 0 and base["min_authority"] > base["max_authority"]:
        base["min_authority"], base["max_authority"] = base["max_authority"], base["min_authority"]

    raw_sources = base.get("sources")
    if isinstance(raw_sources, list):
        clean_sources = [str(s).strip() for s in raw_sources if str(s).strip()]
        base["sources"] = clean_sources if clean_sources else list(DEFAULT_OUTREACH_SOURCES)
    else:
        base["sources"] = list(DEFAULT_OUTREACH_SOURCES)

    sort_by = str(base.get("sort_by") or "fresh").lower().strip()
    base["sort_by"] = sort_by if sort_by in ("fresh", "damage", "authority") else "fresh"
    base["batch_size"] = max(1, min(20, int(base["batch_size"] or 5)))
    base["delay_between_requests_sec"] = max(1.0, min(30.0, float(base["delay_between_requests_sec"] or 3.0)))
    base["cycle_interval_sec"] = max(60, min(3600, int(base["cycle_interval_sec"] or 300)))
    base["exclude_keywords"] = str(base.get("exclude_keywords") or "").strip()
    return base


async def count_outreach_sent_last_24h(
    account_id: int = 1,
    now_ts: Optional[float] = None,
    engine: Optional[AsyncEngine] = None,
) -> int:
    """Считает количество успешно отправленных заявок (`status == 'sent'`) за скользящие 24 часа."""
    import time as _time
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from core.models import FriendOutreachHistory, SentFriendRequest

    cur_ts = float(now_ts if now_ts is not None else _time.time())
    cutoff_ts = cur_ts - 86400.0
    async with get_session(engine) as session:
        res_hist = await session.execute(
            select(FriendOutreachHistory.target_id).where(
                FriendOutreachHistory.account_id == account_id,
                FriendOutreachHistory.status == "sent",
                FriendOutreachHistory.sent_at >= cutoff_ts,
            )
        )
        hist_ids = {int(r) for r in res_hist.scalars().all() if r is not None}

        cutoff_dt = datetime.utcfromtimestamp(cutoff_ts)
        res_legacy = await session.execute(
            select(SentFriendRequest.target_user_id).where(
                SentFriendRequest.account_id == account_id,
                SentFriendRequest.status == "sent",
                SentFriendRequest.created_at >= cutoff_dt,
            )
        )
        legacy_ids = {int(r) for r in res_legacy.scalars().all() if r is not None}
    return len(hist_ids | legacy_ids)


async def get_outreach_excluded_ids(
    account_id: int = 1,
    engine: Optional[AsyncEngine] = None,
) -> set[int]:
    """Возвращает множество target_id, которым уже отправлялась заявка или они недоступны."""
    from sqlalchemy import select
    from core.models import FriendOutreachHistory, SentFriendRequest

    excluded: set[int] = set()
    async with get_session(engine) as session:
        res_h = await session.execute(
            select(FriendOutreachHistory.target_id).where(
                FriendOutreachHistory.account_id == account_id,
                FriendOutreachHistory.status.in_(["sent", "already_friend", "already_pending", "privacy_blocked"]),
            )
        )
        for uid in res_h.scalars().all():
            if uid is not None:
                excluded.add(int(uid))

        res_l = await session.execute(
            select(SentFriendRequest.target_user_id).where(
                SentFriendRequest.account_id == account_id,
            )
        )
        for uid in res_l.scalars().all():
            if uid is not None:
                excluded.add(int(uid))
    return excluded


async def record_outreach_history(
    account_id: int,
    target_id: int,
    nickname: str = "",
    source: str = "radar",
    damage: int = 0,
    authority: int = 0,
    status: str = "sent",
    error_message: Optional[str] = None,
    sent_at: Optional[float] = None,
    engine: Optional[AsyncEngine] = None,
) -> None:
    """Сохраняет или обновляет запись в `friend_outreach_history` (upsert по account_id + target_id)."""
    import time as _time
    from sqlalchemy import select
    from core.models import FriendOutreachHistory

    ts = float(sent_at if sent_at is not None else _time.time())
    async with get_session(engine) as session:
        stmt = select(FriendOutreachHistory).where(
            FriendOutreachHistory.account_id == account_id,
            FriendOutreachHistory.target_id == int(target_id),
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.nickname = nickname or existing.nickname
            existing.source = source or existing.source
            existing.damage = max(int(existing.damage or 0), int(damage or 0))
            existing.authority = max(int(existing.authority or 0), int(authority or 0))
            existing.status = status
            existing.error_message = error_message[:255] if error_message else None
            existing.sent_at = ts
        else:
            session.add(
                FriendOutreachHistory(
                    account_id=account_id,
                    target_id=int(target_id),
                    nickname=nickname or f"Игрок #{target_id}",
                    source=source or "radar",
                    damage=int(damage or 0),
                    authority=int(authority or 0),
                    status=status,
                    error_message=error_message[:255] if error_message else None,
                    sent_at=ts,
                )
            )
        await session.commit()
