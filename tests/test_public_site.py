import asyncio
import httpx
from app.main import app


def get(path):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)
    return asyncio.run(run())


def test_public_site_is_not_the_control_plane():
    response = get("/")
    assert response.status_code == 200
    assert "AI Assurance Infrastructure" in response.text
    assert "Trust and control for autonomous AI." in response.text
    assert "/console" in response.text
    assert "/protocol" in response.text
    assert "AI Workflow Qualification" not in response.text


def test_console_is_separate_from_public_site():
    response = get("/console")
    assert response.status_code == 200
    assert "Assurance Control Plane" in response.text
    assert "AI Workflow Qualification" not in response.text


def test_protocol_public_surface():
    page = get("/protocol")
    manifest = get("/protocol.json")
    schema = get("/protocol/v1/schema.json")
    discovery = get("/.well-known/ai-assurance-protocol.json")
    assert page.status_code == 200
    assert "AI Assurance Protocol v1" in page.text
    assert manifest.status_code == 200
    assert manifest.json()["protocol"] == "AI Assurance Protocol"
    assert manifest.json()["version"] == "1.0.0"
    assert schema.status_code == 200
    assert schema.json()["properties"]["protocol"]["const"] == "AI Assurance Protocol"
    assert discovery.status_code == 200
    assert discovery.json()["version"] == "1.0.0"
