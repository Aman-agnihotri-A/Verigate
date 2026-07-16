# VeriGate Assessment Compliance Checklist

This checklist maps the submitted implementation to the Valuepitch assignment.

## Part A — Core Verification API

| Requirement | Implementation | Status |
|---|---|---|
| Three fictional clients and 2–3 users each | `scripts/seed.py` creates `alphabank`, `zetafin`, and `novahr`, with three active users each | Complete |
| `X-API-Key` authentication | `app/auth/` and `app/verification.py` perform exact API-key lookup and active-client checks | Complete |
| `X-User-Id` tracking | `app/verification.py` validates an active user belonging to the authenticated client | Complete |
| `POST /api/v1/verify` | `app/verification.py` | Complete |
| IP whitelisting | `app/security/ip_whitelist.py`; blocked attempts return `VP4003` and are audited | Complete |
| Trusted `X-Forwarded-For` boundary | XFF is accepted only in explicit development mode or when the immediate peer is configured as trusted | Complete |
| Primary and fallback vendors | `app/vendors/simulator.py`; every execution returns a PII-free attempt trail | Complete |
| Configurable primary failure, timeout, and latency | Environment-backed values in `app/config.py` and `.env.example` | Complete |
| Per-client TPS limiting | Thread-safe rolling one-second limiter in `app/rate_limit/limiter.py` | Complete for one process |
| Standard error codes | Frozen mapping in `app/models/api_log.py` and endpoint orchestration | Complete |
| Audit every request | Verification endpoint logs success/rejection paths, `vendor_attempts`, `failover_reason`, and has JSONL emergency fallback | Complete |
| PII masking and SHA-256 hashing | `app/security/masking.py`; raw name and ID number are not stored | Complete |
| Required indexes | `app/models/indexes.py`; applied by `scripts/seed.py` | Complete |
| Circuit breaker | Optional bonus | Not implemented |

## Part B — MIS and Analytics

| Requirement | Implementation | Status |
|---|---|---|
| Separate admin key | `X-Admin-Key` decorator in `app/mis/routes.py` | Complete |
| ISO date-range filters | Strict `YYYY-MM-DD` parsing with inclusive `to` date | Complete |
| Usage by client, user, and day | `/api/v1/mis/usage` using MongoDB aggregation | Complete |
| Error-code distribution | `/api/v1/mis/errors` using MongoDB aggregation | Complete |
| TPS metrics | `/api/v1/mis/tps`; peak second and p95 are calculated in MongoDB 7 aggregation | Complete |
| Fallback report | `/api/v1/mis/fallback` | Complete |
| IP security report | `/api/v1/mis/ips`; joins client whitelist and surfaces blocked IPs | Complete |
| CSV export | `format=csv` for usage and errors, including headers for empty results | Complete |

## Part C — Load Demonstration

| Requirement | Implementation | Status |
|---|---|---|
| Mixed traffic from all clients | `scripts/load_test.py` | Complete |
| Non-whitelisted IP traffic | `novahr` load profile intentionally uses a blocked IP | Complete |
| A client exceeds TPS | Eight concurrent Alpha workers send one request/second against the seeded limit of five | Complete |
| Per-client summary | Sent, succeeded, rate-limited, blocked, and other failures | Complete |
| Cross-check MIS after run | Manual verification procedure documented in README | Complete |

## Part D — AI Workflow and Testing

| Requirement | Implementation | Status |
|---|---|---|
| Root `CLAUDE.md` | Present | Complete |
| `docs/AI_WORKFLOW.md` | Includes representative workflow and corrected AI mistake | Complete |
| 10+ meaningful commits | Must be present in the submitted Git repository | **User action required** |
| Required pytest coverage | Direct tests cover API key, IP block, payload validation, TPS, fallback, endpoint auditing, and MIS pipelines | Complete |
| Understand every line | Interview guide and module-level tests support walkthrough preparation | Ongoing review recommended |

## Deliverables

| Deliverable | Status |
|---|---|
| README setup, run, test, seed, load-test instructions | Complete |
| Seed script with clients/users and thousands of logs | Complete |
| Curl examples covering endpoints and failures | Complete |
| Tests | Complete; final automated result recorded during audit |
| Private GitHub repository or ZIP | User submission step |
| Screen recording | Optional; not included |

## Part E — Bonus Deployment

| Bonus | Status |
|---|---|
| Dockerfile and Docker Compose for app + MongoDB | Complete |
| Kubernetes manifests | Not implemented |
| AWS deployment write-up | `docs/DEPLOYMENT.md` | Complete |

## Known limitations to explain in the interview

1. The in-memory TPS limiter is correct only within one application process. Docker therefore runs one Gunicorn worker with multiple threads. Redis is the recommended multi-worker/pod replacement.
2. The emergency JSONL audit fallback is local-process resilience, not a shared distributed audit system.
3. Vendor behavior is simulated and the optional circuit breaker is not implemented.
4. TPS p95 uses MongoDB 7's `$percentile` accumulator; use MongoDB 7+ locally, as configured in Docker Compose.
5. Git commit history cannot be manufactured at packaging time; the submitted repository must retain 10+ meaningful development commits.
