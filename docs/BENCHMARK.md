# AI Assurance Benchmark v1

The benchmark is a transparent reference suite for continuous assurance controls in AI workflows.

## Categories

1. Identity
2. Authority
3. Evidence
4. Policy
5. Reliability
6. Failure handling
7. Review escalation
8. Dependency visibility
9. Provenance
10. Runtime control

## Scoring

Each scenario carries equal weight in v1. A scenario passes only when its observable input satisfies the published criterion. The aggregate score is the proportion of passed scenarios.

The benchmark does **not** certify an AI system as safe or suitable for production. It is an engineering reference suite and should be supplemented by domain-specific security, safety, privacy, compliance, and operational testing.

## Reproducibility

The public endpoint accepts declarative inputs and returns the scenario-level failures, score, and resulting assurance state. This makes the reference result independently reproducible.
