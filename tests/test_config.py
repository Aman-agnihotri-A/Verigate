"""Tests for app.config -- env-var driven configuration."""
from __future__ import annotations

import importlib

import pytest


def _reload_config(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import app.config as config_module

    importlib.reload(config_module)
    return config_module


def test_defaults_when_env_absent(monkeypatch):
    for var in [
        "SECRET_KEY", "ADMIN_API_KEY", "MONGO_URI", "MONGO_DB_NAME",
        "VENDOR_A_FAILURE_RATE", "DEFAULT_TPS_LIMIT", "TRUSTED_PROXY_IPS",
        "TRUST_XFF_HEADER_DEV_ONLY",
    ]:
        monkeypatch.delenv(var, raising=False)
    config_module = _reload_config(monkeypatch)
    assert config_module.Config.MONGO_URI == "mongodb://localhost:27017"
    assert config_module.Config.DEFAULT_TPS_LIMIT == 5
    assert config_module.Config.TRUSTED_PROXY_IPS == ["127.0.0.1"]
    assert config_module.Config.TRUST_XFF_HEADER_DEV_ONLY is False


def test_env_overrides_are_read(monkeypatch):
    config_module = _reload_config(
        monkeypatch,
        MONGO_URI="mongodb://example-host:27017",
        DEFAULT_TPS_LIMIT="9",
        TRUSTED_PROXY_IPS="10.0.0.1,10.0.0.2",
        TRUST_XFF_HEADER_DEV_ONLY="true",
    )
    assert config_module.Config.MONGO_URI == "mongodb://example-host:27017"
    assert config_module.Config.DEFAULT_TPS_LIMIT == 9
    assert config_module.Config.TRUSTED_PROXY_IPS == ["10.0.0.1", "10.0.0.2"]
    assert config_module.Config.TRUST_XFF_HEADER_DEV_ONLY is True


def test_validate_raises_when_secrets_missing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    config_module = _reload_config(monkeypatch, MONGO_URI="mongodb://localhost:27017")
    with pytest.raises(config_module.ConfigError):
        config_module.Config.validate()


def test_validate_passes_when_secrets_present(monkeypatch):
    config_module = _reload_config(
        monkeypatch,
        SECRET_KEY="dev-only-placeholder",
        ADMIN_API_KEY="dev-only-placeholder",
        MONGO_URI="mongodb://localhost:27017",
    )
    config_module.Config.validate()  # should not raise
