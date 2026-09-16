import asyncio
import httpx

from app.main import app
from app.assurance.passport import AssurancePassport
from app.assurance.protocol import AssuranceProtocol


def passport():
    return AssurancePassport(
        passport_id="p_public",
        assurance_id="a_public",
        system_id="agent_public",
        system_version="1.0.0",
        environment="production",
        verdict="ASSURED",
        metrics={"reliability": 99.0},
        policy_id="policy_public",
        evaluation_ids=["eval_public"],
        evidence_ids=["evidence_public"],
        reasons=["passed"],
        engine_version="3.3.0",
    ).to_dict()


def post(path, payload):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(path, json=payload)
    return asyncio.run(run())


def test_public_passport_verification():
    response = post("/v1/verify/passport", {"passport": passport()})
    assert response.status_code == 200
    assert response.json()["passport_valid"] is True


def test_protocol_conformance_endpoint():
    envelope = AssuranceProtocol.envelope("identity.asset", {"system_id": "agent_public"})
    response = post("/v1/protocol/conformance", envelope)
    assert response.status_code == 200
    assert response.json()["conformant"] is True
