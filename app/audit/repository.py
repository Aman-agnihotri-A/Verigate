"""Centralized audit-log repository (design contracts).

Exactly one attempted primary write to MongoDB's `api_logs` collection
per request. If that write fails, exactly one sanitized emergency
record is appended to a local JSONL file — never both, never a Mongo
document carrying a `logging_failed` field (that field only exists in
the emergency schema).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

# Fields that are safe to mirror into the emergency record. Anything
# not in this set is dropped — defense in depth, on top of the fact
# that the api_log document itself never carries raw PII or secrets.
_ALLOWED_EMERGENCY_FIELDS = (
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

# Patterns that must never reach the emergency file, applied to the
# stringified Mongo exception before it is written anywhere.
_CREDENTIAL_PATTERNS = [
    re.compile(r"mongodb(\+srv)?://\S+", re.IGNORECASE),
    re.compile(r"(?i)(password|pwd|api[_-]?key|secret)\s*[=:]\s*\S+"),
]


class AuditRepositoryError(RuntimeError):
    """Raised only if both the primary write and the emergency write fail."""


def sanitize_mongo_error(exc: Exception) -> str:
    """Redact anything resembling a connection string, credential, or
    secret from an exception's string representation before it is
    ever written to disk.
    """
    message = str(exc)
    for pattern in _CREDENTIAL_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


def _sanitize_log_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Keep only allow-listed fields, dropping anything unexpected
    (e.g. an accidental raw body/name/id_number key) before the
    document is ever written to the emergency file.
    """
    return {k: doc.get(k) for k in _ALLOWED_EMERGENCY_FIELDS}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _append_emergency_record(path: str, record: dict[str, Any]) -> None:
    """Append one JSON line to the emergency file.

    Safe-append mechanism: open with O_APPEND|O_CREAT and issue a
    single write() call for the whole line. On POSIX-compliant local
    filesystems, O_APPEND makes the seek-to-end-and-write sequence
    atomic at the kernel level for writes that fit in one system call,
    so concurrent writers within a single process won't interleave
    mid-line.

    Documented limitation: this guarantee does NOT extend to multiple
    OS processes/pods writing the same path on a shared *networked*
    filesystem (e.g. NFS), where O_APPEND atomicity is not guaranteed
    by the protocol, and it does not prevent interleaving when a
    single line exceeds the OS's atomic-write buffer size. In a
    multi-process deployment (e.g. several Gunicorn workers or pods),
    each process should be given a distinct emergency file path (e.g.
    suffixed by PID) rather than sharing one file, or the fallback
    should be redirected to a per-process-safe sink (e.g. syslog).
    This module implements the single-path, single-process-safe case
    only, matching phase-1 scope.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    line = (json.dumps(record, default=_json_default) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def write_audit_log(
    doc: dict[str, Any],
    db,
    emergency_log_path: str,
) -> dict[str, Any]:
    """Attempt exactly one primary insert; on failure, attempt exactly
    one sanitized emergency append.

    Returns a small status dict: {"written_to": "mongo" | "emergency"}.
    Raises AuditRepositoryError only if both attempts fail. Note: this
    function never raises just because the PRIMARY write failed and
    the emergency write succeeded — that path is the intended
    resilience behavior, and callers (phase 2 orchestration) must not
    turn a logging-fallback into a client-facing error.
    """
    try:
        db["api_logs"].insert_one(dict(doc))
        return {"written_to": "mongo"}
    except Exception as mongo_exc:  # noqa: BLE001 - audit path must not raise past this
        sanitized_error = sanitize_mongo_error(mongo_exc)
        emergency_record = _sanitize_log_doc(doc)
        emergency_record["logging_failed"] = True
        emergency_record["mongo_error"] = sanitized_error
        emergency_record["attempted_at"] = datetime.now(timezone.utc)
        try:
            _append_emergency_record(emergency_log_path, emergency_record)
            return {"written_to": "emergency"}
        except Exception as emergency_exc:  # noqa: BLE001
            raise AuditRepositoryError(
                "both primary and emergency audit writes failed: "
                f"mongo_error={sanitized_error!r}, "
                f"emergency_error={sanitize_mongo_error(emergency_exc)!r}"
            ) from None
