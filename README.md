# AI Workflow Qualification

AI Workflow Qualification is a deployment-readiness engine for AI agents performing business workflows.

## Core question

Instead of asking:

"Does this AI agent look good?"

the system asks:

"Does this AI agent meet the reliability and control requirements for this specific workflow?"

## Current qualification signals

- Reliability
- Critical failures
- Tool failures
- Human-review rate
- Latency
- Estimated operating cost
- Configurable deployment thresholds

## Verdicts

QUALIFIED
- Reliability target met
- Critical-failure threshold met
- Human-review threshold met

QUALIFIED_WITH_REVIEW
- Reliability target met but the workflow requires more human review than the configured target

NOT_QUALIFIED
- Reliability target is not met

BLOCKED
- Critical failures exceed the allowed threshold

## Run locally

Windows PowerShell:

python -m venv .venv

.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt

python -m pytest -q

uvicorn app.main:app --reload

Open:

http://127.0.0.1:8000

## API

GET /api/health

GET /api/demo

POST /api/qualify

POST /api/qualify/json

POST /api/qualify/csv

## Deployment

Start command:

uvicorn app.main:app --host 0.0.0.0 --port $PORT

The application is self-contained and does not require a database or API key.

## Product direction

The next commercial layer is an agent execution adapter.

That adapter will allow a customer's actual agent to run qualification cases automatically and send the resulting traces/outcomes into this engine.

The qualification engine should remain deterministic and independent from the customer's model provider.

## Important

This product is an engineering qualification system, not a legal, regulatory, safety, or security certification.


## Production deployment

The recommended production topology is FastAPI + PostgreSQL. Set
`ASSURANCE_DATABASE_URL` to a PostgreSQL connection string. All platform
stores then share the same server-grade database while retaining their
logical table boundaries.

For a local production simulation:

```bash
cp .env.example .env
docker compose -f docker-compose.production.yml --env-file .env up --build
```

Production readiness is exposed at `/api/readiness`; it verifies live database
connectivity rather than checking for local database files.

See `docs/PRODUCTION.md` for secrets, migrations, backup/recovery, and
provider-neutral deployment guidance.
