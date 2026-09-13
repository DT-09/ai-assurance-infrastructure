from app.models import QualificationResult

from gateway.control import evaluate_control
from gateway.engine import evaluate_action
from gateway.models import AgentAction, Decision, Policy


def test_allowed_action():
    action = AgentAction(
        agent_id="support-agent",
        tool="crm",
        action="read",
    )

    policy = Policy(
        allowed_tools=["crm"],
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.ALLOW


def test_blocked_tool():
    action = AgentAction(
        agent_id="support-agent",
        tool="database",
        action="delete",
    )

    policy = Policy(
        allowed_tools=["crm"],
        blocked_tools=["database"],
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.BLOCK


def test_human_approval_for_sensitive_action():
    action = AgentAction(
        agent_id="sales-agent",
        tool="refund",
        action="create",
        parameters={"amount_usd": 500},
    )

    policy = Policy(
        allowed_tools=["refund"],
        approval_tools=["refund"],
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.APPROVAL_REQUIRED


def test_transaction_limit():
    action = AgentAction(
        agent_id="sales-agent",
        tool="payment",
        action="charge",
        parameters={"amount_usd": 5000},
    )

    policy = Policy(
        allowed_tools=["payment"],
        max_transaction_usd=1000,
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.APPROVAL_REQUIRED


def make_qualification(verdict: str) -> QualificationResult:
    return QualificationResult(
        workflow_name="Test Agent",
        total_cases=10,
        successful_cases=10 if verdict == "QUALIFIED" else 5,
        failed_cases=0 if verdict == "QUALIFIED" else 5,
        reliability_score=100 if verdict == "QUALIFIED" else 50,
        critical_failures=0,
        tool_failures=0,
        human_review_cases=0,
        human_review_rate=0,
        average_latency_ms=100,
        total_estimated_cost_usd=1,
        average_cost_per_case_usd=0.1,
        target_reliability=95,
        maximum_critical_failures=0,
        maximum_human_review_rate=20,
        verdict=verdict,
        reasons=["test"],
        failures=[],
    )


def test_unqualified_agent_is_blocked():
    action = AgentAction(
        agent_id="untrusted-agent",
        tool="crm",
        action="read",
    )

    policy = Policy(
        allowed_tools=["crm"],
    )

    result = evaluate_control(
        action=action,
        policy=policy,
        qualification=make_qualification("NOT_QUALIFIED"),
    )

    assert result.decision == Decision.BLOCK


def test_qualified_agent_reaches_gateway():
    action = AgentAction(
        agent_id="trusted-agent",
        tool="crm",
        action="read",
    )

    policy = Policy(
        allowed_tools=["crm"],
    )

    result = evaluate_control(
        action=action,
        policy=policy,
        qualification=make_qualification("QUALIFIED"),
    )

    assert result.decision == Decision.ALLOW