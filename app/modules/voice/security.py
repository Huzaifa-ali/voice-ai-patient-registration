"""Shared-secret verification for the Vapi webhook.

Vapi can be configured to send a shared secret on each tool call (header
``x-vapi-secret``) or to sign requests (``x-vapi-signature``). We verify it against
``settings.VAPI_WEBHOOK_SECRET``.

Policy (pragmatic for this deployment):
  - No secret configured  -> allow (local dev).
  - Secret configured AND a matching header present -> allow.
  - Secret configured AND a *wrong* secret present  -> REJECT (someone is spoofing).
  - Secret configured but NO secret header at all    -> allow, with a warning.

The last case is deliberate: Vapi has known issues forwarding tool ``server.secret``
headers, and the webhook URL is an unguessable random tunnel/host. Failing open on a
*missing* header keeps the voice flow working, while a *mismatched* secret is still
rejected. Set ``VAPI_WEBHOOK_STRICT=true`` to require the header instead.
"""

from __future__ import annotations

import hmac

from starlette.datastructures import Headers

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("voice.security")

# Header names Vapi may use to carry the server secret / signature.
_SECRET_HEADERS = ("x-vapi-secret", "x-vapi-signature", "secret")


def verify_secret(headers: Headers) -> bool:
    """Return True if the request is authorised (see module docstring for policy)."""
    expected = settings.VAPI_WEBHOOK_SECRET
    if not expected:
        return True

    provided_any = False
    for name in _SECRET_HEADERS:
        provided = headers.get(name)
        if provided:
            provided_any = True
            if hmac.compare_digest(provided, expected):
                return True

    if provided_any:
        # A secret header WAS sent but did not match -> genuine mismatch, reject.
        logger.warning("Vapi webhook secret header present but did not match")
        return False

    # No secret header at all. Reject only in strict mode; otherwise allow + warn.
    if settings.VAPI_WEBHOOK_STRICT:
        logger.warning("Vapi webhook rejected: no secret header (strict mode)")
        return False
    logger.warning(
        "Vapi webhook: no secret header present — allowing (set VAPI_WEBHOOK_STRICT=true to enforce)"
    )
    return True
