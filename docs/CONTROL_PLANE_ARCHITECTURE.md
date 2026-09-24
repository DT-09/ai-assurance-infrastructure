# AI Assurance Control Plane — Architecture

## Purpose

The Control Plane is the authoritative operating layer between AI systems and deployment/runtime authority. It is not a dashboard over disconnected services.

```text
AI systems / models / agents / workflows
                |
                v
        [ Identity Registry ]
                |
        versions + environments
                |
                v
        [ Dependency Graph ]
                |
                v
        [ Evidence Fabric ] <--- evaluations / attestations / provenance
                |
                v
        [ Trust Engine ]
                |
                v
        [ Policy Layer ] <--- workspace + environment policy bindings
                |
                v
        [ Decision Engine ]
          /             \
         v               v
   deployment          runtime
     gates             authority
          \             /
           v           v
             [ Audit ]
                |
             [ Outbox ]
```

## Control-plane invariants

1. **Tenant isolation:** every customer-owned read/write is scoped by organization identity.
2. **Identity first:** an asset is the root object for evidence, evaluations, dependencies, trust and decisions.
3. **Version awareness:** evidence and deployment checks can reference an exact asset version.
4. **Trust is the safety floor:** missing or blocked trust cannot become an ALLOW decision through policy.
5. **Policy is explicit:** policies are persisted and can be bound to an asset and environment.
6. **Decisions are durable:** deployment/runtime decisions are stored and audited.
7. **Audit is tamper-evident:** events form a per-organization cryptographic chain.
8. **Integration is asynchronous:** the outbox is the durable boundary for future event transport.
9. **Protocol is separate from implementation:** public protocol artifacts remain portable and vendor-neutral.
10. **Control is explainable:** decisions return the trust state, policy context and reasons used to reach the result.

## Primary API surfaces

- `/v1/control/assets` — registry
- `/v1/control/assets/{asset_id}/control-plane` — unified asset control view
- `/v1/control/graph` — dependency topology
- `/v1/control/evidence` — evidence ingestion and verification
- `/v1/control/evaluations` — evaluation records
- `/v1/control/policies` — policy lifecycle
- `/v1/control/policies/bind` — persistent policy bindings
- `/v1/runtime/authorize` — runtime authority decision
- `/v1/control/assets/{asset_id}/versions/{version_id}/deployment-check` — deployment gate
- `/v1/control/audit` and `/v1/control/audit/verify` — audit evidence
- `/v1/control/overview` — single operational control-plane snapshot
- `/public/protocol` — public interoperability contract

## UI model

The console mirrors the architecture instead of exposing implementation modules as unrelated pages:

**Command center → AI registry → Control decisions → Dependency graph → Evidence fabric → Policy layer → Audit → Protocol**

Selecting an asset makes that asset the working context for trust, evidence, policy and enforcement views.
