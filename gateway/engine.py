from .models import AgentAction, Decision, DecisionResult, Policy
from .policy import evaluate_policy


def evaluate_action(action: AgentAction, policy: Policy) -> DecisionResult:
    decision, reason = evaluate_policy(action, policy)

    return DecisionResult(
        decision=Decision(decision),
        reason=reason,
        agent_id=action.agent_id,
        tool=action.tool,
        action=action.action,
    )
