AI ASSURANCE INFRASTRUCTURE — CLIENT-READY REVENUE BUILD 11.0.0

PRODUCT
AAI is a vendor-neutral AI control and assurance layer for production AI systems.

Core loop:
AI estate -> identity -> dependency impact -> evaluation -> evidence -> risk -> policy -> decision -> runtime control -> incident -> remediation -> re-assurance.

LOCAL RUN
1. Create/activate a Python 3.11+ environment.
2. Install dependencies: pip install -e ".[dev]"
3. Start: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
4. Open: http://127.0.0.1:8000/

PUBLIC WEBSITE
/                       enterprise website
/solutions.html         solutions
/developers.html        developer platform
/enterprise.html        enterprise architecture
/pricing.html           commercial scope
/security.html          trust and security
/company.html           company
/status.html            service status surface
/privacy.html           privacy placeholder
/terms.html             terms placeholder
/ecosystem.html         ecosystem website
/protocol.html          protocol website
/playground.html        public benchmark/playground
/observatory.html       failure observatory
/assure.html            free assurance scan

CONTROL PLANE
/console                enterprise control plane

API / PROTOCOL
/api/health
/api/readiness
/protocol.json
/protocol/v1/schema.json
/.well-known/ai-assurance-protocol.json
/public/ecosystem/*

DEPLOYMENT
The static directory can be deployed as Worker assets using wrangler.jsonc.
The full FastAPI control plane requires a Python-capable runtime, production secrets and PostgreSQL for production/staging.

VERIFICATION
118 pytest tests passing.
Public HTML link audit: zero missing local links.

COMMERCIAL NOTE
The $10K fixed-scope production assurance sprint range is a target enterprise deployment band for high-value control-plane engagements. It is not a guaranteed market price. The product is designed to earn this value through operational dependency: AI estate inventory, policy, evidence, runtime control, continuous assurance and enterprise deployment.

SEE ALSO
docs/CLIENT_READY_RELEASE.md
docs/CONTROL_PLANE_ARCHITECTURE.md
docs/FINAL_PRODUCT.md
docs/PRODUCTION.md
docs/SECURITY_MODEL.md
