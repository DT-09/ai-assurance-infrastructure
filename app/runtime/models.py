from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class AuthorityContract:
    agent_id: str
    version: str
    environment: str = "production"
    allowed_actions: set[str] = field(default_factory=set)
    allowed_tools: set[str] = field(default_factory=set)
    allowed_data_classes: set[str] = field(default_factory=set)
    denied_actions: set[str] = field(default_factory=set)
    approval_required_for: set[str] = field(default_factory=set)
    max_transaction_usd: float | None = None
    allowed_destinations: set[str] = field(default_factory=set)
    purpose: str = ""
    contract_version: str = "1"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthorityContract":
        def s(name: str) -> set[str]:
            value = data.get(name) or []
            if isinstance(value, str):
                value = [value]
            return {str(x).strip().lower() for x in value if str(x).strip()}

        return cls(
            agent_id=str(data.get("agent_id", "")),
            version=str(data.get("version", "")),
            environment=str(data.get("environment", "production")),
            allowed_actions=s("allowed_actions"),
            allowed_tools=s("allowed_tools"),
            allowed_data_classes=s("allowed_data_classes"),
            denied_actions=s("denied_actions"),
            approval_required_for=s("approval_required_for"),
            max_transaction_usd=(float(data["max_transaction_usd"]) if data.get("max_transaction_usd") is not None else None),
            allowed_destinations=s("allowed_destinations"),
            purpose=str(data.get("purpose", "")),
            contract_version=str(data.get("contract_version", "1")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "environment": self.environment,
            "allowed_actions": sorted(self.allowed_actions),
            "allowed_tools": sorted(self.allowed_tools),
            "allowed_data_classes": sorted(self.allowed_data_classes),
            "denied_actions": sorted(self.denied_actions),
            "approval_required_for": sorted(self.approval_required_for),
            "max_transaction_usd": self.max_transaction_usd,
            "allowed_destinations": sorted(self.allowed_destinations),
            "purpose": self.purpose,
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True)
class ActionRequest:
    agent_id: str
    agent_version: str
    action: str
    tool: str
    target: str = ""
    data_classes: set[str] = field(default_factory=set)
    amount_usd: float | None = None
    destination: str = ""
    trace_id: str = ""
    intent: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    requested_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionRequest":
        raw = data.get("data_classes") or []
        if isinstance(raw, str): raw = [raw]
        return cls(
            agent_id=str(data.get("agent_id", "")),
            agent_version=str(data.get("agent_version", data.get("version", ""))),
            action=str(data.get("action", "")),
            tool=str(data.get("tool", "")),
            target=str(data.get("target", "")),
            data_classes={str(x).lower() for x in raw},
            amount_usd=(float(data["amount_usd"]) if data.get("amount_usd") is not None else None),
            destination=str(data.get("destination", "")),
            trace_id=str(data.get("trace_id", "")),
            intent=str(data.get("intent", "")),
            context=dict(data.get("context") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "action": self.action,
            "tool": self.tool,
            "target": self.target,
            "data_classes": sorted(self.data_classes),
            "amount_usd": self.amount_usd,
            "destination": self.destination,
            "trace_id": self.trace_id,
            "intent": self.intent,
            "context": self.context,
            "requested_at": self.requested_at,
        }


@dataclass(frozen=True)
class RuntimeDecisionRecord:
    decision_id: str
    decision: RuntimeDecision
    action: ActionRequest
    reasons: list[str]
    policy_version: str
    contract_hash: str
    evidence_hash: str
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision": self.decision.value,
            "action": self.action.to_dict(),
            "reasons": self.reasons,
            "policy_version": self.policy_version,
            "contract_hash": self.contract_hash,
            "evidence_hash": self.evidence_hash,
            "created_at": self.created_at,
        }
