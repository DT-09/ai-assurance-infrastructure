from app.models import QualificationResult

from .engine import evaluate_action
from .models import AgentAction, Decision, DecisionResult, Policy


def evaluate_control(
    action: AgentAction,
    policy: Policy,
    qualification: QualificationResult,
) -> DecisionResult:
    if qualification.verdict != "QUALIFIED":
        return DecisionResult(
            decision=Decision.BLOCK,
            reason=(
                f"Agent is not qualified. "
                f"Qualification verdict: {qualification.verdict}"
            ),
            agent_id=action.agent_id,
            tool=action.tool,
            action=action.action,
        )

    return evaluate_action(action, policy)
