from typing import Dict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Game API Configuration
    API_BASE_URL: str = "https://oldprison-prod.luckygem.online"
    BOT_USERNAME: str = "oldprison_bot"
    WEBAPP_URL: str = "https://oldprison-prod.luckygem.online/"

    # Telegram MTProto Credentials
    TG_API_ID: int = 0
    TG_API_HASH: str = ""
    TG_PHONE: str = ""
    TG_SESSION_PATH: str = "storage/user_session"

    # Database Configuration
    DB_URL: str = "sqlite+aiosqlite:///storage/prison_bot.db"

    # Client Emulation Settings
    CLIENT_PLATFORM: str = "web"
    CLIENT_LANGUAGE: str = "ru"
    CLIENT_COUNTRY: str = "RU"

    # Scheduler & Timing Settings
    ROUTINE_INTERVAL_MINUTES: int = 15
    JITTER_MIN_SEC: float = 1.5
    JITTER_MAX_SEC: float = 4.0

    # Business & Boss Settings
    BUSINESS_COLLECT_MIN_MINUTES: int = 480
    BOSS_INTERVAL_MINUTES: int = 10
    BOSS_ALLOW_PAID_WEAPONS: bool = False

    # Prison & Energy Settings
    PRISON_INTERVAL_MINUTES: int = 3
    PRISON_MIN_ENERGY: int = 0
    PRISON_TARGET_ID: int = 0  # 0 for highest unlocked prison, or specific prisonId
    PRISON_PREFER_NIGHT: bool = False
    PRISON_ALLOW_ENERGY_REFILL: bool = False  # strict prohibition on spending soap/chefir/rubles

    # Telegram Management Bot
    TG_BOT_TOKEN: str = ""
    ADMIN_TG_ID: int = 0

    # Social & Events Settings
    SOCIAL_INTERVAL_MINUTES: int = 30
    NOTIFICATIONS_RETENTION_DAYS: int = 7

    # Web Dashboard & Mini App Server
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8080
    WEBAPP_PUBLIC_URL: str = ""
    WEB_ADMIN_TOKEN: str = "prison_local_admin"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "X-Language": self.CLIENT_LANGUAGE,
            "X-Country": self.CLIENT_COUNTRY,
            "X-Platform": self.CLIENT_PLATFORM,
            "Origin": self.API_BASE_URL,
            "Referer": f"{self.API_BASE_URL}/",
        }


settings = Settings()
