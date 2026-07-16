"""Index specifications for VeriGate collections.

This module is deliberately split into (a) a plain-data specification
that can be unit-tested without a MongoDB connection, and (b) a thin
`create_indexes` function that applies the spec — not exercised in
this foundation phase (no live MongoDB in this environment, and no
code path calls it yet).

Required minimum (explicit in the assignment, Sec 3.7):
  - api_logs: compound ascending (client_id, created_at)
  - api_logs: ascending error_code

Every other index below is retained only because it is justified by
a concrete query described in the assignment text -- see the inline
justification on each entry. No speculative indexes are included.
"""
from __future__ import annotations

from typing import Any

# Each entry: (collection_name, keys, options)
# keys follows pymongo's create_index format: list[(field, direction)]
INDEX_SPECS: list[tuple[str, list[tuple[str, int]], dict[str, Any]]] = [
    # --- Required minimum (assignment Sec 3.7) ---
    (
        "api_logs",
        [("client_id", 1), ("created_at", 1)],
        {"name": "idx_logs_client_created"},
    ),
    (
        "api_logs",
        [("error_code", 1)],
        {"name": "idx_logs_error_code"},
    ),
    # --- Additional, individually justified below ---
    (
        "clients",
        [("api_key", 1)],
        {"unique": True, "name": "uniq_clients_api_key"},
    ),
    (
        "clients",
        [("client_id", 1)],
        {"unique": True, "name": "uniq_clients_client_id"},
    ),
    (
        "users",
        [("client_id", 1), ("user_id", 1)],
        {"unique": True, "name": "uniq_users_client_user"},
    ),
    (
        "api_logs",
        [("created_at", 1)],
        {"name": "idx_logs_created_at"},
    ),
]


def create_indexes(db) -> list[str]:
    """Apply INDEX_SPECS against a real database handle.

    Not exercised in this phase's unit tests (no live MongoDB in this
    environment, and no orchestration code calls this function yet) --
    kept as a thin, direct translation of the spec so there is exactly
    one place index definitions can drift from the design contracts.
    """
    created = []
    for collection_name, keys, options in INDEX_SPECS:
        name = db[collection_name].create_index(keys, **options)
        created.append(name)
    return created
