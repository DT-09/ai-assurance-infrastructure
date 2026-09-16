from pathlib import Path
import sys

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from gateway.approvals import ApprovalStore
from gateway.control import evaluate_control
from gateway.models import Agent, AgentAction, Policy


def print_result(title: str, result) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Decision : {result.decision.value}")
    print(f"Reason   : {result.reason}")
    print(f"Risk     : {result.risk_score:.2f}")

    if result.approval_id:
        print(f"Approval : {result.approval_id}")


def main() -> None:
    approval_store = ApprovalStore(
        database_path="demo_gateway.db"
    )

    agent = Agent(
        agent_id="demo-support-agent",
        organization_id="demo-org",
        owner="demo-team",
        environment="production",
        qualification_status="QUALIFIED",
        policy=Policy(
            allowed_tools=[
                "crm",
                "email",
            ],
            blocked_tools=[
                "payments",
            ],
            approval_tools=[
                "email",
            ],
            blocked_actions=[
                "delete_customer",
            ],
            approval_actions=[
                "send_external_email",
            ],
            max_transaction_usd=1000,
        ),
    )

    print()
    print("AI Agent Trust & Control Plane")
    print("End-to-end gateway demonstration")
    print()

    # ---------------------------------------------------------
    # 1. Safe action -> ALLOW
    # ---------------------------------------------------------

    safe_action = AgentAction(
        agent_id=agent.agent_id,
        tool="crm",
        action="read_customer",
        parameters={
            "customer_id": "CUST-1001",
        },
    )

    result = evaluate_control(
        action=safe_action,
        agent=agent,
        approval_store=approval_store,
    )

    print_result(
        "1. SAFE ACTION",
        result,
    )

    # ---------------------------------------------------------
    # 2. Unauthorized tool -> BLOCK
    # ---------------------------------------------------------

    blocked_action = AgentAction(
        agent_id=agent.agent_id,
        tool="payments",
        action="refund",
        parameters={
            "amount_usd": 500,
        },
    )

    result = evaluate_control(
        action=blocked_action,
        agent=agent,
        approval_store=approval_store,
    )

    print_result(
        "2. BLOCKED ACTION",
        result,
    )

    # ---------------------------------------------------------
    # 3. Sensitive action -> APPROVAL_REQUIRED
    # ---------------------------------------------------------

    approval_action = AgentAction(
        agent_id=agent.agent_id,
        tool="email",
        action="send_external_email",
        parameters={
            "recipient": "customer@example.com",
            "subject": "Account update",
        },
    )

    result = evaluate_control(
        action=approval_action,
        agent=agent,
        approval_store=approval_store,
    )

    print_result(
        "3. APPROVAL-REQUIRED ACTION",
        result,
    )

    print()
    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
