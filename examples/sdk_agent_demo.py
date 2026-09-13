from pathlib import Path
import sys

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from gateway_sdk import GatewayClient


BASE_URL = "http://127.0.0.1:8000"
API_KEY = "gw_ZpWFM0lge47RBO_NW6gvRN3LLf9_ltX-V9V6AhZMjmg"


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
    print("SDK integration demonstration")
    print()

    with GatewayClient(
        base_url=BASE_URL,
        api_key=API_KEY,
    ) as client:

        # -----------------------------------------------------
        # 1. Check gateway health
        # -----------------------------------------------------

        health = client.health()

        print("Gateway status :", health["status"])
        print("Gateway service:", health["service"])
        print("Gateway version:", health["version"])

        # -----------------------------------------------------
        # 2. Register the agent
        # -----------------------------------------------------

        agent = client.register_agent(
            agent_id="sdk-demo-agent",
            organization_id="demo-org",
            owner="demo-team",
            environment="production",
            qualification_status="QUALIFIED",
            policy={
                "allowed_tools": [
                    "crm",
                    "email",
                ],
                "blocked_tools": [
                    "payments",
                ],
                "approval_tools": [
                    "email",
                ],
                "blocked_actions": [
                    "delete_customer",
                ],
                "approval_actions": [
                    "send_external_email",
                ],
                "max_transaction_usd": 1000,
            },
        )

        print()
        print("Registered agent:", agent.agent_id)
        print("Status          :", agent.status)
        print("Qualification   :", agent.qualification_status)

        # -----------------------------------------------------
        # 3. Safe action -> ALLOW
        # -----------------------------------------------------

        result = client.evaluate(
            agent_id=agent.agent_id,
            tool="crm",
            action="read_customer",
            parameters={
                "customer_id": "CUST-1001",
            },
        )

        print_result(
            "1. SAFE ACTION",
            result,
        )

        # -----------------------------------------------------
        # 4. Unauthorized tool -> BLOCK
        # -----------------------------------------------------

        result = client.evaluate(
            agent_id=agent.agent_id,
            tool="payments",
            action="refund",
            parameters={
                "amount_usd": 500,
            },
        )

        print_result(
            "2. BLOCKED ACTION",
            result,
        )

        # -----------------------------------------------------
        # 5. Sensitive action -> APPROVAL_REQUIRED
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # 6. Show pending approvals
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # 7. Show audit trail
        # -----------------------------------------------------

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
    print("SDK DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
