"""Environment-driven configuration.

All secrets and tunables come from environment variables. Nothing in
this module hardcodes a real secret; .env.example documents every
variable with a safe placeholder.
"""
from __future__ import annotations

import os


class ConfigError(RuntimeError):
    """Raised when required configuration is missing at startup."""


def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val not in (None, "") else default


class Config:
    """Base configuration, values resolved from environment at import time."""

    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    FLASK_DEBUG = _get_bool("FLASK_DEBUG", False)
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "verigate")

    ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

    VENDOR_A_FAILURE_RATE = _get_float("VENDOR_A_FAILURE_RATE", 0.2)
    VENDOR_A_TIMEOUT_RATE = _get_float("VENDOR_A_TIMEOUT_RATE", 0.1)
    VENDOR_A_TIMEOUT_BUDGET_MS = _get_int("VENDOR_A_TIMEOUT_BUDGET_MS", 2000)
    VENDOR_LATENCY_MIN_MS = _get_int("VENDOR_LATENCY_MIN_MS", 100)
    VENDOR_LATENCY_MAX_MS = _get_int("VENDOR_LATENCY_MAX_MS", 800)

    DEFAULT_TPS_LIMIT = _get_int("DEFAULT_TPS_LIMIT", 5)

    TRUSTED_PROXY_IPS = [
        ip.strip()
        for ip in os.environ.get("TRUSTED_PROXY_IPS", "127.0.0.1").split(",")
        if ip.strip()
    ]
    TRUST_XFF_HEADER_DEV_ONLY = _get_bool("TRUST_XFF_HEADER_DEV_ONLY", False)

    EMERGENCY_LOG_PATH = os.environ.get(
        "EMERGENCY_LOG_PATH", "logs/emergency_fallback.jsonl"
    )

    @classmethod
    def validate(cls) -> None:
        """Raise ConfigError if required secrets/config are missing.

        Intentionally NOT called automatically at import time so that
        tests and local scaffolding work without real secrets; the
        application entrypoint (phase 2) is expected to call this
        before serving real traffic.
        """
        missing = []
        if not cls.SECRET_KEY:
            missing.append("SECRET_KEY")
        if not cls.ADMIN_API_KEY:
            missing.append("ADMIN_API_KEY")
        if not cls.MONGO_URI:
            missing.append("MONGO_URI")
        if missing:
            raise ConfigError(
                "Missing required configuration: " + ", ".join(missing)
            )
