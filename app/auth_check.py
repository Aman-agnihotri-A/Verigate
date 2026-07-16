"""Temporary route for exercising the authentication layer.

This blueprint exists only to prove `require_api_key` works end to
end. It contains no verification, vendor, rate-limiting, or MIS
logic, and is isolated so it can be removed or replaced later without
touching app/auth/*.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from app.auth.context import get_auth_context
from app.auth.decorators import require_api_key

auth_check_bp = Blueprint("auth_check", __name__)


@auth_check_bp.route("/auth/check", methods=["GET"])
@require_api_key
def auth_check():
    context = get_auth_context()
    return jsonify({"status": "ok", "client_id": context["client_id"]}), 200