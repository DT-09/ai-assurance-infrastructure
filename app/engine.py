from typing import List

from .models import (
    Failure,
    QualificationResult,
    Workflow,
)


def qualify_workflow(workflow: Workflow) -> QualificationResult:
    cases = workflow.test_cases

    if not cases:
        return QualificationResult(
            workflow_name=workflow.name,
            total_cases=0,
            successful_cases=0,
            failed_cases=0,
            reliability_score=0,
            critical_failures=0,
            tool_failures=0,
            human_review_cases=0,
            human_review_rate=0,
            average_latency_ms=0,
            total_estimated_cost_usd=0,
            average_cost_per_case_usd=0,
            target_reliability=workflow.target_reliability,
            maximum_critical_failures=workflow.maximum_critical_failures,
            maximum_human_review_rate=workflow.maximum_human_review_rate,
            verdict="NO_DATA",
            reasons=["No test cases were supplied."],
            failures=[],
        )

    total = len(cases)

    successful = sum(
        1 for case in cases
        if case.success
    )

    failed = total - successful

    critical_failures = sum(
        1 for case in cases
        if not case.success and case.critical
    )

    tool_failures = sum(
        1 for case in cases
        if case.tool_error
    )

    human_review_cases = sum(
        1 for case in cases
        if case.human_review_required
    )

    reliability = (
        successful / total
    ) * 100

    human_review_rate = (
        human_review_cases / total
    ) * 100

    average_latency = (
        sum(case.latency_ms for case in cases)
        / total
    )

    total_cost = sum(
        case.estimated_cost_usd
        for case in cases
    )

    average_cost = total_cost / total

    failures: List[Failure] = []

    for case in cases:
        if case.success:
            continue

        if case.tool_error:
            category = "TOOL_FAILURE"
            severity = "CRITICAL" if case.critical else "HIGH"
            message = (
                "The agent failed while interacting with a tool."
            )

        else:
            category = "TASK_FAILURE"
            severity = "CRITICAL" if case.critical else "MEDIUM"
            message = (
                "The agent did not produce the expected successful outcome."
            )

        failures.append(
            Failure(
                case_id=case.case_id,
                category=category,
                severity=severity,
                message=message,
            )
        )

    reasons = []

    if reliability < workflow.target_reliability:
        reasons.append(
            f"Reliability {reliability:.2f}% is below "
            f"the required {workflow.target_reliability:.2f}%."
        )

    if critical_failures > workflow.maximum_critical_failures:
        reasons.append(
            f"{critical_failures} critical failures detected; "
            f"maximum allowed is "
            f"{workflow.maximum_critical_failures}."
        )

    if human_review_rate > workflow.maximum_human_review_rate:
        reasons.append(
            f"Human review rate {human_review_rate:.2f}% exceeds "
            f"the allowed {workflow.maximum_human_review_rate:.2f}%."
        )

    if (
        workflow.maximum_average_latency_ms is not None
        and average_latency > workflow.maximum_average_latency_ms
    ):
        reasons.append(
            f"Average latency {average_latency:.2f} ms exceeds "
            f"the allowed {workflow.maximum_average_latency_ms:.2f} ms."
        )

    if (
        workflow.maximum_average_cost_usd is not None
        and average_cost > workflow.maximum_average_cost_usd
    ):
        reasons.append(
            f"Average cost ${average_cost:.4f} exceeds "
            f"the allowed ${workflow.maximum_average_cost_usd:.4f}."
        )

    if not reasons:
        reasons.append(
            "The workflow satisfied all configured qualification thresholds."
        )

    if (
        reliability >= workflow.target_reliability
        and critical_failures <= workflow.maximum_critical_failures
        and human_review_rate <= workflow.maximum_human_review_rate
        and (
            workflow.maximum_average_latency_ms is None
            or average_latency <= workflow.maximum_average_latency_ms
        )
        and (
            workflow.maximum_average_cost_usd is None
            or average_cost <= workflow.maximum_average_cost_usd
        )
    ):
        verdict = "QUALIFIED"
    elif critical_failures > workflow.maximum_critical_failures:
        verdict = "BLOCKED"
    elif reliability >= workflow.target_reliability:
        verdict = "QUALIFIED_WITH_REVIEW"
    else:
        verdict = "NOT_QUALIFIED"

    return QualificationResult(
        workflow_name=workflow.name,
        total_cases=total,
        successful_cases=successful,
        failed_cases=failed,
        reliability_score=round(reliability, 2),
        critical_failures=critical_failures,
        tool_failures=tool_failures,
        human_review_cases=human_review_cases,
        human_review_rate=round(human_review_rate, 2),
        average_latency_ms=round(average_latency, 2),
        total_estimated_cost_usd=round(total_cost, 4),
        average_cost_per_case_usd=round(average_cost, 4),
        target_reliability=workflow.target_reliability,
        maximum_critical_failures=workflow.maximum_critical_failures,
        maximum_human_review_rate=workflow.maximum_human_review_rate,
        verdict=verdict,
        reasons=reasons,
        failures=failures,
    )
