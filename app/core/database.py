"""Database engine, session management, and schema initialisation.

Synchronous SQLAlchemy over SQLite by default. SQLite keeps the challenge simple and
zero-config while still being a real relational database that persists to disk — so
data survives restarts and spans multiple calls (NFR-1). Swap ``DATABASE_URL`` to a
Postgres URL and nothing else here needs to change.

Transaction model (mirrors VLE, sync variant):
  - CRUD methods ``add``/``flush`` only (make changes visible, get generated ids).
  - The ``get_db`` dependency commits on success and rolls back on error.
  - This keeps a request a single atomic transaction.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# SQLite needs ``check_same_thread=False`` so a connection can be used across
# FastAPI's threadpool. Harmless/ignored for other engines.
_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def init_db() -> None:
    """Create tables if they do not exist. Called once at application startup."""
    # Import models so they register on Base.metadata before create_all.
    from app.modules.patient import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session, commit on success, roll back on error.

    CRUD methods flush (not commit) within the request; this boundary owns the
    final commit/rollback and always closes the session.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
