"""Centralised logging setup.

Logs go to stdout (so hosting platforms capture them) at the configured level. The
voice webhook logs the final collected patient payload here, satisfying the
observability requirement (NFR-3).
"""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


def setup_logging() -> None:
    """Configure root logging once. Safe to call repeatedly."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers.clear()
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, ensuring logging is configured."""
    setup_logging()
    return logging.getLogger(name)
