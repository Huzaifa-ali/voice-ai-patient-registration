"""Patient Pydantic schemas and validation rules.

These enforce ALL field-level validation server-side — the API never trusts the voice
agent to have validated anything (brief: "do not rely solely on the voice agent").
The same rules power both the REST API and the voice webhook, so a 3-digit phone
number or a future DOB is rejected no matter how the data arrives.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.modules.patient.constants import SEX_VALUES, US_STATES

# --- Reusable validation primitives ----------------------------------------

# Letters plus space/hyphen/apostrophe/period — covers "Mary-Jane", "O'Brien",
# "St. John". Must start with a letter.
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z \-'.]*$")
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")

# Normalise ``sex`` aliases that commonly arrive from speech.
_SEX_ALIASES = {"M": "Male", "F": "Female", "Decline": "Decline to Answer"}


def normalize_phone(value: str) -> str:
    """Strip to digits and validate a US 10-digit number.

    Accepts formatting like ``(555) 123-4567`` or ``+1 555-123-4567``. A leading
    country-code ``1`` on an 11-digit number is dropped. Raises ``ValueError`` on
    anything that is not a valid 10-digit US number.
    """
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("must be a valid US 10-digit phone number")
    if digits[0] in "01":
        raise ValueError("US area code cannot start with 0 or 1")
    return digits


def normalize_name(value: str, field: str) -> str:
    value = (value or "").strip()
    if not (1 <= len(value) <= 50):
        raise ValueError(f"{field} must be 1-50 characters")
    if not _NAME_RE.match(value):
        raise ValueError(f"{field} may only contain letters, hyphens, and apostrophes")
    return value


def validate_dob(value: str) -> str:
    """Accept MM/DD/YYYY or YYYY-MM-DD; store as ISO YYYY-MM-DD.

    Rejects unparseable dates, future dates, and absurdly old (< 1900) years.
    """
    value = (value or "").strip()
    parsed: date | None = None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError("date_of_birth must be a valid date (MM/DD/YYYY)")
    if parsed > date.today():
        raise ValueError("date_of_birth cannot be in the future")
    if parsed.year < 1900:
        raise ValueError("date_of_birth year is unrealistically old")
    return parsed.isoformat()


def validate_sex(value: str) -> str:
    v = (value or "").strip().title()
    v = _SEX_ALIASES.get(v, v)
    if v not in SEX_VALUES:
        raise ValueError(f"sex must be one of {', '.join(SEX_VALUES)}")
    return v


def validate_state(value: str) -> str:
    v = (value or "").strip().upper()
    if v not in US_STATES:
        raise ValueError("state must be a valid 2-letter US abbreviation")
    return v


def validate_zip(value: str) -> str:
    v = (value or "").strip()
    if not _ZIP_RE.match(v):
        raise ValueError("zip_code must be 5-digit or ZIP+4 format")
    return v


def validate_city(value: str) -> str:
    v = (value or "").strip()
    if not (1 <= len(v) <= 100):
        raise ValueError("city must be 1-100 characters")
    return v


# --- Create schema ----------------------------------------------------------

class PatientCreate(BaseModel):
    """Payload for creating a patient. All required fields enforced here."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str
    last_name: str
    date_of_birth: str
    sex: str
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str

    # Optional
    email: EmailStr | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name")
    @classmethod
    def _v_first(cls, v: str) -> str:
        return normalize_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def _v_last(cls, v: str) -> str:
        return normalize_name(v, "last_name")

    @field_validator("date_of_birth")
    @classmethod
    def _v_dob(cls, v: str) -> str:
        return validate_dob(v)

    @field_validator("sex")
    @classmethod
    def _v_sex(cls, v: str) -> str:
        return validate_sex(v)

    @field_validator("phone_number")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("emergency_contact_phone")
    @classmethod
    def _v_ec_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state")
    @classmethod
    def _v_state(cls, v: str) -> str:
        return validate_state(v)

    @field_validator("zip_code")
    @classmethod
    def _v_zip(cls, v: str) -> str:
        return validate_zip(v)

    @field_validator("city")
    @classmethod
    def _v_city(cls, v: str) -> str:
        return validate_city(v)

    @field_validator("address_line_1")
    @classmethod
    def _v_addr(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("address_line_1 is required")
        return v


# --- Update schema (partial) ------------------------------------------------

class PatientUpdate(BaseModel):
    """Partial update. Every field optional; provided fields are validated."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    sex: str | None = None
    phone_number: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    email: EmailStr | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @model_validator(mode="after")
    def _validate_provided(self) -> "PatientUpdate":
        if self.first_name is not None:
            self.first_name = normalize_name(self.first_name, "first_name")
        if self.last_name is not None:
            self.last_name = normalize_name(self.last_name, "last_name")
        if self.date_of_birth is not None:
            self.date_of_birth = validate_dob(self.date_of_birth)
        if self.phone_number is not None:
            self.phone_number = normalize_phone(self.phone_number)
        if self.emergency_contact_phone is not None:
            self.emergency_contact_phone = normalize_phone(self.emergency_contact_phone)
        if self.sex is not None:
            self.sex = validate_sex(self.sex)
        if self.state is not None:
            self.state = validate_state(self.state)
        if self.zip_code is not None:
            self.zip_code = validate_zip(self.zip_code)
        if self.city is not None:
            self.city = validate_city(self.city)
        return self
