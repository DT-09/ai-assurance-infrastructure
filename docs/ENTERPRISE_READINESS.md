# Enterprise readiness

This repository contains the product architecture and implementation surface for enterprise operation. The following are implemented in code: tenant-scoped persistence, scoped credentials, idempotency, evidence/audit chains, durable outbox, trust passports, runtime authorization, deployment controls, OIDC verification, SAML verification hook, SCIM provisioning, provider adapters, metrics/SLO collection, PostgreSQL deployment, Kubernetes HA primitives, backup automation, and recovery runbooks.

Operational prerequisites cannot be manufactured by software. Before a customer calls the service production-ready, the operator must provision a managed PostgreSQL HA cluster, external KMS/HSM, enterprise IdP, TLS, monitoring/alerting, backups, restore drills, and an event sink. Those are environment facts, not source-code features.

Likewise, customer references and production evidence must come from real customers. The repository includes a signed/evidence model and a template, but it deliberately does not fabricate references.
