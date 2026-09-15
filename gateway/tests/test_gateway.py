import asyncio

import httpx
import pytest

import gateway.main as gateway_main
from gateway.approvals import ApprovalStatus, ApprovalStore
from gateway.audit import AuditLog
from gateway.control import evaluate_control
from gateway.engine import evaluate_action
from gateway.main import app
from gateway.models import (
    Agent,
    AgentAction,
    AgentStatus,
    Decision,
    Policy,
)
from gateway.registry import AgentRegistry
from gateway.storage import SQLiteStorage


def make_qualified_agent(
    agent_id: str = "test-agent",
    organization_id: str = "test-org",
    status: AgentStatus = AgentStatus.ACTIVE,
) -> Agent:
    return Agent(
        agent_id=agent_id,
        organization_id=organization_id,
        owner="test-owner",
        environment="production",
        status=status,
        qualification_status="QUALIFIED",
        policy=Policy(
            allowed_tools=["crm", "payment"],
            approval_tools=[],
            max_transaction_usd=1000,
        ),
    )


def api_request(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    json: dict | None = None,
) -> httpx.Response:
    async def make_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(
                method=method,
                url=path,
                headers=headers,
                json=json,
            )

    return asyncio.run(make_request())


@pytest.fixture
def isolated_gateway(monkeypatch, tmp_path):
    database = str(tmp_path / "gateway.db")

    monkeypatch.setattr(
        gateway_main,
        "storage",
        SQLiteStorage(database),
    )

    monkeypatch.setattr(
        gateway_main,
        "registry",
        AgentRegistry(database),
    )

    monkeypatch.setattr(
        gateway_main,
        "approval_store",
        ApprovalStore(database),
    )

    monkeypatch.setattr(
        gateway_main,
        "audit_log",
        AuditLog(database),
    )

    monkeypatch.chdir(tmp_path)


def create_test_organization(
    database: str,
    organization_id: str = "test-org",
):
    storage = SQLiteStorage(database)

    from gateway.models import Organization

    organization = Organization(
        organization_id=organization_id,
        name="Test Organization",
    )

    storage.save_organization(organization)

    credential, api_key = storage.create_credential(
        organization_id=organization_id,
        name="test-key",
    )

    return credential, api_key


