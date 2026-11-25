from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_user_id = Column(BigInteger, nullable=True)
    nickname = Column(String(100), nullable=True)
    phone = Column(String(50), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session_data = relationship("SessionData", back_populates="account", uselist=False, cascade="all, delete-orphan")
    snapshots = relationship("PlayerSnapshot", back_populates="account", cascade="all, delete-orphan")
    action_logs = relationship("ActionLog", back_populates="account", cascade="all, delete-orphan")
    config = relationship("BotConfig", back_populates="account", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="account", cascade="all, delete-orphan")
    sent_friend_requests = relationship("SentFriendRequest", back_populates="account", cascade="all, delete-orphan")
    tracked_candidates = relationship("TrackedCandidate", back_populates="account", cascade="all, delete-orphan")
    cached_raid_posts = relationship("CachedRaidPost", back_populates="account", cascade="all, delete-orphan")
    friend_stats = relationship("FriendStats", back_populates="account", cascade="all, delete-orphan")
    boss_friend_damage_logs = relationship("BossFriendDamageLog", back_populates="account", cascade="all, delete-orphan")
    friends_count_snapshots = relationship("FriendsCountSnapshot", back_populates="account", cascade="all, delete-orphan")
    boss_presets = relationship("BossPreset", back_populates="account", cascade="all, delete-orphan")
    boss_battle_snapshot = relationship("BossBattleSnapshot", back_populates="account", uselist=False, cascade="all, delete-orphan")


class SessionData(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    access_exp = Column(BigInteger, default=0, nullable=False)
    init_data = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="session_data")


class PlayerSnapshot(Base):
    __tablename__ = "player_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, default=0, nullable=False)
    authority = Column(BigInteger, default=0, nullable=False)
    biceps = Column(BigInteger, default=0, nullable=False)
    energy = Column(Integer, default=0, nullable=False)
    max_energy = Column(Integer, default=0, nullable=False)
    cigarettes = Column(BigInteger, default=0, nullable=False)
    sugar = Column(BigInteger, default=0, nullable=False)
    rubles = Column(BigInteger, default=0, nullable=False)
    paper = Column(BigInteger, default=0, nullable=False)
    soap = Column(BigInteger, default=0, nullable=False)
    can_claim_toilet_paper = Column(Boolean, default=False, nullable=False)
    last_business_collect_time = Column(String(100), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="snapshots")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(100), nullable=False)
    endpoint = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="action_logs")


