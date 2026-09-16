# Protocol v1 Conformance

AI Assurance Protocol v1 is designed to be independently implementable. A conforming implementation must preserve the protocol name/version, canonical JSON integrity semantics, supported trust states, and machine-verifiable passport integrity.

## Local verification

```bash
python -m cli.aai protocol
python -m cli.aai verify path/to/passport.json
python -m cli.aai conformance path/to/protocol-document.json
```

## GitHub Actions

Use the composite action from `integrations/github/action.yml` to make passport verification a CI gate.

## Compatibility

Implementations should reject malformed or tampered integrity data rather than silently accepting it. Additional metadata may be carried in protocol payloads, but required protocol fields must remain compatible with the v1 schema.

## Public verification API

`POST /v1/verify/passport` verifies a passport without an API key.

`POST /v1/protocol/conformance` validates a Protocol v1 envelope and, for `passport.issue`, validates the embedded passport integrity.

These endpoints are intentionally vendor-neutral: a verifier does not need an account with the issuing control plane to check cryptographic integrity.
