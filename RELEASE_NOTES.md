# AAI Final Enterprise Build — 12.0.0

This release consolidates the production assurance/control foundation with an independent assessment layer and a redesigned enterprise website.

## Major additions
- Independent evidence-producing enterprise assessment engine
- 16 deterministic enterprise failure scenarios
- Runtime trace ingestion surface
- Authority-drift detection from observed execution
- Sensitive-data egress detection
- AI Bill of Materials output
- Change-impact output and re-assessment signals
- Risk scoring and business-impact context
- Evidence hashes and evidence-root integrity
- Remediation control generation
- SLO/telemetry signal summary
- Enterprise control-plane website shell
- AI estate, assurance, control, runtime, intelligence and evidence views
- Professional platform / solutions / developers / enterprise / trust / legal website structure

## Product boundary
The public assessment is explicitly not a user-entered metric calculator. It derives findings from system contracts and observed traces and makes the evidence chain visible.

## Verification
- `120 passed`
- Public assessment endpoint returns evidence-backed findings and a deterministic decision.
- Existing control-plane, protocol, passport, ecosystem and deployment tests remain green.

## 13.1 — VA HSTI Integration Profile

- Added `va_health_integrator.py`.
- Added VA HSTI profile and assessment API surfaces.
- Added FHIR-style clinical normalization with provenance.
- Added X12 837/835/834/278/270/271 normalization.
- Added deterministic identity conflict handling and eligibility/attribution records.
- Added claim/payment/ledger reconciliation with evidence hashing.
- Added AI validation, monitoring, reversibility, human-oversight, policy and ATO evidence checks.
- Added security/ATO readiness and transition-out portability checks.
- Added dedicated regression tests; full suite: 131 passed.