class BotConfig(Base):
    __tablename__ = "bot_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    is_paused = Column(Boolean, default=False, nullable=False)
    sleep_mode_enabled = Column(Boolean, default=False, nullable=False)
    sleep_start_hour = Column(Integer, default=2, nullable=False)
    sleep_end_hour = Column(Integer, default=7, nullable=False)

    # Routine
    auto_toilet_paper = Column(Boolean, default=False, nullable=False)
    auto_business = Column(Boolean, default=False, nullable=False)
    auto_beard = Column(Boolean, default=False, nullable=False)
    auto_podogrev = Column(Boolean, default=False, nullable=False)
    auto_podogrev_send = Column(Boolean, default=False, nullable=False)
    auto_katala = Column(Boolean, default=False, nullable=False)
    auto_biceps = Column(Boolean, default=False, nullable=False)
    auto_spit_balanda = Column(Boolean, default=False, nullable=False)
    auto_throw_yeast = Column(Boolean, default=False, nullable=False)
    auto_monthly_tasks = Column(Boolean, default=False, nullable=False)
    auto_kolsik = Column(Boolean, default=False, nullable=False)
    kolsik_currency = Column(String(20), default="paper", nullable=False)

    # Bosses
    auto_boss_enabled = Column(Boolean, default=False, nullable=False)
    auto_boss_hits = Column(Boolean, default=False, nullable=False)
    auto_boss_summon = Column(Boolean, default=False, nullable=False)
    boss_auto_melee = Column(Boolean, default=False, nullable=False)
    boss_allow_paid_weapons = Column(Boolean, default=False, nullable=False)
    boss_targets = Column(JSON, default=list, nullable=False)

    # Prisons & Masters
    auto_prison = Column(Boolean, default=False, nullable=False)
    prison_target_id = Column(Integer, default=0, nullable=False)
    prison_prefer_night = Column(Boolean, default=False, nullable=False)
    prison_min_energy = Column(Integer, default=10, nullable=False)
    auto_masters = Column(Boolean, default=False, nullable=False)
    master_target_id = Column(Integer, default=1, nullable=False)

    # Social & Events
    auto_gifts = Column(Boolean, default=False, nullable=False)
    auto_friends = Column(Boolean, default=False, nullable=False)
    auto_events = Column(Boolean, default=False, nullable=False)

    # Friend Filters
    friend_accept_all = Column(Boolean, default=False, nullable=False)
    friend_filter_mode = Column(String(10), default="and", nullable=False)  # "and" | "or"
    friend_min_level = Column(Integer, default=0, nullable=False)
    friend_min_authority = Column(BigInteger, default=0, nullable=False)
    friend_min_biceps = Column(Integer, default=0, nullable=False)
    friend_min_talents = Column(Integer, default=0, nullable=False)
    friend_min_poison_damage = Column(Integer, default=0, nullable=False)
    friend_min_total_damage = Column(Integer, default=0, nullable=False)
    friend_auto_decline_below = Column(Boolean, default=False, nullable=False)

    # Friend Outreach & Limits (Safe Auto-Friend Radar)
    auto_friend_outreach = Column(Boolean, default=False, nullable=False)
    auto_parse_news_raids = Column(Boolean, default=False, nullable=False)
    friend_outreach_daily_limit = Column(Integer, default=50, nullable=False)
    friend_outreach_min_damage = Column(BigInteger, default=0, nullable=False)
    friend_outreach_max_damage = Column(BigInteger, default=0, nullable=False)
    friend_outreach_only_active = Column(Boolean, default=True, nullable=False)
    friends_parser_tier = Column(String(20), default="accessible", nullable=False)
    friends_parser_min_authority = Column(BigInteger, default=0, nullable=False)
    friends_parser_max_authority = Column(BigInteger, default=0, nullable=False)
    raid_tg_channels = Column(JSON, default=list, nullable=False)
    guild_scan_cursor = Column(Integer, default=0, nullable=False)

    # Friend Cleanup
    auto_friend_cleanup = Column(Boolean, default=False, nullable=False)
    friend_cleanup_inactive_days = Column(Integer, default=14, nullable=False)
    friend_cleanup_daily_limit = Column(Integer, default=5, nullable=False)
    friend_cleanup_trigger_threshold = Column(Integer, default=10, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="config")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(32), index=True, nullable=False)  # "bosses", "prisons", "business", "other"
    title = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True)
    rewards = Column(JSON, default=list, nullable=False)
    drops = Column(JSON, default=list, nullable=False)
    meta_json = Column(JSON, default=dict, nullable=False)
    is_read = Column(Boolean, default=False, index=True, nullable=False)
    event_key = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    account = relationship("Account", back_populates="notifications")


class SentFriendRequest(Base):
    __tablename__ = "sent_friend_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id = Column(BigInteger, nullable=False, index=True)
    target_nickname = Column(String(100), nullable=True)
    source = Column(String(50), default="radar", nullable=False)  # "raid", "radar", "import", "news_ad", "tg_channel", "guild", "weekly_top", "achievements"
    status = Column(String(32), default="sent", nullable=False)  # "sent", "accepted", "ignored", "failed"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="sent_friend_requests")


class TrackedCandidate(Base):
    __tablename__ = "tracked_candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    nickname = Column(String(100), nullable=True)
    photo_url = Column(Text, nullable=True)

    guild_id = Column(Integer, nullable=True)
    guild_name = Column(String(100), nullable=True)

    level = Column(Integer, default=0, nullable=False)
    authority = Column(BigInteger, default=0, nullable=False)
    prev_authority = Column(BigInteger, default=0, nullable=False)
    authority_delta = Column(BigInteger, default=0, nullable=False)

    poison_damage = Column(Integer, default=0, nullable=False)
    gunshot_damage = Column(Integer, default=0, nullable=False)
    knife_damage = Column(Integer, default=0, nullable=False)
    total_damage = Column(BigInteger, default=0, nullable=False)
    prev_total_damage = Column(BigInteger, default=0, nullable=False)
    damage_delta = Column(BigInteger, default=0, nullable=False)
    camp_activity = Column(Integer, default=0, nullable=False)
    talents = Column(Integer, default=0, nullable=False)
    score = Column(Integer, default=0, index=True, nullable=False)
    enriched_at = Column(DateTime, nullable=True)

    source = Column(String(50), default="guild", nullable=False)  # "guild", "weekly_top", "tg_channel", "import", "news_ad", "achievements"
    is_active_recently = Column(Boolean, default=False, nullable=False)

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_snapshot_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="tracked_candidates")

    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_tracked_candidate_acc_user"),
    )


