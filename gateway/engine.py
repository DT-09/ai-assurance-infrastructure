from .models import AgentAction, Decision, DecisionResult, Policy
from .policy import evaluate_policy
from .risk import calculate_risk_score


def evaluate_action(
    action: AgentAction,
    policy: Policy,
) -> DecisionResult:
    decision, reason = evaluate_policy(action, policy)
    risk_score = calculate_risk_score(action, policy)

    return DecisionResult(
        decision=Decision(decision),
        reason=reason,
        agent_id=action.agent_id,
        tool=action.tool,
        action=action.action,
        risk_score=risk_score,
    )