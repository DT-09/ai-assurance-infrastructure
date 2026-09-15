import os
import tempfile
import uuid

import httpx
import pytest

from app.main import app


def request(method, path, headers=None, json=None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=json)
    import asyncio
    return asyncio.run(run())


def test_protocol_manifest_is_public():
    response = request("GET", "/v1/control/protocol/manifest")
    assert response.status_code == 200
    assert response.json()["protocol"] == "AI Assurance Protocol"


def test_bootstrap_and_tenant_isolation(monkeypatch):
    db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("ASSURANCE_IDENTITY_DB", db)
    monkeypatch.setenv("ASSURANCE_BOOTSTRAP_KEY", "test-bootstrap")
    try:
        created = request(
            "POST", "/v1/control/organizations/bootstrap",
            headers={"X-Bootstrap-Key": "test-bootstrap"},
            json={"name": "Tenant One"},
        )
        assert created.status_code == 201
        data = created.json()
        key = data["credential"]["api_key"]
        org = data["organization"]["organization_id"]

        project = request(
            "POST", "/v1/control/projects",
            headers={"X-API-Key": key},
            json={"name": "Production"},
        )
        assert project.status_code == 201
        project_id = project.json()["project_id"]

        asset = request(
            "POST", "/v1/control/assets",
            headers={"X-API-Key": key},
            json={"project_id": project_id, "name": "Refund Agent", "asset_type": "agent"},
        )
        assert asset.status_code == 201
        asset_id = asset.json()["asset_id"]

        forbidden = request(
            "GET", f"/v1/control/assets/{asset_id}",
            headers={"X-API-Key": "invalid"},
        )
        assert forbidden.status_code == 401
        assert org.startswith("org_")
    finally:
        try:
            os.remove(db)
        except FileNotFoundError:
            pass


def test_end_to_end_assurance_enforcement_passport(monkeypatch):
    db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("ASSURANCE_IDENTITY_DB", db)
    monkeypatch.setenv("ASSURANCE_BOOTSTRAP_KEY", "test-bootstrap")
    try:
        created = request(
            "POST", "/v1/control/organizations/bootstrap",
            headers={"X-Bootstrap-Key": "test-bootstrap"},
            json={"name": "Assurance Tenant"},
        )
        key = created.json()["credential"]["api_key"]
        headers = {"X-API-Key": key}

        project = request("POST", "/v1/control/projects", headers=headers, json={"name": "AI"})
        asset = request(
            "POST", "/v1/control/assets", headers=headers,
            json={"project_id": project.json()["project_id"], "name": "Agent", "asset_type": "agent"},
        )
        asset_id = asset.json()["asset_id"]
        version = request(
            "POST", f"/v1/control/assets/{asset_id}/versions", headers=headers,
            json={"version": "1.0.0", "environment": "production"},
        )
        version_id = version.json()["version_id"]
        policy = request(
            "POST", "/v1/control/policies", headers=headers,
            json={"name": "Production", "rules": [{"metric": "reliability", "operator": ">=", "threshold": 0.95, "severity": "blocking"}]},
        )
        assert policy.status_code == 201
        bound = request(
            "POST", "/v1/control/policies/bind", headers=headers,
            json={"asset_id": asset_id, "policy_id": policy.json()["policy_id"]},
        )
        assert bound.status_code == 200
        assurance = request(
            "POST", f"/v1/control/assets/{asset_id}/assure", headers=headers,
            json={"version": "1.0.0", "environment": "production", "evaluations": [{"metrics": {"reliability": 0.99}, "passed": True}]},
        )
        assert assurance.status_code == 200
        assurance_id = assurance.json()["assurance_id"]

        check = request("POST", f"/v1/control/assets/{asset_id}/versions/{version_id}/deployment-check", headers=headers)
        assert check.status_code == 200
        assert check.json()["decision"] == "ALLOW"

        passport = request("GET", f"/v1/control/assurance/{assurance_id}/passport", headers=headers)
        assert passport.status_code == 200
        verification = request("POST", "/v1/control/verify/passport", json={"passport": passport.json()})
        assert verification.status_code == 200
        assert verification.json()["passport_valid"] is True
    finally:
        try:
            os.remove(db)
        except FileNotFoundError:
            pass


def test_two_tenants_cannot_cross_access(monkeypatch):
    db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("ASSURANCE_IDENTITY_DB", db)
    monkeypatch.setenv("ASSURANCE_BOOTSTRAP_KEY", "test-bootstrap")
    try:
        a = request("POST", "/v1/control/organizations/bootstrap", headers={"X-Bootstrap-Key": "test-bootstrap"}, json={"organization_id": "tenant-a-" + uuid.uuid4().hex[:8], "name": "Tenant A"}).json()
        b = request("POST", "/v1/control/organizations/bootstrap", headers={"X-Bootstrap-Key": "test-bootstrap"}, json={"organization_id": "tenant-b-" + uuid.uuid4().hex[:8], "name": "Tenant B"}).json()
        ka, kb = a["credential"]["api_key"], b["credential"]["api_key"]
        pa = request("POST", "/v1/control/projects", headers={"X-API-Key": ka}, json={"name": "A Project"}).json()
        aa = request("POST", "/v1/control/assets", headers={"X-API-Key": ka}, json={"project_id": pa["project_id"], "name": "A Agent", "asset_type": "agent"}).json()
        cross_asset = request("GET", f"/v1/control/assets/{aa['asset_id']}", headers={"X-API-Key": kb})
        assert cross_asset.status_code == 404
        policy = request("POST", "/v1/control/policies", headers={"X-API-Key": ka}, json={"name": "A Policy", "rules":[{"metric":"reliability","operator":">=","threshold":.9}]}).json()
        cross_policy = request("POST", "/v1/control/policies/bind", headers={"X-API-Key": kb}, json={"asset_id": aa["asset_id"], "policy_id": policy["policy_id"]})
        assert cross_policy.status_code == 404
    finally:
        try:
            os.remove(db)
        except FileNotFoundError:
            pass
