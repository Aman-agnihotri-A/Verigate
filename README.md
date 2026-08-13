# VeriGate

VeriGate is a production-style Flask and MongoDB identity-verification API gateway designed to demonstrate secure, resilient backend verification workflows.. It demonstrates client API-key authentication, sub-user validation, trusted-proxy-aware IP whitelisting, per-client TPS limits, simulated vendor failover, PII-safe audit logging, and administrative MIS analytics.

The external verification vendors are deliberately simulated so timeout, failure, fallback, audit, and reporting behaviour can be tested locally without third-party credentials.

## Key features

- Flask application-factory architecture
- MongoDB persistence and aggregation pipelines
- Client authentication through `X-API-Key`
- Sub-user validation through `X-User-Id`
- Trusted-proxy-aware client IP extraction
- Client-specific IP whitelisting
- Thread-safe per-client TPS limiting
- Primary and fallback vendor simulation
- Timeout, failure, mismatch, and success scenarios
- PII masking and SHA-256 hashing
- MongoDB audit logging with sanitized JSONL emergency fallback
- Admin-protected MIS reports with selected CSV exports
- Synthetic seed data and concurrent load testing
- Docker, Docker Compose, Pytest, and GitHub Actions support

## Request flow

```text
Client request
      |
      v
API-key authentication
      |
      v
Sub-user validation
      |
      v
Trusted client-IP resolution
      |
      v
IP-whitelist enforcement
      |
      v
Per-client TPS limiter
      |
      v
Payload validation
      |
      v
Primary vendor
   /       \
Success   Failure/timeout
  |             |
  |             v
  |       Fallback vendor
  |             |
  +-------------+
        |
        v
PII-safe audit record
        |
        v
Standard API response
```

## Technology stack

- Python 3.11+
- Flask 3
- MongoDB 7+
- PyMongo
- Pytest
- Docker and Docker Compose
- Gunicorn in the containerized deployment

## Project structure

```text
app/
├── audit/          # MongoDB and emergency audit persistence
├── auth/           # API-key authentication components
├── mis/            # Administrative analytics endpoints
├── models/         # Document builders and MongoDB index definitions
├── rate_limit/     # Per-client TPS limiter
├── schemas/        # Verification request validation
├── security/       # IP whitelist, trusted proxies, masking, and hashing
├── vendors/        # Primary and fallback vendor simulation
├── config.py
├── extensions.py
├── health.py
├── responses.py
└── verification.py

docs/               # Assumptions, deployment notes, test results, and examples
scripts/
├── seed.py          # Synthetic client, user, and audit data
└── load_test.py     # Concurrent verification traffic demonstration

tests/              # Automated unit and endpoint tests
Dockerfile
docker-compose.yml
requirements.txt
run.py
```

## Local setup

### Prerequisites

- Python 3.11 or newer
- MongoDB 7 or newer

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python scripts/seed.py
python run.py
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python scripts/seed.py
python run.py
```

The application runs at `http://localhost:5000`. The `.env` file contains local configuration and must not be committed.

### Health check

```bash
curl http://localhost:5000/health
```

## Environment configuration

Copy `.env.example` to `.env` and adjust values for the local environment.

Important variables include:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask application secret |
| `MONGO_URI` | MongoDB connection URI |
| `MONGO_DB_NAME` | Application database name |
| `ADMIN_API_KEY` | Protects MIS endpoints |
| `DEFAULT_TPS_LIMIT` | Default transactions-per-second limit |
| `TRUSTED_PROXY_IPS` | Immediate proxy addresses allowed to supply `X-Forwarded-For` |
| `TRUST_XFF_HEADER_DEV_ONLY` | Explicit local-development override for forwarded IPs |
| `EMERGENCY_LOG_PATH` | Sanitized JSONL audit fallback path |

The values in `.env.example` are placeholders or fictional local-development settings, not production credentials.

## Seeded development data

Run:

```bash
python scripts/seed.py
```

The script creates three fictional clients, three users per client, required indexes, and approximately 3,000 synthetic historical audit records.

| Client | API key | Example user | Allowed test IP | TPS |
|---|---|---|---|---:|
| `alphabank` | `alpha-key` | `al_ops_01` | `103.24.10.5` | 5 |
| `zetafin` | `zeta-key` | `ze_ops_01` | `103.24.10.6` | 3 |
| `novahr` | `nova-key` | `no_ops_01` | `103.24.10.7` | 4 |

These credentials and identities are synthetic and intended only for local assessment testing.

## Verification API

### Endpoint

```http
POST /api/v1/verify
```

### Required headers

```http
Content-Type: application/json
X-API-Key: alpha-key
X-User-Id: al_ops_01
X-Forwarded-For: 103.24.10.5
```

`X-Forwarded-For` is trusted only when the immediate connection comes from a configured trusted proxy, unless the explicit development-only override is enabled.

### Example request

```bash
curl -X POST http://localhost:5000/api/v1/verify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: alpha-key" \
  -H "X-User-Id: al_ops_01" \
  -H "X-Forwarded-For: 103.24.10.5" \
  -d '{
    "client_ref_id": "REF-10001",
    "id_type": "PAN",
    "id_number": "ABCDE1234F",
    "name": "Synthetic User"
  }'
```

### Example success response

```json
{
  "status": "success",
  "request_id": "req_123456789abc",
  "error_code": "VP2000",
  "data": {
    "verified": true,
    "name_match_score": 92,
    "source": "PRIMARY"
  },
  "latency_ms": 436
}
```

### Example error response

```json
{
  "status": "error",
  "request_id": "req_123456789abc",
  "error_code": "VP4010",
  "message": "Invalid API key"
}
```

Exact outcomes vary because vendor behaviour is simulated. Additional request examples are available in `docs/curl_examples.md`.

