from decimal import Decimal
from va_health_integrator import VAHealthIntegrator

def test_fhir_and_x12_normalization():
    x=VAHealthIntegrator()
    clinical=x.normalize_clinical([{"resourceType":"Observation","id":"o1","subject":{"reference":"Patient/V123"},"code":{"coding":[{"system":"loinc","code":"1234","display":"Test"}]}}],"Oracle Health")
    assert clinical[0]["veteran_id"]=="V123"
    tx=x.normalize_x12([{"transaction_set":"837","claim_id":"c1","amount":"12.00"}],"TPA")
    assert tx[0]["semantic_type"]=="claim"

def test_financial_reconciliation():
    r=VAHealthIntegrator().reconcile_financials([{"kind":"claim","amount":"100"},{"kind":"payment","amount":"100"},{"kind":"ledger","amount":"100"}])
    assert r["reconciled"] is True

def test_ai_governance_requires_real_evidence():
    r=VAHealthIntegrator().ai_governance([{"asset_id":"a1","owner":"team","validation_evidence":True,"monitoring":True,"rollback_version":"v0","policy_controls":["p1"],"human_oversight":True,"ato_reference":"ato","data_boundary":"internal"}])
    assert r["assured_count"]==1

def test_full_profile_flags_gaps_without_false_assurance():
    r=VAHealthIntegrator().assess({"financial_events":[{"kind":"claim","amount":"10"},{"kind":"payment","amount":"9"}],"ai_assets":[{"asset_id":"a1"}],"security_controls":[],"transition_artifacts":[]})
    assert r["status"]=="REVIEW"
    assert {f["code"] for f in r["findings"]} >= {"VA-FIN-001","VA-AI-001","VA-SEC-001","VA-TR-001"}
