import asyncio

import httpx

from app.main import app


def api_request(
    method: str,
    path: str,
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
                json=json,
            )

    return asyncio.run(make_request())


def test_health():
    response = api_request("GET", "/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_qualification_pass():
    payload = {
        "name": "Test Workflow",
        "target_reliability": 95,
        "maximum_critical_failures": 0,
        "maximum_human_review_rate": 20,
        "test_cases": [
            {
                "case_id": "1",
                "expected_output": "A",
                "actual_output": "A",
                "success": True,
                "latency_ms": 100,
                "critical": False,
                "human_review_required": False,
                "estimated_cost_usd": 0.01,
            },
            {
                "case_id": "2",
                "expected_output": "B",
                "actual_output": "B",
                "success": True,
                "latency_ms": 200,
                "critical": False,
                "human_review_required": False,
                "estimated_cost_usd": 0.01,
            },
        ],
    }

    response = api_request(
        "POST",
        "/api/qualify",
        json=payload,
    )

    assert response.status_code == 200

    result = response.json()

    assert result["reliability_score"] == 100
    assert result["verdict"] == "QUALIFIED"


def test_critical_failure_blocks():
    payload = {
        "name": "Critical Workflow",
        "target_reliability": 90,
        "maximum_critical_failures": 0,
        "maximum_human_review_rate": 20,
        "test_cases": [
            {
                "case_id": "1",
                "expected_output": "approve",
                "actual_output": "reject",
                "success": False,
                "latency_ms": 100,
                "critical": True,
                "human_review_required": False,
                "estimated_cost_usd": 0.01,
            },
        ],
    }

    response = api_request(
        "POST",
        "/api/qualify",
        json=payload,
    )

    assert response.status_code == 200

    result = response.json()

    assert result["critical_failures"] == 1
    assert result["verdict"] == "BLOCKED"


def test_demo():
    response = api_request("GET", "/api/demo")

    assert response.status_code == 200

    result = response.json()

    assert result["workflow_name"] == "Customer Refund Agent"
    assert result["total_cases"] == 4
    assert result["critical_failures"] == 1
    assert result["verdict"] == "BLOCKED"


def test_real_agent_execution():
    from app.demo_agent import refund_agent
    from app.runner import AgentRunner, ExecutionCase

    cases = [
        ExecutionCase(
            case_id="REAL-001",
            input_data="Customer received a damaged product",
            expected_output="REFUND_APPROVED",
        ),
        ExecutionCase(
            case_id="REAL-002",
            input_data="Request is outside policy",
            expected_output="REFUND_DENIED",
        ),
    ]

    runner = AgentRunner(refund_agent)

    result = runner.run(
        workflow_name="Real Refund Agent",
        cases=cases,
        target_reliability=100,
        maximum_critical_failures=0,
        maximum_human_review_rate=0,
    )

    assert result.total_cases == 2
    assert result.successful_cases == 2
    assert result.reliability_score == 100
    assert result.verdict == "QUALIFIED"


def test_remote_qualification_endpoint_validation():
    payload = {
        "name": "X",
        "test_cases": [
            {
                "input_data": "x",
                "expected_output": "y",
            }
        ],
    }

    response = api_request(
        "POST",
        "/api/qualify/remote",
        json=payload,
    )

    assert response.status_code == 400
    assert "agent_url" in response.json()["detail"]