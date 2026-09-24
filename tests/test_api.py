import os
from pathlib import Path
os.environ["AAI_DB_PATH"] = "/tmp/aai_v6_api_test.db"
os.environ["AAI_API_KEY"] = "aai_test_master_key"
from fastapi.testclient import TestClient
from app.main import app


def test_health_and_readiness():
    c=TestClient(app); assert c.get("/api/health").status_code==200; assert c.get("/api/readiness").json()["status"]=="ready"

def test_auth_scopes():
    c=TestClient(app); assert c.get("/v1/control/assets").status_code==401; assert c.get("/v1/control/assets",headers={"X-API-Key":"aai_test_master_key"}).status_code==200

def test_asset_evaluation_and_decision():
    c=TestClient(app); h={"X-API-Key":"aai_test_master_key","Idempotency-Key":"asset-001"}
    r=c.post("/v1/control/assets",headers=h,json={"name":"Checkout Agent","criticality":"high"}); assert r.status_code==201; a=r.json();
    assert c.post("/v1/control/assets",headers=h,json={"name":"Checkout Agent","criticality":"high"}).json()["id"]==a["id"]
    r=c.post("/v1/control/evaluations",headers={"X-API-Key":"aai_test_master_key"},json={"asset_id":a["id"],"reliability":0.99,"critical_failures":0,"human_review_rate":0.01}); assert r.status_code==201
    d=c.post("/v1/control/decisions",headers={"X-API-Key":"aai_test_master_key"},json={"asset_id":a["id"],"action":"execute","context":{}}); assert d.json()["decision"]=="ALLOW"

def test_tenant_bootstrap():
    c=TestClient(app); r=c.post("/v1/control/organizations/bootstrap",headers={"X-Bootstrap-Key":"local-bootstrap-key"},json={"name":"Example Enterprise"}); assert r.status_code==201; assert r.json()["credential"]["api_key"].startswith("aai_")
