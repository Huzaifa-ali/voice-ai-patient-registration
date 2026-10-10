"""Patient REST API router.

Implements the five endpoints from the brief with proper status codes
(200/201/400/404/422/500) and the ``{ data, error }`` envelope.

Thin-router discipline: the router calls one service function and returns. The only
"logic" it owns is request-shape translation — wrapping Pydantic schema construction
in ``try/except ValidationError`` to produce the 422 envelope. That is an HTTP concern
(malformed request body), not a business decision; domain errors like 404 are raised
by the service and rendered by the global handler.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.common.schemas import err, ok
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.modules.patient import service
from app.modules.patient.schemas import PatientCreate, PatientUpdate

logger = get_logger("patient.api")

router = APIRouter(prefix="/patients", tags=["patients"])


def _flatten(exc: ValidationError) -> list[dict]:
    """Flatten Pydantic errors into a compact ``[{field, message}]`` list."""
    return [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]


@router.get("")
def list_patients(
    last_name: str | None = None,
    date_of_birth: str | None = None,
    phone_number: str | None = None,
    db: Session = Depends(get_db),
):
    """List all (non-deleted) patients, newest first, with optional filters."""
    patients = service.list_patients(
        db,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
    )
    return ok([p.to_dict() for p in patients])


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve a single patient by UUID (404 if missing/soft-deleted)."""
    patient = service.get_patient(db, patient_id)
    return ok(patient.to_dict())


@router.post("")
async def create_patient(request: Request, db: Session = Depends(get_db)):
    """Create a new patient. Returns 201 with the created record."""
    try:
        body = await request.json()
    except Exception:
        return err("BAD_REQUEST", "Request body must be valid JSON", 400)
    if not isinstance(body, dict):
        return err("BAD_REQUEST", "Request body must be a JSON object", 400)

    try:
        data = PatientCreate(**body)
    except ValidationError as exc:
        return err("VALIDATION_ERROR", "Validation failed", 422, fields=_flatten(exc))

    patient = service.create_patient(db, data)
    logger.info(
        "Created patient %s (%s %s)",
        patient.patient_id,
        patient.first_name,
        patient.last_name,
    )
    return ok(patient.to_dict(), status_code=201)


@router.put("/{patient_id}")
async def update_patient(
    patient_id: str, request: Request, db: Session = Depends(get_db)
):
    """Partial update of an existing patient (404 if missing/soft-deleted)."""
    try:
        body = await request.json()
    except Exception:
        return err("BAD_REQUEST", "Request body must be valid JSON", 400)
    if not isinstance(body, dict):
        return err("BAD_REQUEST", "Request body must be a JSON object", 400)

    try:
        data = PatientUpdate(**body)
    except ValidationError as exc:
        return err("VALIDATION_ERROR", "Validation failed", 422, fields=_flatten(exc))

    patient = service.update_patient(db, patient_id, data)
    logger.info("Updated patient %s", patient_id)
    return ok(patient.to_dict())


@router.delete("/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    """Soft-delete a patient (sets deleted_at; row is retained)."""
    patient = service.soft_delete_patient(db, patient_id)
    logger.info("Soft-deleted patient %s", patient_id)
    deleted_at = patient.deleted_at.isoformat() if patient.deleted_at else None
    return ok({"patient_id": patient_id, "deleted_at": deleted_at})
