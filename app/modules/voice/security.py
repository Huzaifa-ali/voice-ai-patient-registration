"""Shared-secret verification for the Vapi webhook.

Vapi sends a configured secret header on every tool call. We compare it (in constant
time) to ``settings.VAPI_WEBHOOK_SECRET``. If no secret is configured (local dev), the
check is skipped. Header name is matched case-insensitively and we accept the common
Vapi variants.
"""

from __future__ import annotations

import hmac

from starlette.datastructures import Headers

from app.core.config import settings

# Header names Vapi may use to carry the server secret.
_SECRET_HEADERS = ("x-vapi-secret", "x-vapi-signature", "secret")


def verify_secret(headers: Headers) -> bool:
    """Return True if the request is authorised.

    - If no secret is configured, always True (local dev).
    - Otherwise, at least one known secret header must match exactly.
    """
    expected = settings.VAPI_WEBHOOK_SECRET
    if not expected:
        return True
    for name in _SECRET_HEADERS:
        provided = headers.get(name)
        if provided and hmac.compare_digest(provided, expected):
            return True
    return False
