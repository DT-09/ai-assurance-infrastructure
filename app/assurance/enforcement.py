from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from .trust_state import TrustState
from .trust_store import TrustStateStore


class EnforcementDecision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    DENY = "DENY"


@dataclass(frozen=True)
class EnforcementResult:
    decision: EnforcementDecision
    trust_state: TrustState
    asset_id: str
    version_id: str
    environment: str
    assurance_id: Optional[str] = None
    policy_id: Optional[str] = None
    reasons: list[str] = field(default_factory=list)
    action: str = "deployment"
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "trust_state": self.trust_state.value,
            "asset_id": self.asset_id,
            "version_id": self.version_id,
            "environment": self.environment,
            "assurance_id": self.assurance_id,
            "policy_id": self.policy_id,
            "reasons": list(self.reasons),
            "action": self.action,
            "created_at": self.created_at,
        }


class EnforcementEngine:
    """
    Converts persistent AI trust state into an operational
    deployment/runtime decision.

    ASSURED  -> ALLOW
    DEGRADED -> REVIEW
    everything else -> DENY
    """

    VERSION = "enforcement-1.0.0"

    def __init__(
        self,
        trust_store: Optional[TrustStateStore] = None,
    ):
        self.trust_store = (
            trust_store or TrustStateStore()
        )

    @staticmethod
    def decision_for_state(
        state: TrustState,
    ) -> EnforcementDecision:

        if state == TrustState.ASSURED:
            return EnforcementDecision.ALLOW

        if state == TrustState.DEGRADED:
            return EnforcementDecision.REVIEW

        return EnforcementDecision.DENY

    def check(
        self,
        *,
        asset_id: str,
        version_id: str,
        environment: str,
        action: str = "deployment",
        assurance_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        reasons: Optional[list[str]] = None,
    ) -> EnforcementResult:

        state = self.trust_store.get_state(
            asset_id,
            version_id,
        )

        return EnforcementResult(
            decision=self.decision_for_state(state),
            trust_state=state,
            asset_id=asset_id,
            version_id=version_id,
            environment=environment,
            assurance_id=assurance_id,
            policy_id=policy_id,
            reasons=reasons or [],
            action=action,
        )