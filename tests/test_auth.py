"""Tests for API-key authentication and the temporary auth-check route."""
from __future__ import annotations

from pymongo.errors import AutoReconnect

from app import create_app
from app.auth.repository import find_client_by_api_key
from app.config import Config


class _AuthTestConfig(Config):
    TESTING = True
    MONGO_URI = "mongodb://mongo-does-not-exist.invalid:27017"
    MONGO_DB_NAME = "verigate_auth_test"


def _client():
    app = create_app(_AuthTestConfig)
    return app.test_client()


def test_auth_check_rejects_missing_api_key():
    response = _client().get("/auth/check")

    assert response.status_code == 401
    assert response.get_json() == {
        "status": "error",
        "error_code": "MISSING_API_KEY",
        "message": "API key is required",
    }


def test_auth_check_rejects_invalid_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.auth.decorators.find_client_by_api_key",
        lambda collection, api_key: None,
    )

    response = _client().get(
        "/auth/check",
        headers={"X-API-Key": "unknown-test-key"},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "status": "error",
        "error_code": "INVALID_API_KEY",
        "message": "Invalid API key",
    }


def test_auth_check_rejects_inactive_client(monkeypatch):
    monkeypatch.setattr(
        "app.auth.decorators.find_client_by_api_key",
        lambda collection, api_key: {
            "client_id": "client-inactive",
            "tps_limit": 5,
            "status": "inactive",
        },
    )

    response = _client().get(
        "/auth/check",
        headers={"X-API-Key": "inactive-test-key"},
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "status": "error",
        "error_code": "CLIENT_INACTIVE",
        "message": "Client is inactive",
    }


def test_auth_check_returns_503_when_mongo_lookup_fails(monkeypatch):
    def raise_mongo_error(collection, api_key):
        raise AutoReconnect("simulated test outage")

    monkeypatch.setattr(
        "app.auth.decorators.find_client_by_api_key",
        raise_mongo_error,
    )

    response = _client().get(
        "/auth/check",
        headers={"X-API-Key": "valid-looking-test-key"},
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "error",
        "error_code": "AUTH_SERVICE_UNAVAILABLE",
        "message": "Authentication service is temporarily unavailable",
    }
    assert "simulated test outage" not in response.get_data(as_text=True)


def test_auth_check_accepts_active_client(monkeypatch):
    monkeypatch.setattr(
        "app.auth.decorators.find_client_by_api_key",
        lambda collection, api_key: {
            "client_id": "client-active",
            "tps_limit": 7,
            "status": "active",
        },
    )

    response = _client().get(
        "/auth/check",
        headers={"X-API-Key": "active-test-key"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "client_id": "client-active",
    }


def test_repository_uses_exact_api_key_query():
    class RecordingCollection:
        def __init__(self):
            self.query = None

        def find_one(self, query):
            self.query = query
            return {"client_id": "client-active"}

    collection = RecordingCollection()

    result = find_client_by_api_key(collection, "Case-Sensitive-Key")

    assert collection.query == {"api_key": "Case-Sensitive-Key"}
    assert result == {"client_id": "client-active"}
