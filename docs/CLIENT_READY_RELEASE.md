# AAI Client-Ready Revenue Release

## Release

AAI Client-Ready Revenue Build 11.0.0

## Product thesis

AAI is a vendor-neutral AI control and assurance layer for production AI systems. The product connects:

**AI estate → identity → dependency impact → evaluation → evidence → risk → policy → decision → runtime control → incident → remediation → re-assurance.**

The commercial objective is to earn high-value enterprise deployments by becoming an operational dependency around consequential AI systems, rather than selling a benchmark or dashboard alone.

## Product surfaces

- Public enterprise website
- Free Assurance Scan
- Public benchmark / playground
- AI Failure Observatory
- AI Assurance Protocol
- Ecosystem / network surface
- Enterprise Control Plane
- API / SDK / CLI surfaces
- Enterprise deployment architecture
- Security / trust surface
- Commercial / enterprise scope surface
- Privacy / terms placeholders
- Status placeholder

## Website conversion path

1. Public homepage explains the control-plane thesis.
2. Visitor can run a free assurance scan.
3. Visitor can inspect the benchmark and failure observatory.
4. Visitor can read the protocol and developer surfaces.
5. Visitor can inspect the enterprise architecture and security model.
6. Every major path leads to an enterprise assessment CTA.
7. Footer provides platform, solutions, developers, resources, legal and contact links.

## Commercial model

Target enterprise deployments are scoped around:

- criticality of governed AI workflows
- number of AI systems and dependencies
- runtime control depth
- evidence and audit requirements
- integrations
- private/VPC/hybrid deployment requirements
- enterprise identity and security requirements

The target $10K fixed-scope production assurance sprint range is a commercial objective for high-value deployments, not a claim that every deployment currently commands that price.

## Verification

- 118 automated tests passing
- local HTML link audit: zero missing local links across public HTML pages
- release preserves public protocol and benchmark routes
- release preserves the separate control-plane surface

## Production boundary

The Cloudflare Worker deployment currently represents the public static website surface. The full FastAPI control plane remains a separate Python-capable deployment requiring production secrets and PostgreSQL.
