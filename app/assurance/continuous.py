from dataclasses import dataclass
from typing import Callable, List, Optional

from app.assurance.engine import AssuranceEngine
from app.assurance.models import (
    AssuranceRecord,
    EvaluationResult,
    Policy,
)
from app.assurance.impact import (
    DependencyImpactEngine,
    ImpactAnalysis,
)
from app.assurance.policy_store import PolicyStore
from app.control_plane.bridge import AssuranceControlPlaneBridge
from app.control_plane.events import ControlPlaneEventBus
from app.control_plane.models import AuditEvent


@dataclass
class ImpactResult:
    event_id: str
    affected_asset_id: str
    affected_version_id: str
    reason: str
    requires_re_evaluation: bool


@dataclass
class ReEvaluationResult:
    event_id: str
    asset_id: str
    version: str
    environment: str
    verdict: str
    assurance: Optional[AssuranceRecord] = None
    assurance_id: Optional[str] = None
    evaluation_ids: Optional[List[str]] = None
    policy_id: Optional[str] = None


class ContinuousAssuranceEngine:
    VERSION = "continuous-assurance-1.1.0"

    def __init__(
        self,
        control_plane,
        assurance_engine: AssuranceEngine,
        event_bus: Optional[ControlPlaneEventBus] = None,
        evaluator: Optional[
            Callable[[str, str, str], List[EvaluationResult]]
        ] = None,
        policy_store: Optional[PolicyStore] = None,
    ):
        self.control_plane = control_plane
        self.assurance_engine = assurance_engine
        self.event_bus = event_bus or ControlPlaneEventBus()
        self.evaluator = evaluator
        self.policy_store = policy_store

        self.impact_engine = DependencyImpactEngine(
            control_plane
        )

        self.bridge = AssuranceControlPlaneBridge(
            control_plane=control_plane,
            assurance_engine=assurance_engine,
        )

        self._impacts: List[ImpactResult] = []
        self._analyses: List[ImpactAnalysis] = []
        self._reevaluations: List[ReEvaluationResult] = []

        self.event_bus.subscribe(
            self.handle_event
        )

    def _resolve_policy(
        self,
        asset_id: str,
        version_id: str,
        environment: str,
    ) -> Optional[Policy]:
        if self.policy_store is None:
            return None

        return self.policy_store.resolve(
            asset_id=asset_id,
            version_id=version_id,
            environment=environment,
        )

    def handle_event(
        self,
        event: AuditEvent,
    ) -> Optional[ReEvaluationResult]:

        analysis = self.impact_engine.analyze_event(
            event
        )

        if not analysis:
            return None

        self._analyses.append(
            analysis
        )

        if not analysis.affected_versions:
            return None

        first_result: Optional[
            ReEvaluationResult
        ] = None

        plan = (
            self.impact_engine
            .build_re_evaluation_plan(
                analysis
            )
        )

        depth_by_version = {
            item.version_id: item.depth
            for item in analysis.affected_versions
        }

        for target in plan:
            depth = depth_by_version.get(
                target.version_id,
                0,
            )

            impact = ImpactResult(
                event_id=event.event_id,
                affected_asset_id=target.asset_id,
                affected_version_id=target.version_id,
                reason="dependency_changed",
                requires_re_evaluation=True,
            )

            self._impacts.append(
                impact
            )

            self.control_plane.store.update_version_status(
                target.version_id,
                "assurance_stale",
            )

            self.control_plane.record_event(
                "asset_version",
                target.version_id,
                "assurance.stale",
                {
                    "trigger_event_id": event.event_id,
                    "reason": target.reason,
                    "priority": target.priority,
                    "depth": depth,
                    "critical": target.critical,
                    "blast_radius": analysis.blast_radius,
                    "critical_impacts": (
                        analysis.critical_impacts
                    ),
                    "engine_version": self.VERSION,
                },
            )

            if self.evaluator is None:
                continue

            version_record = (
                self.control_plane.store.get_version(
                    target.version_id
                )
            )

            if version_record is None:
                continue

            evaluations = self.evaluator(
                target.asset_id,
                version_record.version,
                version_record.environment,
            )

            policy = self._resolve_policy(
                asset_id=target.asset_id,
                version_id=target.version_id,
                environment=version_record.environment,
            )

            assurance = (
                self.bridge.issue_assurance(
                    asset_id=target.asset_id,
                    version=version_record.version,
                    environment=version_record.environment,
                    evaluations=evaluations,
                    policy=policy,
                )
            )

            status = (
                assurance.verdict.value.lower()
            )

            self.control_plane.store.update_version_status(
                target.version_id,
                status,
            )

            self.control_plane.record_event(
                "asset_version",
                target.version_id,
                "assurance.updated",
                {
                    "trigger_event_id": event.event_id,
                    "assurance_id": (
                        assurance.assurance_id
                    ),
                    "verdict": (
                        assurance.verdict.value
                    ),
                    "evaluation_ids": (
                        assurance.evaluation_ids
                    ),
                    "policy_id": (
                        assurance.policy_id
                    ),
                    "policy_version": (
                        policy.version
                        if policy
                        else None
                    ),
                    "depth": depth,
                    "critical": target.critical,
                    "engine_version": self.VERSION,
                },
            )

            result = ReEvaluationResult(
                event_id=event.event_id,
                asset_id=target.asset_id,
                version=version_record.version,
                environment=version_record.environment,
                verdict=assurance.verdict.value,
                assurance=assurance,
                assurance_id=assurance.assurance_id,
                evaluation_ids=assurance.evaluation_ids,
                policy_id=assurance.policy_id,
            )

            self._reevaluations.append(
                result
            )

            if first_result is None:
                first_result = result

        return first_result

    def resolve_impact(
        self,
        event: AuditEvent,
    ) -> Optional[ImpactResult]:

        analysis = (
            self.impact_engine.analyze_event(
                event
            )
        )

        if (
            not analysis
            or not analysis.affected_versions
        ):
            return None

        target = (
            analysis.affected_versions[0]
        )

        return ImpactResult(
            event_id=event.event_id,
            affected_asset_id=target.asset_id,
            affected_version_id=target.version_id,
            reason="dependency_changed",
            requires_re_evaluation=True,
        )

    def impacts(
        self,
    ) -> List[ImpactResult]:
        return list(
            self._impacts
        )

    def analyses(
        self,
    ) -> List[ImpactAnalysis]:
        return list(
            self._analyses
        )

    def reevaluations(
        self,
    ) -> List[ReEvaluationResult]:
        return list(
            self._reevaluations
        )

    def re_evaluations(
        self,
    ) -> List[ReEvaluationResult]:
        return self.reevaluations()

    def list_impacts(
        self,
    ) -> List[ImpactResult]:
        return self.impacts()

    def list_analyses(
        self,
    ) -> List[ImpactAnalysis]:
        return self.analyses()

    def list_reevaluations(
        self,
    ) -> List[ReEvaluationResult]:
        return self.reevaluations()