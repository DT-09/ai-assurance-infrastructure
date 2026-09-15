from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class Organization(BaseModel):
    organization_id: str
    name: str


class Credential(BaseModel):
    credential_id: str
    organization_id: str
    name: str
    created_at: str
    revoked_at: str | None = None


class AgentAction(BaseModel):
    agent_id: str
    tool: str
    action: str
    parameters: dict = Field(default_factory=dict)


class Policy(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    approval_tools: list[str] = Field(default_factory=list)

    max_transaction_usd: float | None = None

    blocked_actions: list[str] = Field(default_factory=list)
    approval_actions: list[str] = Field(default_factory=list)


class Agent(BaseModel):
    agent_id: str
    organization_id: str
    owner: str
    environment: str
    status: AgentStatus = AgentStatus.ACTIVE
    qualification_status: str = "NOT_QUALIFIED"
    policy: Policy = Field(default_factory=Policy)


class DecisionResult(BaseModel):
    decision: Decision
    reason: str
    agent_id: str
    tool: str
    action: str
    risk_score: float = 0.0
    approval_id: str | None = None


class AuditEvent(BaseModel):
    agent_id: str
    tool: str
    action: str
    decision: Decision
    reason: str
    risk_score: float = 0.0
    approval_id: str | None = None