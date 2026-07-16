# curl Examples

## Health
`curl http://localhost:5000/health`

## Verify success
```bash
curl -X POST http://localhost:5000/api/v1/verify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: alpha-key" \
  -H "X-User-Id: al_ops_01" \
  -H "X-Forwarded-For: 103.24.10.5" \
  -d '{"client_ref_id":"ALB-2026-000123","id_type":"PAN","id_number":"ABCDE1234F","name":"Rahul Sharma"}'
```

## Invalid API key
Use `X-API-Key: wrong-key` with the verification request.

## Blocked IP
Use `X-Forwarded-For: 198.51.100.99` with Alpha Bank.

## Payload failure
Remove `id_number` or send an unsupported `id_type`.

## MIS usage
```bash
curl "http://localhost:5000/api/v1/mis/usage?from=2026-07-01&to=2026-07-31&group_by=client" -H "X-Admin-Key: local-admin-key"
```

## MIS errors CSV
```bash
curl -OJ "http://localhost:5000/api/v1/mis/errors?from=2026-07-01&to=2026-07-31&format=csv" -H "X-Admin-Key: local-admin-key"
```
