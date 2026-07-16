"""Health check endpoint.

Deliberately has no dependency on MongoDB or any other external
system — it only proves the Flask process itself is up.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "verigate"}), 200
