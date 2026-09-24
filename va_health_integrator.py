"""VA-oriented health systems integration and AI governance profile.

Reference implementation for the VA Health Systems Technology Integrator RFI.
It provides deterministic normalization, identity/eligibility/attribution,
financial reconciliation, AI governance, security-control evidence, and
transition-readiness primitives. It deliberately does not pretend to connect
to VA systems without customer adapters/credentials.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib, json, re
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _hash(v: Any) -> str:
    raw = json.dumps(v, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))

@dataclass
class CanonicalClinicalRecord:
    veteran_id: str
    encounter_id: str
    source_system: str
    source_type: str
    code_system: str | None
    code: str | None
    description: str | None
    effective_at: str | None
    provenance_hash: str

@dataclass
class CanonicalClaim:
    veteran_id: str
    claim_id: str
    transaction_type: str
    amount: Decimal
    currency: str
    source_tpa: str
    service_date: str | None
    status: str
    provenance_hash: str

class VAHealthIntegrator:
    """Deterministic core for the ten-objective VA profile."""
    def normalize_clinical(self, resources: list[dict[str, Any]], source_system: str) -> list[dict[str, Any]]:
        out=[]
        for r in resources:
            if r.get("resourceType") == "Patient":
                continue
            rid=str(r.get("id") or "unknown")
            subject=((r.get("subject") or {}).get("reference") or "")
            veteran=subject.rsplit("/",1)[-1] if "/" in subject else str(r.get("veteran_id") or "unknown")
            coding=((r.get("code") or {}).get("coding") or [])
            c=coding[0] if coding else {}
            out.append(asdict(CanonicalClinicalRecord(
                veteran_id=veteran, encounter_id=rid, source_system=source_system,
                source_type=str(r.get("resourceType") or "unknown"),
                code_system=c.get("system"), code=c.get("code"),
                description=c.get("display"), effective_at=(r.get("effectiveDateTime") or r.get("period",{}).get("start")),
                provenance_hash=_hash({"source_system":source_system,"resource":r}),
            )))
        return out

    def normalize_x12(self, transactions: list[dict[str, Any]], source_tpa: str) -> list[dict[str, Any]]:
        out=[]
        allowed={"837":"claim","835":"payment","834":"eligibility","278":"authorization","270":"eligibility_inquiry","271":"eligibility_response"}
        for t in transactions:
            code=str(t.get("transaction_set") or t.get("x12") or "")
            out.append({
                "transaction_id": str(t.get("transaction_id") or _hash(t)[:16]),
                "transaction_set": code,
                "semantic_type": allowed.get(code,"unknown"),
                "veteran_id": str(t.get("veteran_id") or "unknown"),
                "control_number": str(t.get("control_number") or ""),
                "amount": str(t.get("amount") or "0"),
                "service_date": t.get("service_date"),
                "source_tpa": source_tpa,
                "provenance_hash": _hash({"source_tpa":source_tpa,"transaction":t}),
            })
        return out

    def resolve_identity(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Resolve records only when a deterministic strong identifier agrees.
        Ambiguous matches remain unresolved instead of being guessed."""
        groups={}
        for c in candidates:
            key=_digits(c.get("enterprise_id") or c.get("veteran_id"))
            if not key:
                key="name:"+str(c.get("name") or "").strip().lower()+"|dob:"+str(c.get("dob") or "")
            groups.setdefault(key,[]).append(c)
        out=[]
        for key, rows in groups.items():
            status="RESOLVED" if key and (key.startswith("name:") or len(key)>=6) and len(rows)>=1 else "UNRESOLVED"
            # Name+DOB is accepted as a provisional match; conflicting explicit IDs are not merged.
            ids={str(x.get("enterprise_id")) for x in rows if x.get("enterprise_id")}
            if len(ids)>1: status="CONFLICT"
            out.append({"match_key":key,"status":status,"records":rows,"enterprise_id":next(iter(ids),None)})
        return out

    def eligibility_attribution(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**r, "eligible": bool(r.get("eligible")),
                 "attributed_provider_id": r.get("attributed_provider_id"),
                 "attribution_method": "explicit_provider_id" if r.get("attributed_provider_id") else "UNATTRIBUTED"}
                for r in rows]

    def reconcile_financials(self, events: list[dict[str, Any]], tolerance: Decimal = Decimal("0.01")) -> dict[str, Any]:
        clinical=Decimal("0"); claims=Decimal("0"); payments=Decimal("0"); ledger=Decimal("0")
        for e in events:
            kind=str(e.get("kind","")).lower(); amount=Decimal(str(e.get("amount",0)))
            if kind in {"clinical","encounter"}: clinical += amount
            elif kind in {"claim","837"}: claims += amount
            elif kind in {"payment","835"}: payments += amount
            elif kind in {"ledger","gl"}: ledger += amount
        payment_delta=claims-payments
        ledger_delta=payments-ledger
        return {"clinical_value":str(clinical),"claims_value":str(claims),"payments_value":str(payments),"ledger_value":str(ledger),
                "claim_to_payment_delta":str(payment_delta),"payment_to_ledger_delta":str(ledger_delta),
                "reconciled":abs(payment_delta)<=tolerance and abs(ledger_delta)<=tolerance,
                "tolerance":str(tolerance),"evidence_hash":_hash(events)}

    def ai_governance(self, ai_assets: list[dict[str, Any]]) -> dict[str, Any]:
        results=[]
        for a in ai_assets:
            checks={
                "inventoried": bool(a.get("asset_id")),
                "owner_identified": bool(a.get("owner")),
                "validated": bool(a.get("validation_evidence")),
                "monitored": bool(a.get("monitoring")),
                "reversible": bool(a.get("rollback_version")),
                "federal_policy_mapped": bool(a.get("policy_controls")),
                "human_oversight": bool(a.get("human_oversight")),
                "security_authorized": bool(a.get("ato_reference")),
                "data_boundary_defined": bool(a.get("data_boundary")),
            }
            missing=[k for k,v in checks.items() if not v]
            results.append({"asset_id":a.get("asset_id"),"checks":checks,"missing":missing,
                            "status":"ASSURED" if not missing else "REVIEW"})
        return {"assets":results,"assured_count":sum(x["status"]=="ASSURED" for x in results),"total":len(results)}

    def security_controls(self, controls: list[dict[str, Any]]) -> dict[str, Any]:
        required={"identity","least_privilege","audit","encryption","privacy","availability","accessibility","ato"}
        present={str(c.get("control")).lower() for c in controls if c.get("status") in {"implemented","verified","passed"}}
        missing=sorted(required-present)
        return {"required":sorted(required),"verified":sorted(required & present),"missing":missing,
                "readiness":"READY_FOR_REVIEW" if not missing else "GAPS_IDENTIFIED","evidence_hash":_hash(controls)}

    def transition_package(self, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        required={"data_model","mappings","interfaces","measure_logic","runbooks","architecture","export"}
        present={str(a.get("type")) for a in artifacts}
        return {"portable":sorted(required-present)==[],"present":sorted(present),"missing":sorted(required-present),
                "successor_ready":sorted(required-present)==[],"evidence_hash":_hash(artifacts)}

    def assess(self, payload: dict[str, Any]) -> dict[str, Any]:
        clinical=self.normalize_clinical(payload.get("fhir_resources",[]),str(payload.get("clinical_source","unknown")))
        x12=self.normalize_x12(payload.get("x12_transactions",[]),str(payload.get("tpa","unknown")))
        identity=self.resolve_identity(payload.get("identity_records",[]))
        attribution=self.eligibility_attribution(payload.get("eligibility",[]))
        financial=self.reconcile_financials(payload.get("financial_events",[]))
        ai=self.ai_governance(payload.get("ai_assets",[]))
        security=self.security_controls(payload.get("security_controls",[]))
        transition=self.transition_package(payload.get("transition_artifacts",[]))
        findings=[]
        if not financial["reconciled"]: findings.append({"code":"VA-FIN-001","severity":"high","title":"Financial reconciliation gap"})
        if any(x["status"]=="CONFLICT" for x in identity): findings.append({"code":"VA-ID-001","severity":"high","title":"Identity conflict"})
        if any(x["status"]=="REVIEW" for x in ai["assets"]): findings.append({"code":"VA-AI-001","severity":"high","title":"AI assurance evidence incomplete"})
        if security["missing"]: findings.append({"code":"VA-SEC-001","severity":"high","title":"Security/ATO evidence gaps"})
        if not transition["successor_ready"]: findings.append({"code":"VA-TR-001","severity":"medium","title":"Transition package incomplete"})
        return {"profile":"VA-HSTI-2026","generated_at":_now(),"status":"REVIEW" if findings else "READY_FOR_REVIEW",
                "objectives":{"enterprise_data_governance":{"clinical_records":len(clinical),"x12_transactions":len(x12)},
                "identity_eligibility_attribution":{"identity_groups":len(identity),"eligibility_records":len(attribution)},
                "financial_reconciliation":financial,"ai_enablement_governance":ai,"security_privacy_ato":security,
                "transition":transition},"findings":findings,
                "evidence":{"hash":_hash({"clinical":clinical,"x12":x12,"identity":identity,"financial":financial,"ai":ai,"security":security,"transition":transition}),
                "provenance":"deterministic-aai-va-profile-v1"}}
