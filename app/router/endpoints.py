"""Centralised API router registry.

Single mount point for all versioned routes. Module routers declare only their domain
prefix (e.g. ``/patients``); the version prefix ``/api/v1`` is applied once here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.patient.router import router as patient_router
from app.modules.voice.router import router as voice_router

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)

# --- Module routers ---
api_router.include_router(patient_router)
api_router.include_router(voice_router)
