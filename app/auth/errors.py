"""Uniform error-response envelope for authentication failures.

Deliberately separate from app.models.api_log's VP-code table -- that
table belongs to the (not-yet-implemented) verification endpoint's
audit contract. Authentication uses its own small, explicit error-code
set as specified for this module.
"""
from __future__ import annotations

from typing import Any


def auth_error_response(error_code: str, message: str) -> dict[str, Any]:
    """Build the uniform {status, error_code, message} envelope.

    Never include the supplied API key, any MongoDB exception detail,
    or any client-identifying information beyond what the caller
    explicitly passes as `message` (which itself must be one of the
    four fixed, generic messages defined by the auth contract).
    """
    return {"status": "error", "error_code": error_code, "message": message}