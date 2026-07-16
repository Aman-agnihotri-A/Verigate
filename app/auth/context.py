"""Safe authenticated-client request-context helpers.

Only `client_id` and `tps_limit` are ever placed into Flask's
per-request context (`flask.g`) -- never the raw API key, the MongoDB
`_id`, or the complete client document.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from flask import g

_CONTEXT_ATTR = "auth_client"


class AuthContext(TypedDict):
    client_id: str
    tps_limit: int


def set_auth_context(client_id: str, tps_limit: int) -> None:
    """Store exactly the two allowed fields on flask.g for this request."""
    setattr(g, _CONTEXT_ATTR, {"client_id": client_id, "tps_limit": tps_limit})


def get_auth_context() -> Optional[AuthContext]:
    """Return the current request's safe auth context, or None if the
    request has not passed through `require_api_key`.
    """
    return getattr(g, _CONTEXT_ATTR, None)