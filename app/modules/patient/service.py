"""Patient service layer — the single source of truth for patient operations.

Both the REST API and the voice webhook call into this module, so persistence and
business rules (soft-delete, duplicate detection, timestamp bumps, 404 ownership)
live in exactly one place.

404 ownership: ``get/update/soft_delete`` take a ``patient_id`` and raise
``PatientNotFound`` when the row is missing or soft-deleted, so routers stay thin.
``find_by_phone`` is the deliberate exception — a non-match is a normal ``None``
(duplicate detection, not an error).

Transaction model: CRUD flushes; the ``get_db`` request boundary commits.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.patient.crud import patient_crud
from app.modules.patient.exceptions import PatientNotFound
from app.modules.patient.models import Patient
from app.modules.patient.schemas import PatientCreate, PatientUpdate


def create_patient(db: Session, data: PatientCreate) -> Patient:
    """Insert a new patient and return the persisted row."""
    return patient_crud.create(db, **data.model_dump())


def get_patient(db: Session, patient_id: str) -> Patient:
    """Return an active patient or raise ``PatientNotFound``."""
    patient = patient_crud.get_active(db, patient_id)
    if patient is None:
        raise PatientNotFound(patient_id)
    return patient


def list_patients(
    db: Session,
    *,
    last_name: str | None = None,
    date_of_birth: str | None = None,
    phone_number: str | None = None,
) -> list[Patient]:
    """List active patients with optional filters, newest first."""
    return patient_crud.list_filtered(
        db,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
    )


def update_patient(db: Session, patient_id: str, data: PatientUpdate) -> Patient:
    """Apply a partial update to an existing patient (or raise ``PatientNotFound``)."""
    patient = get_patient(db, patient_id)
    changes = data.model_dump(exclude_unset=True)
    return patient_crud.update(db, patient, **changes)


def soft_delete_patient(db: Session, patient_id: str) -> Patient:
    """Soft-delete: set ``deleted_at`` rather than removing the row."""
    patient = get_patient(db, patient_id)
    return patient_crud.update(db, patient, deleted_at=datetime.now(timezone.utc))


def find_by_phone(db: Session, phone_number: str) -> Patient | None:
    """Duplicate detection: active patient matching a phone number, or None."""
    return patient_crud.get_by_phone(db, phone_number)
