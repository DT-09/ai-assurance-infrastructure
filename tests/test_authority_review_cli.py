import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "authority_review.py"
FIXTURE = ROOT / "examples" / "authority_review_input.json"


def test_synthetic_review_reports_authority_drift_and_evidence():
    result = subprocess.run(
        [sys.executable, str(CLI), str(FIXTURE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assessment = report["assessment"]
    codes = {finding["code"] for finding in assessment["findings"]}
    assert "OBS-AUTH-DRIFT" in codes
    assert "OBS-HITL-BYPASS" in codes
    assert "OBS-SENSITIVE-EGRESS" in codes
    assert assessment["decision"] == "DENY"
    assert len(assessment["evidence"]) >= 2
    assert assessment["evidence_root"]
    assert all(item["execution"] == "NOT_RUN" for item in report["attack_coverage_plan"])


def test_invalid_input_fails_without_creating_a_report(tmp_path):
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps({"asset_id": "", "traces": []}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), str(source)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "asset_id is required" in result.stderr
    assert result.stdout == ""
