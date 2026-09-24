from __future__ import annotations

import json
import sys
from pathlib import Path


def evaluate_report(report_path: str) -> int:
    path = Path(report_path)

    if not path.exists():
        print(f"ERROR: Report not found: {path}")
        return 2

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Invalid qualification report: {exc}")
        return 2

    verdict = report.get("verdict")

    print()
    print("=" * 60)
    print("AI AGENT RELEASE GATE")
    print("=" * 60)
    print(f"Workflow:          {report.get('workflow_name')}")
    print(f"Reliability:       {report.get('reliability_score', 0):.2f}%")
    print(f"Required:          {report.get('target_reliability', 0):.2f}%")
    print(f"Critical failures: {report.get('critical_failures', 0)}")
    print(f"Human review:      {report.get('human_review_rate', 0):.2f}%")
    print(f"Verdict:           {verdict}")
    print("=" * 60)

    if verdict in {"QUALIFIED", "QUALIFIED_WITH_REVIEW"}:
        print("\nRELEASE ALLOWED")
        return 0

    print("\nRELEASE BLOCKED")

    reasons = report.get("reasons", [])

    for reason in reasons:
        print(f"- {reason}")

    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.release_gate qualification-result.json")
        sys.exit(2)

    sys.exit(evaluate_report(sys.argv[1]))