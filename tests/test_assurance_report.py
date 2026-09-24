from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_public_assurance_report_contains_actionable_artifacts():
    r=client.post("/public/assurance/report",json={
        "workflow_name":"Refund Agent","workflow_version":"v42","reliability":0.968,
        "target_reliability":0.95,"critical_failures":0,"human_review_rate":0.08,
        "test_runs":1000,"tool_failures":2,"policy_violations":1,"recovery_rate":0.97,
        "dependency_incidents":0,"identity":True,"authority":True,"provenance":True,
        "deterministic_policy":True,"dependencies_visible":True,"runtime_control":True,
        "degraded_review":True})
    assert r.status_code==200
    body=r.json()
    assert body["report_type"]=="AI Assurance Assessment"
    assert body["release_decision"]["action"] in {"ALLOW","REVIEW","DENY"}
    assert body["findings"]
    assert body["evidence"]
    assert body["remediation"]

def test_playground_has_no_inline_script_or_event_handler():
    text=client.get("/playground.html").text
    assert "<script>" not in text
    assert "onclick=" not in text
    assert "style=" not in text
    assert "playground.js" in text
