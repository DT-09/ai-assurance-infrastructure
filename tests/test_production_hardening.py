import asyncio

import httpx

from app.main import app


def request(method: str, path: str, headers=None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers)
    return asyncio.run(run())


def test_security_headers_and_request_id():
    response = request("GET", "/api/health", headers={"X-Request-ID": "not-a-uuid"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Request-ID"] != "not-a-uuid"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_valid_request_id_is_preserved():
    request_id = "12345678-1234-5678-1234-567812345678"
    response = request("GET", "/api/health", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_readiness_reports_store_checks():
    response = request("GET", "/api/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert all(body["checks"].values())
    assert body["environment"]


def test_readiness_uses_live_database_backend_shape():
    response = request("GET", "/api/readiness")
    body = response.json()
    assert body["database_backend"] in {"sqlite", "postgresql"}
    for check in body["checks"].values():
        assert check["status"] == "ok"
        assert check["backend"] in {"sqlite", "postgresql"}


def test_protocol_manifest_is_public():
    response = request("GET", "/v1/control/protocol/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol"] == "AI Assurance Protocol"
    assert body["version"]
