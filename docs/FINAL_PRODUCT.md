# AI Assurance Infrastructure — Final Product

## Product position

AI Assurance Infrastructure is a vendor-neutral control plane for establishing, computing, verifying and enforcing machine-readable trust for autonomous AI systems.

The product is designed as infrastructure rather than a reporting dashboard. Its durable system of record includes AI asset identity, version lineage, dependencies, evidence, policy, assurance state, provenance, Trust Passports and deployment/runtime decisions.

## Production capabilities

- Tenant-scoped control plane
- Persistent AI asset and version registry
- Dependency and impact graph
- Evidence storage and canonical integrity hashing
- Policy-as-code and scoped policy bindings
- Continuous trust state and transition history
- Deployment and runtime enforcement decisions
- Portable Trust Passports
- Public Passport verification
- AI Assurance Protocol v1
- Protocol conformance validation
- Python SDK and CLI
- GitHub CI integration
- PostgreSQL production path
- Production readiness and health endpoints
- API-key identity with revocation and last-use tracking
- Self-serve commercial billing integration
- Plan entitlements and monthly usage metering
- Stripe Checkout and webhook reconciliation
- Public pricing surface

## Commercial model

The commercial layer supports three plan classes:

- Developer — free protocol adoption
- Growth — production continuous assurance
- Enterprise — custom assurance infrastructure and contractual support

Stripe price IDs are configured through environment variables. No payment credentials are stored in source code.

## Production deployment requirements

Production requires:

1. PostgreSQL through `ASSURANCE_DATABASE_URL`.
2. A strong `ASSURANCE_BOOTSTRAP_KEY` kept outside source control.
3. Explicit `ASSURANCE_CORS_ORIGINS` and `ASSURANCE_TRUSTED_HOSTS`.
4. HTTPS termination.
5. Stripe secrets and price IDs when self-serve billing is enabled.
6. A Stripe webhook pointing at `/v1/billing/webhook` when subscriptions are enabled.
7. Regular database backups and tested restore procedures.

## Strategic objective

The economic objective is to become infrastructure that AI platforms and enterprises depend on for interoperable assurance, rather than a one-off qualification application.

A $10B+ outcome is **not guaranteed by software completeness**. It would require substantial adoption, recurring revenue, ecosystem/network effects, strategic dependence, defensible standards position and a market that values the resulting infrastructure at that scale.
