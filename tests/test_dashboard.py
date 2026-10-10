"""Dashboard UI tests — the Jinja + Tailwind pages served at the app root.

These assert the list renders, search filters by name and phone, the detail page
shows a patient, and an unknown id returns 404.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

PATIENTS = "/api/v1/patients"

_JANE = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "03/14/1990",
    "sex": "Female",
    "phone_number": "4155550142",
    "address_line_1": "1 Market St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94105",
}
_CARLOS = {
    "first_name": "Carlos",
    "last_name": "Ramirez",
    "date_of_birth": "07/22/1985",
    "sex": "Male",
    "phone_number": "2125550177",
    "address_line_1": "5 Ave",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
}


def _seed(client: TestClient) -> None:
    client.post(PATIENTS, json=_JANE)
    client.post(PATIENTS, json=_CARLOS)


def test_list_page_renders_patients(client: TestClient) -> None:
    _seed(client)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Jane" in html and "Carlos" in html
    # Phone is rendered in the human format via the template filter.
    assert "(415) 555-0142" in html


def test_list_empty_state(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No patients registered yet" in resp.text


def test_search_by_name_filters(client: TestClient) -> None:
    _seed(client)
    resp = client.get("/", params={"q": "carlos"})
    assert resp.status_code == 200
    assert "Carlos" in resp.text
    assert "Jane" not in resp.text


def test_search_by_phone_filters(client: TestClient) -> None:
    _seed(client)
    resp = client.get("/", params={"q": "4155"})
    assert resp.status_code == 200
    assert "Jane" in resp.text
    assert "Carlos" not in resp.text


def test_detail_page_renders(client: TestClient) -> None:
    _seed(client)
    pid = client.get(PATIENTS).json()["data"][0]["patient_id"]
    resp = client.get(f"/patients/{pid}")
    assert resp.status_code == 200
    assert "Demographics" in resp.text
    assert "Address" in resp.text


def test_detail_unknown_returns_404(client: TestClient) -> None:
    resp = client.get("/patients/does-not-exist")
    assert resp.status_code == 404
