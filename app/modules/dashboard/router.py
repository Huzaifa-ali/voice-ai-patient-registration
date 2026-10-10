"""Read-only dashboard — Jinja + Tailwind UI over the real patient database.

Mounted at the application root (unversioned). Reads via ``patient.service`` only (no
direct DB access). Two pages: a searchable patient list (``/``) and a per-patient
detail view (``/patients/{id}``). Tailwind is loaded via CDN so there is no build step.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.patient import service

router = APIRouter(tags=["dashboard"])

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# --- Template filters -------------------------------------------------------

def _format_phone(value: str | None) -> str:
    """Render a 10-digit phone as (XXX) XXX-XXXX; pass anything else through."""
    digits = "".join(c for c in (value or "") if c.isdigit())
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return value or "—"


def _format_datetime(value: datetime | None) -> str:
    """Render a datetime as a short, readable UTC string."""
    if not value:
        return "—"
    return value.strftime("%b %d, %Y %H:%M")


templates.env.filters["phone"] = _format_phone
templates.env.filters["datetime"] = _format_datetime


# --- Routes -----------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, q: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    """Searchable list of active patients.

    ``q`` matches (case-insensitively) against first name, last name, or phone digits.
    Filtering is done in Python over the active set — fine for a demo-scale dataset and
    keeps the service's query surface simple.
    """
    patients = service.list_patients(db)

    query = (q or "").strip()
    if query:
        needle = query.lower()
        phone_needle = "".join(c for c in query if c.isdigit())
        filtered = []
        for p in patients:
            if (
                needle in p.first_name.lower()
                or needle in p.last_name.lower()
                or needle in f"{p.first_name} {p.last_name}".lower()
                or (phone_needle and phone_needle in p.phone_number)
            ):
                filtered.append(p)
        patients = filtered

    return templates.TemplateResponse(
        request,
        "list.html",
        {"patients": patients, "query": query},
    )


@router.get("/patients/{patient_id}", response_class=HTMLResponse)
def patient_detail(request: Request, patient_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Detail view for a single patient (raises 404 via the service if missing)."""
    patient = service.get_patient(db, patient_id)
    return templates.TemplateResponse(request, "detail.html", {"p": patient})
