from .models import AgentAction, Policy


def evaluate_policy(action: AgentAction, policy: Policy) -> tuple[str, str]:
    if action.tool in policy.blocked_tools:
        return "BLOCK", f"Tool '{action.tool}' is explicitly blocked"

    if action.tool not in policy.allowed_tools:
        return "BLOCK", f"Tool '{action.tool}' is not allowed"

    if action.action in policy.blocked_actions:
        return "BLOCK", f"Action '{action.action}' is explicitly blocked"

    if action.action in policy.approval_actions:
        return "APPROVAL_REQUIRED", (
            f"Action '{action.action}' requires human approval"
        )

    if action.tool in policy.approval_tools:
        return "APPROVAL_REQUIRED", (
            f"Tool '{action.tool}' requires human approval"
        )

    if policy.max_transaction_usd is not None:
        amount = action.parameters.get("amount_usd")

        if amount is not None and amount > policy.max_transaction_usd:
            return "APPROVAL_REQUIRED", (
                f"Transaction amount ${amount:.2f} exceeds "
                f"autonomous limit of ${policy.max_transaction_usd:.2f}"
            )

    return "ALLOW", "Action satisfies policy"
