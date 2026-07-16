"""Unit tests for client IP extraction and whitelist validation."""
from __future__ import annotations

import pytest

from app.security.ip_whitelist import (
    ClientIPError,
    extract_client_ip,
    is_ip_whitelisted,
    validate_client_ip,
)


def test_extracts_forwarded_ip_when_present():
    assert extract_client_ip("203.0.113.10", "127.0.0.1") == "203.0.113.10"


def test_uses_first_address_from_forwarded_chain():
    assert (
        extract_client_ip("203.0.113.10, 198.51.100.4", "127.0.0.1")
        == "203.0.113.10"
    )


def test_trims_forwarded_ip_whitespace():
    assert extract_client_ip(" 203.0.113.10 ", "127.0.0.1") == "203.0.113.10"


def test_falls_back_to_remote_address():
    assert extract_client_ip(None, " 127.0.0.1 ") == "127.0.0.1"


def test_blank_forwarded_header_falls_back_to_remote_address():
    assert extract_client_ip("   ", "127.0.0.1") == "127.0.0.1"


def test_forwarded_header_takes_precedence_over_remote_address():
    assert extract_client_ip("203.0.113.10", "198.51.100.4") == "203.0.113.10"


@pytest.mark.parametrize(
    ("forwarded_for", "remote_addr"),
    [(None, None), ("", ""), ("   ", None)],
)
def test_rejects_missing_client_ip(forwarded_for, remote_addr):
    with pytest.raises(ClientIPError) as exc_info:
        extract_client_ip(forwarded_for, remote_addr)

    assert exc_info.value.reason == "MISSING_CLIENT_IP"


@pytest.mark.parametrize(
    ("forwarded_for", "remote_addr"),
    [("not-an-ip", "127.0.0.1"), (None, "999.1.1.1")],
)
def test_rejects_malformed_client_ip(forwarded_for, remote_addr):
    with pytest.raises(ClientIPError) as exc_info:
        extract_client_ip(forwarded_for, remote_addr)

    assert exc_info.value.reason == "INVALID_CLIENT_IP"


def test_matches_whitelisted_ipv4_exactly():
    assert is_ip_whitelisted("203.0.113.10", ["203.0.113.10"])


def test_rejects_non_whitelisted_ipv4():
    assert not is_ip_whitelisted("203.0.113.11", ["203.0.113.10"])


def test_matches_whitelisted_ipv6():
    assert is_ip_whitelisted("2001:db8::1", ["2001:db8::1"])


def test_matches_equivalent_ipv6_representations():
    assert is_ip_whitelisted(
        "2001:0db8:0000:0000:0000:0000:0000:0001",
        ["2001:db8::1"],
    )


def test_empty_whitelist_does_not_allow_client_ip():
    assert not is_ip_whitelisted("203.0.113.10", [])


@pytest.mark.parametrize("entry", ["not-an-ip", "", "   ", None, 123])
def test_rejects_invalid_whitelist_entries(entry):
    with pytest.raises(ClientIPError) as exc_info:
        is_ip_whitelisted("203.0.113.10", [entry])

    assert exc_info.value.reason == "INVALID_WHITELIST_ENTRY"


def test_does_not_mutate_whitelist():
    whitelist = [" 203.0.113.10 ", "2001:0db8::1"]
    original = whitelist.copy()

    assert is_ip_whitelisted("203.0.113.10", whitelist)
    assert whitelist == original


def test_validate_client_ip_returns_normalized_allowed_ip():
    result = validate_client_ip(
        "2001:0db8:0000:0000:0000:0000:0000:0001",
        "127.0.0.1",
        ["2001:db8::1"],
    )

    assert result == "2001:db8::1"


def test_validate_client_ip_rejects_blocked_ip_safely():
    blocked_ip = "203.0.113.99"

    with pytest.raises(ClientIPError) as exc_info:
        validate_client_ip(blocked_ip, "127.0.0.1", ["203.0.113.10"])

    assert exc_info.value.reason == "IP_NOT_WHITELISTED"
    assert blocked_ip not in str(exc_info.value)


def test_invalid_forwarded_chain_first_entry_is_rejected():
    with pytest.raises(ClientIPError) as exc_info:
        extract_client_ip("unknown, 203.0.113.10", "127.0.0.1")

    assert exc_info.value.reason == "INVALID_CLIENT_IP"
