# OrderFlow — Day 1

A Cloud/DevOps portfolio project for simulated orders and payments.

## Environment
Windows editor and PowerShell, Docker Desktop running Linux containers.
No host Python or separate Ubuntu distribution is required.

## Quick start
Generate a random API key of at least 32 characters and put it in a local `.env` file:

```text
ORDERFLOW_API_KEY=<generated-secret>
```

```powershell
docker compose up --build -d
docker compose run --rm --no-deps api python -m pytest -q
```

Open http://localhost:8000/docs and authorize with the local API key.
Stop the environment with `docker compose down`.

## Endpoints
- GET /health/live: public process health.
- GET /health/ready: public readiness for the current in-memory implementation.
- POST /api/v1/orders: X-API-Key and Idempotency-Key required.
- GET /api/v1/orders/{order_id}: X-API-Key required.

## Behavior
Amounts are integers in USD cents. A new order is PENDING.
Replaying the same key and validated payload returns the existing order (200).
Reusing the key with another payload returns 409. New orders return 201.
Tests use FastAPI TestClient and do not need a live API server.

## Limitations
- In-memory storage is lost on reload/restart.
- Only one application process is supported.
- No database, payment worker, AWS integration or rate limiting yet.
- One shared API key; no per-customer authorization.
- Development image runs as root and contains test dependencies.
- Environment-variable secrets are a local-development compromise, not production secret management.
- Dependencies use ranges; create and validate a lockfile before CI reproducibility claims.
- Localhost only. Do not expose this version publicly.

## Next milestone
PostgreSQL persistence, database uniqueness constraints and transactional outbox.
