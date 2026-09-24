"""AAI runtime assurance vertical-slice demo.

Demonstrates the product behavior: an agent requests consequential actions,
AAI independently evaluates them, blocks out-of-authority actions, creates
evidence, and runs an adversarial assurance suite.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.approvals import ApprovalStore
from gateway.assurance import run_assurance
from gateway.control import evaluate_control
from gateway.models import Agent, AgentAction, Policy
from gateway.storage import SQLiteStorage


def main() -> None:
    db = "runtime_assurance_demo.db"
    storage = SQLiteStorage(db)
    approvals = ApprovalStore(db)

    agent = Agent(
        agent_id="claims-agent",
        organization_id="demo-org",
        owner="claims-platform",
        environment="production",
        qualification_status="QUALIFIED",
        authority_version="2026-09-23.1",
        policy=Policy(
            allowed_tools=["crm", "refunds"],
            blocked_tools=["payments-admin"],
            blocked_actions=["delete_customer", "publish"],
            allowed_data_classes=["customer_profile", "claim"],
            allowed_targets=["crm-record", "assigned-claim"],
            max_transaction_usd=5000,
        ),
    )

    action = AgentAction(
        agent_id=agent.agent_id,
        tool="refunds",
        action="refund",
        parameters={"amount_usd": 25000},
        target="assigned-claim",
        data_classes=["claim"],
        trace_id="demo-trace-001",
    )

    result = evaluate_control(action, agent, approvals, storage)

    print("=== AAI RUNTIME DECISION ===")
    print(result.model_dump_json(indent=2))

    assurance = run_assurance(agent, approvals, storage)

    print("\n=== AAI INDEPENDENT ASSURANCE ===")
    print(f"status={assurance['status']}")
    print(f"scenarios={assurance['scenario_count']}")
    print(f"blocked={assurance['blocked']}")
    print(f"approval_required={assurance['approval_required']}")
    print(f"escaped_controls={assurance['escaped_controls']}")
    print(f"evidence_root={assurance['evidence_root']}")


if __name__ == "__main__":
    main()