def test_allowed_action():
    action = AgentAction(
        agent_id="support-agent",
        tool="crm",
        action="read",
    )

    policy = Policy(
        allowed_tools=["crm"],
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.ALLOW


def test_blocked_tool():
    action = AgentAction(
        agent_id="support-agent",
        tool="database",
        action="delete",
    )

    policy = Policy(
        allowed_tools=["crm"],
        blocked_tools=["database"],
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.BLOCK


def test_human_approval_for_sensitive_action():
    action = AgentAction(
        agent_id="sales-agent",
        tool="refund",
        action="create",
        parameters={"amount_usd": 500},
    )

    policy = Policy(
        allowed_tools=["refund"],
        approval_tools=["refund"],
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.APPROVAL_REQUIRED


def test_transaction_limit():
    action = AgentAction(
        agent_id="sales-agent",
        tool="payment",
        action="charge",
        parameters={"amount_usd": 5000},
    )

    policy = Policy(
        allowed_tools=["payment"],
        max_transaction_usd=1000,
    )

    result = evaluate_action(action, policy)

    assert result.decision == Decision.APPROVAL_REQUIRED


def test_unqualified_agent_is_blocked():
    agent = Agent(
        agent_id="untrusted-agent",
        organization_id="test-org",
        owner="security-team",
        environment="production",
        qualification_status="NOT_QUALIFIED",
        policy=Policy(
            allowed_tools=["crm"],
        ),
    )

    action = AgentAction(
        agent_id="untrusted-agent",
        tool="crm",
        action="read",
    )

    result = evaluate_control(
        action=action,
        agent=agent,
    )

    assert result.decision == Decision.BLOCK


def test_qualified_agent_reaches_gateway():
    agent = make_qualified_agent("trusted-agent")

    action = AgentAction(
        agent_id="trusted-agent",
        tool="crm",
        action="read",
    )

    result = evaluate_control(
        action=action,
        agent=agent,
    )

    assert result.decision == Decision.ALLOW


def test_suspended_agent_is_blocked():
    agent = make_qualified_agent(
        "suspended-agent",
        status=AgentStatus.SUSPENDED,
    )

    action = AgentAction(
        agent_id="suspended-agent",
        tool="crm",
        action="read",
    )

    result = evaluate_control(
        action=action,
        agent=agent,
    )

    assert result.decision == Decision.BLOCK


def test_revoked_agent_is_blocked():
    agent = make_qualified_agent(
        "revoked-agent",
        status=AgentStatus.REVOKED,
    )

    action = AgentAction(
        agent_id="revoked-agent",
        tool="crm",
        action="read",
    )

    result = evaluate_control(
        action=action,
        agent=agent,
    )

    assert result.decision == Decision.BLOCK


def test_registry_register_and_get(tmp_path):
    database = str(tmp_path / "registry.db")

    registry = AgentRegistry(database)
    agent = make_qualified_agent("registry-agent")

    registry.register(agent)

    stored = registry.get("registry-agent")

    assert stored is not None
    assert stored.agent_id == "registry-agent"
    assert stored.organization_id == "test-org"
    assert stored.status == AgentStatus.ACTIVE


def test_registry_suspend(tmp_path):
    database = str(tmp_path / "registry.db")

    registry = AgentRegistry(database)
    registry.register(make_qualified_agent("suspend-test"))

    result = registry.suspend("suspend-test")

    assert result is not None
    assert result.status == AgentStatus.SUSPENDED

    stored = registry.get("suspend-test")

    assert stored is not None
    assert stored.status == AgentStatus.SUSPENDED


def test_registry_revoke(tmp_path):
    database = str(tmp_path / "registry.db")

    registry = AgentRegistry(database)
    registry.register(make_qualified_agent("revoke-test"))

    result = registry.revoke("revoke-test")

    assert result is not None
    assert result.status == AgentStatus.REVOKED

    stored = registry.get("revoke-test")

    assert stored is not None
    assert stored.status == AgentStatus.REVOKED


def test_registry_persists_across_instances(tmp_path):
    database = str(tmp_path / "persistent.db")

    registry_one = AgentRegistry(database)

    agent = make_qualified_agent("persistent-agent")
    registry_one.register(agent)

    registry_two = AgentRegistry(database)

    stored = registry_two.get("persistent-agent")

    assert stored is not None
    assert stored.agent_id == "persistent-agent"
    assert stored.organization_id == "test-org"
    assert stored.qualification_status == "QUALIFIED"


def test_approval_creation_and_persistence(tmp_path):
    database = str(tmp_path / "approval.db")

    store_one = ApprovalStore(database)

    action = AgentAction(
        agent_id="sales-agent",
        tool="payment",
        action="charge",
        parameters={"amount_usd": 5000},
    )

    request = store_one.create(
        action=action,
        reason="Transaction exceeds autonomous limit",
    )

    store_two = ApprovalStore(database)

    stored = store_two.get(request.approval_id)

    assert stored is not None
    assert stored.approval_id == request.approval_id
    assert stored.status == ApprovalStatus.PENDING


def test_approval_can_be_approved(tmp_path):
    database = str(tmp_path / "approval.db")

    store = ApprovalStore(database)

    action = AgentAction(
        agent_id="sales-agent",
        tool="payment",
        action="charge",
    )

    request = store.create(
        action=action,
        reason="Human approval required",
    )

    request.approve()
    store.update(request)

    stored = store.get(request.approval_id)

    assert stored is not None
    assert stored.status == ApprovalStatus.APPROVED
    assert stored.resolved_at is not None


def test_approval_can_be_rejected(tmp_path):
    database = str(tmp_path / "approval.db")

    store = ApprovalStore(database)

    action = AgentAction(
        agent_id="sales-agent",
        tool="payment",
        action="charge",
    )

    request = store.create(
        action=action,
        reason="Human approval required",
    )

    request.reject()
    store.update(request)

    stored = store.get(request.approval_id)

    assert stored is not None
    assert stored.status == ApprovalStatus.REJECTED
    assert stored.resolved_at is not None


def test_health_is_public():
    response = api_request(
        "GET",
        "/health",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_requires_api_key(
    monkeypatch,
    isolated_gateway,
):
    monkeypatch.delenv(
        "GATEWAY_API_KEYS",
        raising=False,
    )

    response = api_request(
        "GET",
        "/api/agents",
    )

    assert response.status_code == 401


def test_api_accepts_valid_database_api_key(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    _, api_key = create_test_organization(
        database
    )

    response = api_request(
        "GET",
        "/api/agents",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_invalid_api_key_is_rejected(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    create_test_organization(
        database
    )

    response = api_request(
        "GET",
        "/api/agents",
        headers={
            "X-API-Key": "gw_invalid",
        },
    )

    assert response.status_code == 401


def test_revoked_api_key_is_rejected(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    credential, api_key = create_test_organization(
        database
    )

    storage = SQLiteStorage(database)

    storage.revoke_credential(
        credential.credential_id
    )

    response = api_request(
        "GET",
        "/api/agents",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert response.status_code == 401


def test_credential_can_be_created(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    _, api_key = create_test_organization(
        database
    )

    response = api_request(
        "POST",
        "/api/credentials",
        headers={
            "X-API-Key": api_key,
        },
        json={
            "name": "production-agent",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["credential"]["name"] == (
        "production-agent"
    )
    assert data["api_key"].startswith("gw_")


def test_organization_only_sees_its_own_agents(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    _, key_a = create_test_organization(
        database,
        "org-a",
    )

    _, key_b = create_test_organization(
        database,
        "org-b",
    )

    agent_a = {
        "agent_id": "agent-a",
        "organization_id": "org-a",
        "owner": "team-a",
        "environment": "production",
        "qualification_status": "QUALIFIED",
        "policy": {
            "allowed_tools": ["crm"],
        },
    }

    agent_b = {
        "agent_id": "agent-b",
        "organization_id": "org-b",
        "owner": "team-b",
        "environment": "production",
        "qualification_status": "QUALIFIED",
        "policy": {
            "allowed_tools": ["crm"],
        },
    }

    first_response = api_request(
        "POST",
        "/api/agents",
        headers={
            "X-API-Key": key_a,
        },
        json=agent_a,
    )

    second_response = api_request(
        "POST",
        "/api/agents",
        headers={
            "X-API-Key": key_b,
        },
        json=agent_b,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    response_a = api_request(
        "GET",
        "/api/agents",
        headers={
            "X-API-Key": key_a,
        },
    )

    assert response_a.status_code == 200

    agents_a = response_a.json()["agents"]

    assert len(agents_a) == 1
    assert agents_a[0]["agent_id"] == "agent-a"

    response_b = api_request(
        "GET",
        "/api/agents",
        headers={
            "X-API-Key": key_b,
        },
    )

    assert response_b.status_code == 200

    agents_b = response_b.json()["agents"]

    assert len(agents_b) == 1
    assert agents_b[0]["agent_id"] == "agent-b"


def test_organization_cannot_access_another_organization_agent(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    _, key_a = create_test_organization(
        database,
        "org-a",
    )

    _, key_b = create_test_organization(
        database,
        "org-b",
    )

    response = api_request(
        "POST",
        "/api/agents",
        headers={
            "X-API-Key": key_a,
        },
        json={
            "agent_id": "org-a-agent",
            "organization_id": "org-a",
            "owner": "team-a",
            "environment": "production",
            "qualification_status": "QUALIFIED",
            "policy": {
                "allowed_tools": ["crm"],
            },
        },
    )

    assert response.status_code == 200

    access_response = api_request(
        "GET",
        "/api/agents/org-a-agent",
        headers={
            "X-API-Key": key_b,
        },
    )

    assert access_response.status_code == 404


def test_wrong_organization_agent_registration_is_rejected(
    isolated_gateway,
    tmp_path,
):
    database = str(tmp_path / "gateway.db")

    _, key_a = create_test_organization(
        database,
        "org-a",
    )

    response = api_request(
        "POST",
        "/api/agents",
        headers={
            "X-API-Key": key_a,
        },
        json={
            "agent_id": "wrong-org-agent",
            "organization_id": "org-b",
            "owner": "team-b",
            "environment": "production",
            "qualification_status": "QUALIFIED",
            "policy": {
                "allowed_tools": ["crm"],
            },
        },
    )

    assert response.status_code == 403