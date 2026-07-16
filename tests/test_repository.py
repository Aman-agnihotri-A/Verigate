"""Tests for the centralized audit repository (app.audit.repository).

Covers: successful primary write, emergency fallback on primary
failure, and sanitization of the emergency record (no credentials, no
raw body/PII beyond the already-masked fields).

All values below (including the fake connection string and fake
password) are synthetic placeholders used only to prove the
sanitizer redacts them -- never real secrets.
"""
from __future__ import annotations

import json

from app.audit.repository import (
    sanitize_mongo_error,
    write_audit_log,
)


class _FakeCollection:
    def __init__(self, should_fail):
        self.should_fail = should_fail
        self.inserted = []

    def insert_one(self, doc):
        if self.should_fail:
            raise ConnectionError(
                "mongodb://admin:not-a-real-password@10.0.0.5:27017 unreachable"
            )
        self.inserted.append(doc)


class _FakeDb:
    def __init__(self, should_fail):
        self._collections = {"api_logs": _FakeCollection(should_fail)}

    def __getitem__(self, name):
        return self._collections[name]


_SAMPLE_DOC = {
    "request_id": "req_test1",
    "client_id": "alphabank",
    "user_id": "ab_ops_01",
    "client_ref_id": "ALB-2026-000123",
    "ip": "203.0.113.5",
    "endpoint": "/api/v1/verify",
    "id_type": "PAN",
    "id_number_masked": "******234F",
    "id_number_hash": "deadbeef",
    "name_masked": "********arma",
    "name_hash": "cafebabe",
    "http_status": 200,
    "error_code": "VP2000",
    "vendor_used": "PRIMARY",
    "fallback_used": False,
    "latency_ms": 240,
}


def test_successful_write_goes_to_mongo_only(tmp_path):
    db = _FakeDb(should_fail=False)
    emergency_path = tmp_path / "emergency.jsonl"
    result = write_audit_log(_SAMPLE_DOC, db, str(emergency_path))
    assert result == {"written_to": "mongo"}
    assert not emergency_path.exists()
    assert db["api_logs"].inserted == [_SAMPLE_DOC]


def test_mongo_failure_falls_back_to_emergency_file(tmp_path):
    db = _FakeDb(should_fail=True)
    emergency_path = tmp_path / "emergency.jsonl"
    result = write_audit_log(_SAMPLE_DOC, db, str(emergency_path))
    assert result == {"written_to": "emergency"}
    lines = emergency_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["logging_failed"] is True
    assert record["request_id"] == "req_test1"


def test_emergency_record_never_contains_credentials(tmp_path):
    db = _FakeDb(should_fail=True)
    emergency_path = tmp_path / "emergency.jsonl"
    write_audit_log(_SAMPLE_DOC, db, str(emergency_path))
    content = emergency_path.read_text(encoding="utf-8")
    assert "not-a-real-password" not in content
    assert "mongodb://" not in content


def test_emergency_record_drops_unexpected_fields(tmp_path):
    db = _FakeDb(should_fail=True)
    emergency_path = tmp_path / "emergency.jsonl"
    doc_with_extra = dict(_SAMPLE_DOC)
    doc_with_extra["raw_body"] = "this must never be written"
    write_audit_log(doc_with_extra, db, str(emergency_path))
    content = emergency_path.read_text(encoding="utf-8")
    assert "must never be written" not in content


def test_emergency_record_never_contains_raw_name_or_id_number(tmp_path):
    # Defense-in-depth: even if an orchestration bug upstream ever put
    # raw fields on the doc, the audit repository's allow-list must
    # strip them before they reach disk.
    db = _FakeDb(should_fail=True)
    emergency_path = tmp_path / "emergency.jsonl"
    doc_with_raw_pii = dict(_SAMPLE_DOC)
    doc_with_raw_pii["id_number"] = "ABCDE1234F"
    doc_with_raw_pii["name"] = "Rahul Sharma"
    write_audit_log(doc_with_raw_pii, db, str(emergency_path))
    content = emergency_path.read_text(encoding="utf-8")
    assert "ABCDE1234F" not in content
    assert "Rahul Sharma" not in content


def test_sanitize_mongo_error_redacts_connection_strings():
    exc = ConnectionError("mongodb://admin:secretpass@10.0.0.5:27017 unreachable")
    sanitized = sanitize_mongo_error(exc)
    assert "secretpass" not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_mongo_error_redacts_password_style_fields():
    exc = RuntimeError("auth failed: password=hunter2 api_key=abc123")
    sanitized = sanitize_mongo_error(exc)
    assert "hunter2" not in sanitized
    assert "abc123" not in sanitized
