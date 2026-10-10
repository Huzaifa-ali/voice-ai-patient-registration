"""Seed the patient database with a couple of demo patients.

Idempotent: a patient is only inserted if no active patient already exists with the
same (normalised) phone number. Safe to run repeatedly.

Run with:
    uv run python scripts/seed.py

Uses the application's own service/validation layer so seeded rows go through the
exact same normalisation (phone, sex, state, DOB, ...) as real API/voice writes.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``app`` importable when run as a plain script (``uv run python scripts/seed.py``).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.patient import service  # noqa: E402
from app.modules.patient.schemas import PatientCreate  # noqa: E402

# Demo patients. These are intentionally written in "human" form (formatted phone,
# MM/DD/YYYY date, lowercase state) to prove the normalisation path works end to end.
_DEMO_PATIENTS: list[dict[str, str]] = [
    {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "03/14/1990",
        "sex": "Female",
        "phone_number": "(415) 555-0142",
        "address_line_1": "1 Market St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105",
        "email": "jane.doe@example.com",
    },
    {
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "11/02/1985",
        "sex": "M",
        "phone_number": "212-555-0177",
        "address_line_1": "350 Fifth Ave",
        "city": "New York",
        "state": "ny",
        "zip_code": "10118",
    },
]


def seed() -> None:
    """Insert demo patients that are not already present (by phone number)."""
    init_db()
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        for raw in _DEMO_PATIENTS:
            data = PatientCreate(**raw)
            # ``data.phone_number`` is already normalised to 10 digits by the schema.
            existing = service.find_by_phone(db, data.phone_number)
            if existing is not None:
                print(
                    f"SKIP  {data.first_name} {data.last_name} "
                    f"({data.phone_number}) — already exists as {existing.patient_id}"
                )
                skipped += 1
                continue
            patient = service.create_patient(db, data)
            db.commit()
            print(
                f"CREATE {patient.first_name} {patient.last_name} "
                f"({patient.phone_number}) — id {patient.patient_id}"
            )
            created += 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"\nDone. created={created} skipped={skipped}")


if __name__ == "__main__":
    seed()
