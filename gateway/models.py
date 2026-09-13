from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


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


class DecisionResult(BaseModel):
    decision: Decision
    reason: str
    agent_id: str
    tool: str
    action: str


class AuditEvent(BaseModel):
    agent_id: str
    tool: str
    action: str
    decision: Decision
    reason: str
