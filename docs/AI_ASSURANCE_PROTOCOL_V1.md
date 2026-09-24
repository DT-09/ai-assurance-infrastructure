# AI Assurance Protocol v1.0.0

## Status

Version 1.0.0. Machine-readable, vendor-neutral protocol for exchanging AI identity, assurance evidence, trust state and enforcement decisions.

## Design goals

1. **Portable identity** — identify an AI asset and exact version independent of provider or framework.
2. **Evidence binding** — connect claims to evidence and provenance.
3. **Deterministic trust** — represent an explicit state derived from policy and evidence.
4. **Operational control** — make deployment/runtime decisions consumable by enforcement points.
5. **Independent verification** — permit a verifier to validate message integrity without trusting the originating UI.

## Envelope

```json
{
  "protocol": "AI Assurance Protocol",
  "protocol_version": "1.0.0",
  "kind": "assurance.state",
  "payload": {},
  "integrity": {
    "algorithm": "SHA-256",
    "content_hash": "..."
  }
}
```

The `content_hash` is SHA-256 over the canonical JSON representation of the envelope containing `protocol`, `protocol_version`, `kind`, and `payload`, before the `integrity` member is added.

Canonical JSON uses sorted object keys, compact separators, UTF-8 encoding and no insignificant whitespace.

## Core kinds

- `identity.asset`
- `identity.version`
- `dependency.declaration`
- `evidence.record`
- `assurance.evaluation`
- `assurance.state`
- `enforcement.decision`
- `passport.issue`
- `passport.verify`

Implementations may introduce extension kinds using a reverse-domain or organization namespace.

## Trust states

| State | Operational meaning | Default enforcement |
|---|---|---|
| `ASSURED` | Required assurance conditions are satisfied | `ALLOW` |
| `DEGRADED` | Assurance is below preferred posture but may be reviewable | `REVIEW` |
| `BLOCKED` | A blocking policy condition exists | `DENY` |
| `UNKNOWN` | Assurance cannot be established | `DENY` |
| `EVALUATING` | Evaluation is in progress | `DENY` |
| `STALE` | Previously valid assurance is no longer current | `DENY` |

## Verification requirements

A verifier MUST:

1. confirm `protocol` and `protocol_version` are supported;
2. validate the envelope schema;
3. reconstruct the canonical pre-integrity body;
4. calculate SHA-256 over its UTF-8 bytes;
5. compare the calculated digest with `integrity.content_hash` using a constant-time comparison where supported;
6. reject the message on any mismatch.

## Security considerations

Protocol integrity does not by itself establish authorization, authenticity of the originating organization, correctness of evidence, or safety of the AI system. Implementations SHOULD combine protocol verification with authenticated transport, issuer identity, policy evaluation, provenance and appropriate authorization controls.

## Compatibility

Version 1.x implementations MUST preserve the semantics of the v1 envelope. Breaking changes require a new protocol major version.
