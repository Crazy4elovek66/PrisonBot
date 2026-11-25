from contextlib import asynccontextmanager
from pathlib import Path
import re
from typing import AsyncGenerator, Optional
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
    ]

    for col_name, col_type in col_defs:
        if col_name not in existing_cols:
            connection.execute(text(f"ALTER TABLE bot_configs ADD COLUMN {col_name} {col_type};"))

    # Миграция старого дефолтного лимита 25 -> 50 (если не настраивался пользователем вручную)
    if "friend_outreach_daily_limit" in existing_cols:
        connection.execute(
            text("UPDATE bot_configs SET friend_outreach_daily_limit = 50 WHERE friend_outreach_daily_limit = 25;")
        )


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


def is_worker_active(config) -> bool:
    """Проверка активности воркера с учетом паузы и режима сна (время МСК)."""
    from datetime import datetime, timezone, timedelta

    if getattr(config, "is_paused", False):
        return False
    if getattr(config, "sleep_mode_enabled", False):
        now_msk = datetime.now(timezone.utc) + timedelta(hours=3)
        current_hour = now_msk.hour
        start = getattr(config, "sleep_start_hour", 2)
        end = getattr(config, "sleep_end_hour", 7)
        if start <= end:
            if start <= current_hour < end:
                return False
        else:
            if current_hour >= start or current_hour < end:
                return False
    return True


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
