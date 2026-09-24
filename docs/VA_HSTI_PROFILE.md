# VA Health Systems Technology Integrator Profile

AAI includes a deterministic VA-oriented integration profile aligned to RFI 36C10G26Q0087's ten draft objectives. It is a **capability component**, not a claim that AAI alone replaces a full health-systems integrator.

## Implemented reference capabilities

1. Enterprise canonical clinical normalization with provenance.
2. X12 transaction normalization for 837/835/834/278/270/271.
3. Deterministic Veteran identity resolution with conflict preservation.
4. Eligibility and provider attribution records.
5. Claim/payment/general-ledger reconciliation with explicit deltas and evidence hashes.
6. AI inventory, validation, monitoring, reversibility, human oversight, policy mapping and ATO evidence checks.
7. Security/privacy/ATO readiness evidence model.
8. Portable transition-out artifact checklist and successor-readiness state.
9. A single evidence-backed assessment package covering the above domains.

## Integration boundary

Customer-specific adapters are still required for live VA/VHA systems, EHRs, TPA feeds, financial platforms, identity providers and network/security infrastructure. AAI does not claim to connect to VA systems without authorized interfaces and credentials.

## Why this profile exists

AAI's role in a broader VA integrator architecture is the AI assurance, governance, evidence, monitoring and control layer. It can sit beside the enterprise integration/data layer and continuously determine whether AI systems remain validated, monitored, authorized, reversible and policy-compliant.

## RFI alignment

The profile is designed around Objectives 1–10 in the draft SOO, with deepest native coverage for Objective 7 (AI Enablement and Governance), and supporting primitives for Objectives 1, 2, 3, 4, 5, 6, 9 and 10.
