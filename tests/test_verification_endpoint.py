from __future__ import annotations

from dataclasses import dataclass

import pytest
from pymongo.errors import ConnectionFailure

from app import create_app
from app.rate_limit import limiter
from app.vendors import VendorFailure, VendorResult


class FakeCollection:
    def __init__(self, documents=None, error=None):
        self.documents = list(documents or [])
        self.error = error
        self.inserted = []

    def find_one(self, query):
        if self.error:
            raise self.error
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return dict(document)
        return None

    def insert_one(self, document):
        self.inserted.append(dict(document))
        return object()


class FakeDB(dict):
    def __getitem__(self, name):
        return super().__getitem__(name)


class TestConfig:
    TESTING = True
    MONGO_URI = "mongodb://localhost:27017"
    MONGO_DB_NAME = "verigate_test"
    SECRET_KEY = "test"
    ADMIN_API_KEY = "admin"
    DEFAULT_TPS_LIMIT = 5
    TRUSTED_PROXY_IPS = ["127.0.0.1"]
    TRUST_XFF_HEADER_DEV_ONLY = True
    EMERGENCY_LOG_PATH = "logs/test-emergency.jsonl"
    VENDOR_A_FAILURE_RATE = 0.0
    VENDOR_A_TIMEOUT_RATE = 0.0
    VENDOR_A_TIMEOUT_BUDGET_MS = 2000
    VENDOR_LATENCY_MIN_MS = 0
    VENDOR_LATENCY_MAX_MS = 0


@pytest.fixture
def gateway(monkeypatch):
    app = create_app(TestConfig)
    clients = FakeCollection(
        [
            {
                "client_id": "alphabank",
                "api_key": "alpha-key",
                "status": "active",
                "whitelisted_ips": ["103.24.10.5"],
                "tps_limit": 5,
            }
        ]
    )
    users = FakeCollection(
        [{"client_id": "alphabank", "user_id": "ab_ops_01", "status": "active"}]
    )
    logs = FakeCollection()
    database = FakeDB(clients=clients, users=users, api_logs=logs)
    app.extensions["mongo_db"] = database
    limiter.reset()
    yield app.test_client(), database
    limiter.reset()


def headers(**overrides):
    values = {
        "X-API-Key": "alpha-key",
        "X-User-Id": "ab_ops_01",
        "X-Forwarded-For": "103.24.10.5",
    }
    values.update(overrides)
    return values


def payload(**overrides):
    values = {
        "client_ref_id": "ALB-2026-000123",
        "id_type": "PAN",
        "id_number": "ABCDE1234F",
        "name": "Rahul Sharma",
    }
    values.update(overrides)
    return values


