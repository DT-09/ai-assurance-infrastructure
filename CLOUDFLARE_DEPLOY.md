# AAI Cloudflare deployment

This release fixes the production website/API split.

## Deploy

From this directory:

```powershell
npm.cmd install
npx.cmd wrangler login
npx.cmd wrangler deploy
```

The Worker now serves the existing `static/` website through the `ASSETS` binding and handles:

- `GET /api/health`
- `GET /api/assurance/scenarios`
- `POST /api/assurance/report`
- `POST /api/contact`

## Verify after deployment

```powershell
$base = "https://YOUR-WORKER.workers.dev"

Invoke-WebRequest "$base/api/health"

$body = @{
  system = @{
    system_id = "customer-support-agent"
    version = "2.4.1"
    environment = "production"
    business_criticality = "high"
  }
  contract = @{
    allowed_actions = @("refund","escalate")
    tools = @("crm","payments")
    data_classes = @("PII","financial")
    permissions = @("write")
    least_privilege = $false
    egress_controls = $false
    dependency_attestation = $false
    adversarial_testing = $false
    change_reassessment = $false
  }
  traces = @(
    @{
      trace_id = "t-001"
      timestamp = (Get-Date).ToUniversalTime().ToString("o")
      action = "refund"
      tool = "payments"
      status = "ok"
      data_classification = "PII"
    }
  )
  changes = @("payments-tool@4.2")
} | ConvertTo-Json -Depth 10

Invoke-RestMethod "$base/api/assurance/report" -Method Post -ContentType "application/json" -Body $body
```

The returned object must contain `assessment_id`, `decision`, `findings`, `evidence`, `controls`, and `evidence_root`.

## Contact

The contact form validates the submission through `/api/contact` and then opens a pre-populated email handoff. It does not silently pretend that an email was delivered. WhatsApp and direct email are also provided on the contact page.

For true server-side lead storage/email delivery, connect a transactional email provider or D1/Queues later; this release deliberately does not invent an unconfigured provider.
