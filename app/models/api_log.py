"""api_logs document contract (frozen schema) — see design contracts.

This module defines the authoritative Mongo schema for the audit log
and the frozen error-code table. It intentionally does NOT include a
`logging_failed` field — that field exists only in the separate
emergency JSONL schema (see app/logging_/repository.py), never in the
Mongo document: a successful Mongo insert has no need for the flag,
and a failed insert means there is no Mongo document to hold it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

# Frozen error-code -> HTTP status map. Do not rename or renumber.
ERROR_CODE_HTTP_MAP: dict[str, int] = {
    "VP2000": 200,
    "VP2001": 200,
    "VP2002": 200,
    "VP4001": 401,
    "VP4003": 403,
    "VP4022": 422,
    "VP4029": 429,
    "VP5001": 502,
    "VP5000": 500,
}

# Frozen length constraints.
MAX_CLIENT_REF_ID_LEN = 64
MAX_ID_NUMBER_LEN = 20
MAX_NAME_LEN = 100
MAX_USER_ID_HEADER_LEN = 64

REQUIRED_LOG_FIELDS = (
    "request_id",
    "client_id",
    "user_id",
    "client_ref_id",
    "ip",
    "endpoint",
    "id_type",
    "id_number_masked",
    "id_number_hash",
    "name_masked",
    "name_hash",
    "http_status",
    "error_code",
    "vendor_used",
    "fallback_used",
    "failover_reason",
    "vendor_attempts",
    "latency_ms",
    "created_at",
)


class ApiLogValidationError(ValueError):
    pass


def build_api_log_document(
    *,
    request_id: str,
    client_id: Optional[str],
    user_id: Optional[str],
    client_ref_id: Optional[str],
    ip: str,
    endpoint: str,
    id_type: Optional[str],
    id_number_masked: Optional[str],
    id_number_hash: Optional[str],
    name_masked: Optional[str],
    name_hash: Optional[str],
    http_status: int,
    error_code: str,
    vendor_used: Optional[str],
    fallback_used: bool,
    failover_reason: Optional[str],
    vendor_attempts: list[dict[str, Any]],
    latency_ms: int,
    created_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Construct one api_logs document matching the frozen schema.

    Pure construction only — no side effects, no I/O. Raises
    ApiLogValidationError if error_code is not in the frozen table or
    if http_status disagrees with the frozen mapping.
    """
    if error_code not in ERROR_CODE_HTTP_MAP:
        raise ApiLogValidationError(f"unknown error_code: {error_code!r}")
    if ERROR_CODE_HTTP_MAP[error_code] != http_status:
        raise ApiLogValidationError(
            f"http_status {http_status} does not match {error_code} "
            f"(expected {ERROR_CODE_HTTP_MAP[error_code]})"
        )

    return {
        "request_id": request_id,
        "client_id": client_id,
        "user_id": user_id,
        "client_ref_id": client_ref_id,
        "ip": ip,
        "endpoint": endpoint,
        "id_type": id_type,
        "id_number_masked": id_number_masked,
        "id_number_hash": id_number_hash,
        "name_masked": name_masked,
        "name_hash": name_hash,
        "http_status": http_status,
        "error_code": error_code,
        "vendor_used": vendor_used,
        "fallback_used": fallback_used,
        "failover_reason": failover_reason,
        "vendor_attempts": list(vendor_attempts),
        "latency_ms": latency_ms,
        "created_at": created_at or datetime.now(timezone.utc),
    }
