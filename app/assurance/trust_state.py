from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class TrustState(str, Enum):
    UNKNOWN = "UNKNOWN"
    EVALUATING = "EVALUATING"
    ASSURED = "ASSURED"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


@dataclass(frozen=True)
class TrustTransition:
    transition_id: str
    asset_id: str
    version_id: str
    previous_state: TrustState
    new_state: TrustState
    reason: str
    assurance_id: Optional[str]
    trigger_event_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: str


class TrustStateMachine:
    VERSION = "trust-state-1.0.0"

    def __init__(self):
        self._states: Dict[str, TrustState] = {}
        self._history: Dict[str, List[TrustTransition]] = {}

    @staticmethod
    def _key(
        asset_id: str,
        version_id: str,
    ) -> str:
        return f"{asset_id}:{version_id}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_state(
        self,
        asset_id: str,
        version_id: str,
    ) -> TrustState:
        return self._states.get(
            self._key(asset_id, version_id),
            TrustState.UNKNOWN,
        )

    def transition(
        self,
        asset_id: str,
        version_id: str,
        new_state: TrustState,
        reason: str,
        assurance_id: Optional[str] = None,
        trigger_event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TrustTransition:
        key = self._key(asset_id, version_id)

        previous = self._states.get(
            key,
            TrustState.UNKNOWN,
        )

        allowed = {
            TrustState.UNKNOWN: {
                TrustState.EVALUATING,
                TrustState.STALE,
            },
            TrustState.EVALUATING: {
                TrustState.ASSURED,
                TrustState.DEGRADED,
                TrustState.BLOCKED,
                TrustState.STALE,
            },
            TrustState.ASSURED: {
                TrustState.EVALUATING,
                TrustState.STALE,
                TrustState.BLOCKED,
                TrustState.DEGRADED,
            },
            TrustState.DEGRADED: {
                TrustState.EVALUATING,
                TrustState.ASSURED,
                TrustState.BLOCKED,
                TrustState.STALE,
            },
            TrustState.BLOCKED: {
                TrustState.EVALUATING,
                TrustState.STALE,
            },
            TrustState.STALE: {
                TrustState.EVALUATING,
                TrustState.BLOCKED,
                TrustState.ASSURED,
                TrustState.DEGRADED,
            },
        }

        if new_state not in allowed[previous]:
            raise ValueError(
                f"Invalid trust transition: "
                f"{previous.value} -> {new_state.value}"
            )

        transition = TrustTransition(
            transition_id=f"trn_{uuid4().hex}",
            asset_id=asset_id,
            version_id=version_id,
            previous_state=previous,
            new_state=new_state,
            reason=reason,
            assurance_id=assurance_id,
            trigger_event_id=trigger_event_id,
            metadata=metadata or {},
            created_at=self._now(),
        )

        self._states[key] = new_state

        self._history.setdefault(
            key,
            [],
        ).append(transition)

        return transition

    def history(
        self,
        asset_id: str,
        version_id: str,
    ) -> List[TrustTransition]:
        return list(
            self._history.get(
                self._key(asset_id, version_id),
                [],
            )
        )
