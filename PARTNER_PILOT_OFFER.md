# AAI Partner Pilot — AI Agent Authority Evaluation

**Purpose:** give an AI consultancy a bounded, reproducible way to evaluate whether one designated agent workflow respects declared tool, action, data, destination, transaction, and human-approval limits.

This is an evaluation service and reusable test harness—not a claim that the platform can secure an agent that is not routed through its enforcement boundary.

## Buyer

An AI implementation consultancy or agent-development studio that deploys customer-support, CRM, or payment-adjacent agents and needs demonstrable controls before a customer handover.

## One-workflow scope

For one named agent workflow and one agreed authority contract:

1. Map the permitted actions, tools, data classes, destinations, transaction limit, and approval-required actions.
2. Run a deterministic baseline suite covering permitted action, approval required, approval granted, over-limit transaction, undeclared tool, denied action, excess data classification, external destination, and unknown agent/version.
3. Export expected-versus-observed decisions, decision identifiers, evidence hashes, limitations, and remediation recommendations.
4. Hold a findings review and provide a retest result after one agreed policy adjustment.

## Deliverables

- Scope and authority-contract sheet
- Test matrix with explicit expected results
- Machine-readable JSON results and evidence hashes
- Findings summary and prioritized remediation notes
- Retest record for one agreed change

## Commercial proposal

**Initial partner evaluation: US$250 fixed fee** for the synthetic demonstration and one bounded evaluation session, with no customer data required for the initial demonstration. A customer-specific assessment requires written scope and explicit authorization before any data is accessed.

This is a proposed pilot price, not a validated market rate. If the partner intends to resell the assessment, agree the end-client price, delivery responsibilities, and revenue split in writing before work begins. No unpaid custom integration or open-ended development is included.

## Acceptance criteria

The pilot is complete when:
- all agreed fixture cases execute;
- observed decisions are compared with the agreed expected decisions;
- mismatches and limitations are documented;
- the partner receives the evidence package and review;
- both sides record whether the result is useful enough to repeat.

No claim of complete security, regulatory compliance, certification, or guaranteed prevention is made.

## Required before customer-specific work

- Written authorization from the workflow owner
- Agreed test environment and prohibited actions
- No real payments, outbound messages, destructive writes, or production side effects during initial testing
- Data minimization and retention/deletion terms
- Written fee, payment date, acceptance criteria, IP and reuse terms

## Why a partner might buy

The partner can use the same bounded assessment structure across client engagements instead of assembling a new checklist and evidence report each time. That is only commercially valuable if it reduces delivery time, uncovers material control gaps, or helps the partner win/retain client work. The pilot must measure this; it should not be assumed.

## Stop conditions

Do not expand into a subscription or connector build unless the partner identifies a repeated workflow, demonstrates a measurable gap versus its existing checks, and commits to a second paid use or a documented customer pipeline.
