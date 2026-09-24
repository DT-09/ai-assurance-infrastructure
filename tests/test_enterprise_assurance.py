from app.assurance.enterprise import run_assessment


def test_assessment_does_not_trust_submitted_metrics():
    result = run_assessment({
        "system": {"system_id": "agent-1", "name": "Support Agent", "version": "2", "environment": "prod", "business_criticality": "high"},
        "contract": {"permissions": ["write"], "allowed_actions": ["refund"], "tools": ["crm"], "data_classes": ["PII"]},
        "metrics": {"reliability": 1.0},
        "traces": [],
    })
    assert result["decision"] in {"BLOCKED", "REVIEW"}
    assert result["finding_count"] > 0
    assert result["evidence_root"]


def test_observed_authority_drift_creates_critical_finding():
    result = run_assessment({
        "system": {"system_id": "agent-2", "version": "1", "environment": "prod"},
        "contract": {"allowed_actions": ["refund"], "least_privilege": True, "egress_controls": True},
        "traces": [{"trace_id": "t1", "timestamp": "2026-09-22T00:00:00Z", "action": "delete_customer"}],
        "scenario_ids": ["AUTH-001"],
    })
    assert any(f["code"] == "OBS-AUTH-DRIFT" for f in result["findings"])
    assert result["decision"] == "BLOCKED"
