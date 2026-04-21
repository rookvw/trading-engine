from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator
from typing import Literal
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: Literal["development", "production"] = "development"
    secret_key: str = "dev-secret-change-in-production"
    allowed_origins: str = "http://localhost:3000"

    # Database
    database_url: str
    database_url_sync: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kiwoom
    kiwoom_app_key: str = ""
    kiwoom_app_secret: str = ""
    kiwoom_account_number: str = ""
    kiwoom_env: Literal["real", "mock"] = "real"
    kiwoom_base_url: str = "https://api.kiwoom.com"
    kiwoom_ws_url: str = "wss://api.kiwoom.com:10000"

    # Order safety
    order_execution_enabled: bool = False       # kill switch
    order_max_amount_krw: int = 5_000_000       # 1회 최대 주문액

    # Scheduler
    theme_score_interval_minutes: int = 30
    portfolio_sync_interval_minutes: int = 5

    @property
    def origins_list(self) -> list[str]:
        v = self.allowed_origins.strip()
        if v.startswith("["):
            import json
            return json.loads(v)
        return [o.strip() for o in v.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def kiwoom_configured(self) -> bool:
        return bool(self.kiwoom_app_key and self.kiwoom_app_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
