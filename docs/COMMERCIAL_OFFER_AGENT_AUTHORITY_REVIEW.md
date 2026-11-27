# Commercial Offer: AI Agent Authority Review

## Buyer

AI automation agencies and B2B software companies that operate tool-using agents in customer-support, order-management, CRM or internal operations workflows.

The buyer is the person accountable for releasing or operating the agent: founder/CTO, head of engineering, AI lead or delivery director.

Do not target hobby projects, demos, agents without tool access, or regulated/high-impact workflows as an initial market.

## Trigger events

- An agent is moving from staging to production.
- A model, prompt, tool, permission or policy has changed.
- A customer or internal reviewer has questioned what the agent can access or execute.
- The team has observed an unexpected tool call, approval bypass, data-boundary issue or failed escalation.
- An agency must provide evidence before handing an agent to a client.

## The problem we sell against

The buyer has a declared authority boundary but cannot easily establish whether observed execution traces stayed inside it. Reviewing traces manually is slow and inconsistent. AAI compares the declared contract with supplied traces and identifies observable deviations such as unauthorized actions/tools, missing approval evidence, data-class boundary violations, unexpected destinations and transaction-limit breaches.

## Entry offer: 60-minute Authority Review

**Proposed price: US$179 fixed fee.** This is a test price, benchmarked against a publicly advertised US$179 one-hour AI-agent architecture session. It is not yet validated by an AAI customer transaction.

Scope:
- One agent
- One version
- One declared authority contract
- Up to 500 sanitized execution traces
- One review session of 60 minutes
- One machine-readable report and prioritized remediation list

Buyer supplies, before the session:
- Sanitized JSON traces
- Tool/action allow-list and denied actions
- Data classes and allowed destinations
- Approval-required actions and any transaction thresholds
- Version/change context

Deliverables:
1. Deterministic report with decision state and evidence root.
2. Findings linked to the supplied trace evidence.
3. Authority graph derived from the contract.
4. Prioritized remediation actions.
5. Explicit limitations and missing evidence.

The fee buys an evidence review and interpretation, not a guarantee that no failure exists.

## Expansion offer

After a successful first review, offer a scoped release-regression engagement for the same agent across a defined set of versions and scenarios. Quote only after the first review establishes trace volume, release frequency and required coverage. Do not promise continuous monitoring until a production integration is implemented and tested.

## Recurrence

A repeat review is justified when the buyer changes the model, prompt, tools, identity, permissions, policy or workflow, or when new execution evidence arrives. Do not sell an automatic monthly subscription to a buyer whose agent does not change or generate enough new evidence.

## Acceptance criteria

A paid review is complete only when:
- Input files are sanitized and authorized for review.
- The report is generated from the supplied contract and traces.
- Every finding includes its evidence reference and remediation.
- The buyer receives the report and a 60-minute walkthrough.
- The buyer confirms whether the findings changed a release or remediation decision.

## Exclusions

- No penetration test or adversarial execution is performed by the CLI.
- No certification, compliance attestation, legal opinion or security guarantee.
- No access to production systems, credentials or live customer data.
- No autonomous production changes.
- No healthcare, financial decisioning, employment, education or other high-impact deployment assessments in the initial offer.
- No claims of recovered money or prevented incidents unless independently verified.

## Commercial gates

1. First 3 paid reviews: validate the exact scope, time and report usefulness.
2. At least 2 buyers must identify a concrete decision or remediation caused by the findings.
3. At least 1 buyer must pay for a second review or release-regression engagement.
4. If these gates fail, revise the segment or stop the offer. Do not respond by building more features.
