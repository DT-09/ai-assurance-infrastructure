# AI Assurance Protocol v1

## What it is

AAP defines a common machine-readable vocabulary for continuous AI assurance. It is designed to sit between AI systems and production control infrastructure without requiring a particular model provider, agent framework, cloud, or observability vendor.

## Assurance object

A conforming implementation should be able to represent:

```json
{
  "asset_id": "ast_example",
  "version": "2.4.1",
  "environment": "production",
  "assurance_state": "ASSURED",
  "evidence": [],
  "dependencies": [],
  "policies": [],
  "provenance": "sha256:...",
  "epoch": 42
}
```

The example is illustrative; implementations may add fields while preserving the core semantics.

## Why a protocol

An assurance layer becomes more useful when independent agents, gateways, evaluators, security systems, and enterprise control planes can exchange the same trust information. The protocol therefore emphasizes stable identifiers, explicit states, provenance, and deterministic control semantics.

## Interoperability goal

A future implementation should be able to consume an assurance object from another implementation without requiring the same model provider or agent framework.
