import asyncio

import httpx

from app.main import app


def request(path):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)
    return asyncio.run(run())


def test_console_serves_assurance_infrastructure_ui():
    response = request("/console")
    assert response.status_code == 200
    assert "AI Assurance Infrastructure" in response.text
    assert "AI Workflow Qualification" not in response.text
    assert "Assurance Control Plane" in response.text
    assert "/static/console.css" in response.text
    assert "/static/console.js" in response.text


def test_console_static_assets_are_served():
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            css = await client.get("/static/console.css")
            js = await client.get("/static/console.js")
            return css, js
    css, js = asyncio.run(run())
    assert css.status_code == 200
    assert js.status_code == 200
    assert "Content-Security-Policy" not in css.text
    assert "AI Workflow Qualification" not in js.text


def test_protocol_manifest_is_still_public():
    response = request("/v1/control/protocol/manifest")
    assert response.status_code == 200
    assert response.json()["protocol"] == "AI Assurance Protocol"
