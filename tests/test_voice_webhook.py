"""Vapi voice-webhook contract tests for ``POST /api/v1/voice/vapi``.

The webhook ALWAYS returns HTTP 200 with ``{"results": [{"toolCallId", "result"}]}``.
Validation feedback surfaces as ``result`` (so the agent re-prompts), never as
``error`` — ``error`` is reserved for infrastructure failures. These tests pin that
contract plus save/lookup behaviour.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

VOICE = "/api/v1/voice/vapi"
PATIENTS = "/api/v1/patients"

_FUTURE_DOB = (date.today() + timedelta(days=1)).strftime("%m/%d/%Y")

_VALID_ARGS = {
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


def _tool_call_payload(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    """Build a Vapi webhook body wrapping a single tool call."""
    return {
        "message": {
            "toolCalls": [
                {"id": call_id, "function": {"name": name, "arguments": arguments}}
            ]
        }
    }


def test_save_patient_valid_returns_200_with_result_and_echoes_tool_call_id(
    client: TestClient,
) -> None:
    resp = client.post(VOICE, json=_tool_call_payload("save_patient", _VALID_ARGS))
    assert resp.status_code == 200
    body = resp.json()
    results = body["results"]
    assert len(results) == 1

    first = results[0]
    assert first["toolCallId"] == "call_1"
    assert first.get("result")  # non-empty success string
    assert "error" not in first  # exclude_none drops the unset error field

    # Persisted and retrievable via the REST API.
    listed = client.get(PATIENTS).json()["data"]
    assert len(listed) == 1
    assert listed[0]["phone_number"] == "4155550142"


def test_save_patient_invalid_surfaces_as_result_not_error(
    client: TestClient,
) -> None:
    args = dict(_VALID_ARGS)
    args["date_of_birth"] = _FUTURE_DOB
    resp = client.post(VOICE, json=_tool_call_payload("save_patient", args))

    # Still HTTP 200 — Vapi ignores other statuses.
    assert resp.status_code == 200
    first = resp.json()["results"][0]
    assert first["toolCallId"] == "call_1"
    assert first.get("result")  # validation feedback lives in result
    assert "error" not in first  # NOT an error

    # Nothing was persisted.
    assert client.get(PATIENTS).json()["data"] == []


def test_save_patient_empty_optional_email_does_not_fail(client: TestClient) -> None:
    args = dict(_VALID_ARGS)
    args["email"] = ""  # declined over the phone -> should be coerced away, not fail
    resp = client.post(VOICE, json=_tool_call_payload("save_patient", args))
    assert resp.status_code == 200
    first = resp.json()["results"][0]
    assert first.get("result")
    assert "error" not in first

    data = client.get(PATIENTS).json()["data"]
    assert len(data) == 1
    assert data[0]["email"] is None


def test_lookup_existing_phone_mentions_patient(client: TestClient) -> None:
    # Seed via the save tool first.
    client.post(VOICE, json=_tool_call_payload("save_patient", _VALID_ARGS))

    resp = client.post(
        VOICE,
        json=_tool_call_payload(
            "lookup_patient", {"phone_number": "(415) 555-0142"}, call_id="call_2"
        ),
    )
    assert resp.status_code == 200
    first = resp.json()["results"][0]
    assert first["toolCallId"] == "call_2"
    result = first.get("result") or ""
    # Mentions the matched patient.
    assert "Jane" in result
    assert "error" not in first


def test_lookup_unknown_phone_reports_no_existing_record(client: TestClient) -> None:
    resp = client.post(
        VOICE,
        json=_tool_call_payload("lookup_patient", {"phone_number": "415-555-9999"}),
    )
    assert resp.status_code == 200
    first = resp.json()["results"][0]
    result = (first.get("result") or "").lower()
    assert "no existing record" in result
    assert "error" not in first
