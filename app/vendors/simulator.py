"""Simulated primary/fallback vendors and failover orchestration.

No external service is called.  The simulator models latency, timeout,
service failure, and a synthetic verification result so the gateway's
resilience behaviour can be exercised deterministically in tests.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable


class VendorFailure(RuntimeError):
    """A vendor could not produce a usable verification response.

    ``attempts`` is attached when the complete primary/fallback chain fails,
    allowing the API layer to preserve the failover trail in the audit log.
    """

    def __init__(self, message: str, *, attempts: list[dict] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


class VendorTimeout(VendorFailure):
    """A vendor exceeded its simulated timeout condition."""


@dataclass(frozen=True, slots=True)
class VendorResult:
    """Normalized result returned by either simulated vendor."""

    verified: bool
    name_match_score: int
    source: str


VendorCallable = Callable[[object], VendorResult]


def _simulate(
    source: str,
    failure_rate: float,
    timeout_rate: float,
    min_ms: int,
    max_ms: int,
    timeout_budget_ms: int,
) -> VendorResult:
    """Return a synthetic result or raise a simulated vendor exception."""
    latency = random.randint(min_ms, max_ms)
    outcome = random.random()

    if outcome < timeout_rate or latency > timeout_budget_ms:
        raise VendorTimeout(f"{source} timed out")

    # Sleep only after the timeout decision to imitate network/vendor latency.
    time.sleep(latency / 1000)

    if outcome < timeout_rate + failure_rate:
        raise VendorFailure(f"{source} failed")

    # The assignment requires synthetic vendors, not a real identity datastore.
    score = random.randint(70, 100)
    return VendorResult(
        verified=score >= 80,
        name_match_score=score,
        source=source,
    )


def _attempt(vendor: str, outcome: str, error_type: str | None = None) -> dict:
    """Build the small, PII-free vendor-attempt object stored in MongoDB."""
    record = {"vendor": vendor, "outcome": outcome}
    if error_type:
        record["error_type"] = error_type
    return record


def verify_with_fallback(
    payload,
    config: dict,
    primary: VendorCallable | None = None,
    fallback: VendorCallable | None = None,
) -> tuple[VendorResult, bool, list[dict]]:
    """Call primary first and fallback only after failure or timeout.

    Returns ``(result, fallback_used, vendor_attempts)``.  The attempt trail is
    deliberately limited to vendor name, outcome, and exception class; it never
    contains raw PII, credentials, or exception text.
    """
    primary = primary or (
        lambda request_payload: _simulate(
            "PRIMARY",
            config["VENDOR_A_FAILURE_RATE"],
            config["VENDOR_A_TIMEOUT_RATE"],
            config["VENDOR_LATENCY_MIN_MS"],
            config["VENDOR_LATENCY_MAX_MS"],
            config["VENDOR_A_TIMEOUT_BUDGET_MS"],
        )
    )
    fallback = fallback or (
        lambda request_payload: _simulate(
            "FALLBACK",
            0.05,
            0.0,
            config["VENDOR_LATENCY_MIN_MS"],
            config["VENDOR_LATENCY_MAX_MS"],
            config["VENDOR_A_TIMEOUT_BUDGET_MS"],
        )
    )

    attempts: list[dict] = []
    try:
        result = primary(payload)
        attempts.append(_attempt("PRIMARY", "SUCCESS"))
        return result, False, attempts
    except VendorFailure as primary_error:
        attempts.append(
            _attempt("PRIMARY", "FAILED", type(primary_error).__name__)
        )

    try:
        result = fallback(payload)
        attempts.append(_attempt("FALLBACK", "SUCCESS"))
        return result, True, attempts
    except VendorFailure as fallback_error:
        attempts.append(
            _attempt("FALLBACK", "FAILED", type(fallback_error).__name__)
        )
        raise VendorFailure(
            "primary and fallback vendors failed",
            attempts=attempts,
        ) from fallback_error
