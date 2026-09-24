# AAI Assurance Assessment

## Purpose

The public benchmark is a deterministic reference mechanism. The commercial assurance product is the assessment package around that mechanism: findings, evidence, remediation, regression context and a release action.

## Assessment inputs

- workflow name, version and environment
- observed reliability and target reliability
- evaluation run count
- critical failures
- tool failures
- policy violations
- recovery rate
- dependency incidents
- identity, authority, provenance, policy, dependency and runtime-control posture
- optional previous score and reliability for regression comparison

## Assessment outputs

- benchmark control coverage
- assurance state: `ASSURED`, `DEGRADED`, or `BLOCKED`
- release action: `ALLOW`, `REVIEW`, or `DENY`
- severity-ranked findings
- remediation guidance
- scenario-level evidence records with provenance metadata
- category summary
- regression deltas when a baseline is supplied
- machine-readable JSON report
- explicit limitations

## Boundary

The reference benchmark evaluates supplied observable inputs. It is not a universal safety, security, compliance or production certification. Production customer assessments must use customer-specific workflows, expected behavior, policies, test cases, dependencies and evidence sources.
