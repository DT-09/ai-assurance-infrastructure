import httpx
import pytest

from gateway_sdk.client import (
    GatewayAuthenticationError,
    GatewayClient,
    GatewayNotFoundError,
)
from gateway_sdk.models import (
    Agent,
    DecisionResult,
    Organization,
)


def make_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "service": "ai-agent-trust-control-plane",
                    "version": "1.3.0",
                },
            )

        if request.url.path == "/api/organization":
            return httpx.Response(
                200,
                json={
                    "organization_id": "org_test",
                    "name": "Test Organization",
                },
            )

        if request.url.path == "/api/agents":
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "agent": {
                            "agent_id": "agent_1",
                            "organization_id": "org_test",
                            "owner": "test",
                            "environment": "production",
                            "status": "ACTIVE",
                            "qualification_status": "QUALIFIED",
                            "policy": {},
                        }
                    },
                )

            return httpx.Response(
                200,
                json={
                    "agents": [
                        {
                            "agent_id": "agent_1",
                            "organization_id": "org_test",
                            "owner": "test",
                            "environment": "production",
                            "status": "ACTIVE",
                            "qualification_status": "QUALIFIED",
                            "policy": {},
                        }
                    ]
                },
            )

        if request.url.path == "/api/control/evaluate":
            return httpx.Response(
                200,
                json={
                    "decision": "ALLOW",
                    "reason": "Action allowed by policy",
                    "agent_id": "agent_1",
                    "tool": "crm",
                    "action": "read",
                    "risk_score": 0.0,
                    "approval_id": None,
                },
            )

        if request.url.path == "/api/missing":
            return httpx.Response(
                404,
                json={
                    "detail": "Resource not found",
                },
            )

        if request.url.path == "/api/auth-error":
            return httpx.Response(
                401,
                json={
                    "detail": "Invalid API key",
                },
            )

        return httpx.Response(
            404,
            json={
                "detail": "Not found",
            },
        )

    return httpx.MockTransport(handler)


def make_client():
    client = GatewayClient(
        base_url="http://testserver",
        api_key="gw_test_key",
    )

    client._client = httpx.Client(
        transport=make_transport(),
        base_url="http://testserver",
        headers={
            "X-API-Key": "gw_test_key",
            "Content-Type": "application/json",
        },
    )

    return client


def test_health():
    client = make_client()

    try:
        result = client.health()

        assert result["status"] == "ok"
        assert result["service"] == (
            "ai-agent-trust-control-plane"
        )
    finally:
        client.close()


def test_get_organization():
    client = make_client()

    try:
        organization = client.get_organization()

        assert isinstance(
            organization,
            Organization,
        )
        assert organization.organization_id == "org_test"
        assert organization.name == "Test Organization"
    finally:
        client.close()


def test_register_agent():
    client = make_client()

    try:
        agent = client.register_agent(
            agent_id="agent_1",
            organization_id="org_test",
            owner="test",
            environment="production",
            qualification_status="QUALIFIED",
        )

        assert isinstance(agent, Agent)
        assert agent.agent_id == "agent_1"
        assert agent.status == "ACTIVE"
        assert agent.qualification_status == "QUALIFIED"
    finally:
        client.close()


def test_list_agents():
    client = make_client()

    try:
        agents = client.list_agents()

        assert len(agents) == 1
        assert isinstance(agents[0], Agent)
        assert agents[0].agent_id == "agent_1"
    finally:
        client.close()


def test_evaluate():
    client = make_client()

    try:
        result = client.evaluate(
            agent_id="agent_1",
            tool="crm",
            action="read",
        )

        assert isinstance(
            result,
            DecisionResult,
        )
        assert result.decision == "ALLOW"
        assert result.agent_id == "agent_1"
        assert result.tool == "crm"
        assert result.action == "read"
        assert result.risk_score == 0.0
    finally:
        client.close()


def test_not_found_error():
    client = make_client()

    try:
        with pytest.raises(
            GatewayNotFoundError
        ):
            client._request(
                "GET",
                "/api/missing",
            )
    finally:
        client.close()


def test_authentication_error():
    client = make_client()

    try:
        with pytest.raises(
            GatewayAuthenticationError
        ):
            client._request(
                "GET",
                "/api/auth-error",
            )
    finally:
        client.close()


def test_context_manager():
    client = GatewayClient(
        base_url="http://testserver",
        api_key="gw_test_key",
    )

    client._client = httpx.Client(
        transport=make_transport(),
        base_url="http://testserver",
        headers={
            "X-API-Key": "gw_test_key",
            "Content-Type": "application/json",
        },
    )

    with client as active_client:
        result = active_client.health()

        assert result["status"] == "ok"

