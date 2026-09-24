from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .gateway import RuntimeGateway, generate_attack_paths
from .models import ActionRequest, AuthorityContract
from .store import RuntimeStore

router = APIRouter(prefix="", tags=["runtime-enforcement"])
store = RuntimeStore()
gateway = RuntimeGateway(store)


@router.post("/contracts")
def register_contract(body: dict):
    try:
        contract = AuthorityContract.from_dict(body)
        return gateway.register_contract(contract)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/contracts/{agent_id}/{version}")
def get_contract(agent_id: str, version: str):
    contract = gateway.get_contract(agent_id, version)
    if not contract:
        raise HTTPException(404, "Authority contract not found")
    return {"contract": contract.to_dict(), "attack_paths": generate_attack_paths(contract)}


@router.post("/agent-authorize")
def authorize(body: dict):
    try:
        request = ActionRequest.from_dict(body)
        record = gateway.authorize(request, approval_id=body.get("approval_id"))
        return record.to_dict()
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/approve/{decision_id}")
def approve(decision_id: str, body: dict):
    try:
        return gateway.approve(decision_id, str(body.get("approver", "")))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/authorize-and-execute")
def authorize_and_execute(body: dict):
    """Demo/local execution boundary. Production adapters should call authorize before invoking their real tool."""
    request = ActionRequest.from_dict(body)
    tool = request.tool.lower()
    if tool not in {"demo_payments", "demo_crm"}:
        record = gateway.authorize(request, approval_id=body.get("approval_id"))
        return {"executed": False, "decision": record.to_dict(), "note": "No arbitrary remote execution is performed by the AAI server. Integrate the SDK/gateway with the customer's tool adapter."}

    def executor(req: ActionRequest):
        if tool == "demo_payments":
            return {"tool": "demo_payments", "action": req.action, "amount_usd": req.amount_usd, "target": req.target, "status": "simulated-side-effect"}
        return {"tool": "demo_crm", "action": req.action, "target": req.target, "status": "simulated-side-effect"}

    return gateway.execute(request, executor, approval_id=body.get("approval_id"))


@router.get("/decisions")
def decisions(limit: int = 100):
    return {"decisions": store.list_decisions(max(1, min(limit, 500)))}


@router.post("/verify-evidence")
def verify_evidence(body: dict):
    return {"valid": store.verify_evidence(body)}


@router.post("/attack-plan")
def attack_plan(body: dict):
    contract = AuthorityContract.from_dict(body)
    return {"agent_id": contract.agent_id, "version": contract.version, "attack_paths": generate_attack_paths(contract)}
