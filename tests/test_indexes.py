"""Tests for the index specification.

Checks the *specification* only -- no live MongoDB connection is
available in this sandbox, so `create_indexes()` itself is not
exercised here; it is a thin, direct translation of INDEX_SPECS.
"""
from __future__ import annotations

from app.models.indexes import INDEX_SPECS


def _find(collection, keys):
    return [
        (c, k, o)
        for (c, k, o) in INDEX_SPECS
        if c == collection and k == keys
    ]


def test_required_minimum_client_created_compound_index_exists():
    matches = _find("api_logs", [("client_id", 1), ("created_at", 1)])
    assert len(matches) == 1


def test_required_minimum_error_code_index_exists():
    matches = _find("api_logs", [("error_code", 1)])
    assert len(matches) == 1


def test_clients_api_key_index_is_unique():
    matches = _find("clients", [("api_key", 1)])
    assert len(matches) == 1
    assert matches[0][2]["unique"] is True


def test_clients_client_id_index_is_unique():
    matches = _find("clients", [("client_id", 1)])
    assert len(matches) == 1
    assert matches[0][2]["unique"] is True


def test_users_compound_index_is_unique():
    matches = _find("users", [("client_id", 1), ("user_id", 1)])
    assert len(matches) == 1
    assert matches[0][2]["unique"] is True


def test_api_logs_created_at_single_field_index_exists():
    assert _find("api_logs", [("created_at", 1)])


def test_no_standalone_ip_index_is_claimed():
    # A standalone api_logs.ip index does not cover the IP report's
    # real (client_id + date range) filter pattern and is not
    # justified by any query in the assignment text as a single-field
    # index -- it must not appear in the spec.
    assert not _find("api_logs", [("ip", 1)])


def test_no_speculative_client_error_created_compound_index():
    # This compound index was removed on review: the required
    # (client_id, created_at) index already narrows the working set
    # for any client-scoped, date-ranged error query: MongoDB can use
    # (client_id, created_at) to satisfy the filter, then group by
    # error_code over the already-small filtered result set -- an
    # additional (client_id, error_code, created_at) index is not
    # justified as a *required* addition on top of that.
    assert not _find(
        "api_logs", [("client_id", 1), ("error_code", 1), ("created_at", 1)]
    )


def test_index_spec_only_contains_reviewed_entries():
    # Exactly six indexes are currently justified. If this count
    # changes, the change must come with an explicit justification
    # added to app/models/indexes.py and to this test file.
    assert len(INDEX_SPECS) == 6
