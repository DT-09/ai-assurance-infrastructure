import asyncio
import httpx

from gateway.main import app
import gateway.main as gateway_main
from gateway.models import Agent, AgentStatus, Policy


def request(method, path, headers=None, json=None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=json)
    return asyncio.run(run())


def setup_org(tmp_path):
    db = str(tmp_path / "gateway.db")
    import os
    os.chdir(tmp_path)
    gateway_main.storage = __import__("gateway.storage", fromlist=["SQLiteStorage"]).SQLiteStorage(db)
    gateway_main.registry = __import__("gateway.registry", fromlist=["AgentRegistry"]).AgentRegistry(db)
    gateway_main.approval_store = __import__("gateway.approvals", fromlist=["ApprovalStore"]).ApprovalStore(db)
    gateway_main.audit_log = __import__("gateway.audit", fromlist=["AuditLog"]).AuditLog(db)
    from gateway.models import Organization
    org = Organization(organization_id="assurance-org", name="Assurance Org")
    gateway_main.storage.save_organization(org)
    _, key = gateway_main.storage.create_credential("assurance-org", "test")
    return key


def test_runtime_action_creates_independent_evidence(tmp_path):
    key = setup_org(tmp_path)
    agent = Agent(
        agent_id="claims",
        organization_id="assurance-org",
        owner="security",
        environment="production",
        qualification_status="QUALIFIED",
        policy=Policy(
            allowed_tools=["crm"],
            blocked_tools=["payments"],
            blocked_actions=["delete_customer", "publish"],
            allowed_data_classes=["customer_profile"],
            allowed_targets=["crm-record"],
            max_transaction_usd=1000,
        ),
    )
    gateway_main.registry.register(agent)

    response = request(
        "POST", "/api/control/evaluate",
        headers={"X-API-Key": key},
        json={
            "agent_id": "claims",
            "tool": "payments",
            "action": "refund",
            "parameters": {"amount_usd": 25000},
            "data_classes": ["financial"],
            "trace_id": "trace-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "BLOCK"
    assert data["evidence_id"]
    assert len(data["evidence_hash"]) == 64

    ev = request("GET", "/api/evidence", headers={"X-API-Key": key})
    assert ev.status_code == 200
    assert ev.json()["count"] == 1


def test_assurance_attacks_real_authority_boundary(tmp_path):
    key = setup_org(tmp_path)
    agent = Agent(
        agent_id="claims",
        organization_id="assurance-org",
        owner="security",
        environment="production",
        qualification_status="QUALIFIED",
        policy=Policy(
            allowed_tools=["crm"],
            blocked_tools=["payments"],
            blocked_actions=["delete_customer", "publish"],
            allowed_data_classes=["customer_profile"],
            allowed_targets=["crm-record"],
            max_transaction_usd=1000,
        ),
    )
    gateway_main.registry.register(agent)

    response = request(
        "POST", "/api/agents/claims/assurance",
        headers={"X-API-Key": key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_count"] == 6
    assert data["escaped_controls"] == 0
    assert data["status"] == "ASSURED"
    assert len(data["evidence_root"]) == 64
