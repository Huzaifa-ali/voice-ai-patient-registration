"""Application configuration — data only, no logic (VLE config rule).

All runtime configuration is loaded from environment variables here so the rest of
the codebase never reads ``os.environ`` directly. Secrets (DB URL, webhook secret)
are supplied via environment variables — never hardcoded — per the security
requirement. Any derived/computed value belongs in the service layer, not here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Database ──
    # SQLAlchemy URL. Default is a local SQLite file that persists to disk.
    DATABASE_URL: str = "sqlite:///./patients.db"

    # ── Voice webhook ──
    # Shared secret matched against the header Vapi sends on tool calls. Blank
    # disables the check (local dev only).
    VAPI_WEBHOOK_SECRET: str = ""

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Observability ──
    LOG_LEVEL: str = "INFO"


settings = Settings()
