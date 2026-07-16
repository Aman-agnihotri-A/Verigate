"""API-key authentication decorator (Flask request guard).

Flow: extract header -> exact-match repository lookup -> evaluate
client status -> place safe context on flask.g -> call the view.

Catches only pymongo.errors.PyMongoError -- no broad `except
Exception`. A database failure is reported as a generic 503, never as
an invalid-credential response, so that authentication errors and
service outages remain distinguishable to the caller.
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from flask import current_app, jsonify, request
from pymongo.errors import PyMongoError

from app.auth.context import set_auth_context
from app.auth.errors import auth_error_response
from app.auth.repository import find_client_by_api_key

API_KEY_HEADER = "X-API-Key"
ACTIVE_STATUS = "active"


def require_api_key(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Guard a Flask view with X-API-Key authentication.

    On success, `app.auth.context.get_auth_context()` is populated for
    the duration of the request with exactly `client_id` and
    `tps_limit` -- never the raw key or the full client document.
    """

    @functools.wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        api_key = request.headers.get(API_KEY_HEADER, "")
        if not api_key:
            return (
                jsonify(
                    auth_error_response("MISSING_API_KEY", "API key is required")
                ),
                401,
            )

        clients_collection = current_app.extensions["mongo_db"]["clients"]
        try:
            client = find_client_by_api_key(clients_collection, api_key)
        except PyMongoError:
            return (
                jsonify(
                    auth_error_response(
                        "AUTH_SERVICE_UNAVAILABLE",
                        "Authentication service is temporarily unavailable",
                    )
                ),
                503,
            )

        if client is None:
            return (
                jsonify(auth_error_response("INVALID_API_KEY", "Invalid API key")),
                401,
            )

        if client.get("status") != ACTIVE_STATUS:
            return (
                jsonify(auth_error_response("CLIENT_INACTIVE", "Client is inactive")),
                403,
            )

        set_auth_context(client_id=client["client_id"], tps_limit=client["tps_limit"])
        return view_func(*args, **kwargs)

    return wrapped