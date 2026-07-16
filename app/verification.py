"""POST /api/v1/verify gateway orchestration."""
from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from pymongo.errors import PyMongoError

from app.audit.repository import write_audit_log
from app.auth.repository import find_client_by_api_key
from app.models.api_log import build_api_log_document
from app.rate_limit import limiter
from app.responses import error_response, success_response
from app.schemas import RequestValidationError, validate_verification_request
from app.security import ClientIPError, extract_client_ip, validate_client_ip
from app.security.masking import hash_value, mask_value
from app.vendors import VendorFailure, verify_with_fallback

verification_bp = Blueprint("verification", __name__)


def _request_id() -> str:
    return "req_" + uuid4().hex[:12]


def _elapsed_ms(start: float) -> int:
    return max(0, int((perf_counter() - start) * 1000))


def _trusted_forwarded_for() -> str | None:
    """Return XFF only when the immediate peer is configured as trusted."""
    value = request.headers.get("X-Forwarded-For")
    if not value:
        return None
    if current_app.config.get("TRUST_XFF_HEADER_DEV_ONLY"):
        return value
    trusted = set(current_app.config.get("TRUSTED_PROXY_IPS", ()))
    return value if request.remote_addr in trusted else None


def _write_log(
    db,
    *,
    request_id: str,
    client_id: str | None,
    user_id: str | None,
    ip: str,
    payload,
    http_status: int,
    error_code: str,
    vendor_used: str | None,
    fallback_used: bool,
    failover_reason: str | None,
    vendor_attempts: list[dict],
    latency_ms: int,
) -> None:
    """Write a PII-safe audit record, using the repository's emergency fallback."""
    try:
        document = build_api_log_document(
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            client_ref_id=getattr(payload, "client_ref_id", None),
            ip=ip or "unknown",
            endpoint="/api/v1/verify",
            id_type=getattr(getattr(payload, "id_type", None), "value", None),
            id_number_masked=mask_value(payload.id_number) if payload else None,
            id_number_hash=hash_value(payload.id_number) if payload else None,
            name_masked=mask_value(payload.name) if payload else None,
            name_hash=hash_value(payload.name) if payload else None,
            http_status=http_status,
            error_code=error_code,
            vendor_used=vendor_used,
            fallback_used=fallback_used,
            failover_reason=failover_reason,
            vendor_attempts=vendor_attempts,
            latency_ms=latency_ms,
        )
        write_audit_log(document, db, current_app.config["EMERGENCY_LOG_PATH"])
    except Exception:  # audit failure must never replace the API result
        current_app.logger.exception("audit logging failed")


def _failure(
    db,
    *,
    start: float,
    request_id: str,
    client_id: str | None,
    user_id: str | None,
    ip: str,
    payload,
    http_status: int,
    error_code: str,
    message: str,
    fallback_used: bool = False,
):
    latency = _elapsed_ms(start)
    _write_log(
        db,
        request_id=request_id,
        client_id=client_id,
        user_id=user_id,
        ip=ip,
        payload=payload,
        http_status=http_status,
        error_code=error_code,
        vendor_used=None,
        fallback_used=fallback_used,
        failover_reason=None,
        vendor_attempts=[],
        latency_ms=latency,
    )
    return jsonify(error_response(request_id, error_code, message)), http_status


@verification_bp.post("/api/v1/verify")
def verify():
    """Authenticate, control, verify, and audit one identity request."""
    start = perf_counter()
    request_id = _request_id()
    db = current_app.extensions["mongo_db"]
    api_key = request.headers.get("X-API-Key", "")
    user_id = request.headers.get("X-User-Id", "").strip()
    forwarded_for = _trusted_forwarded_for()

    try:
        raw_ip = extract_client_ip(forwarded_for, request.remote_addr)
    except ClientIPError:
        raw_ip = "unknown"

    if not api_key:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=None,
            user_id=user_id or None,
            ip=raw_ip,
            payload=None,
            http_status=401,
            error_code="VP4001",
            message="Missing or invalid API key",
        )

    try:
        client = find_client_by_api_key(db["clients"], api_key)
    except PyMongoError:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=None,
            user_id=user_id or None,
            ip=raw_ip,
            payload=None,
            http_status=500,
            error_code="VP5000",
            message="Internal service error",
        )

    if not client or client.get("status") != "active":
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client.get("client_id") if client else None,
            user_id=user_id or None,
            ip=raw_ip,
            payload=None,
            http_status=401,
            error_code="VP4001",
            message="Missing or invalid API key",
        )

    client_id = client["client_id"]
    try:
        active_user = (
            user_id
            and len(user_id) <= 64
            and db["users"].find_one(
                {"client_id": client_id, "user_id": user_id, "status": "active"}
            )
        )
    except PyMongoError:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id or None,
            ip=raw_ip,
            payload=None,
            http_status=500,
            error_code="VP5000",
            message="Internal service error",
        )

    if not active_user:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id or None,
            ip=raw_ip,
            payload=None,
            http_status=422,
            error_code="VP4022",
            message="Valid X-User-Id header is required",
        )

    try:
        client_ip = validate_client_ip(
            forwarded_for,
            request.remote_addr,
            client.get("whitelisted_ips", []),
        )
    except ClientIPError:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            ip=raw_ip,
            payload=None,
            http_status=403,
            error_code="VP4003",
            message=f"Source IP {raw_ip} is not whitelisted for client {client_id}",
        )

    if not limiter.allow(
        client_id,
        int(client.get("tps_limit", current_app.config["DEFAULT_TPS_LIMIT"])),
    ):
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            payload=None,
            http_status=429,
            error_code="VP4029",
            message="Client TPS limit exceeded",
        )

    try:
        payload = validate_verification_request(request.get_json(silent=True))
    except RequestValidationError as exc:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            payload=None,
            http_status=422,
            error_code="VP4022",
            message=exc.message,
        )

    try:
        result, fallback_used, vendor_attempts = verify_with_fallback(
            payload, current_app.config
        )
        error_code = (
            "VP2002"
            if not result.verified
            else ("VP2001" if fallback_used else "VP2000")
        )
        latency = _elapsed_ms(start)
        _write_log(
            db,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            payload=payload,
            http_status=200,
            error_code=error_code,
            vendor_used=result.source,
            fallback_used=fallback_used,
            failover_reason=(
                vendor_attempts[0].get("error_type") if fallback_used else None
            ),
            vendor_attempts=vendor_attempts,
            latency_ms=latency,
        )
        return (
            jsonify(
                success_response(
                    request_id,
                    error_code,
                    {
                        "verified": result.verified,
                        "name_match_score": result.name_match_score,
                        "source": result.source,
                    },
                    latency,
                )
            ),
            200,
        )
    except VendorFailure as exc:
        latency = _elapsed_ms(start)
        attempts = getattr(exc, "attempts", [])
        _write_log(
            db,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            payload=payload,
            http_status=502,
            error_code="VP5001",
            vendor_used=None,
            fallback_used=True,
            failover_reason=(
                attempts[0].get("error_type") if attempts else "VendorFailure"
            ),
            vendor_attempts=attempts,
            latency_ms=latency,
        )
        return jsonify(
            error_response(
                request_id,
                "VP5001",
                "Primary and fallback vendors failed",
            )
        ), 502

    except Exception:
        return _failure(
            db,
            start=start,
            request_id=request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            payload=payload,
            http_status=500,
            error_code="VP5000",
            message="Unhandled internal error",
        )
