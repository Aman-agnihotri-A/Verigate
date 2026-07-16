"""PII masking and hashing helpers (design contracts, frozen rule).

Rule: keep exactly the last 4 characters visible; mask every
preceding character with '*'. If the value's length is <= 4, mask the
entire value. The same rule applies to both `name` and `id_number` per
the original assignment's single, combined PII instruction.
"""
from __future__ import annotations

import hashlib

VISIBLE_SUFFIX_LEN = 4


def mask_value(value: str) -> str:
    if value is None:
        raise ValueError("cannot mask None")
    length = len(value)
    if length > VISIBLE_SUFFIX_LEN:
        return "*" * (length - VISIBLE_SUFFIX_LEN) + value[-VISIBLE_SUFFIX_LEN:]
    return "*" * length


def hash_value(value: str) -> str:
    """SHA-256 hex digest of the raw value, computed before masking."""
    if value is None:
        raise ValueError("cannot hash None")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
