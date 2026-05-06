from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: Literal["dev", "prod", "test"] = "dev"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    MASTER_SCHEMA: str = "public"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 1440

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-7"

    REDIS_URL: str = "redis://redis:6379/0"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@anutech.in"

    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REFRESH_TOKEN: str = ""

    APP_BASE_DOMAIN: str = "payroll.anutech.in"
    CORS_ORIGINS: str = Field(
        default="",
        description="Comma-separated extra allowed origins (e.g. https://anutech-frontend.onrender.com)",
    )
    AUTO_INIT_DB: bool = Field(
        default=False,
        description="Run master_schema.sql on startup (safe — idempotent). Recommended for cloud platforms.",
    )
    AUTO_SEED_TENANT: bool = Field(
        default=False,
        description="Seed the Anutech demo tenant on startup if missing.",
    )

    DEFAULT_PROFESSIONAL_TAX: float = Field(default=200.0, description="Maharashtra default")
    ESI_GROSS_THRESHOLD: float = Field(default=21000.0)

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
