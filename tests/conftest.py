"""Pytest fixtures for the patient-registration backend.

Isolation strategy
------------------
The app binds its SQLAlchemy engine at import time from ``settings.DATABASE_URL``.
We therefore point ``DATABASE_URL`` at a throwaway temp SQLite file *before* importing
anything from ``app`` (see the module-level env setup below). This guarantees the real
``./patients.db`` is never touched by the test suite.

Each test gets a clean schema: the ``client`` fixture drops and recreates all tables
on the shared test engine, then yields a ``TestClient`` used as a context manager so
the FastAPI lifespan (which calls ``init_db()``) also runs.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Make ``app`` importable regardless of how pytest is invoked.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# --- Point the app at a disposable DB BEFORE importing it -------------------
# A single temp file is used for the whole session; the schema is reset per test.
_TMP_DIR = tempfile.mkdtemp(prefix="patient-tests-")
_TEST_DB_PATH = Path(_TMP_DIR) / "test_patients.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
# Keep the webhook secret empty so the Vapi security check is a no-op in tests.
os.environ["VAPI_WEBHOOK_SECRET"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

# Importing the model module registers the ``patients`` table on ``Base.metadata``.
from app.modules.patient import models as _patient_models  # noqa: E402,F401


def _reset_schema() -> None:
    """Drop and recreate every table so each test starts from an empty database."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient backed by a fresh, isolated SQLite schema.

    Used as a context manager so the app lifespan runs (which also calls
    ``init_db()``). The real ``patients.db`` is never involved — the engine is bound
    to a temp file configured at import time.
    """
    _reset_schema()
    with TestClient(app) as test_client:
        yield test_client
    # Leave the schema empty behind us for good measure.
    _reset_schema()


# --- Shared test data -------------------------------------------------------

VALID_PATIENT: dict[str, str] = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "03/14/1990",
    "sex": "Female",
    "phone_number": "(415) 555-0142",
    "address_line_1": "1 Market St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94105",
}


@pytest.fixture
def valid_patient() -> dict[str, str]:
    """A fresh copy of a known-good patient payload."""
    return dict(VALID_PATIENT)
