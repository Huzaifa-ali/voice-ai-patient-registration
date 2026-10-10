"""Application exception hierarchy.

Services raise these; the global handler in ``app/main.py`` renders them into the
``{ data, error }`` envelope with the right HTTP status. Routers do not translate
domain errors (VLE error-handling rule).
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base for all application errors carrying an HTTP status + machine code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        fields: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        # ``fields`` is a per-field error list, present only for validation errors.
        self.fields = fields
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(code="NOT_FOUND", message=message, status_code=404)


class BadRequestError(AppException):
    def __init__(self, message: str = "Bad request") -> None:
        super().__init__(code="BAD_REQUEST", message=message, status_code=400)


class ValidationError(AppException):
    def __init__(
        self,
        message: str = "Validation failed",
        fields: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            code="VALIDATION_ERROR", message=message, status_code=422, fields=fields
        )


class ConflictError(AppException):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(code="CONFLICT", message=message, status_code=409)
