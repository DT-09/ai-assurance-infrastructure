import os

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .approvals import ApprovalStatus, ApprovalStore
from .audit import AuditLog
from .auth import require_api_key
from .control import evaluate_control
from .identity import revoke_agent, suspend_agent
from .models import (
    Agent,
    AgentAction,
    AuditEvent,
    Organization,
)
from .registry import AgentRegistry
from .storage import SQLiteStorage
from app.assurance.platform import AssurancePlatform
from app.control_plane.public_api import router as control_plane_router


app = FastAPI(
    title="AI Agent Trust & Control Plane",
    version="1.3.0",
)

audit_log = AuditLog()
registry = AgentRegistry()
approval_store = ApprovalStore()
storage = SQLiteStorage()
assurance_platform = AssurancePlatform()
app.include_router(control_plane_router)
app.state.assurance_platform = assurance_platform


class OrganizationCreateRequest(BaseModel):
    organization_id: str = Field(
        min_length=2,
        max_length=100,
    )
    name: str = Field(
        min_length=2,
        max_length=200,
    )


class CredentialCreateRequest(BaseModel):
    name: str = Field(
        default="default",
        min_length=1,
        max_length=100,
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-agent-trust-control-plane",
        "version": "1.3.0",
    }


# -------------------------
# Bootstrap
# -------------------------

@app.post("/api/setup/organization")
def setup_organization(
    request: OrganizationCreateRequest,
):
    bootstrap_key = os.getenv(
        "GATEWAY_BOOTSTRAP_KEY"
    )

    if not bootstrap_key:
        raise HTTPException(
            status_code=500,
            detail="Gateway bootstrap credentials are not configured",
        )

    supplied_key = os.getenv(
        "GATEWAY_BOOTSTRAP_REQUEST_KEY"
    )

    if supplied_key != bootstrap_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid bootstrap credential",
        )

    existing = storage.get_organization(
        request.organization_id
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Organization "
                f"'{request.organization_id}' "
                f"already exists"
            ),
        )

    organization = Organization(
        organization_id=request.organization_id,
        name=request.name,
    )

    storage.save_organization(
        organization
    )

    credential, api_key = storage.create_credential(
        organization_id=organization.organization_id,
        name="initial",
    )

    return {
        "status": "created",
        "organization": organization,
        "credential": credential,
        "api_key": api_key,
        "warning": (
            "Store this API key securely. "
            "It will not be returned again."
        ),
    }


# -------------------------
# Organizations
# -------------------------

@app.get("/api/organization")
def get_organization(
    organization_id: str = Depends(require_api_key),
):
    organization = storage.get_organization(
        organization_id
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization


# -------------------------
# Credentials
# -------------------------

@app.post("/api/credentials")
def create_credential(
    request: CredentialCreateRequest,
    organization_id: str = Depends(require_api_key),
):
    organization = storage.get_organization(
        organization_id
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    credential, api_key = storage.create_credential(
        organization_id=organization_id,
        name=request.name,
    )

    return {
        "credential": credential,
        "api_key": api_key,
        "warning": (
            "Store this API key securely. "
            "It will not be returned again."
        ),
    }


@app.get("/api/credentials")
def get_credentials(
    organization_id: str = Depends(require_api_key),
):
    credentials = (
        storage.get_credentials_for_organization(
            organization_id
        )
    )

    return {
        "credentials": credentials,
        "count": len(credentials),
    }


@app.post("/api/credentials/{credential_id}/revoke")
def revoke_credential(
    credential_id: str,
    organization_id: str = Depends(require_api_key),
):
    credential = storage.get_credential(
        credential_id
    )

    if credential is None:
        raise HTTPException(
            status_code=404,
            detail="Credential not found",
        )

    if credential.organization_id != organization_id:
        raise HTTPException(
            status_code=404,
            detail="Credential not found",
        )

    revoked = storage.revoke_credential(
        credential_id
    )

    return {
        "status": "revoked",
        "credential": revoked,
    }


# -------------------------
# Agents
# -------------------------

@app.post("/api/agents")
def register_agent(
    agent: Agent,
    organization_id: str = Depends(require_api_key),
):
    if agent.organization_id != organization_id:
        raise HTTPException(
            status_code=403,
            detail="Agent organization does not match API credential",
        )

    if storage.get_organization(
        organization_id
    ) is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    if registry.get(agent.agent_id) is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Agent '{agent.agent_id}' "
                f"already exists"
            ),
        )

    registry.register(agent)

    return {
        "status": "registered",
        "agent": agent,
    }


@app.get("/api/agents")
def get_agents(
    organization_id: str = Depends(require_api_key),
):
    agents = registry.all()

    organization_agents = [
        agent
        for agent in agents.values()
        if agent.organization_id == organization_id
    ]

    return {
        "agents": organization_agents,
        "count": len(organization_agents),
    }