class CachedRaidPost(Base):
    __tablename__ = "cached_raid_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_username = Column(String(100), nullable=False, index=True)
    message_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    post_date = Column(DateTime, nullable=True)
    raw_preview = Column(Text, nullable=True)
    participants = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    account = relationship("Account", back_populates="cached_raid_posts")

    __table_args__ = (
        UniqueConstraint("account_id", "channel_username", "message_id", name="uq_cached_raid_post_msg"),
    )


class FriendStats(Base):
    __tablename__ = "friend_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    nickname = Column(String(100), nullable=True)
    photo_url = Column(Text, nullable=True)

    level = Column(Integer, default=0, nullable=False)
    authority = Column(BigInteger, default=0, nullable=False)
    prev_authority = Column(BigInteger, default=0, nullable=False)

    biceps = Column(Integer, default=0, nullable=False)
    talents = Column(Integer, default=0, nullable=False)

    poison_damage = Column(Integer, default=0, nullable=False)
    gunshot_damage = Column(Integer, default=0, nullable=False)
    knife_damage = Column(Integer, default=0, nullable=False)

    total_damage_to_my_bosses = Column(BigInteger, default=0, nullable=False)
    boss_hits_count = Column(Integer, default=0, nullable=False)
    last_boss_hit_at = Column(DateTime, nullable=True)

    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_whitelisted = Column(Boolean, default=False, nullable=False)
    is_current_friend = Column(Boolean, default=True, index=True, nullable=False)

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="friend_stats")

    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_friend_stats_acc_user"),
    )


class BossFriendDamageLog(Base):
    __tablename__ = "boss_friend_damage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    boss_session_id = Column(String(128), nullable=False, index=True)
    boss_id = Column(Integer, nullable=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    recorded_damage = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True, nullable=False)

    account = relationship("Account", back_populates="boss_friend_damage_logs")

    __table_args__ = (
        UniqueConstraint("account_id", "boss_session_id", "user_id", name="uq_boss_friend_dmg_session_user"),
    )


class FriendsCountSnapshot(Base):
    __tablename__ = "friends_count_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    friends_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    account = relationship("Account", back_populates="friends_count_snapshots")


class BossBattleSnapshot(Base):
    __tablename__ = "boss_battle_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    boss_id = Column(Integer, nullable=True)
    boss_name = Column(String(120), nullable=True)
    mode = Column(String(40), nullable=True)
    session_id = Column(String(128), nullable=True)
    current_hp = Column(BigInteger, default=0, nullable=False)
    max_hp = Column(BigInteger, default=0, nullable=False)
    total_damage = Column(BigInteger, default=0, nullable=False)
    personal_damage = Column(BigInteger, default=0, nullable=False)
    ends_at = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="boss_battle_snapshot")


class BossPreset(Base):
    """
    Пресет боссов: список шагов (босс + режим + количество) с ежедневным расписанием по МСК.
    """
    __tablename__ = "boss_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    items = Column(JSON, nullable=False, default=list)  # [{"bossId": int, "bossName": str, "mode": str, "count": int}]
    daily_enabled = Column(Boolean, nullable=False, default=False)
    schedule_time_msk = Column(String(5), nullable=False, default="09:00")
    last_run_date_msk = Column(String(10), nullable=True)  # "YYYY-MM-DD"
    is_running = Column(Boolean, nullable=False, default=False)
    current_step_index = Column(Integer, nullable=False, default=0)
    last_status = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="boss_presets")


class DailyInteractionTarget(Base):
    """
    Суточный трекер целей авто-взаимодействий по МСК (biceps vs negative).
    Гарантирует правило игры: 1 негативное действие (Harknut или TossDroj) на игрока в сутки.
    """
    __tablename__ = "daily_interaction_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    day_msk = Column(String(16), nullable=False, index=True)
    action_group = Column(String(24), nullable=False)  # "biceps" | "negative"
    target_id = Column(BigInteger, nullable=False)
    action_type = Column(String(32), nullable=False)  # "UpgradeBiceps" | "Harknut" | "TossDroj"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "day_msk", "action_group", "target_id", name="uq_daily_interaction_target"),
    )

