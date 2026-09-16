from pathlib import Path
import sys
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway_sdk import GatewayClient


BASE_URL = "https://ai-agent-trust-control-plane.onrender.com"

# Paste the gw_... key you received when creating demo-company.
# Do NOT share this key with anyone.
API_KEY = os.getenv("AI_ASSURANCE_API_KEY", "")

if not API_KEY:
    raise RuntimeError("Set AI_ASSURANCE_API_KEY before running this demo.")


def print_result(title: str, result) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Decision : {result.decision}")
    print(f"Reason   : {result.reason}")
    print(f"Risk     : {result.risk_score:.2f}")

    if result.approval_id:
        print(f"Approval : {result.approval_id}")


def main() -> None:
    print()
    print("AI Agent Trust & Control Plane")
    print("PUBLIC SDK integration demonstration")
    print()

    with GatewayClient(
        base_url=BASE_URL,
        api_key=API_KEY,
    ) as client:

        health = client.health()

        print("Gateway status :", health["status"])
        print("Gateway service:", health["service"])
        print("Gateway version:", health["version"])

        agent = client.register_agent(
            agent_id="public-sdk-demo-agent",
            organization_id="demo-company",
            owner="demo-team",
            environment="production",
            qualification_status="QUALIFIED",
            policy={
                "allowed_tools": ["crm", "email"],
                "blocked_tools": ["payments"],
                "approval_tools": ["email"],
                "blocked_actions": ["delete_customer"],
                "approval_actions": ["send_external_email"],
                "max_transaction_usd": 1000,
            },
        )

        print()
        print("Registered agent:", agent.agent_id)
        print("Status          :", agent.status)
        print("Qualification   :", agent.qualification_status)

        result = client.evaluate(
            agent_id=agent.agent_id,
            tool="crm",
            action="read_customer",
            parameters={
                "customer_id": "CUST-1001"
            },
        )

        print_result(
            "1. SAFE ACTION",
            result,
        )

        result = client.evaluate(
            agent_id=agent.agent_id,
            tool="payments",
            action="refund",
            parameters={
                "amount_usd": 500
            },
        )

        print_result(
            "2. BLOCKED ACTION",
            result,
        )

        result = client.evaluate(
            agent_id=agent.agent_id,
            tool="email",
            action="send_external_email",
            parameters={
                "recipient": "customer@example.com",
                "subject": "Account update",
            },
        )

        print_result(
            "3. APPROVAL-REQUIRED ACTION",
            result,
        )

        approvals = client.list_approvals()

        print()
        print("=" * 60)
        print("PENDING APPROVALS")
        print("=" * 60)

        for approval in approvals:
            print(
                f"Approval ID : "
                f"{approval.get('approval_id')}"
            )
            print(
                f"Status      : "
                f"{approval.get('status')}"
            )

        events = client.audit()

        print()
        print("=" * 60)
        print("AUDIT TRAIL")
        print("=" * 60)

        for event in events:
            print(
                f"{event.get('tool')}"
                f" -> "
                f"{event.get('action')}"
                f" : "
                f"{event.get('decision')}"
            )

    print()
    print("=" * 60)
    print("PUBLIC SDK DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()