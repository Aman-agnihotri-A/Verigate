# VeriGate

VeriGate is a Flask + MongoDB mini verification API gateway implementing API-key authentication, sub-user tracking, IP whitelisting, per-client TPS limits, simulated vendor fallback, a MongoDB vendor-attempt trail, PII-safe audit logging, and MIS analytics.

## Local setup

Requirements: Python 3.11+ and MongoDB 7+.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python scripts/seed.py
python run.py
```

The `.env` file is loaded automatically by both the application entrypoint and seed script. Do not commit it.

Run tests:

```powershell
python -m pytest -v
```

## Docker bonus

Install Docker Desktop separately, then run:

```powershell
docker compose up --build -d
docker compose exec app python scripts/seed.py
docker compose ps
```

Stop the stack:

```powershell
docker compose down
```

Docker runs one Gunicorn worker with multiple threads so the process-local TPS limiter remains consistent. Multiple workers or pods would each maintain independent counters; production should replace the limiter with an atomic Redis implementation.

## Seeded development data

The seed script creates three fictional clients and three users per client, plus approximately 3,000 synthetic historical logs.

| Client | API key | Example user | Allowed test IP | TPS |
|---|---|---|---|---:|
| `alphabank` | `alpha-key` | `al_ops_01` | `103.24.10.5` | 5 |
| `zetafin` | `zeta-key` | `ze_ops_01` | `103.24.10.6` | 3 |
| `novahr` | `nova-key` | `no_ops_01` | `103.24.10.7` | 4 |

These credentials and identities are synthetic and only for local assessment use.

## Verification endpoint

`POST /api/v1/verify` requires:

- `X-API-Key`
- `X-User-Id`
- JSON body with `client_ref_id`, `id_type`, `id_number`, and `name`

For local testing, `X-Forwarded-For` supplies the synthetic client IP. In production, it is accepted only when the immediate connection is a configured trusted proxy/load balancer, because arbitrary clients can otherwise spoof the header.

## MIS endpoints

All MIS endpoints require `X-Admin-Key` and use MongoDB aggregation pipelines:

- `/api/v1/mis/usage?from=2026-07-01&to=2026-07-07&group_by=client|user|day`
- `/api/v1/mis/errors?from=2026-07-01&to=2026-07-07`
- `/api/v1/mis/tps?client_id=alphabank&date=2026-07-05`
- `/api/v1/mis/fallback?from=2026-07-01&to=2026-07-07`
- `/api/v1/mis/ips?client_id=alphabank&from=2026-07-01&to=2026-07-07`

The `to` date is inclusive. Usage and errors support `format=csv`.

## Load/TPS demonstration

With the seeded app running:

```powershell
python scripts/load_test.py
```

The script runs mixed traffic for about 60 seconds, uses concurrent per-second bursts to deliberately exceed Alpha Bank's TPS limit, and sends Nova HR traffic from a blocked IP. It prints sent, succeeded, rate-limited, blocked, and other-failure totals per client. Query the MIS endpoints afterward to cross-check the resulting logs.

## Indexes

- `api_logs(client_id, created_at)`: client/date-range MIS filtering.
- `api_logs(error_code)`: error distribution queries.
- `api_logs(created_at)`: global date-range reports.
- unique `clients(api_key)`: authentication lookup and duplicate prevention.
- unique `clients(client_id)`: stable client identity.
- unique `users(client_id, user_id)`: sub-user validation.

## PII and audit safety

Raw names and identity numbers are never stored in `api_logs`. Audit records contain masked values and SHA-256 hashes. Vendor execution is auditable through `fallback_used`, `failover_reason`, and a PII-free `vendor_attempts` array showing primary/fallback success or failure without storing exception text. A failed Mongo audit write falls back to a sanitized local JSONL record. The local fallback is suitable for single-host resilience only; a distributed deployment should use a durable centralized sink.

## Submission checklist

See `docs/ASSESSMENT_CHECKLIST.md`. The code package cannot create a meaningful Git history retroactively, so ensure the submitted private repository retains at least 10 meaningful commits.
