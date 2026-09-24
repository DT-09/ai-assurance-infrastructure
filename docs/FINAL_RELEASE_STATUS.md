# AI Assurance Infrastructure — Final Software Release

Release: 6.0.0

## Release status

The repository is complete as a production-deployable software package. The final local gate covers application behavior, control-plane lifecycle, tenant isolation, assurance, passport verification, protocol integrity, security middleware, static console delivery, and Python compilation.

## Verification

- 100 automated tests passed
- 0 test warnings in the release gate
- `python -m compileall app sdk gateway` passed
- production configuration rejects production startup without PostgreSQL
- static console CSS/JS are served from the FastAPI application
- strict same-origin CSP is compatible with the console
- obsolete AI Workflow Qualification backup UI removed from the release
- local database files are excluded from the distributable release

## Production deployment contract

Production requires:

- PostgreSQL via `ASSURANCE_DATABASE_URL`
- operator-managed `ASSURANCE_BOOTSTRAP_KEY`
- explicit CORS origins
- explicit trusted hosts
- TLS termination at the deployment boundary
- persistent PostgreSQL storage with organizational backup/recovery controls

`docker-compose.production.yml` provides the reference PostgreSQL + API deployment topology.

## Commercial boundary

This release establishes the software asset and deployment foundation. A $10B+ enterprise value is not a property that can be guaranteed by source code. It must be established through market adoption, recurring revenue, ecosystem/protocol adoption, strategic integrations, security assurance, and durable customer dependence.

## 8.1.0 control-plane hardening

The final control-plane pass consolidates the operational model around a single asset context. The console now follows the lifecycle from inventory through evidence, trust, policy and enforcement. Persistent policy bindings replace the earlier process-local compatibility binding. The API exposes a unified control-plane snapshot and workspace overview, and deployment checks now honor explicit deployment controls rather than looking only at the latest trust state.

Validation: **114 automated tests passing** and Python compilation completed successfully.
