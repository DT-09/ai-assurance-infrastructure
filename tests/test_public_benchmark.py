import asyncio
import httpx
from app.main import app


def request(method, path, **kwargs):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(run())


def test_public_protocol_reference():
    response = request("GET", "/public/protocol")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol"] == "AI Assurance Protocol"
    assert body["version"] == "1.0.0"
    assert body["public"] is True
    assert body["benchmark"]["endpoint"] == "/public/benchmark"


def test_public_benchmark_catalog_is_deterministic():
    first = request("GET", "/public/benchmark")
    second = request("GET", "/public/benchmark")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(first.json()["scenarios"]) == 10


def test_public_benchmark_assured_and_blocked_states():
    assured = request("POST", "/public/benchmark/run", json={
        "reliability": 0.99,
        "target_reliability": 0.95,
        "critical_failures": 0,
        "human_review_rate": 0.05,
        "identity": True,
        "authority": True,
        "provenance": True,
        "deterministic_policy": True,
        "dependencies_visible": True,
        "runtime_control": True,
        "degraded_review": True,
    })
    assert assured.status_code == 200
    assert assured.json()["state"] == "ASSURED"
    assert assured.json()["passed"] == 10

    blocked = request("POST", "/public/benchmark/run", json={
        "reliability": 0.50,
        "target_reliability": 0.95,
        "critical_failures": 1,
    })
    assert blocked.status_code == 200
    assert blocked.json()["state"] == "BLOCKED"
    assert blocked.json()["passed"] < blocked.json()["total"]


def test_public_site_and_playground_are_reachable():
    site = request("GET", "/public")
    playground = request("GET", "/public/playground")
    assert site.status_code == 200
    assert "vendor-neutral assurance layer" in site.text
    assert playground.status_code == 200
    assert "AI Assurance Playground" in playground.text