## Vendor fallback and audit fields

The primary vendor can simulate success, verification mismatch, service failure, or timeout. The fallback vendor is attempted only when the primary vendor fails or times out.

| Field | Meaning |
|---|---|
| `vendor_used` | Vendor that produced the final usable result |
| `fallback_used` | Whether the fallback vendor was attempted |
| `failover_reason` | Failure or timeout reason from the primary vendor |
| `vendor_attempts` | PII-free trail of primary and fallback outcomes |

When both vendors fail, `fallback_used` is `true` because fallback was attempted, while `vendor_used` is `null` because neither vendor produced a usable result.

Example:

```json
{
  "vendor_used": null,
  "fallback_used": true,
  "failover_reason": "VendorFailure",
  "vendor_attempts": [
    {
      "vendor": "PRIMARY",
      "outcome": "FAILED",
      "error_type": "VendorFailure"
    },
    {
      "vendor": "FALLBACK",
      "outcome": "FAILED",
      "error_type": "VendorFailure"
    }
  ]
}
```

## MIS endpoints

All MIS endpoints require:

```http
X-Admin-Key: <configured-admin-key>
```

Available reports:

```text
GET /api/v1/mis/usage
GET /api/v1/mis/errors
GET /api/v1/mis/tps
GET /api/v1/mis/fallback
GET /api/v1/mis/ips
```

Examples:

```text
/api/v1/mis/usage?from=2026-07-01&to=2026-07-07&group_by=client
/api/v1/mis/usage?from=2026-07-01&to=2026-07-07&group_by=user
/api/v1/mis/usage?from=2026-07-01&to=2026-07-07&group_by=day
/api/v1/mis/errors?from=2026-07-01&to=2026-07-07
/api/v1/mis/tps?client_id=alphabank&date=2026-07-05
/api/v1/mis/fallback?from=2026-07-01&to=2026-07-07
/api/v1/mis/ips?client_id=alphabank&from=2026-07-01&to=2026-07-07
```

The `to` date is inclusive. Usage and error reports support `format=csv`.

## Running tests

```bash
python -m pytest -q
```

Current validated result:

```text
187 passed
```

The suite covers application setup, authentication, client/user isolation, trusted proxies, IP whitelisting, masking and hashing, request validation, TPS limiting, vendor fallback, audit persistence, emergency logging, MIS pipelines, seed helpers, and endpoint behaviour.

GitHub Actions runs the same test command on pushes to `main` and pull requests.

## Load and TPS demonstration

Start the seeded application, then run:

```bash
python scripts/load_test.py
```

The script generates traffic from all three clients, deliberately exceeds Alpha Bank's TPS limit with concurrent bursts, sends blocked Nova HR traffic, and exercises successful and failed vendor outcomes. It prints sent, successful, rate-limited, blocked, and other-failure totals per client. MIS endpoints can then be queried to compare the resulting audit data.

## Docker setup

Install Docker Desktop or Docker Engine, then run:

```bash
docker compose up --build -d
docker compose exec app python scripts/seed.py
docker compose ps
```

Stop the stack with:

```bash
docker compose down
```

The container uses one Gunicorn worker with multiple threads because the assessment limiter is process-local. A multi-worker or multi-pod production deployment should use Redis or another shared atomic rate-limiting store.

## MongoDB indexes

- `api_logs(client_id, created_at)` for client/date-range MIS filtering
- `api_logs(error_code)` for error distribution reporting
- `api_logs(created_at)` for global date-range reports
- unique `clients(api_key)` for authentication lookup and duplicate prevention
- unique `clients(client_id)` for stable client identity
- unique `users(client_id, user_id)` for sub-user validation

## Security and privacy decisions

Raw names and identity numbers are never stored in `api_logs`. Audit records contain masked values and SHA-256 hashes for correlation without retaining the original PII.

Vendor execution is represented through `vendor_used`, `fallback_used`, `failover_reason`, and a PII-free `vendor_attempts` list. Exception text is not stored in the normal attempt trail.

If the MongoDB audit write fails, VeriGate attempts to write one sanitized JSONL emergency record. The emergency writer uses an allow-list and removes credential-like content before writing. This fallback is suitable for single-host resilience only; a distributed system should use a centralized durable audit sink.

## Known limitations and assessment trade-offs

- The TPS limiter is process-local and is not suitable for independent workers or pods.
- The JSONL emergency audit file is local to one host.
- Verification vendors are simulated rather than real HTTP integrations.
- The optional circuit breaker is not implemented.
- Fictional development API keys are stored in plaintext for simple local lookup.
- MongoDB 7+ is expected for the MIS percentile aggregation.

## Production improvements

- Redis-backed distributed rate limiting
- High-entropy API keys stored only as hashes, with rotation and revocation
- Real vendor HTTP adapters with retry budgets and circuit breaking
- Centralized structured logging and durable emergency audit transport
- OpenAPI/Swagger documentation
- Metrics, tracing, and alerting
- CI linting, type checking, dependency scanning, and container scanning

## AI-assisted development

AI tooling was used as a development assistant for planning, test scaffolding, documentation, and code review. Generated suggestions were inspected, corrected where necessary, and validated through the automated test suite before inclusion. Representative workflow notes are documented in `docs/AI_WORKFLOW.md`.

## Assessment status

- Core verification API: complete
- API-key and sub-user authentication: complete
- IP whitelisting: complete
- TPS limiting: complete
- Vendor fallback: complete
- PII-safe audit logging: complete
- MIS analytics: complete
- Seed and load-test scripts: complete
- Docker support: complete
- Automated tests: 187 passing
- Meaningful Git history: 10 commits

Additional documentation is available under `docs/`.
