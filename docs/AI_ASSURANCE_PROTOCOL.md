# AI Assurance Protocol

## Purpose

The AI Assurance Protocol is the machine-readable contract used to exchange AI assurance state between AI systems, platforms, enterprises, and control planes.

## Protocol

- Name: `AI Assurance Protocol`
- Version: `1.0.0`
- Integrity: SHA-256 over canonical JSON

## Core lifecycle

1. Register organization and AI asset.
2. Register an immutable asset version/environment record.
3. Declare dependencies.
4. Submit or generate evaluation evidence.
5. Apply the applicable policy.
6. Issue an assurance record.
7. Persist trust state.
8. Enforce deployment/runtime decisions.
9. Re-evaluate when dependency or assurance-relevant state changes.
10. Export and independently verify a Trust Passport.

## Decisions

| Trust state | Enforcement |
|---|---|
| `ASSURED` | `ALLOW` |
| `DEGRADED` | `REVIEW` |
| `UNKNOWN` | `DENY` |
| `EVALUATING` | `DENY` |
| `STALE` | `DENY` |
| `BLOCKED` | `DENY` |

## Envelope

Protocol messages use:

```json
{
  "protocol": "AI Assurance Protocol",
  "protocol_version": "1.0.0",
  "kind": "...",
  "payload": {},
  "integrity": {
    "algorithm": "SHA-256",
    "content_hash": "..."
  }
}
```

The integrity hash covers the canonical JSON representation of the envelope before the `integrity` field is added.

## Public control-plane API

The unified API is exposed under `/v1/control`.

Authentication uses `X-API-Key` for tenant-scoped operations. Passport verification and the protocol manifest are independently accessible because they are intended for machine-to-machine verification.


## Public discovery

Implementations may discover the protocol manifest at `/.well-known/ai-assurance-protocol.json`. The manifest exposes the protocol version, capabilities, supported trust states, enforcement decisions and public specification/schema paths.
