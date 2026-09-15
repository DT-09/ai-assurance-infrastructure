# AI Assurance Infrastructure

**Production AI assurance control plane, protocol and trust infrastructure.**

# AI Assurance Infrastructure

AI Assurance Infrastructure is a vendor-neutral control plane for autonomous AI systems. It provides identity, asset/version registration, dependency intelligence, evidence, policy evaluation, continuous trust state, provenance, assurance passports, and enforcement decisions through APIs and SDKs.

## Product boundary

The platform is designed to answer and enforce four machine-level questions:

1. **Who is this AI system?**
2. **What is it allowed to do?**
3. **What evidence supports its current trust state?**
4. **Should it be allowed to operate right now?**

The core system is intentionally vendor-neutral: model providers, agent frameworks, tool vendors, clouds, and deployment environments can integrate through the control-plane API, SDK, and assurance protocol.

## Architecture

```text
Agent / Model / Tool
        │
        ▼
   Identity + Registry
        │
        ▼
 Dependency / Authority Graph
        │
        ▼
 Evidence + Provenance
        │
        ▼
 Continuous Evaluation
        │
        ▼
 Policy Engine → Trust State
        │              │
        ▼              ▼
 Deployment / Runtime Enforcement
        │
        ▼
 Machine-verifiable Assurance Passport
```

## Production status

This repository is a release-complete software foundation, with PostgreSQL support, tenant-scoped API-key authentication, production middleware, migrations ledger, backup/restore scripts, Docker deployment configuration, an assurance protocol, SDKs, and automated tests.

**Important:** a $10B valuation or acquisition is not something software can guarantee. Commercial value must be established by production adoption, recurring revenue, ecosystem integration, standards adoption, and strategic dependence. This repository is engineered toward that category; it does not represent a valuation claim.

## Quick start

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Production

Set `ASSURANCE_ENV=production` and provide a PostgreSQL URL through `ASSURANCE_DATABASE_URL`. Production configuration rejects a missing PostgreSQL URL.

```text
ASSURANCE_ENV=production
ASSURANCE_DATABASE_URL=postgresql://...
ASSURANCE_BOOTSTRAP_KEY=<strong-secret>
```

See:
- `docs/PRODUCTION.md`
- `docs/CONTROL_PLANE_API.md`
- `docs/AI_ASSURANCE_PROTOCOL.md`
- `docs/PRODUCT_SPEC.md`
- `docs/SECURITY_MODEL.md`

## Core APIs

- `/api/health` — liveness
- `/api/readiness` — dependency/database readiness
- `/v1/control/health` — control-plane liveness
- `/v1/control/protocol/manifest` — protocol manifest
- `/v1/control/organizations/bootstrap` — tenant bootstrap
- `/v1/control/assets` — AI asset registry
- `/v1/control/assets/{asset_id}/versions` — immutable asset versions
- `/v1/control/assets/{asset_id}/dependencies` — dependency graph
- `/v1/control/assets/{asset_id}/assure` — assurance evaluation
- `/v1/control/assets/{asset_id}/trust` — current trust state
- `/v1/control/assets/{asset_id}/passport` — assurance passport
- `/v1/control/assets/{asset_id}/provenance` — evidence lineage
- `/v1/control/assets/{asset_id}/verify` — passport/evidence verification

## Engineering quality

The current repository test suite passes with **72 tests** in the validated local build. Run `python -m pytest -q` after any environment or dependency change.


## Final product

See [`docs/FINAL_PRODUCT.md`](docs/FINAL_PRODUCT.md) for the production, protocol and commercial capability boundary. The repository is intended to be deployed as one product; intermediate development archives are not part of the product distribution.
