# AAI Final Enterprise Build

## Product boundary
AAI is an AI control and assurance infrastructure layer. It is not a benchmark form that converts user-entered metrics into a pass/fail label.

## Independent assessment engine
The enterprise assessment surface derives findings from:
- AI system identity and version
- declared authority, tools and data boundaries
- observed execution traces
- material dependency/configuration changes
- executable policy declarations

The engine records evidence hashes, findings, remediation controls, risk, scenario coverage, AIBOM components, change impact and a final assurance decision.

Public reference endpoint:
- `POST /public/assurance/assessment`

Authenticated enterprise endpoint:
- `POST /v1/assurance/assessment`

Runtime evidence ingestion:
- `POST /v1/runtime/traces`

Scenario catalog:
- `GET /public/assurance/scenarios`

## Enterprise capability map

### P0 — production-critical
- AI estate discovery and durable identity
- authority/dependency graph
- observed execution trace ingestion
- adversarial and failure-mode assessment
- evidence/provenance
- policy and risk evaluation
- deployment and runtime control
- continuous re-assurance
- incident/remediation lifecycle
- enterprise integration surfaces

### P1 — strategic value
- AI Bill of Materials / supply-chain inventory
- change impact analysis
- compliance evidence mapping
- human approval / four-eyes workflows
- executive risk intelligence
- model/vendor switching assurance
- cost and reliability SLO signals
- agent-to-agent authority controls
- sensitive-data boundary controls

### P2 — ecosystem expansion
- third-party evaluator marketplace
- policy and compliance packs
- protocol-based assurance exchange
- external conformance and verification network

## Product principle
The final control decision is only the actuator:

`Decision → Policy → Requirement → Finding → Test → Observed behavior → Trace → Asset/version → Dependency → Evidence`

## Website
The public website and control plane use a single design system with separate surfaces for:
- platform
- solutions
- developers
- enterprise
- intelligence
- trust/security
- protocol
- benchmark/assessment
- control plane
- legal and company pages

The site is intentionally positioned as enterprise infrastructure rather than a casual AI tool landing page.
