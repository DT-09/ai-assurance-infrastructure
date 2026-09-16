# Release 6.0.0 — Enterprise Hardening Foundation

## This release adds
- PostgreSQL-capable durable persistence through SQLAlchemy.
- Tenant-scoped organizations and API credentials.
- Scoped API-key authorization.
- Idempotent write handling.
- Durable outbox boundary for event streaming.
- Hash-chained evidence provenance and audit verification.
- Persistent trust epochs and state hashes.
- Signed Trust Passports.
- Production-mode secret/default checks.
- Docker deployment with PostgreSQL.
- Expanded SDK and automated test coverage.

## Explicitly not faked
The release does not pretend to provide SSO, KMS, Kafka, Kubernetes, runtime sidecars, HA, DR, SOC 2, ISO certification, or external AI-provider integrations when those systems have not actually been deployed and validated. Those capabilities require real infrastructure and operational evidence.
