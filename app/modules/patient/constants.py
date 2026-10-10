"""Patient module constants — the single source of truth for enumerations.

Kept in one place so the ORM CHECK constraint and the Pydantic validators cannot
drift apart.
"""

from __future__ import annotations

MODULE = "patient"

# Allowed values for the ``sex`` field (brief data model).
SEX_VALUES: tuple[str, ...] = ("Male", "Female", "Other", "Decline to Answer")

# 50 US states + DC + common territories, for 2-letter state validation.
US_STATES: frozenset[str] = frozenset(
    {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
        "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
        "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
        "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
        "WI", "WY", "DC", "PR", "GU", "VI", "AS", "MP",
    }
)
