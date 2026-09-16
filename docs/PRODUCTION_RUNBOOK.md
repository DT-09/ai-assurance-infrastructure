# Production Runbook

## Required production controls

- PostgreSQL 16/17 with Multi-AZ/HA, automated backups, point-in-time recovery and tested restores.
- External KMS/HSM for signing keys. Do not use the development HMAC provider in production.
- TLS at the ingress/load balancer; mTLS for high-trust service-to-service deployments.
- OIDC/SAML through the enterprise identity provider; SCIM for lifecycle provisioning.
- At least three API replicas, PDB, autoscaling and rolling deployment.
- Durable outbox worker connected to the organization's event bus or webhook sink.
- Centralized logs, metrics and traces; alerting on SLO burn rate.
- Quarterly disaster-recovery restore test and documented RPO/RTO.

## RPO/RTO targets

Default target: RPO <= 5 minutes, RTO <= 30 minutes. These are service objectives, not claims about an actual deployment until the operator measures them.

## Key rotation

Rotate KMS signing keys according to the enterprise KMS policy. Passport verification must retain public-key history so previously issued records remain verifiable.

## Deployment gate

Every deployment/change should call `/v1/runtime/authorize` for the affected asset and refuse deployment when the returned decision is `DENY`.

## Customer evidence

Use `docs/PRODUCTION_EVIDENCE_TEMPLATE.md` for real customer evidence. Never substitute synthetic traffic, screenshots or internal tests for customer references.
