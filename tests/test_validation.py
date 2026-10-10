"""Parametrized server-side validation tests for patient creation.

The API never trusts upstream validation, so these assert the schema rejects bad
data with HTTP 422 and that the offending field appears in ``error.fields``. One case
(11-digit phone with a leading country code) asserts the *accepting* + normalising
behaviour instead.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/patients"

VALID: dict[str, str] = {
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

_FUTURE_DOB = (date.today() + timedelta(days=1)).strftime("%m/%d/%Y")


def _payload(**overrides: str) -> dict:
    data = dict(VALID)
    data.update(overrides)
    return data


# Each case: (id, overrides, offending_field)
_INVALID_CASES = [
    ("future_dob", {"date_of_birth": _FUTURE_DOB}, "date_of_birth"),
    ("malformed_dob", {"date_of_birth": "19900314"}, "date_of_birth"),
    ("three_digit_phone", {"phone_number": "123"}, "phone_number"),
    ("invalid_state", {"state": "ZZ"}, "state"),
    ("invalid_zip", {"zip_code": "123"}, "zip_code"),
    ("invalid_sex", {"sex": "Unknown"}, "sex"),
    ("invalid_name_chars", {"first_name": "Jane123"}, "first_name"),
]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [pytest.param(ov, fld, id=case_id) for case_id, ov, fld in _INVALID_CASES],
)
def test_invalid_field_rejected_with_422(
    client: TestClient, overrides: dict, field: str
) -> None:
    resp = client.post(BASE, json=_payload(**overrides))
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"

    fields = body["error"]["fields"]
    assert isinstance(fields, list)
    offending = {f["field"] for f in fields}
    assert field in offending, f"expected {field} in {offending}"
    # Every reported field carries a human message.
    assert all(f.get("message") for f in fields)


def test_eleven_digit_phone_with_leading_one_accepted_and_normalised(
    client: TestClient,
) -> None:
    resp = client.post(BASE, json=_payload(phone_number="1 (415) 555-0142"))
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    # Leading country-code 1 dropped, formatting stripped -> 10 digits.
    assert data["phone_number"] == "4155550142"
