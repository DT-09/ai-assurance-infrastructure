from dataclasses import dataclass
from typing import Any


@dataclass
class DecisionResult:
    decision: str
    reason: str
    agent_id: str
    tool: str
    action: str
    risk_score: float
    approval_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls(
            decision=data["decision"],
            reason=data["reason"],
            agent_id=data["agent_id"],
            tool=data["tool"],
            action=data["action"],
            risk_score=float(
                data.get("risk_score", 0.0)
            ),
            approval_id=data.get("approval_id"),
        )


@dataclass
class Agent:
    agent_id: str
    organization_id: str
    owner: str
    environment: str
    status: str
    qualification_status: str
    policy: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls(
            agent_id=data["agent_id"],
            organization_id=data["organization_id"],
            owner=data["owner"],
            environment=data["environment"],
            status=data["status"],
            qualification_status=data[
                "qualification_status"
            ],
            policy=data.get("policy", {}),
        )


@dataclass
class Organization:
    organization_id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls(
            organization_id=data["organization_id"],
            name=data["name"],
        )


@dataclass
class Credential:
    credential_id: str
    organization_id: str
    name: str
    created_at: str
    revoked_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls(
            credential_id=data["credential_id"],
            organization_id=data["organization_id"],
            name=data["name"],
            created_at=data["created_at"],
            revoked_at=data.get("revoked_at"),
        )