@app.get("/api/agents/{agent_id}")
def get_agent(
    agent_id: str,
    organization_id: str = Depends(require_api_key),
):
    agent = registry.get(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.organization_id != organization_id:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    return agent


@app.post("/api/agents/{agent_id}/suspend")
def suspend(
    agent_id: str,
    organization_id: str = Depends(require_api_key),
):
    agent = registry.get(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.organization_id != organization_id:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    suspend_agent(agent)
    registry.register(agent)

    return {
        "status": "suspended",
        "agent_id": agent_id,
        "agent_status": agent.status,
    }


@app.post("/api/agents/{agent_id}/revoke")
def revoke(
    agent_id: str,
    organization_id: str = Depends(require_api_key),
):
    agent = registry.get(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.organization_id != organization_id:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    revoke_agent(agent)
    registry.register(agent)

    return {
        "status": "revoked",
        "agent_id": agent_id,
        "agent_status": agent.status,
    }


@app.post("/api/agents/{agent_id}/qualification")
def set_qualification(
    agent_id: str,
    qualification_status: str,
    organization_id: str = Depends(require_api_key),
):
    agent = registry.get(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    if agent.organization_id != organization_id:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )

    agent.qualification_status = qualification_status
    registry.register(agent)

    return {
        "status": "updated",
        "agent_id": agent_id,
        "qualification_status": (
            agent.qualification_status
        ),
    }


# -------------------------
# Gateway
# -------------------------

@app.post("/api/control/evaluate")
def control_evaluate(
    action: AgentAction,
    organization_id: str = Depends(require_api_key),
):
    agent = registry.get(action.agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{action.agent_id}' not found",
        )

    if agent.organization_id != organization_id:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{action.agent_id}' not found",
        )

    result = evaluate_control(
        action=action,
        agent=agent,
        approval_store=approval_store,
    )

    audit_log.record(
        AuditEvent(
            agent_id=action.agent_id,
            tool=action.tool,
            action=action.action,
            decision=result.decision,
            reason=result.reason,
            risk_score=result.risk_score,
            approval_id=result.approval_id,
        )
    )

    return result


# -------------------------
# Approvals
# -------------------------

@app.get("/api/approvals")
def get_approvals(
    organization_id: str = Depends(require_api_key),
):
    requests = approval_store.all()

    organization_agent_ids = {
        agent.agent_id
        for agent in registry.all().values()
        if agent.organization_id == organization_id
    }

    organization_requests = [
        request
        for request in requests
        if request.action.agent_id
        in organization_agent_ids
    ]

    return {
        "approvals": [
            request.to_dict()
            for request in organization_requests
        ],
        "count": len(organization_requests),
    }


@app.get("/api/approvals/{approval_id}")
def get_approval(
    approval_id: str,
    organization_id: str = Depends(require_api_key),
):
    request = approval_store.get(
        approval_id
    )

    if request is None:
        raise HTTPException(
            status_code=404,
            detail=f"Approval '{approval_id}' not found",
        )

    agent = registry.get(
        request.action.agent_id
    )

    if (
        agent is None
        or agent.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Approval '{approval_id}' not found",
        )

    return request.to_dict()


@app.post("/api/approvals/{approval_id}/approve")
def approve(
    approval_id: str,
    organization_id: str = Depends(require_api_key),
):
    request = approval_store.get(
        approval_id
    )

    if request is None:
        raise HTTPException(
            status_code=404,
            detail=f"Approval '{approval_id}' not found",
        )

    agent = registry.get(
        request.action.agent_id
    )

    if (
        agent is None
        or agent.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Approval '{approval_id}' not found",
        )

    if request.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Approval is already "
                f"{request.status}"
            ),
        )

    request.approve()
    approval_store.update(request)

    return request.to_dict()


@app.post("/api/approvals/{approval_id}/reject")
def reject(
    approval_id: str,
    organization_id: str = Depends(require_api_key),
):
    request = approval_store.get(
        approval_id
    )

    if request is None:
        raise HTTPException(
            status_code=404,
            detail=f"Approval '{approval_id}' not found",
        )

    agent = registry.get(
        request.action.agent_id
    )

    if (
        agent is None
        or agent.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Approval '{approval_id}' not found",
        )

    if request.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Approval is already "
                f"{request.status}"
            ),
        )

    request.reject()
    approval_store.update(request)

    return request.to_dict()


# -------------------------
# Audit
# -------------------------

@app.get("/api/gateway/audit")
def audit(
    organization_id: str = Depends(require_api_key),
):
    organization_agent_ids = {
        agent.agent_id
        for agent in registry.all().values()
        if agent.organization_id == organization_id
    }

    events = [
        event
        for event in audit_log.all()
        if event.agent_id in organization_agent_ids
    ]

    return {
        "events": events,
        "count": len(events),
    }
# -------------------------
# VA Health Systems Technology Integrator profile
# -------------------------
from va_health_integrator import VAHealthIntegrator

_va_hsti = VAHealthIntegrator()

@app.get('/v1/va-hsti/profile')
def va_hsti_profile():
    return {
        'profile': 'VA-HSTI-2026',
        'rfi': '36C10G26Q0087',
        'role': 'AI assurance, governance, evidence and integration component',
        'capabilities': [
            'canonical clinical normalization', 'X12 837/835/834/278/270/271 normalization',
            'identity/eligibility/attribution', 'financial reconciliation',
            'AI validation/monitoring/reversibility', 'security/ATO evidence',
            'portable transition evidence'
        ],
        'live_system_adapters_required': True,
    }

@app.post('/v1/va-hsti/assess')
def va_hsti_assess(body: dict, organization_id: str = Depends(require_api_key)):
    result = _va_hsti.assess(body)
    result['organization_id'] = organization_id
    return result
