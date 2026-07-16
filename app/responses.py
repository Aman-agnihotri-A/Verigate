"""Uniform API response envelope helpers."""
from __future__ import annotations

from typing import Any


def success_response(
    request_id: str,
    error_code: str,
    data: dict[str, Any],
    latency_ms: int,
) -> dict[str, Any]:
    """Build the assignment's successful response envelope."""
    return {
        "request_id": request_id,
        "status": "SUCCESS",
        "error_code": error_code,
        "data": data,
        "latency_ms": latency_ms,
    }


def error_response(
    request_id: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    """Build the assignment's failed response envelope."""
    return {
        "request_id": request_id,
        "status": "FAILED",
        "error_code": error_code,
        "message": message,
    }
