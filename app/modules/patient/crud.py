"""Patient data-access layer.

Pure data access via ``CRUDBase`` plus named query methods for anything non-trivial
(soft-delete filtering, combined filters, phone lookup). No business logic here —
the service decides what a ``None`` means (VLE layer rules).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.crud_base import CRUDBase
from app.modules.patient.models import Patient


def _phone_digits(value: str) -> str:
    """Normalise a phone string to comparable 10-digit form (best effort)."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


class CRUDPatient(CRUDBase[Patient, None, None]):
    model = Patient

    def get_active(self, db: Session, patient_id: str) -> Patient | None:
        """Fetch a non-deleted patient by id, or None."""
        stmt = (
            select(Patient)
            .where(Patient.patient_id == patient_id)
            .where(Patient.deleted_at.is_(None))
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_filtered(
        self,
        db: Session,
        *,
        last_name: str | None = None,
        date_of_birth: str | None = None,
        phone_number: str | None = None,
    ) -> list[Patient]:
        """List non-deleted patients, newest first, with optional combined filters."""
        stmt = select(Patient).where(Patient.deleted_at.is_(None))
        if last_name:
            stmt = stmt.where(Patient.last_name.ilike(last_name))
        if date_of_birth:
            stmt = stmt.where(Patient.date_of_birth == date_of_birth)
        if phone_number:
            digits = _phone_digits(phone_number)
            if digits:
                stmt = stmt.where(Patient.phone_number == digits)
        stmt = stmt.order_by(Patient.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    def get_by_phone(self, db: Session, phone_number: str) -> Patient | None:
        """Return the most recent active patient matching a phone number, or None."""
        digits = _phone_digits(phone_number)
        if len(digits) != 10:
            return None
        stmt = (
            select(Patient)
            .where(Patient.phone_number == digits)
            .where(Patient.deleted_at.is_(None))
            .order_by(Patient.created_at.desc())
        )
        return db.execute(stmt).scalars().first()


patient_crud = CRUDPatient()
