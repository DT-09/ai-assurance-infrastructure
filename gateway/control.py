from .approvals import ApprovalStore
from .engine import evaluate_action
from .models import Agent, AgentAction, Decision, DecisionResult


def evaluate_control(
    action: AgentAction,
    agent: Agent,
    approval_store: ApprovalStore | None = None,
) -> DecisionResult:

    if agent.status.value != "ACTIVE":
        return DecisionResult(
            decision=Decision.BLOCK,
            reason=f"Agent is {agent.status.value.lower()}",
            agent_id=action.agent_id,
            tool=action.tool,
            action=action.action,
        )

    if agent.qualification_status != "QUALIFIED":
        return DecisionResult(
            decision=Decision.BLOCK,
            reason=(
                "Agent is not qualified. "
                f"Qualification status: {agent.qualification_status}"
            ),
            agent_id=action.agent_id,
            tool=action.tool,
            action=action.action,
        )

    result = evaluate_action(
        action=action,
        policy=agent.policy,
    )

    if (
        result.decision == Decision.APPROVAL_REQUIRED
        and approval_store is not None
    ):
        approval = approval_store.create(
            action=action,
            reason=result.reason,
        )

        result.approval_id = approval.approval_id

    return result