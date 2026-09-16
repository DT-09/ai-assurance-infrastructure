# AI Assurance Infrastructure — Production Foundation v6

This release turns the Assurance Core into a durable, tenant-scoped control-plane foundation.

## Implemented

- Durable SQLAlchemy persistence with SQLite WAL locally and PostgreSQL for hosted deployments.
- Organization/tenant isolation at the persistence and API layers.
- Hashed, scoped API keys plus an environment master key for controlled bootstrap/local operation.
- Idempotency keys for safe retry of write requests.
- Hash-chained evidence provenance.
- Hash-chained audit log with verification endpoint.
- Durable outbox events for downstream event-bus integration.
- Persistent trust epochs and trust-state hashes.
- Dependency impact analysis.
- Policy decisions: ALLOW / REVIEW / DENY.
- Signed Trust Passport using HMAC-SHA256.
- Versioned vendor-neutral protocol manifest and schema.
- Python SDK covering the control-plane primitives.
- FastAPI OpenAPI surface, readiness and request IDs.
- Docker + PostgreSQL deployment foundation.
- Automated core/API tests.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
$env:AAI_API_KEY="aai_local_development_key"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` for the control plane and `/docs` for the API contract.

## Production configuration

Set `AAI_ENVIRONMENT=production`, a PostgreSQL `AAI_DATABASE_URL`, a long random `AAI_API_KEY`, `AAI_BOOTSTRAP_KEY`, and `AAI_SIGNING_SECRET`. Never ship the development defaults.

## Architecture

```text
AI SYSTEM
  -> IDENTITY / REGISTRY
  -> VERSION STATE
  -> DEPENDENCY GRAPH
  -> EVIDENCE FABRIC
  -> ASSURANCE ENGINE
  -> TRUST STATE
  -> POLICY ENGINE
  -> CONTROL DECISION
  -> AUDIT + OUTBOX
  -> TRUST PASSPORT
  -> ASSURANCE PROTOCOL
```

The next enterprise-hardening layer should add external identity federation, managed secrets/KMS, a real event bus/worker fleet, distributed runtime enforcement, observability/SLOs, HA/DR, formal protocol governance, signed key rotation, and production integrations. Those are deliberately separate infrastructure concerns rather than fake implementations hidden behind the UI.
