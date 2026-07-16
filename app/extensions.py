"""Shared extension singletons (MongoDB client).

Phase 1 only wires the client factory; no collections are queried yet.
"""
from __future__ import annotations

from flask import Flask
from pymongo import MongoClient


def init_mongo(app: Flask) -> MongoClient:
    """Attach a lazily-connecting MongoClient to the Flask app.

    pymongo's MongoClient does not open a network connection at
    construction time for a standard mongodb:// URI, so this is safe
    to call even when no MongoDB server is reachable (e.g. in tests
    or sandboxed environments) — connections are only attempted when
    an actual operation is issued.
    """
    client: MongoClient = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DB_NAME"]]
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = db
    return client


def get_db(app: Flask):
    return app.extensions["mongo_db"]
