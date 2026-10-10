"""Patient ORM model.

Enforces the brief's demographic data model with appropriate column types, lengths,
nullability, and a CHECK constraint on ``sex``. Soft-delete is implemented via
``deleted_at`` (DELETE sets the timestamp rather than removing the row).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _new_uuid() -> str:
    """Generate a string UUID4 for the primary key."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Timezone-aware UTC now (created/updated/deleted timestamps)."""
    return datetime.now(timezone.utc)


class Patient(Base):
    """A registered patient and their demographic data."""

    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "sex IN ('Male', 'Female', 'Other', 'Decline to Answer')",
            name="ck_patients_sex_valid",
        ),
    )

    # --- Identity / audit ---------------------------------------------------
    patient_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    # Soft-delete marker. NULL = active, non-NULL = deleted.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # --- Required demographics ---------------------------------------------
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # ISO date string (YYYY-MM-DD) — portable and sufficient for a date-only field.
    date_of_birth: Mapped[str] = mapped_column(String(10), nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # --- Optional demographics ---------------------------------------------
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insurance_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurance_member_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="English"
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict for API responses."""

        def iso(dt: datetime | None) -> str | None:
            return dt.isoformat() if dt else None

        return {
            "patient_id": self.patient_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "date_of_birth": self.date_of_birth,
            "sex": self.sex,
            "phone_number": self.phone_number,
            "email": self.email,
            "address_line_1": self.address_line_1,
            "address_line_2": self.address_line_2,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "insurance_provider": self.insurance_provider,
            "insurance_member_id": self.insurance_member_id,
            "preferred_language": self.preferred_language,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "deleted_at": iso(self.deleted_at),
        }
