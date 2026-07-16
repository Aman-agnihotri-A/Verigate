"""Tests for the frozen masking/hashing rule.

Values used here are synthetic sample strings for rule-verification
only -- not real personal data.
"""
from __future__ import annotations

import hashlib

import pytest

from app.security.masking import mask_value, hash_value


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ABCDE1234F", "******234F"),
        ("Rahul Sharma", "********arma"),
        ("Verma", "*erma"),
        ("XY1237788K", "******788K"),
        ("AB12", "****"),
        ("Al", "**"),
    ],
)
def test_mask_value_matches_frozen_rule(raw, expected):
    assert mask_value(raw) == expected


def test_hash_value_is_sha256_of_raw_value():
    raw = "ABCDE1234F"
    assert hash_value(raw) == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_mask_and_hash_never_expose_more_than_contract():
    raw = "ABCDE1234F"
    masked = mask_value(raw)
    assert raw not in masked
    assert masked.endswith(raw[-4:])


def test_mask_value_rejects_none():
    with pytest.raises(ValueError):
        mask_value(None)


def test_hash_value_rejects_none():
    with pytest.raises(ValueError):
        hash_value(None)
