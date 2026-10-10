"""Patient module domain exceptions.

Raised by the service layer; rendered by the global handler in ``app/main.py``.
"""

from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError


class PatientNotFound(NotFoundError):
    def __init__(self, patient_id: str | None = None) -> None:
        msg = "Patient not found"
        if patient_id:
            msg = f"Patient {patient_id} not found"
        super().__init__(message=msg)


class DuplicatePatient(ConflictError):
    def __init__(self, message: str = "A patient with this phone number already exists") -> None:
        super().__init__(message=message)
