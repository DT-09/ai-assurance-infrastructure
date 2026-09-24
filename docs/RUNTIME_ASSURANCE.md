# AAI Runtime Assurance

AAI's runtime assurance layer is an enforcement system, not a reporting-only assessment.

## Runtime contract

A consequential AI action is evaluated at the action boundary:

`Agent -> AAI Gateway -> Authority/Policy -> ALLOW | APPROVAL_REQUIRED | BLOCK -> Tool/API`

The gateway evaluates:

- agent lifecycle and qualification state
- tool authorization
- action authorization
- target boundaries
- data-classification boundaries
- transaction limits
- human-approval requirements
- risk thresholds

Every evaluation produces an evidence record containing the observed action, authority version, decision, controls evaluated, timestamp and SHA-256 evidence hash.

## Independent assurance

`POST /api/agents/{agent_id}/assurance` executes a deterministic adversarial reference suite against the registered authority boundary. It attempts:

- unauthorized tool use
- sensitive-data boundary crossing
- excessive transaction authority
- blocked consequential actions
- unauthorized targets
- injected instructions attempting privileged actions

The result reports blocked actions, approval-required actions, escaped controls and a root evidence hash.

This is a reference assurance suite. Production customers should extend it with environment-specific scenarios and connectors.

## Evidence

`GET /api/evidence` lists evidence for the authenticated organization.

`GET /api/evidence/{evidence_id}` retrieves a single evidence record.

## Why this matters

The commercial unit is no longer a report generated from customer-entered metrics. The gateway can sit on a consequential action path and enforce the customer's authority boundary while retaining machine-verifiable evidence of the decision.

## Deployment

The production compose file includes the AAI API and a dedicated gateway service. For a customer deployment, place the gateway between the agent runtime and the consequential tools/APIs. Keep the API/control plane as the system of record for assets, policies, trust, dependencies and evidence.

The gateway currently uses SQLite for its local enforcement state in the reference deployment. Enterprise deployments should replace or back it with the customer's durable database/event infrastructure before production scale.
