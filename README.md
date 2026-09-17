# AI Assurance Infrastructure

**Vendor-neutral assurance infrastructure for autonomous AI systems.**

This repository contains the persistent control-plane foundation, AI Assurance Protocol v1, and the public AI Assurance Benchmark v1.

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

## Important status

The protocol and benchmark are **experimental**. They are intended for engineering interoperability and research, not as a safety, security, compliance, or production certification by themselves.
