# Production Deployment

## Recommended topology

Run one FastAPI API service against PostgreSQL. The control plane, assurance,
evidence, policy, trust, graph, and identity stores share the same PostgreSQL
database and remain logically separated by table.

## Local production simulation

1. Copy `.env.example` to `.env`.
2. Set strong values for `POSTGRES_PASSWORD` and `ASSURANCE_BOOTSTRAP_KEY`.
3. Run:

```bash
docker compose -f docker-compose.production.yml --env-file .env up --build
```

4. Verify:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/readiness
curl http://localhost:8000/v1/control/protocol/manifest
```

Readiness checks the actual database connection, not the existence of local
SQLite files.

## Database

`ASSURANCE_DATABASE_URL` enables PostgreSQL. When unset, SQLite remains
available for development and single-instance deployments.

The application performs idempotent schema initialization and records a
migration ledger in `schema_migrations`. Future schema changes must be added
as versioned migrations before increasing `MIGRATION_VERSION`.

Run the migration ledger explicitly when needed:

```bash
python -m app.migrations --database-url "$ASSURANCE_DATABASE_URL"
```

## Secrets

Never commit `.env`, database passwords, API keys, or bootstrap credentials.
Inject them through the hosting platform's secret/environment mechanism.

The bootstrap credential should be high entropy and rotated after initial
organization provisioning.

## Backup and recovery

PostgreSQL:

```bash
python scripts/backup.py --database-url "$ASSURANCE_DATABASE_URL"
python scripts/restore.py backups/assurance-YYYYMMDDTHHMMSSZ.dump \
  --database-url "$ASSURANCE_DATABASE_URL"
```

SQLite:

```bash
python scripts/backup.py --sqlite-path data/control_plane.db
python scripts/restore.py backups/assurance-YYYYMMDDTHHMMSSZ.db \
  --sqlite-path data/control_plane.db
```

For real production, schedule PostgreSQL backups at the infrastructure layer,
retain multiple recovery points, and periodically perform a restore drill.

## Operational contract

- `/api/health` = process is serving.
- `/api/readiness` = all persistence dependencies are reachable.
- `X-Request-ID` is generated/propagated for tracing.
- Security headers and production CORS/trusted-host controls are enabled.
- The container runs as a non-root user.
- The container has a healthcheck.
- The API is designed to be horizontally scalable when PostgreSQL is used.

## Deployment

The image is provider-neutral. Any platform capable of running the Docker
image and providing PostgreSQL plus secret injection can host it. Do not
depend on a single cloud vendor's ephemeral filesystem for persistence.
