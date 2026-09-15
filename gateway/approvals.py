from datetime import datetime, timezone
from uuid import uuid4

from .models import AgentAction
from .storage import SQLiteStorage


class ApprovalStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequest:
    def __init__(
        self,
        action: AgentAction,
        reason: str,
        approval_id: str | None = None,
        status: str = ApprovalStatus.PENDING,
        created_at: str | None = None,
        resolved_at: str | None = None,
    ):
        self.approval_id = approval_id or str(uuid4())
        self.action = action
        self.reason = reason
        self.status = status
        self.created_at = (
            created_at
            or datetime.now(timezone.utc).isoformat()
        )
        self.resolved_at = resolved_at

    def approve(self) -> None:
        self.status = ApprovalStatus.APPROVED
        self.resolved_at = datetime.now(timezone.utc).isoformat()

    def reject(self) -> None:
        self.status = ApprovalStatus.REJECTED
        self.resolved_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "agent_id": self.action.agent_id,
            "tool": self.action.tool,
            "action": self.action.action,
            "parameters": self.action.parameters,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict):
        action = AgentAction(
            agent_id=data["agent_id"],
            tool=data["tool"],
            action=data["action"],
            parameters=data.get("parameters", {}),
        )

        return cls(
            action=action,
            reason=data["reason"],
            approval_id=data["approval_id"],
            status=data["status"],
            created_at=data["created_at"],
            resolved_at=data.get("resolved_at"),
        )


class ApprovalStore:
    def __init__(self, database_path: str = "gateway.db"):
        self.storage = SQLiteStorage(database_path)

    def create(
        self,
        action: AgentAction,
        reason: str,
    ) -> ApprovalRequest:
        request = ApprovalRequest(action, reason)

        self.storage.save_approval(
            request.approval_id,
            request.to_dict(),
        )

        return request

    def get(self, approval_id: str) -> ApprovalRequest | None:
        data = self.storage.get_approval(approval_id)

        if data is None:
            return None

        return ApprovalRequest.from_dict(data)

    def all(self) -> list[ApprovalRequest]:
        return [
            ApprovalRequest.from_dict(data)
            for data in self.storage.get_all_approvals()
        ]

    def update(self, request: ApprovalRequest) -> None:
        self.storage.save_approval(
            request.approval_id,
            request.to_dict(),
        )