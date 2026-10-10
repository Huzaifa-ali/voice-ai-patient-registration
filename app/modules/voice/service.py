"""Voice webhook business logic — maps Vapi tool calls onto the patient service.

Cross-module rule: this adapter calls ``patient.service`` only (never its crud/models).
It owns the voice-specific concerns: coercing empty/whitespace optional fields from
speech to ``None`` (so an unspoken email does not fail ``EmailStr``), and turning
outcomes into flat strings the agent can speak.

Return contract: ``(result, error)`` where exactly one is a string and the other is
None. ``result`` is used for success AND validation feedback (agent re-prompts the
named field); ``error`` only for infrastructure failures.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.modules.patient import service as patient_service
from app.modules.patient.schemas import PatientCreate

logger = get_logger("voice.service")

# Optional string fields that may arrive empty from speech when the caller declines.
_OPTIONAL_STR_FIELDS = (
    "email",
    "address_line_2",
    "insurance_provider",
    "insurance_member_id",
    "preferred_language",
    "emergency_contact_name",
    "emergency_contact_phone",
)


def _coerce_optionals(args: dict[str, Any]) -> dict[str, Any]:
    """Drop empty/whitespace optional fields so they become schema defaults/None."""
    cleaned = dict(args)
    for field in _OPTIONAL_STR_FIELDS:
        value = cleaned.get(field)
        if isinstance(value, str) and not value.strip():
            cleaned.pop(field, None)
    return cleaned


def _first_field_error(exc: ValidationError) -> str:
    """Produce a spoken-friendly message naming the first invalid field."""
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"])
    msg = first["msg"]
    pretty = field.replace("_", " ")
    return f"There's a problem with the {pretty}: {msg}. Could you provide it again?"


def handle_tool_call(db: Session, name: str, args: dict[str, Any]) -> tuple[str | None, str | None]:
    """Dispatch one tool call. Returns ``(result, error)`` flat strings."""
    if name == "save_patient":
        return _save_patient(db, args)
    if name == "lookup_patient":
        return _lookup_patient(db, args)
    logger.warning("Unknown tool call: %s", name)
    return None, "I'm not able to do that right now."


def _save_patient(db: Session, args: dict[str, Any]) -> tuple[str | None, str | None]:
    """Validate + persist a patient. Validation issues come back as ``result``."""
    cleaned = _coerce_optionals(args)
    try:
        data = PatientCreate(**cleaned)
    except ValidationError as exc:
        # result (not error): we want the agent to speak this and re-prompt.
        logger.info("save_patient validation failed: %s", exc.errors())
        return _first_field_error(exc), None
    except TypeError:
        return "Some required information is missing. Let's go through it again.", None

    try:
        patient = patient_service.create_patient(db, data)
    except Exception:
        logger.exception("save_patient DB write failed")
        return None, "I'm having trouble saving your information right now."

    # Observability: log the final collected payload + outcome (NFR-3).
    logger.info("Patient registered via voice: %s", patient.to_dict())
    return (
        f"You're all set, {patient.first_name}. Your registration is saved.",
        None,
    )


def _lookup_patient(db: Session, args: dict[str, Any]) -> tuple[str | None, str | None]:
    """Duplicate detection by phone number for returning callers."""
    phone = str(args.get("phone_number") or "")
    match = patient_service.find_by_phone(db, phone)
    if match is None:
        return "No existing record found for that phone number.", None
    return (
        f"Found an existing record for {match.first_name} {match.last_name} "
        f"(id {match.patient_id}). You can offer to update it.",
        None,
    )
