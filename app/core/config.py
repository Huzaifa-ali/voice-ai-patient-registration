"""Application configuration — data only, no logic (VLE config rule).

All runtime configuration is loaded from environment variables here so the rest of
the codebase never reads ``os.environ`` directly. Secrets (DB URL, webhook secret)
are supplied via environment variables — never hardcoded — per the security
requirement. Any derived/computed value belongs in the service layer, not here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_db_url(url: str) -> str:
    """Make a database URL SQLAlchemy-friendly.

    Managed Postgres hosts (Railway, Render, Heroku) hand out URLs starting with
    ``postgres://`` or ``postgresql://``. SQLAlchemy needs an explicit driver, so
    we pin the psycopg (v3) driver. SQLite and already-qualified URLs pass through
    unchanged.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


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
    # When True, a missing secret header is rejected. When False (default), a
    # missing header is allowed (Vapi sometimes doesn't forward tool secrets);
    # a *wrong* header is always rejected regardless.
    VAPI_WEBHOOK_STRICT: bool = False

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Observability ──
    LOG_LEVEL: str = "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        """The DATABASE_URL normalized for SQLAlchemy (driver pinned for Postgres)."""
        return _normalize_db_url(self.DATABASE_URL)


settings = Settings()
