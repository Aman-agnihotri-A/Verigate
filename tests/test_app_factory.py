"""Tests for the Flask application factory.

Proves: create_app() succeeds with no running MongoDB server, performs
no MongoDB network operation, creates no indexes eagerly, and does not
require development secrets to be present. Also proves GET /health
works and does not depend on Mongo being reachable.
"""
from __future__ import annotations

from app import create_app
from app.config import Config


class _TestConfig(Config):
    # Deliberately points at a host that will never resolve/accept a
    # connection, to prove create_app() never talks to it.
    MONGO_URI = "mongodb://mongo-does-not-exist.invalid:27017"
    MONGO_DB_NAME = "verigate_test"
    TESTING = True
    # SECRET_KEY / ADMIN_API_KEY deliberately left as base-class
    # defaults (empty string) -- create_app() must not require them.


def test_create_app_succeeds_without_running_mongodb():
    # If this constructed a real connection or ran a command, it would
    # hang or raise in this network-disabled sandbox. Successfully
    # returning proves MongoClient construction stayed lazy.
    app = create_app(_TestConfig)
    assert app is not None
    assert app.config["MONGO_URI"] == _TestConfig.MONGO_URI


def test_create_app_does_not_require_secrets_present():
    # Config.validate() is a separate, explicit opt-in step (see
    # app/config.py) -- create_app() itself must not call it.
    app = create_app(_TestConfig)
    assert app.config["SECRET_KEY"] == ""
    assert app.config["ADMIN_API_KEY"] == ""


def test_mongo_extension_is_registered_but_not_connected():
    app = create_app(_TestConfig)
    # The client/db handles exist (lazy objects) but constructing them
    # must not have required any network I/O.
    assert "mongo_client" in app.extensions
    assert "mongo_db" in app.extensions


def test_health_endpoint_returns_ok_without_touching_mongo():
    app = create_app(_TestConfig)
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"


def test_expected_application_routes_are_registered():
    app = create_app(_TestConfig)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    # Flask always adds a static route; verify all application blueprints are registered.
    app_rules = {r for r in rules if r != "/static/<path:filename>"}
    assert app_rules == {
        "/health",
        "/auth/check",
        "/api/v1/verify",
        "/api/v1/mis/usage",
        "/api/v1/mis/errors",
        "/api/v1/mis/tps",
        "/api/v1/mis/fallback",
        "/api/v1/mis/ips",
    }
