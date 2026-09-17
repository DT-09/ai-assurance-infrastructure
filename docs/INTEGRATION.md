# Integration quickstart

The authenticated control-plane API is intended for enterprise integrations. The public benchmark is intentionally unauthenticated so engineers can reproduce the reference methodology before integrating a workspace.

## Public benchmark

```bash
curl https://YOUR-HOST/public/benchmark
```

Run it:

```bash
curl -X POST https://YOUR-HOST/public/benchmark/run \
  -H "Content-Type: application/json" \
  -d '{
    "reliability": 0.98,
    "target_reliability": 0.95,
    "critical_failures": 0,
    "human_review_rate": 0.05,
    "identity": true,
    "authority": true,
    "provenance": true,
    "deterministic_policy": true,
    "dependencies_visible": true,
    "runtime_control": true,
    "degraded_review": true
  }'
```

## Authenticated control plane

Use `X-API-Key` for `/v1/control/*` endpoints. Register an asset, create a version, attach dependencies and evidence, record evaluations, compute trust, and query the resulting control decision.
