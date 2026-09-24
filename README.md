# AI Assurance Infrastructure

**Vendor-neutral assurance infrastructure for autonomous AI systems.**

This repository contains the persistent control-plane foundation, AI Assurance Protocol v1, and the public AI Assurance Benchmark v1.

## Inbound developer surface

AAI is designed to be discovered through useful infrastructure rather than cold sales alone. The public surface includes a free assurance scan, benchmark, protocol, failure observatory and GitHub verification action.

- `/public/assurance/report` — structured assurance report API
- `static/assure.html` — public assurance scan
- `static/observatory.html` — reference AI failure observatory
- `integrations/github/action.yml` — CI/CD passport verification

## Public technical surface

- `/public/playground` — interactive reference benchmark
- `/public/protocol` — machine-readable protocol manifest
- `/public/benchmark` — benchmark catalog
- `/public/benchmark/run` — deterministic benchmark execution
- `/v1/control/*` — authenticated control-plane API

## Architecture

`Identity → Authority → Evidence → Policy → Trust → Runtime Control`

The system maintains persistent AI asset identity, versions, dependencies, evidence with SHA-256 provenance, evaluations, policies, decisions, trust states, and audit events.

## Protocol

AI Assurance Protocol v1 defines a vendor-neutral vocabulary for exchanging machine-readable assurance state and control signals. See `protocol/v1/README.md` and `docs/PROTOCOL.md`.

## Benchmark

AI Assurance Benchmark v1 is an experimental, transparent reference suite covering identity, authority, evidence, policy, reliability, failure handling, review escalation, dependency visibility, provenance, and runtime control. See `docs/BENCHMARK.md`.

## Release boundary

AAI is an assurance/control infrastructure product. The protocol and benchmark are interoperability and engineering artifacts; passing the benchmark alone is not a safety, security, compliance, or production certification. Production authorization is determined by the customer's configured policies, controls, evidence, dependencies, evaluations, approvals, and runtime state.

See `docs/CLIENT_DEPLOYMENT.md` for production deployment and customer onboarding.

## VA Health Systems Technology Integrator Profile

Release 13.1 adds a VA-oriented integration profile for RFI 36C10G26Q0087. It is designed to function as AAI's AI assurance/governance component within a broader health-systems integration architecture.

Endpoint surfaces:
- `GET /v1/va-hsti/profile`
- `POST /v1/va-hsti/assess`

The assessment engine covers canonical clinical normalization, X12 transaction normalization, deterministic identity/eligibility/attribution, financial reconciliation, AI validation/monitoring/reversibility/policy evidence, security/ATO readiness, and portable transition evidence. Live VA system access still requires authorized customer-specific adapters and credentials.
