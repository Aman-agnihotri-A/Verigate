"""Tests for schema-construction contracts (clients, users, api_logs).

All sample values below are synthetic placeholders for structural
testing only -- never real secrets or real personal data.
"""
from __future__ import annotations

import pytest

from app.models.client import build_client_document, ClientValidationError
from app.models.user import build_user_document, UserValidationError
from app.models.api_log import build_api_log_document, ApiLogValidationError


def test_build_client_document_has_frozen_fields():
    doc = build_client_document(
        client_id="alphabank",
        client_name="Alpha Bank Ltd.",
        api_key="test-key-not-real",
        whitelisted_ips=["203.0.113.5"],
        tps_limit=5,
    )
    assert doc["client_id"] == "alphabank"
    assert doc["status"] == "active"
    assert doc["created_at"].tzinfo is not None
    assert doc["updated_at"].tzinfo is not None


def test_build_client_document_rejects_bad_status():
    with pytest.raises(ClientValidationError):
        build_client_document(
            client_id="x", client_name="X", api_key="k",
            whitelisted_ips=[], tps_limit=1, status="disabled",
        )


def test_build_client_document_rejects_non_positive_tps_limit():
    with pytest.raises(ClientValidationError):
        build_client_document(
            client_id="x", client_name="X", api_key="k",
            whitelisted_ips=[], tps_limit=0,
        )


def test_build_user_document_has_frozen_fields():
    doc = build_user_document(
        client_id="alphabank", user_id="ab_ops_01", display_name="Ops User 1"
    )
    assert doc["client_id"] == "alphabank"
    assert doc["created_at"].tzinfo is not None


def test_build_user_document_rejects_bad_status():
    with pytest.raises(UserValidationError):
        build_user_document(
            client_id="alphabank", user_id="ab_ops_01",
            display_name="Ops User 1", status="disabled",
        )


def test_build_api_log_document_success_case():
    doc = build_api_log_document(
        request_id="req_test1",
        client_id="alphabank",
        user_id="ab_ops_01",
        client_ref_id="ALB-2026-000123",
        ip="203.0.113.5",
        endpoint="/api/v1/verify",
        id_type="PAN",
        id_number_masked="******234F",
        id_number_hash="deadbeef",
        name_masked="********arma",
        name_hash="cafebabe",
        http_status=200,
        error_code="VP2000",
        vendor_used="PRIMARY",
        fallback_used=False,
        failover_reason=None,
        vendor_attempts=[{"vendor": "PRIMARY", "outcome": "SUCCESS"}],
        latency_ms=240,
    )
    assert "logging_failed" not in doc  # frozen: never in the Mongo schema
    assert doc["error_code"] == "VP2000"


def test_build_api_log_document_rejects_mismatched_http_status():
    with pytest.raises(ApiLogValidationError):
        build_api_log_document(
            request_id="req_test2", client_id=None, user_id=None,
            client_ref_id=None, ip="203.0.113.99", endpoint="/api/v1/verify",
            id_type=None, id_number_masked=None, id_number_hash=None,
            name_masked=None, name_hash=None,
            http_status=200,  # wrong for VP4003
            error_code="VP4003", vendor_used=None, fallback_used=False,
            failover_reason=None, vendor_attempts=[], latency_ms=4,
        )


def test_build_api_log_document_rejects_unknown_error_code():
    with pytest.raises(ApiLogValidationError):
        build_api_log_document(
            request_id="req_test3", client_id=None, user_id=None,
            client_ref_id=None, ip="203.0.113.99", endpoint="/api/v1/verify",
            id_type=None, id_number_masked=None, id_number_hash=None,
            name_masked=None, name_hash=None,
            http_status=200, error_code="VP9999", vendor_used=None,
            fallback_used=False, failover_reason=None, vendor_attempts=[],
            latency_ms=4,
        )
