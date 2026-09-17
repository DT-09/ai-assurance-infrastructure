# Release 5.0.0 — AI Assurance Infrastructure

## Verified release additions

- Public AI Assurance Protocol reference surface.
- Public AI Assurance Benchmark v1 catalog and deterministic execution API.
- Public interactive assurance playground.
- Vendor-neutral machine-readable protocol schema extended with optional assurance fields while preserving the core protocol contract.
- Persistent control-plane, assurance, evidence, dependency, policy, trust, passport, enforcement, billing and enterprise foundations retained.
- Production PostgreSQL deployment path retained.
- Security, identity, audit, provenance and tenant-isolation controls retained.

## Public endpoints

- `/public` — public technical entry point
- `/public/playground` — interactive benchmark
- `/public/protocol` — public protocol manifest
- `/public/benchmark` — benchmark catalog
- `/public/benchmark/run` — deterministic benchmark execution
- `/protocol` — protocol documentation surface
- `/protocol.json` — machine-readable protocol manifest
- `/protocol/v1/schema.json` — protocol schema
- `/.well-known/ai-assurance-protocol.json` — protocol discovery

## Verification

- 101 automated tests passed.
- `python -m compileall -q app sdk gateway` passed.
- Public protocol and benchmark endpoints return successfully.
- Existing control-plane regression suite remains green.

## Strategic boundary

Software completeness does not guarantee a $10B+ valuation or acquisition. Strategic value must be established through real deployments, customer adoption, recurring revenue, ecosystem/protocol adoption, security evidence, integrations, and durable dependence.
