# AI-Assisted Development Workflow

VeriGate was developed iteratively with AI assistance and human review. The project was divided into small, testable concerns: configuration, data contracts, masking, authentication, request validation, IP whitelisting, rate limiting, vendor fallback, verification orchestration, MIS pipelines, scripts, Docker, and documentation.

## Representative prompts used

1. **Authentication tests:** “Create focused pytest coverage for missing and invalid API keys, inactive clients, repository failures, and a successful protected request. Do not change unrelated application behavior.”
2. **Verification schema:** “Implement an immutable request model for `client_ref_id`, `id_type`, `id_number`, and `name`; reject unknown fields and unsafe coercion; generate direct unit tests.”
3. **Validation assumptions:** “Add documented PAN, DL, voter-ID, client-reference, and Unicode-name validation without inventing evaluator-hostile rules.”
4. **IP security:** “Build framework-independent client-IP extraction and exact whitelist matching using `ipaddress`, including XFF chains and IPv6 normalization.”
5. **TPS limiter:** “Implement a thread-safe rolling one-second, per-client limiter and document why it is process-local.”
6. **Vendor fallback:** “Simulate a configurable primary vendor and automatic fallback, with deterministic dependency injection for tests.”
7. **MIS analytics:** “Use MongoDB aggregation pipelines for usage, errors, TPS, fallback, and IP reports; add CSV export for usage and errors.”
8. **Final audit:** “Compare every assignment requirement with the codebase, add missing route and pipeline tests, and correct mismatches without adding speculative bonus features.”

## Examples where AI output was wrong or incomplete

An early AI-generated change created `tests/test_auth.py` but left it empty. The issue was caught by checking test collection rather than trusting the filename. The file was replaced with explicit authentication-path tests.

A later broad implementation had utility tests but no direct tests for `POST /api/v1/verify` or the MIS routes. The final audit added route-level tests for primary success, fallback success, not-verified results, API-key/user/IP/payload/TPS failures, vendor failure, audit behavior, admin authentication, date validation, CSV output, and aggregation pipeline structure.

The final audit also caught a logic bug: a fallback vendor response with `verified=false` was labeled `VP2001`. The correct code is `VP2002` for any processed-but-not-verified result, regardless of vendor source. A regression test now covers this case.

Another correction involved `X-Forwarded-For`. The assignment permits it for localhost testing, but blindly trusting it in production permits spoofing. The final code accepts XFF only in explicit development mode or when the immediate peer is a configured trusted proxy.

## Human ownership

Approximate origin of the implementation:

- 70% AI-generated first drafts
- 30% human-directed architecture, requirement interpretation, corrections, integration decisions, and review

These percentages describe drafting effort, not responsibility. Every file was reviewed, the full automated test suite was run after integration, and ambiguous validation choices were recorded in `docs/ASSUMPTIONS.md`.
