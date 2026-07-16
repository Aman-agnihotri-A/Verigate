"""Client document contract (frozen field names/types).

See design contracts: clients collection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

REQUIRED_FIELDS = (
    "client_id",
    "client_name",
    "api_key",
    "whitelisted_ips",
    "tps_limit",
    "status",
)

VALID_STATUSES = ("active", "inactive")


class ClientValidationError(ValueError):
    pass


def build_client_document(
    *,
    client_id: str,
    client_name: str,
    api_key: str,
    whitelisted_ips: list[str],
    tps_limit: int,
    status: str = "active",
) -> dict[str, Any]:
    """Construct a client document matching the frozen schema.

    Raises ClientValidationError on structurally invalid input. Does
    NOT insert into MongoDB — this is a pure schema-construction
    helper.
    """
    if status not in VALID_STATUSES:
        raise ClientValidationError(f"invalid status: {status!r}")
    if not isinstance(whitelisted_ips, list) or not all(
        isinstance(ip, str) for ip in whitelisted_ips
    ):
        raise ClientValidationError("whitelisted_ips must be a list of strings")
    if not isinstance(tps_limit, int) or tps_limit <= 0:
        raise ClientValidationError("tps_limit must be a positive int")

    now = datetime.now(timezone.utc)
    return {
        "client_id": client_id,
        "client_name": client_name,
        "api_key": api_key,
        "whitelisted_ips": list(whitelisted_ips),
        "tps_limit": tps_limit,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
