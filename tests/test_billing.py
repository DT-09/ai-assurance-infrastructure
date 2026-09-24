import hashlib
import hmac
import json
import os
import tempfile
import time

import httpx

from app.billing import BillingStore, StripeBilling
from app.control_plane.identity import IdentityStore
from app.main import app


def request(method, path, headers=None, json=None):
    import asyncio
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=json)
    return asyncio.run(run())


def test_plans_are_public():
    response = request("GET", "/v1/billing/plans")
    assert response.status_code == 200
    assert {p["key"] for p in response.json()["plans"]} == {"developer", "production"}


def test_billing_account_and_usage():
    db = tempfile.mktemp(suffix=".db")
    store = BillingStore(db)
    account = store.get_account("org_test")
    assert account["plan"] == "developer"
    usage = store.increment_usage("org_test", "evaluations", 2)
    assert usage["evaluations"] == 2
    os.remove(db)


def test_webhook_signature():
    db = tempfile.mktemp(suffix=".db")
    store = BillingStore(db)
    billing = StripeBilling(store)
    secret = "whsec_test"
    billing.webhook_secret = secret
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {"metadata": {"organization_id": "org_test", "plan": "growth"}, "customer": "cus_1", "subscription": "sub_1"}}}).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    assert billing.verify_webhook(payload, f"t={timestamp},v1={digest}")
    result = billing.handle_webhook(json.loads(payload))
    assert result["handled"] is True
    assert store.get_account("org_test")["plan"] == "growth"
    os.remove(db)


def test_billing_account_endpoint(monkeypatch):
    db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("ASSURANCE_IDENTITY_DB", db)
    monkeypatch.setenv("ASSURANCE_BOOTSTRAP_KEY", "test-bootstrap")
    original = app.state.identity_store
    app.state.identity_store = IdentityStore(db)
    try:
        created = request("POST", "/v1/control/organizations/bootstrap", headers={"X-Bootstrap-Key": "test-bootstrap"}, json={"name": "Billing Tenant"})
        assert created.status_code == 201
        key = created.json()["credential"]["api_key"]
        response = request("GET", "/v1/billing/account", headers={"X-API-Key": key})
        assert response.status_code == 200
        assert response.json()["account"]["plan"] == "developer"
    finally:
        app.state.identity_store = original
        try:
            os.remove(db)
        except FileNotFoundError:
            pass
