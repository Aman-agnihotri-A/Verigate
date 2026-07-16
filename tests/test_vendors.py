import pytest

from app.vendors import VendorFailure, VendorResult, VendorTimeout, verify_with_fallback

CONFIG = {
    "VENDOR_A_FAILURE_RATE": 0.0,
    "VENDOR_A_TIMEOUT_RATE": 0.0,
    "VENDOR_LATENCY_MIN_MS": 0,
    "VENDOR_LATENCY_MAX_MS": 0,
    "VENDOR_A_TIMEOUT_BUDGET_MS": 1,
}


def test_primary_success_does_not_use_fallback():
    result, used, attempts = verify_with_fallback(
        {},
        CONFIG,
        primary=lambda payload: VendorResult(True, 92, "PRIMARY"),
        fallback=lambda payload: pytest.fail("fallback called"),
    )
    assert result.source == "PRIMARY"
    assert used is False
    assert attempts == [{"vendor": "PRIMARY", "outcome": "SUCCESS"}]


def test_primary_failure_uses_fallback_and_records_attempts():
    def primary(_):
        raise VendorTimeout("timed out")

    result, used, attempts = verify_with_fallback(
        {},
        CONFIG,
        primary=primary,
        fallback=lambda payload: VendorResult(True, 88, "FALLBACK"),
    )
    assert result.source == "FALLBACK"
    assert used is True
    assert attempts == [
        {
            "vendor": "PRIMARY",
            "outcome": "FAILED",
            "error_type": "VendorTimeout",
        },
        {"vendor": "FALLBACK", "outcome": "SUCCESS"},
    ]


def test_both_failures_propagate_complete_attempt_trail():
    def primary(_):
        raise VendorTimeout("timed out")

    def fallback(_):
        raise VendorFailure("failed")

    with pytest.raises(VendorFailure) as exc_info:
        verify_with_fallback({}, CONFIG, primary=primary, fallback=fallback)

    assert exc_info.value.attempts == [
        {
            "vendor": "PRIMARY",
            "outcome": "FAILED",
            "error_type": "VendorTimeout",
        },
        {
            "vendor": "FALLBACK",
            "outcome": "FAILED",
            "error_type": "VendorFailure",
        },
    ]
