"""Seed the patient database with demo patients.

Idempotent: a patient is only inserted if no active patient already exists
with the same normalized phone number.

Run with:
    uv run python scripts/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.patient import service  # noqa: E402
from app.modules.patient.schemas import PatientCreate  # noqa: E402


# Fictional demo records using human-readable values to exercise
# the application's normalization and validation logic.
_DEMO_PATIENTS: list[dict[str, str]] = [
    {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "03/14/1990",
        "sex": "Female",
        "phone_number": "(415) 555-0142",
        "address_line_1": "1 Market St",
        "address_line_2": "Apt 12B",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105",
        "email": "jane.doe@example.com",
        "insurance_provider": "Blue Cross Blue Shield",
        "insurance_member_id": "BCBS8841203",
        "preferred_language": "English",
        "emergency_contact_name": "Robert Doe",
        "emergency_contact_phone": "415-555-0199",
    },
    {
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "11/02/1985",
        "sex": "Male",
        "phone_number": "212-555-0177",
        "address_line_1": "350 Fifth Ave",
        "city": "New York",
        "state": "ny",
        "zip_code": "10118",
        "email": "j.smith@example.com",
        "insurance_provider": "Aetna",
        "insurance_member_id": "AET5529014",
    },
    {
        "first_name": "Maria",
        "last_name": "Garcia",
        "date_of_birth": "07/22/1978",
        "sex": "Female",
        "phone_number": "(305) 555-0188",
        "address_line_1": "800 Ocean Dr",
        "city": "Miami",
        "state": "FL",
        "zip_code": "33139",
        "email": "maria.garcia@example.com",
        "preferred_language": "Spanish",
        "insurance_provider": "Cigna",
        "insurance_member_id": "CIG7730025",
        "emergency_contact_name": "Luis Garcia",
        "emergency_contact_phone": "305-555-0190",
    },
    {
        "first_name": "David",
        "last_name": "O'Brien",
        "date_of_birth": "01/09/1965",
        "sex": "Male",
        "phone_number": "617-555-0151",
        "address_line_1": "100 Beacon St",
        "city": "Boston",
        "state": "MA",
        "zip_code": "02116",
        "email": "dobrien@example.com",
        "insurance_provider": "UnitedHealthcare",
        "insurance_member_id": "UHC1192847",
    },
    {
        "first_name": "Aisha",
        "last_name": "Khan",
        "date_of_birth": "09/30/1998",
        "sex": "Female",
        "phone_number": "(312) 555-0164",
        "address_line_1": "233 S Wacker Dr",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60606",
        "email": "aisha.khan@example.com",
        "emergency_contact_name": "Omar Khan",
        "emergency_contact_phone": "312-555-0165",
    },
    {
        "first_name": "Mary-Jane",
        "last_name": "Watson",
        "date_of_birth": "05/18/1992",
        "sex": "Female",
        "phone_number": "206-555-0133",
        "address_line_1": "400 Broad St",
        "city": "Seattle",
        "state": "WA",
        "zip_code": "98109",
        "insurance_provider": "Kaiser Permanente",
        "insurance_member_id": "KP44820071",
    },
    {
        "first_name": "Chen",
        "last_name": "Wei",
        "date_of_birth": "12/03/1988",
        "sex": "Male",
        "phone_number": "(408) 555-0122",
        "address_line_1": "1 Infinite Loop",
        "city": "San Jose",
        "state": "ca",
        "zip_code": "95014",
        "email": "chen.wei@example.com",
        "preferred_language": "Mandarin",
    },
    {
        "first_name": "Fatima",
        "last_name": "Al-Sayed",
        "date_of_birth": "02/27/1973",
        "sex": "Decline to Answer",
        "phone_number": "713-555-0147",
        "address_line_1": "1500 Louisiana St",
        "city": "Houston",
        "state": "TX",
        "zip_code": "77002",
        "email": "fatima.alsayed@example.com",
        "insurance_provider": "Humana",
        "insurance_member_id": "HUM6610338",
        "emergency_contact_name": "Yusuf Al-Sayed",
        "emergency_contact_phone": "713-555-0148",
    },
    {
        "first_name": "James",
        "last_name": "Anderson",
        "date_of_birth": "08/15/1959",
        "sex": "Male",
        "phone_number": "(602) 555-0109",
        "address_line_1": "2 N Central Ave",
        "city": "Phoenix",
        "state": "AZ",
        "zip_code": "85004",
        "insurance_provider": "Medicare",
        "insurance_member_id": "MED0049213",
    },
    {
        "first_name": "Priya",
        "last_name": "Patel",
        "date_of_birth": "06/11/1995",
        "sex": "Female",
        "phone_number": "404-555-0176",
        "address_line_1": "191 Peachtree St NE",
        "city": "Atlanta",
        "state": "GA",
        "zip_code": "30303",
        "email": "priya.patel@example.com",
        "preferred_language": "English",
        "insurance_provider": "Anthem",
        "insurance_member_id": "ANT3387190",
        "emergency_contact_name": "Raj Patel",
        "emergency_contact_phone": "404-555-0178",
    },
]


def seed() -> None:
    """Insert demo patients that do not already exist by phone number."""
    init_db()

    created = 0
    skipped = 0

    db = SessionLocal()

    try:
        for raw in _DEMO_PATIENTS:
            data = PatientCreate(**raw)

            existing = service.find_by_phone(db, data.phone_number)

            if existing is not None:
                print(
                    f"SKIP   {data.first_name} {data.last_name} "
                    f"({data.phone_number}) — "
                    f"already exists as {existing.patient_id}"
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
