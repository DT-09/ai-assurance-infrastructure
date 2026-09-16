from app.store import Store
from app.models import AssetCreate, VersionCreate, DependencyCreate, EvidenceCreate, EvaluationCreate, PolicyCreate
from app.services.trust import TrustEngine
from app.services.graph import DependencyGraph
from app.services.policy import PolicyEngine


def make_store(tmp_path): return Store(tmp_path / "test.db")

def test_persistent_asset_and_version(tmp_path):
    s=make_store(tmp_path); a=s.create_asset("org_local",AssetCreate(name="Agent A",criticality="high")); v=s.create_version("org_local",a["id"],VersionCreate(version="1.0")); s2=Store(tmp_path/"test.db")
    assert s2.get_asset("org_local",a["id"])["name"]=="Agent A"; assert s2.get_version("org_local",v["id"])["version"]=="1.0"

def test_evidence_chain_and_verification(tmp_path):
    s=make_store(tmp_path); a=s.create_asset("org_local",AssetCreate(name="Agent A"))
    e=s.add_evidence("org_local",EvidenceCreate(asset_id=a["id"],evidence_type="reliability",source="test",result="pass",payload={"cases":10}))
    assert len(e["provenance_hash"])==64; assert s.get_evidence("org_local",e["id"])["provenance_hash"]==e["provenance_hash"]
    from app.services.evidence import EvidenceService
    assert EvidenceService(s).verify(e)["valid"]

def test_trust_states(tmp_path):
    s=make_store(tmp_path); t=TrustEngine(s); a=s.create_asset("org_local",AssetCreate(name="Agent A"))
    s.add_evaluation("org_local",EvaluationCreate(asset_id=a["id"],reliability=.99,critical_failures=0,human_review_rate=.01)); x=t.compute("org_local",a["id"])
    assert x["state"]=="ASSURED"; s.add_evidence("org_local",EvidenceCreate(asset_id=a["id"],evidence_type="security",source="test",result="fail")); y=t.compute("org_local",a["id"])
    assert y["state"]=="BLOCKED" and y["epoch"]==2

def test_dependency_impact(tmp_path):
    s=make_store(tmp_path); g=DependencyGraph(s); a=s.create_asset("org_local",AssetCreate(name="A")); b=s.create_asset("org_local",AssetCreate(name="B"))
    s.add_dependency("org_local",DependencyCreate(source_asset_id=b["id"],target_ref=a["id"],criticality="critical")); assert any(x["asset_id"]==b["id"] for x in g.impact("org_local",a["id"]))

def test_policy_decision(tmp_path):
    s=make_store(tmp_path); t=TrustEngine(s); p=PolicyEngine(s); a=s.create_asset("org_local",AssetCreate(name="A")); s.add_evaluation("org_local",EvaluationCreate(asset_id=a["id"],reliability=.99)); t.compute("org_local",a["id"]); d=p.decide("org_local",a["id"],"execute",{})
    assert d["decision"]=="ALLOW"

def test_audit_chain(tmp_path):
    s=make_store(tmp_path); a=s.create_asset("org_local",AssetCreate(name="A")); s.create_version("org_local",a["id"],VersionCreate(version="1")); assert s.verify_audit_chain("org_local")["valid"]

def test_api_key_is_scoped(tmp_path):
    s=make_store(tmp_path); org=s.create_organization("Tenant"); key=s.create_api_key(org["id"]); identity=s.authenticate(key["api_key"])
    assert identity["organization_id"]==org["id"] and "control:write" in identity["scopes"]
