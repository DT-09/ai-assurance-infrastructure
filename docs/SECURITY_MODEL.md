# Security Model

## Threat model
The platform assumes AI systems may be compromised, misconfigured, changed without review, or connected to tools/data with excessive authority.

## Security boundaries
- Organizations are isolated by authenticated API-key identity.
- Bootstrap credentials are separate from tenant credentials.
- API keys are stored as salted PBKDF2-HMAC-SHA256 hashes.
- Production requires PostgreSQL for shared state.
- Remote qualification rejects non-global/private endpoint addresses.
- HTTP security headers and trusted-host/CORS controls are configurable.
- Assurance evidence is canonically hashed for integrity verification.
- Assurance passports include machine-verifiable evidence/provenance material.

## Enforcement semantics
`ASSURED → ALLOW`, `DEGRADED → REVIEW`, `BLOCKED/UNKNOWN → DENY` unless an explicit policy overrides the default action.

## Operational requirements
Production deployments should use TLS, secret management, database backups, least-privilege database roles, centralized logs, alerting, key rotation, and tested recovery procedures.

This document describes engineering controls and is not a legal, regulatory, or security certification.
