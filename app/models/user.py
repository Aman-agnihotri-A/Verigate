"""User document contract (frozen field names/types)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VALID_STATUSES = ("active", "inactive")


class UserValidationError(ValueError):
    pass


def build_user_document(
    *,
    client_id: str,
    user_id: str,
    display_name: str,
    status: str = "active",
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise UserValidationError(f"invalid status: {status!r}")
    return {
        "client_id": client_id,
        "user_id": user_id,
        "display_name": display_name,
        "status": status,
        "created_at": datetime.now(timezone.utc),
    }
