# Security baseline

1. Production mode refuses development API/signing defaults.
2. API keys are stored as SHA-256 hashes; the raw key is returned only at creation.
3. API scopes separate read and write control-plane operations.
4. Tenant identity is derived from the authenticated credential and applied to every data query.
5. Evidence and audit records use deterministic canonical JSON plus SHA-256 hash chaining.
6. Write endpoints support `Idempotency-Key` to prevent duplicate side effects on retries.
7. Every response receives an `X-Request-ID` for trace correlation.
8. Trust Passports carry an integrity signature.

For production deployment, put the service behind TLS, use a managed PostgreSQL service, keep secrets in a managed secret store/KMS, rotate credentials, restrict network ingress, enable centralized logs/metrics/traces, and establish backups plus restore drills.
