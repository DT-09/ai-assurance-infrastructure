# AI Assurance Protocol v1

AI Assurance Protocol (AAP) is a vendor-neutral machine-readable contract for representing the identity, authority, evidence, policy, dependencies, assurance state, and control decision of an AI system.

## Core lifecycle

`REGISTER → DECLARE → OBSERVE → EVALUATE → ASSURE → CONTROL → RECOMPUTE`

## Core resources

- Asset
- Version
- Dependency
- Evidence
- Evaluation
- Trust state
- Policy
- Decision
- Trust Passport

## Assurance states

- `ASSURED`: current signals satisfy the configured control thresholds.
- `DEGRADED`: the system remains observable but requires review or has non-critical assurance degradation.
- `BLOCKED`: a critical failure or failed evidence condition prevents execution under the default control policy.

## Control decisions

- `ALLOW`
- `REVIEW`
- `DENY`

## Design requirements

1. Every assurance result is tied to an identifiable AI asset.
2. Evidence must be attributable to a source and protected by provenance metadata.
3. Policy decisions must be deterministic for identical inputs.
4. Trust state is persistent and changes as new evidence/evaluations arrive.
5. Protocol implementations remain vendor-neutral and machine-readable.

This specification is experimental and intended for interoperability and research until independently reviewed.
