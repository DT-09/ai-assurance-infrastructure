from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .engine import AssuranceEngine
from .enforcement import (
    EnforcementEngine,
    EnforcementResult,
)
from .evaluation import EvaluationEngine
from .evidence import EvidenceStore
from .impact import DependencyImpactEngine
from .models import (
    AssuranceRecord,
    EvaluationResult,
)
from .passport import AssurancePassport
from .policy_service import PolicyService
from .policy_store import PolicyStore
from .protocol import AssuranceProtocol
from .provenance import ProvenanceService
from .graph import AssuranceGraph
from .registry import AssuranceRegistry
from .store import AssuranceStore
from .trust_state import (
    TrustState,
    TrustStateMachine,
)
from .trust_store import TrustStateStore

from app.control_plane.bridge import (
    AssuranceControlPlaneBridge,
)
from app.control_plane.events import (
    ControlPlaneEventBus,
)
from app.control_plane.service import (
    ControlPlaneService,
)


class AssurancePlatform:
    """
    Unified AI Assurance Control Plane.

    This class is the orchestration boundary for the complete
    assurance infrastructure.

    It connects:

        Control Plane
            +
        Policy
            +
        Evidence
            +
        Evaluation
            +
        Assurance
            +
        Trust State
            +
        Dependency Impact
            +
        Enforcement
            +
        Passport
            +
        Protocol
    """

    VERSION = "platform-1.0.0"

    def __init__(
        self,
        *,
        control_plane: Optional[
            ControlPlaneService
        ] = None,
        assurance_store: Optional[
            AssuranceStore
        ] = None,
        registry: Optional[
            AssuranceRegistry
        ] = None,
        evidence_store: Optional[
            EvidenceStore
        ] = None,
        policy_store: Optional[
            PolicyStore
        ] = None,
        trust_store: Optional[
            TrustStateStore
        ] = None,
        event_bus: Optional[
            ControlPlaneEventBus
        ] = None,
    ):

        self.event_bus = (
            event_bus
            or ControlPlaneEventBus()
        )

        self.control_plane = (
            control_plane
            or ControlPlaneService(
                event_bus=self.event_bus
            )
        )

        self.assurance_store = (
            assurance_store
            or AssuranceStore()
        )

        self.registry = (
            registry
            or AssuranceRegistry()
        )

        self.evidence_store = (
            evidence_store
            or EvidenceStore()
        )

        self.policy_store = (
            policy_store
            or PolicyStore()
        )

        self.trust_store = (
            trust_store
            or TrustStateStore()
        )

        self.trust_machine = (
            TrustStateMachine()
        )

        self.assurance_engine = (
            AssuranceEngine(
                store=self.assurance_store
            )
        )

        self.evaluation_engine = (
            EvaluationEngine(
                evidence_store=self.evidence_store
            )
        )

        self.policy_service = (
            PolicyService(
                self.policy_store
            )
        )

        self.bridge = (
            AssuranceControlPlaneBridge(
                control_plane=self.control_plane,
                assurance_engine=self.assurance_engine,
            )
        )

        self.impact_engine = (
            DependencyImpactEngine(
                self.control_plane
            )
        )

        self.graph = AssuranceGraph()
        self.provenance = ProvenanceService(
            registry=self.registry,
            assurance_store=self.assurance_store,
            evidence_store=self.evidence_store,
            graph=self.graph,
        )

        self.enforcement = (
            EnforcementEngine(
                self.trust_store
            )
        )

        self.event_bus.subscribe(
            self._on_event
        )

    # ---------------------------------------------------------------
    # Persistent trust
    # ---------------------------------------------------------------

    def _transition_to(
        self,
        asset_id: str,
        version_id: str,
        new_state: TrustState,
        *,
        reason: str,
        assurance_id: Optional[str] = None,
        trigger_event_id: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ):

        current = self.trust_store.get_state(
            asset_id,
            version_id,
        )

        if current == new_state:
            return None

        # Rehydrate the in-memory state machine from
        # the persistent transition history.
        machine_state = (
            self.trust_machine.get_state(
                asset_id,
                version_id,
            )
        )

        if machine_state != current:

            history = self.trust_store.history(
                asset_id,
                version_id,
            )

            for transition in history:

                if (
                    self.trust_machine.get_state(
                        asset_id,
                        version_id,
                    )
                    != transition.previous_state
                ):
                    continue

                try:
                    self.trust_machine.transition(
                        asset_id,
                        version_id,
                        transition.new_state,
                        transition.reason,
                        transition.assurance_id,
                        transition.trigger_event_id,
                        transition.metadata,
                    )
                except ValueError:
                    pass

        transition = (
            self.trust_machine.transition(
                asset_id,
                version_id,
                new_state,
                reason,
                assurance_id,
                trigger_event_id,
                metadata,
            )
        )

        self.trust_store.save_transition(
            transition
        )

        return transition

    # ---------------------------------------------------------------
    # Automatic dependency impact -> STALE
    # ---------------------------------------------------------------

    def _on_event(self, event) -> None:

        assurance_events = {
            "dependency.added",
            "dependency.changed",
            "dependency.removed",
        }

        if event.event_type not in assurance_events:
            return

        analysis = (
            self.impact_engine.analyze_event(
                event
            )
        )

        if analysis is None:
            return

        for impacted in (
            analysis.affected_versions
        ):

            self._transition_to(
                impacted.asset_id,
                impacted.version_id,
                TrustState.STALE,
                reason=(
                    "dependency_event:"
                    f"{event.event_type}"
                ),
                trigger_event_id=event.event_id,
                metadata={
                    "impact_reason": (
                        impacted.reason
                    ),
                    "critical": (
                        impacted.critical
                    ),
                    "depth": (
                        impacted.depth
                    ),
                    "blast_radius": (
                        analysis.blast_radius
                    ),
                },
            )

            self.control_plane.record_event(
                "asset_version",
                impacted.version_id,
                "trust.stale",
                {
                    "trigger_event_id": (
                        event.event_id
                    ),
                    "reason": (
                        impacted.reason
                    ),
                    "critical": (
                        impacted.critical
                    ),
                    "depth": (
                        impacted.depth
                    ),
                    "blast_radius": (
                        analysis.blast_radius
                    ),
                    "engine_version": (
                        self.VERSION
                    ),
                },
            )

    # ---------------------------------------------------------------
    # Assurance
    # ---------------------------------------------------------------

    def assure(
        self,
        *,
        asset_id: str,
        version: str,
        environment: str,
        evaluations: Iterable[
            EvaluationResult
        ],
    ) -> AssuranceRecord:

        version_record = next(
            (
                item
                for item in (
                    self.control_plane
                    .store
                    .list_versions(
                        asset_id
                    )
                )
                if (
                    item.version == version
                    and item.environment
                    == environment
                )
            ),
            None,
        )

        if version_record is None:
            raise ValueError(
                "Asset version/environment not found"
            )

        system = (
            self.bridge.build_system_record(
                asset_id,
                version,
                environment,
            )
        )

        self.registry.register(
            system
        )

        self._transition_to(
            asset_id,
            version_record.version_id,
            TrustState.EVALUATING,
            reason=(
                "assurance_evaluation_started"
            ),
        )

        policy = (
            self.policy_service.resolve(
                asset_id=asset_id,
                version_id=(
                    version_record.version_id
                ),
                environment=environment,
            )
        )

        evaluations = list(
            evaluations
        )

        assurance = (
            self.bridge.issue_assurance(
                asset_id=asset_id,
                version=version,
                environment=environment,
                evaluations=evaluations,
                policy=policy,
            )
        )

        state_map = {
            "ASSURED": TrustState.ASSURED,
            "DEGRADED": TrustState.DEGRADED,
            "BLOCKED": TrustState.BLOCKED,
        }

        target_state = state_map.get(
            assurance.verdict.value
        )

        if target_state is not None:

            self._transition_to(
                asset_id,
                version_record.version_id,
                target_state,
                reason=(
                    "assurance:"
                    f"{assurance.verdict.value.lower()}"
                ),
                assurance_id=(
                    assurance.assurance_id
                ),
                metadata={
                    "policy_id": (
                        assurance.policy_id
                    )
                },
            )

        evidence_records = [
            self.evidence_store.get(evidence_id)
            for evidence_id in assurance.evidence_ids
        ]
        evidence_records = [item for item in evidence_records if item is not None]

        self.graph.sync_assurance(
            system=system,
            assurance=assurance,
            evaluations=evaluations,
            evidence=evidence_records,
            policy=policy,
        )

        self.control_plane.store.update_version_status(
            version_record.version_id,
            assurance.verdict.value.lower(),
        )

        self.control_plane.record_event(
            "asset_version",
            version_record.version_id,
            "assurance.updated",
            {
                "assurance_id": (
                    assurance.assurance_id
                ),
                "verdict": (
                    assurance.verdict.value
                ),
                "policy_id": (
                    assurance.policy_id
                ),
                "evaluation_ids": (
                    assurance.evaluation_ids
                ),
            },
        )

        return assurance

    # ---------------------------------------------------------------
    # Trust
    # ---------------------------------------------------------------

    def current_trust(
        self,
        asset_id: str,
        version_id: str,
    ) -> TrustState:

        return self.trust_store.get_state(
            asset_id,
            version_id,
        )

    def trust_history(
        self,
        asset_id: str,
        version_id: str,
    ):

        return self.trust_store.history(
            asset_id,
            version_id,
        )

    # ---------------------------------------------------------------
    # Deployment enforcement
    # ---------------------------------------------------------------

    def deployment_check(
        self,
        *,
        asset_id: str,
        version_id: str,
        environment: str,
    ) -> EnforcementResult:

        return self.enforcement.check(
            asset_id=asset_id,
            version_id=version_id,
            environment=environment,
            action="deployment",
        )

    # ---------------------------------------------------------------
    # Runtime enforcement
    # ---------------------------------------------------------------

    def runtime_check(
        self,
        *,
        asset_id: str,
        version_id: str,
        environment: str,
    ) -> EnforcementResult:

        return self.enforcement.check(
            asset_id=asset_id,
            version_id=version_id,
            environment=environment,
            action="runtime",
        )

    # ---------------------------------------------------------------
    # Emergency revocation
    # ---------------------------------------------------------------

    def revoke(
        self,
        *,
        asset_id: str,
        version_id: str,
        reason: str = "manual_revocation",
    ):

        current = (
            self.trust_store.get_state(
                asset_id,
                version_id,
            )
        )

        if current == TrustState.BLOCKED:
            history = (
                self.trust_store.history(
                    asset_id,
                    version_id,
                )
            )

            return (
                history[-1]
                if history
                else None
            )

        if current == TrustState.UNKNOWN:

            self._transition_to(
                asset_id,
                version_id,
                TrustState.EVALUATING,
                reason=(
                    "revocation_precondition"
                ),
            )

        return self._transition_to(
            asset_id,
            version_id,
            TrustState.BLOCKED,
            reason=reason,
        )

    # ---------------------------------------------------------------
    # Trust Passport
    # ---------------------------------------------------------------

    def passport(
        self,
        assurance_id: str,
    ) -> AssurancePassport:

        assurance = (
            self.assurance_store.get(
                assurance_id
            )
        )

        if assurance is None:
            raise ValueError(
                "Assurance record not found"
            )

        system = (
            self.registry.get(
                assurance.system_id,
                assurance.system_version,
            )
        )

        if system is None:

            system = (
                self.bridge
                .build_system_record(
                    assurance.system_id,
                    assurance.system_version,
                    assurance.environment,
                )
            )

            self.registry.register(
                system
            )

        return AssurancePassport(
            passport_id=(
                "passport_"
                f"{assurance.assurance_id}"
            ),
            assurance_id=(
                assurance.assurance_id
            ),
            system_id=(
                system.system_id
            ),
            system_version=(
                system.version
            ),
            environment=(
                system.environment
            ),
            verdict=(
                assurance.verdict.value
            ),
            metrics=(
                assurance.metrics
            ),
            policy_id=(
                assurance.policy_id
            ),
            evaluation_ids=(
                assurance.evaluation_ids
            ),
            evidence_ids=(
                assurance.evidence_ids
            ),
            reasons=(
                assurance.reasons
            ),
            engine_version=(
                assurance.engine_version
            ),
            created_at=(
                assurance.created_at
            ),
            metadata={
                "platform_version": (
                    self.VERSION
                )
            },
        )

    # ---------------------------------------------------------------
    # Protocol
    # ---------------------------------------------------------------

    def protocol_manifest(
        self,
    ) -> Dict[str, Any]:

        return AssuranceProtocol.manifest()

    def protocol_enforcement(
        self,
        result: EnforcementResult,
    ) -> Dict[str, Any]:

        return AssuranceProtocol.enforcement(
            result
        )