import asyncio
import httpx
import pytest

from app.main import app


@pytest.mark.anyio
async def test_local_agent_end_to_end_assurance():
    """
    End-to-end integration test for the local test agent.

    Verifies:
    - local test-agent execution
    - multiple workflow cases
    - reliability calculation
    - critical-failure calculation
    - policy evaluation
    - evidence creation
    - AssuranceRecord creation
    - ASSURED verdict
    """

    test_cases = [
        {
            "case_id": "INT-001",
            "input_data": "Customer received a damaged product",
            "expected_output": "REFUND_APPROVED",
            "critical": True,
        },
        {
            "case_id": "INT-002",
            "input_data": "Customer requests a refund outside policy",
            "expected_output": "REFUND_DENIED",
            "critical": True,
        },
        {
            "case_id": "INT-003",
            "input_data": "Customer has an unclear request",
            "expected_output": "ESCALATE",
            "critical": False,
        },
    ]

    # ASGI transport lets the test call the FastAPI app directly.
    # This avoids the public endpoint's SSRF protection because this
    # is an internal integration test, not a production HTTP request.
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:

        # First verify the local test agent itself.
        response = await client.post(
            "/v1/test-agent",
            json={
                "input": test_cases[0]["input_data"]
            },
        )

        assert response.status_code == 200

        agent_result = response.json()

        assert agent_result["output"] == "REFUND_APPROVED"
        assert agent_result["cost_usd"] == 0.01

        # Execute each case directly against the local test agent.
        results = []

        for case in test_cases:
            response = await client.post(
                "/v1/test-agent",
                json={
                    "input": case["input_data"]
                },
            )

            assert response.status_code == 200

            result = response.json()

            actual_output = result["output"]

            results.append(
                {
                    "case_id": case["case_id"],
                    "expected_output": case["expected_output"],
                    "actual_output": actual_output,
                    "critical": case["critical"],
                    "passed": actual_output == case["expected_output"],
                    "cost_usd": result.get("cost_usd", 0.0),
                }
            )

        # All three cases should pass.
        assert len(results) == 3
        assert all(result["passed"] for result in results)

        # Reliability = passed / total * 100
        reliability = (
            sum(result["passed"] for result in results)
            / len(results)
        ) * 100

        critical_failures = sum(
            1
            for result in results
            if result["critical"] and not result["passed"]
        )

        total_cost = sum(
            result["cost_usd"]
            for result in results
        )

        assert reliability == 100.0
        assert critical_failures == 0
        assert total_cost == pytest.approx(0.03)

        # Now send the measured results through the Assurance Core.
        assurance_response = await client.post(
            "/v1/assurance/check",
            json={
                "system": {
                    "system_id": "local-integration-agent",
                    "name": "Local Integration Agent",
                    "version": "1.0.0",
                    "environment": "staging",
                },
                "metrics": {
                    "reliability": reliability,
                    "critical_failures": critical_failures,
                    "latency_p95_ms": 100,
                    "cost_usd": total_cost,
                },
                "evaluation_type": "workflow",
                "policy": {
                    "policy_id": "production-v1",
                    "name": "Production AI Policy",
                    "version": "1.0.0",
                    "rules": [
                        {
                            "metric": "reliability",
                            "operator": ">=",
                            "threshold": 95,
                            "severity": "blocking",
                        },
                        {
                            "metric": "critical_failures",
                            "operator": "==",
                            "threshold": 0,
                            "severity": "blocking",
                        },
                    ],
                },
            },
        )

        assert assurance_response.status_code == 200

        assurance_result = assurance_response.json()

        assert "assurance" in assurance_result
        assert "evaluation" in assurance_result
        assert "evidence" in assurance_result
        assert "system" in assurance_result

        assurance = assurance_result["assurance"]

        assert assurance["system_id"] == "local-integration-agent"
        assert assurance["system_version"] == "1.0.0"
        assert assurance["environment"] == "staging"
        assert assurance["verdict"] == "ASSURED"

        assert assurance["metrics"]["reliability"] == 100.0
        assert assurance["metrics"]["critical_failures"] == 0.0

        assert len(assurance["evaluation_ids"]) >= 1
        assert len(assurance["evidence_ids"]) >= 1
        assert assurance["policy_id"] == "production-v1"


@pytest.mark.anyio
async def test_local_agent_failure_produces_blocked_assurance():
    """
    Verify that the Assurance Core blocks a workflow when a critical
    expected result is wrong.
    """

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:

        response = await client.post(
            "/v1/assurance/check",
            json={
                "system": {
                    "system_id": "local-failure-agent",
                    "name": "Local Failure Agent",
                    "version": "1.0.0",
                    "environment": "staging",
                },
                "metrics": {
                    "reliability": 50.0,
                    "critical_failures": 1,
                    "latency_p95_ms": 100,
                },
                "evaluation_type": "workflow",
                "policy": {
                    "policy_id": "production-v1",
                    "name": "Production AI Policy",
                    "version": "1.0.0",
                    "rules": [
                        {
                            "metric": "reliability",
                            "operator": ">=",
                            "threshold": 95,
                            "severity": "blocking",
                        },
                        {
                            "metric": "critical_failures",
                            "operator": "==",
                            "threshold": 0,
                            "severity": "blocking",
                        },
                    ],
                },
            },
        )

        assert response.status_code == 200

        result = response.json()

        assert result["assurance"]["verdict"] == "BLOCKED"
        assert result["assurance"]["metrics"]["reliability"] == 50.0
        assert result["assurance"]["metrics"]["critical_failures"] == 1.0
