"""Voice AI Patient Registration — FastAPI application entry point.

Lifespan initialises the database schema. CORS is permissive (single-tenant demo).
Global exception handlers render the ``{ data, error }`` envelope and keep internal
error detail server-side. ``/health`` is the deployment readiness probe. The dashboard
is mounted at the root; the versioned API lives under ``/api/v1``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.core.database import init_db
from app.core.exceptions import AppException
from app.core.logging_config import get_logger
from app.modules.dashboard.router import router as dashboard_router
from app.router.endpoints import api_router

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup."""
    init_db()
    logger.info("Database initialised; application ready.")
    yield


app = FastAPI(
    title="Voice AI Patient Registration API",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception handlers -----------------------------------------------------

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Render all AppException subclasses as the error envelope."""
    error: dict = {"code": exc.code, "message": exc.message}
    if exc.fields is not None:
        error["fields"] = exc.fields
    return JSONResponse(status_code=exc.status_code, content={"data": None, "error": error})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log full detail server-side, return a sanitized 500.

    Clients never receive internal exception text, stack traces, or vendor errors.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong on our end. Please try again.",
            },
        },
    )


# --- Routers ----------------------------------------------------------------
app.include_router(api_router)
app.include_router(dashboard_router)


# --- Health check -----------------------------------------------------------

@app.get("/health", tags=["health"])
def health_check() -> JSONResponse:
    """Readiness probe. 200 when the DB is reachable, 503 otherwise."""
    from sqlalchemy import text

    from app.core.database import engine

    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
        logger.exception("Health check: database unreachable")

    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_ok else "degraded",
            "version": __version__,
            "checks": {"database": "up" if db_ok else "down"},
        },
    )