def assert_failed(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == code
    assert body["request_id"].startswith("req_")


def test_primary_success_is_returned_and_pii_safe_log_is_written(gateway, monkeypatch):
    client, database = gateway
    monkeypatch.setattr(
        "app.verification.verify_with_fallback",
        lambda request_payload, config: (VendorResult(True, 92, "PRIMARY"), False, [{"vendor": "PRIMARY", "outcome": "SUCCESS"}]),
    )

    response = client.post("/api/v1/verify", headers=headers(), json=payload())

    assert response.status_code == 200
    body = response.get_json()
    assert body["error_code"] == "VP2000"
    assert body["data"] == {
        "verified": True,
        "name_match_score": 92,
        "source": "PRIMARY",
    }
    log = database["api_logs"].inserted[-1]
    assert log["error_code"] == "VP2000"
    assert log["vendor_used"] == "PRIMARY"
    assert log["fallback_used"] is False
    assert log["id_number_masked"].endswith("234F")
    assert log["name_masked"].endswith("arma")
    serialized = repr(log)
    assert "ABCDE1234F" not in serialized
    assert "Rahul Sharma" not in serialized


def test_fallback_success_uses_vp2001(gateway, monkeypatch):
    client, database = gateway
    monkeypatch.setattr(
        "app.verification.verify_with_fallback",
        lambda request_payload, config: (VendorResult(True, 88, "FALLBACK"), True, [{"vendor": "PRIMARY", "outcome": "FAILED", "error_type": "VendorFailure"}, {"vendor": "FALLBACK", "outcome": "SUCCESS"}]),
    )
    response = client.post("/api/v1/verify", headers=headers(), json=payload())
    assert response.status_code == 200
    assert response.get_json()["error_code"] == "VP2001"
    log = database["api_logs"].inserted[-1]
    assert log["fallback_used"] is True
    assert log["failover_reason"] == "VendorFailure"
    assert log["vendor_attempts"][0]["vendor"] == "PRIMARY"


def test_not_verified_uses_vp2002(gateway, monkeypatch):
    client, database = gateway
    monkeypatch.setattr(
        "app.verification.verify_with_fallback",
        lambda request_payload, config: (VendorResult(False, 71, "PRIMARY"), False, [{"vendor": "PRIMARY", "outcome": "SUCCESS"}]),
    )
    response = client.post("/api/v1/verify", headers=headers(), json=payload())
    assert response.status_code == 200
    assert response.get_json()["error_code"] == "VP2002"
    assert database["api_logs"].inserted[-1]["error_code"] == "VP2002"


def test_missing_api_key_is_logged(gateway):
    client, database = gateway
    response = client.post(
        "/api/v1/verify",
        headers=headers(**{"X-API-Key": ""}),
        json=payload(),
    )
    assert_failed(response, 401, "VP4001")
    assert database["api_logs"].inserted[-1]["error_code"] == "VP4001"


def test_missing_user_is_rejected_and_logged(gateway):
    client, database = gateway
    response = client.post(
        "/api/v1/verify",
        headers=headers(**{"X-User-Id": ""}),
        json=payload(),
    )
    assert_failed(response, 422, "VP4022")
    assert database["api_logs"].inserted[-1]["error_code"] == "VP4022"


def test_non_whitelisted_ip_is_rejected_and_logged(gateway):
    client, database = gateway
    response = client.post(
        "/api/v1/verify",
        headers=headers(**{"X-Forwarded-For": "198.51.100.20"}),
        json=payload(),
    )
    assert_failed(response, 403, "VP4003")
    log = database["api_logs"].inserted[-1]
    assert log["ip"] == "198.51.100.20"
    assert log["error_code"] == "VP4003"


def test_invalid_payload_maps_to_vp4022(gateway):
    client, database = gateway
    response = client.post(
        "/api/v1/verify",
        headers=headers(),
        json=payload(id_number="not-a-pan"),
    )
    assert_failed(response, 422, "VP4022")
    assert database["api_logs"].inserted[-1]["error_code"] == "VP4022"


def test_tps_limit_rejection_is_logged(gateway, monkeypatch):
    client, database = gateway
    monkeypatch.setattr("app.verification.limiter.allow", lambda *args, **kwargs: False)
    response = client.post("/api/v1/verify", headers=headers(), json=payload())
    assert_failed(response, 429, "VP4029")
    assert database["api_logs"].inserted[-1]["error_code"] == "VP4029"


def test_both_vendor_failures_map_to_vp5001(gateway, monkeypatch):
    client, database = gateway

    def fail(*args, **kwargs):
        raise VendorFailure(
            "both unavailable",
            attempts=[
                {"vendor": "PRIMARY", "outcome": "FAILED", "error_type": "VendorTimeout"},
                {"vendor": "FALLBACK", "outcome": "FAILED", "error_type": "VendorFailure"},
            ],
        )

    monkeypatch.setattr("app.verification.verify_with_fallback", fail)
    response = client.post("/api/v1/verify", headers=headers(), json=payload())
    assert_failed(response, 502, "VP5001")
    log = database["api_logs"].inserted[-1]
    assert log["fallback_used"] is True
    assert log["failover_reason"] == "VendorTimeout"
    assert len(log["vendor_attempts"]) == 2


def test_auth_database_failure_is_returned_and_audit_fallback_attempted(gateway):
    client, database = gateway
    database["clients"] = FakeCollection(error=ConnectionFailure("database unavailable"))
    response = client.post("/api/v1/verify", headers=headers(), json=payload())
    assert_failed(response, 500, "VP5000")
    assert database["api_logs"].inserted[-1]["error_code"] == "VP5000"


def test_untrusted_remote_cannot_spoof_x_forwarded_for(gateway):
    client, database = gateway
    client.application.config["TRUST_XFF_HEADER_DEV_ONLY"] = False
    client.application.config["TRUSTED_PROXY_IPS"] = ["127.0.0.1"]
    response = client.post(
        "/api/v1/verify",
        headers=headers(),
        json=payload(),
        environ_base={"REMOTE_ADDR": "198.51.100.40"},
    )
    assert_failed(response, 403, "VP4003")
    assert database["api_logs"].inserted[-1]["ip"] == "198.51.100.40"


def test_fallback_not_verified_uses_vp2002(gateway, monkeypatch):
    client, database = gateway
    monkeypatch.setattr(
        "app.verification.verify_with_fallback",
        lambda request_payload, config: (VendorResult(False, 70, "FALLBACK"), True, [{"vendor": "PRIMARY", "outcome": "FAILED", "error_type": "VendorTimeout"}, {"vendor": "FALLBACK", "outcome": "SUCCESS"}]),
    )
    response = client.post("/api/v1/verify", headers=headers(), json=payload())
    assert response.status_code == 200
    assert response.get_json()["error_code"] == "VP2002"
    log = database["api_logs"].inserted[-1]
    assert log["vendor_used"] == "FALLBACK"
    assert log["fallback_used"] is True
    assert log["error_code"] == "VP2002"
