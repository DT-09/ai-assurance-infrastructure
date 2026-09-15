import json
import sys

from app.demo_agent import refund_agent
from app.runner import AgentRunner, ExecutionCase


def run_demo() -> int:
    cases = [
        ExecutionCase(
            case_id="REF-001",
            input_data="Customer received a damaged product",
            expected_output="REFUND_APPROVED",
        ),
        ExecutionCase(
            case_id="REF-002",
            input_data="Customer was charged twice",
            expected_output="REFUND_APPROVED",
        ),
        ExecutionCase(
            case_id="REF-003",
            input_data="Request is outside policy",
            expected_output="REFUND_DENIED",
        ),
        ExecutionCase(
            case_id="REF-004",
            input_data="unknown policy request",
            expected_output="REFUND_APPROVED",
            critical=True,
        ),
    ]

    runner = AgentRunner(refund_agent)

    result = runner.run(
        workflow_name="Refund Agent",
        cases=cases,
        target_reliability=95.0,
        maximum_critical_failures=0,
        maximum_human_review_rate=20.0,
    )

    print()
    print("=" * 60)
    print("AI WORKFLOW QUALIFICATION")
    print("=" * 60)
    print(f"Workflow:             {result.workflow_name}")
    print(f"Reliability:          {result.reliability_score:.1f}%")
    print(f"Required:             {result.target_reliability:.1f}%")
    print(f"Critical failures:    {result.critical_failures}")
    print(f"Tool failures:        {result.tool_failures}")
    print(f"Human review rate:    {result.human_review_rate:.1f}%")
    print(f"Average latency:      {result.average_latency_ms:.2f} ms")
    print(f"Verdict:              {result.verdict}")
    print("=" * 60)

    if result.reasons:
        print("\nBLOCKING REASONS:")
        for reason in result.reasons:
            print(f"- {reason}")

    with open("qualification-result.json", "w", encoding="utf-8") as file:
        json.dump(result.model_dump(), file, indent=2)

    print("\nReport written to qualification-result.json")

    if result.verdict in {"QUALIFIED", "QUALIFIED_WITH_REVIEW"}:
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(run_demo())