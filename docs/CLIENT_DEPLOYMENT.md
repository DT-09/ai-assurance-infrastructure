# AAI Client Deployment

## Production prerequisites

- PostgreSQL 14+ (16 recommended)
- TLS termination at the edge/load balancer
- External KMS/HSM-backed signing secret management
- AAI API and control-plane hostnames
- Customer identity provider when SSO is enabled
- Durable backups and tested restore procedure

AAI production/staging startup rejects SQLite, development credentials, and the built-in HMAC KMS mode.

## Environment

Set at minimum:

```text
AAI_ENVIRONMENT=production
AAI_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB
AAI_API_KEY=<long-random-admin-or-bootstrap-credential>
AAI_BOOTSTRAP_KEY=<long-random-bootstrap-credential>
AAI_SIGNING_SECRET=<external-secret-reference-or-long-random-secret>
AAI_KMS_PROVIDER=<external-provider>
AAI_CORS_ORIGINS=https://console.example.com
AAI_TRUSTED_HOSTS=api.example.com
AAI_TLS_TERMINATED=true
```

Do not commit real credentials or `.env` files.

## Start with Docker Compose

1. Create production secrets in the deployment environment.
2. Set `POSTGRES_PASSWORD`, `AAI_BOOTSTRAP_KEY`, and the other `AAI_*` variables required by the environment.
3. Start the stack:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

4. Verify:

```bash
curl https://api.example.com/api/health
curl https://api.example.com/api/readiness
```

5. Confirm the API reports `production` and `postgresql`.

## Customer onboarding

1. Create the customer organization.
2. Issue a scoped API credential or configure SSO.
3. Register the customer's AI systems.
4. Register versions and dependencies.
5. Bind policies and deployment controls.
6. Run assurance.
7. Review findings and approvals.
8. Run the deployment check.
9. Enable runtime authorization and monitoring.
10. Export/verify the assurance passport and evidence package.

## Operational boundary

The public website/protocol/benchmark surfaces are intentionally separate from authenticated customer control-plane data. Customer assets, evidence, policies, runtime decisions, and audit records require authenticated control-plane access.

## Pre-sale demonstration

Use the public protocol and benchmark pages for unauthenticated demonstrations. For a real customer assessment, use a dedicated customer deployment rather than relying on the reference/demo UI state.
