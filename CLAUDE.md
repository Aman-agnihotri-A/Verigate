# CLAUDE.md — VeriGate

## Project purpose

VeriGate is a Flask + MongoDB verification API gateway for the Valuepitch take-home assignment. It authenticates API clients, validates client sub-users, enforces IP whitelists and per-client TPS limits, calls simulated primary/fallback vendors, writes PII-safe audit logs, and exposes admin-only MIS analytics.

## Stack

- Python 3.11+
- Flask
- PyMongo, without an ODM
- MongoDB 7+ for `$percentile` in the TPS aggregation
- pytest
- Optional Docker Compose for the app and MongoDB

No real external services or real PII are allowed. Vendor behavior is simulated inside the application.

## Application structure

- `app/__init__.py` — Flask application factory and blueprint registration.
- `app/config.py` — environment-driven configuration.
- `app/extensions.py` — lazy Mongo client/database handles.
- `app/auth/` — exact API-key authentication helpers and safe auth context.
- `app/security/` — IP extraction/whitelisting plus PII masking/hashing.
- `app/schemas/verification.py` — immutable verification request schema and validation.
- `app/rate_limit/` — single-process, thread-safe rolling one-second TPS limiter.
- `app/vendors/` — primary/fallback vendor simulation.
- `app/audit/` — Mongo audit write with sanitized JSONL emergency fallback.
- `app/verification.py` — `POST /api/v1/verify` orchestration.
- `app/mis/` — admin-only MongoDB aggregation endpoints.
- `app/models/` — document builders, error-code contract, and index specification.
- `scripts/seed.py` — clients, users, synthetic historical logs, and indexes.
- `scripts/load_test.py` — mixed traffic and TPS/IP rejection demonstration.
- `tests/` — unit and route-level tests by concern.

## Frozen contracts

Do not change these without explicit review:

- Error-code and HTTP-status mapping in `app/models/api_log.py`.
- Audit-log field names.
- Raw `name` and `id_number` must never be stored or written to logs.
- Masking keeps the final four characters visible; values of length four or less are fully masked.
- Verification request body fields: `client_ref_id`, `id_type`, `id_number`, and `name`.
- Allowed `id_type` values: `PAN`, `DL`, and `VOTER`.
- Gateway order: API-key authentication → active sub-user validation → trusted client-IP extraction and whitelist check → TPS check → payload validation → vendor/fallback call → audit write → response.
- MIS `from` and `to` parameters are ISO dates. The user-facing `to` date is inclusive; internally the query uses the next midnight as an exclusive upper bound.
- Daily average TPS is total requests divided by 86,400 seconds.
- Index definitions live only in `app/models/indexes.py:INDEX_SPECS`.

## Security rules

- Never hardcode real secrets or commit `.env`.
- Trust `X-Forwarded-For` only in explicit local-development mode or when `remote_addr` is in `TRUSTED_PROXY_IPS`.
- Never include API keys, raw request bodies, full names, or full identity numbers in exceptions or audit records.
- All rejected gateway attempts must be audited when the audit sink is available.
- Do not replace the audit repository with direct `insert_one()` calls elsewhere.

## Local commands

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python scripts/seed.py
python run.py
```

Tests:

```bash
python -m pytest -v
```

Load demonstration after seeding and starting the app:

```bash
python scripts/load_test.py
```

Docker:

```bash
docker compose up --build -d
docker compose exec app python scripts/seed.py
docker compose down
```

## Engineering rules

- Keep modules small and independently testable.
- Prefer pure helpers and dependency injection over hidden global behavior.
- Use MongoDB aggregation pipelines for MIS calculations; do not fetch all logs and calculate reports in Python.
- Add or update tests for every behavior change.
- Record unresolved assignment ambiguities in `docs/ASSUMPTIONS.md`.
- Do not implement unrelated bonus features while fixing mandatory behavior.
- Preserve readable formatting and type hints; avoid compressed one-line production code.
