from .models import AgentAction, Policy


def calculate_risk_score(
    action: AgentAction,
    policy: Policy,
) -> float:
    score = 0.0

    # Unknown tools are high risk.
    if action.tool not in policy.allowed_tools:
        score += 50

    # Explicitly blocked tools are maximum risk.
    if action.tool in policy.blocked_tools:
        score += 50

    # Sensitive actions increase risk.
    sensitive_actions = {
        "delete",
        "refund",
        "charge",
        "transfer",
        "withdraw",
        "send",
        "publish",
    }

    if action.action in sensitive_actions:
        score += 25

    # Financial actions receive additional risk.
    amount = action.parameters.get("amount_usd")

    if isinstance(amount, (int, float)):
        if amount >= 1000:
            score += 20
        elif amount >= 100:
            score += 10

    return min(score, 100.0)