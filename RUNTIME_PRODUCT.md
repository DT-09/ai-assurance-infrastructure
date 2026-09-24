# AAI Runtime Control Product

AAI's runtime product is an enforcement boundary, not a post-hoc report generator.

## Execution contract

`Agent -> AAI -> ALLOW / REQUIRE_APPROVAL / BLOCK -> Tool`

The customer defines an authority contract for an exact agent version. Every consequential action is represented as an action envelope and evaluated against that contract before the tool is called.

### Authority dimensions

- agent identity and exact version
- action allow/deny list
- tool allow-list
- data classifications
- external destination boundaries
- autonomous transaction limit
- approval-required actions
- operating environment and purpose

## API

- `POST /v1/runtime/contracts`
- `GET /v1/runtime/contracts/{agent_id}/{version}`
- `POST /v1/runtime/agent-authorize`
- `POST /v1/runtime/approve/{decision_id}`
- `GET /v1/runtime/agent-decisions`
- `POST /v1/runtime/attack-plan`

The existing `/v1/runtime/authorize` asset/policy endpoint remains backward compatible.

## Integration pattern

Use the AAI SDK or call `agent-authorize` before invoking the customer's real tool adapter. AAI deliberately does not accept arbitrary remote URLs and execute them on the customer's behalf.

The server also contains a deterministic local demo execution path for `demo_payments` and `demo_crm` so the enforcement behavior can be demonstrated without external credentials.

## What is now independently enforced

1. Unknown agent/version -> BLOCK
2. Undeclared action -> BLOCK
3. Undeclared tool -> BLOCK
4. Explicitly denied action -> BLOCK
5. Data outside declared boundary -> BLOCK
6. External destination outside boundary -> BLOCK
7. Amount above autonomous limit -> BLOCK
8. Consequential action requiring human approval -> REQUIRE_APPROVAL
9. Approved action -> ALLOW
10. Every decision receives a canonical SHA-256 evidence hash and is persisted in SQLite.

## Attack-path generation

AAI derives attack paths from the actual authority contract instead of showing a fixed generic benchmark list. Current paths include payment authority escalation, sensitive-data egress, CRM boundary crossing, approval bypass and undeclared action expansion.

## Important boundary

This release makes the enforcement core real and executable. A production customer still has to route its actual tool/API calls through the AAI integration boundary; AAI cannot magically intercept a system it is not connected to. The next customer integration work is adapter-specific: OpenTelemetry, API gateway, MCP, Kubernetes, model-provider SDKs and enterprise identity.
