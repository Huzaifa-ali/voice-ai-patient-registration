"""Consistent JSON response envelope: ``{ "data": ..., "error": ... }``.

Every REST response uses this shape (API standard from the brief). The error object is
``{ code, message, fields? }`` where ``fields`` is a per-field list present ONLY on
validation (422) responses and omitted otherwise.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any, status_code: int = 200) -> JSONResponse:
    """Success envelope: payload under ``data``, ``error`` null."""
    return JSONResponse(status_code=status_code, content={"data": data, "error": None})


def err(
    code: str,
    message: str,
    status_code: int,
    fields: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Error envelope: ``data`` null, structured ``error`` object.

    ``fields`` (a list of ``{field, message}``) is included only when provided —
    the key is omitted entirely otherwise, so non-validation errors stay clean.
    """
    error: dict[str, Any] = {"code": code, "message": message}
    if fields is not None:
        error["fields"] = fields
    return JSONResponse(
        status_code=status_code, content={"data": None, "error": error}
    )
