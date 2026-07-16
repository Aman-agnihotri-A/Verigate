"""Client repository for authentication.

Read-only, exact-match lookup against the `clients` collection. No
ODM-style methods (no `save`, `find`, `query`, active-record, or
automatic persistence) -- a single small function receiving an
existing collection handle.
"""
from __future__ import annotations

from typing import Any, Optional


def find_client_by_api_key(
    clients_collection: Any, api_key: str
) -> Optional[dict[str, Any]]:
    """Exact-match lookup by api_key. Returns the raw document or None.

    Uses an exact equality query -- no regex, no partial match, no
    case-insensitive collation. Does not mutate the returned document.

    Raises whatever pymongo.errors.PyMongoError (or subclass) the
    underlying driver raises on a database failure; this function does
    not catch it. Translating that failure into a safe response is the
    caller's responsibility (see app.auth.decorators), so that a
    database outage is never reported as an invalid credential.
    """
    return clients_collection.find_one({"api_key": api_key})