"""REST API tests for ``/api/v1/patients``.

Covers create, read, list (+filters), update, soft-delete, and malformed JSON, plus
the ``{ data, error }`` envelope and server-side normalisation of phone/sex/state/DOB.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

BASE = "/api/v1/patients"


def _create(client: TestClient, payload: dict) -> dict:
    """Helper: POST a patient and return the ``data`` object (asserts 201)."""
    resp = client.post(BASE, json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["error"] is None
    return body["data"]


def test_create_returns_201_envelope_and_normalisation(
    client: TestClient, valid_patient: dict
) -> None:
    resp = client.post(BASE, json=valid_patient)
    assert resp.status_code == 201
    body = resp.json()

    # Envelope shape.
    assert set(body.keys()) == {"data", "error"}
    assert body["error"] is None
    data = body["data"]

    # A UUID was assigned and timestamps are present.
    assert data["patient_id"]
    assert data["created_at"] is not None
    assert data["deleted_at"] is None

    # Normalisation: phone -> 10 digits, sex -> canonical, state -> upper, DOB -> ISO.
    assert data["phone_number"] == "4155550142"
    assert data["sex"] == "Female"
    assert data["state"] == "CA"
    assert data["date_of_birth"] == "1990-03-14"


def test_create_normalises_sex_alias_and_lowercase_state(client: TestClient) -> None:
    payload = {
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "1985-11-02",
        "sex": "m",  # alias -> Male
        "phone_number": "1-212-555-0177",  # leading country code dropped
        "address_line_1": "350 Fifth Ave",
        "city": "New York",
        "state": "ny",  # -> NY
        "zip_code": "10118",
    }
    data = _create(client, payload)
    assert data["sex"] == "Male"
    assert data["state"] == "NY"
    assert data["phone_number"] == "2125550177"
    assert data["date_of_birth"] == "1985-11-02"


def test_get_by_id_returns_patient(client: TestClient, valid_patient: dict) -> None:
    created = _create(client, valid_patient)
    resp = client.get(f"{BASE}/{created['patient_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["patient_id"] == created["patient_id"]
    assert body["data"]["last_name"] == "Doe"


def test_get_missing_returns_404(client: TestClient) -> None:
    resp = client.get(f"{BASE}/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["data"] is None
    assert body["error"]["code"]


def test_list_returns_created_patients(client: TestClient, valid_patient: dict) -> None:
    _create(client, valid_patient)
    resp = client.get(BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1


def test_list_filter_by_last_name(client: TestClient, valid_patient: dict) -> None:
    _create(client, valid_patient)  # Doe
    other = dict(valid_patient)
    other.update(last_name="Smith", phone_number="212-555-0177")
    _create(client, other)

    resp = client.get(BASE, params={"last_name": "Doe"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["last_name"] == "Doe"


def test_list_filter_by_phone_number(client: TestClient, valid_patient: dict) -> None:
    _create(client, valid_patient)  # phone 4155550142
    other = dict(valid_patient)
    other.update(last_name="Smith", phone_number="212-555-0177")
    _create(client, other)

    # Filter accepts formatted phone input (normalised server-side before matching).
    resp = client.get(BASE, params={"phone_number": "(212) 555-0177"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["phone_number"] == "2125550177"


def test_list_filter_by_date_of_birth(client: TestClient, valid_patient: dict) -> None:
    _create(client, valid_patient)  # 1990-03-14
    other = dict(valid_patient)
    other.update(
        last_name="Smith", phone_number="212-555-0177", date_of_birth="1985-11-02"
    )
    _create(client, other)

    resp = client.get(BASE, params={"date_of_birth": "1990-03-14"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["date_of_birth"] == "1990-03-14"


def test_update_partial_returns_200(client: TestClient, valid_patient: dict) -> None:
    created = _create(client, valid_patient)
    resp = client.put(
        f"{BASE}/{created['patient_id']}",
        json={"city": "Oakland", "state": "ca"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["city"] == "Oakland"
    assert body["data"]["state"] == "CA"
    # Untouched fields are preserved.
    assert body["data"]["last_name"] == "Doe"


def test_update_missing_returns_404(client: TestClient) -> None:
    resp = client.put(f"{BASE}/nope", json={"city": "Oakland"})
    assert resp.status_code == 404
    assert resp.json()["data"] is None


def test_soft_delete_then_get_404_and_excluded_from_list(
    client: TestClient, valid_patient: dict
) -> None:
    created = _create(client, valid_patient)
    pid = created["patient_id"]

    resp = client.delete(f"{BASE}/{pid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["patient_id"] == pid
    assert body["data"]["deleted_at"] is not None

    # Subsequent GET is 404.
    assert client.get(f"{BASE}/{pid}").status_code == 404

    # Excluded from the list.
    listed = client.get(BASE).json()["data"]
    assert all(p["patient_id"] != pid for p in listed)
    assert len(listed) == 0


def test_bad_json_body_returns_400(client: TestClient) -> None:
    resp = client.post(
        BASE,
        content="{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["data"] is None
    assert body["error"]["code"] == "BAD_REQUEST"
