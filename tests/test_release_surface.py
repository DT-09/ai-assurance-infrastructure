import asyncio
import httpx
from app.main import app
from app.config import ENGINE_VERSION

PATHS = [
    "/",
    "/ecosystem.html",
    "/protocol.html",
    "/playground.html",
    "/pricing.html",
    "/site.css",
    "/site.js",
    "/api/health",
    "/api/readiness",
    "/public/ecosystem/manifest",
    "/public/ecosystem/stats",
    "/public/ecosystem/participants",
    "/public/ecosystem/artifacts",
    "/public/ecosystem/integrations",
    "/public/ecosystem/graph",
    "/public/ecosystem/conformance",
    "/public/ecosystem/overview",
    "/public/ecosystem/exchange",
]


def request(path):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)
    return asyncio.run(run())


def test_release_surface_routes_are_healthy():
    for path in PATHS:
        response = request(path)
        assert response.status_code == 200, (path, response.status_code, response.text[:300])


def test_release_version_is_consistent():
    health = request("/api/health").json()
    assert health["version"] == ENGINE_VERSION == "15.0.0"


def test_public_homepage_is_new_infrastructure_surface():
    response = request("/")
    assert "Trust infrastructure for autonomous AI." in response.text
    assert "Identity → Evidence → Trust → Control" in response.text
    assert "AI Workflow Qualification" not in response.text
