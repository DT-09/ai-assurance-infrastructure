from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.control_plane.models import AssetVersion, AuditEvent, Dependency


@dataclass
class ImpactedVersion:
    version_id: str
    asset_id: str
    version: str
    environment: str
    depth: int
    critical: bool
    reason: str
    direct: bool = False


@dataclass
class ImpactAnalysis:
    event_id: str
    source_version_id: str
    affected_versions: List[ImpactedVersion] = field(default_factory=list)
    affected_asset_ids: List[str] = field(default_factory=list)
    blast_radius: int = 0
    critical_impacts: int = 0
    max_depth: int = 0
    requires_re_evaluation: bool = False


@dataclass
class ReEvaluationTarget:
    version_id: str
    asset_id: str
    version: str
    environment: str
    priority: str
    critical: bool
    reason: str


class DependencyImpactEngine:
    """
    Dependency impact analysis for the AI assurance control plane.

    dependency.added:
        The downstream consumer is directly affected.
        Downstream dependents are transitively affected.

    dependency.changed / dependency.removed:
        The changed upstream target is identified from the event payload.
        Its downstream dependents are affected.
    """

    VERSION = "dependency-impact-1.2.0"

    ASSURANCE_RELEVANT_EVENTS = {
        "dependency.added",
        "dependency.changed",
        "dependency.removed",
    }

    def __init__(self, control_plane):
        self.control_plane = control_plane

    def analyze_event(
        self,
        event: AuditEvent,
    ) -> ImpactAnalysis | None:

        if event.event_type not in self.ASSURANCE_RELEVANT_EVENTS:
            return None

        if event.event_type == "dependency.added":
            return self._analyze_dependency_added(event)

        return self._analyze_upstream_dependency_change(event)

    def analyze(
        self,
        event_id: str,
        source_version_id: str,
        *,
        include_source: bool = False,
        source_reason: str = "dependency change",
        source_critical: bool = False,
    ) -> ImpactAnalysis:

        source_version = self.control_plane.store.get_version(
            source_version_id
        )

        if source_version is None:
            return ImpactAnalysis(
                event_id=event_id,
                source_version_id=source_version_id,
            )

        affected: Dict[str, ImpactedVersion] = {}

        queue = deque()

        if include_source:
            reason = (
                "critical_dependency_impact"
                if source_critical
                else "noncritical_dependency_impact"
            )

            affected[source_version_id] = ImpactedVersion(
                version_id=source_version.version_id,
                asset_id=source_version.asset_id,
                version=source_version.version,
                environment=source_version.environment,
                depth=1,
                critical=source_critical,
                reason=reason,
                direct=True,
            )

            queue.append(
                (
                    source_version.version_id,
                    1,
                    source_critical,
                )
            )

        else:
            queue.append(
                (
                    source_version.version_id,
                    0,
                    False,
                )
            )

        visited = {source_version_id}

        while queue:

            current_version_id, current_depth, path_critical = (
                queue.popleft()
            )

            dependencies = self.control_plane.store.list_dependents(
                target_version_id=current_version_id
            )

            for dependency in dependencies:

                dependent_version = self.control_plane.store.get_version(
                    dependency.version_id
                )

                if dependent_version is None:
                    continue

                if dependent_version.version_id in visited:
                    continue

                visited.add(dependent_version.version_id)

                depth = current_depth + 1

                critical = bool(
                    path_critical or dependency.critical
                )

                reason = (
                    "critical_dependency_impact"
                    if critical
                    else "noncritical_dependency_impact"
                )

                affected[dependent_version.version_id] = (
                    ImpactedVersion(
                        version_id=dependent_version.version_id,
                        asset_id=dependent_version.asset_id,
                        version=dependent_version.version,
                        environment=dependent_version.environment,
                        depth=depth,
                        critical=critical,
                        reason=reason,
                        direct=False,
                    )
                )

                queue.append(
                    (
                        dependent_version.version_id,
                        depth,
                        critical,
                    )
                )

        affected_versions = sorted(
            affected.values(),
            key=lambda item: (
                not item.critical,
                not item.direct,
                item.depth,
                item.asset_id,
                item.version,
            ),
        )

        affected_asset_ids = sorted(
            {
                item.asset_id
                for item in affected_versions
            }
        )

        critical_impacts = sum(
            1
            for item in affected_versions
            if item.critical
        )

        max_depth = max(
            (
                item.depth
                for item in affected_versions
            ),
            default=0,
        )

        return ImpactAnalysis(
            event_id=event_id,
            source_version_id=source_version_id,
            affected_versions=affected_versions,
            affected_asset_ids=affected_asset_ids,
            blast_radius=len(affected_versions),
            critical_impacts=critical_impacts,
            max_depth=max_depth,
            requires_re_evaluation=bool(affected_versions),
        )

    def _analyze_dependency_added(
        self,
        event: AuditEvent,
    ) -> ImpactAnalysis:

        consumer_version_id = event.entity_id

        dependency = self._dependency_from_event(event)

        critical = (
            dependency.critical
            if dependency is not None
            else False
        )

        return self.analyze(
            event_id=event.event_id,
            source_version_id=consumer_version_id,
            include_source=True,
            source_reason=(
                "critical_dependency_impact"
                if critical
                else "noncritical_dependency_impact"
            ),
            source_critical=critical,
        )

    def _analyze_upstream_dependency_change(
        self,
        event: AuditEvent,
    ) -> ImpactAnalysis:

        payload = event.payload or {}

        target_version_id = payload.get(
            "target_version_id"
        )

        if target_version_id:

            return self.analyze(
                event_id=event.event_id,
                source_version_id=target_version_id,
            )

        target_asset_id = payload.get(
            "target_asset_id"
        )

        if target_asset_id:

            versions = self.control_plane.store.list_versions(
                target_asset_id
            )

            combined: ImpactAnalysis | None = None

            for version in versions:

                analysis = self.analyze(
                    event_id=event.event_id,
                    source_version_id=version.version_id,
                )

                if combined is None:
                    combined = analysis
                    continue

                combined.affected_versions.extend(
                    analysis.affected_versions
                )

                combined.affected_asset_ids = sorted(
                    set(combined.affected_asset_ids)
                    | set(analysis.affected_asset_ids)
                )

            if combined is not None:

                combined.affected_versions = (
                    self._deduplicate_impacts(
                        combined.affected_versions
                    )
                )

                combined.blast_radius = len(
                    combined.affected_versions
                )

                combined.critical_impacts = sum(
                    1
                    for item in combined.affected_versions
                    if item.critical
                )

                combined.max_depth = max(
                    (
                        item.depth
                        for item in combined.affected_versions
                    ),
                    default=0,
                )

                combined.requires_re_evaluation = bool(
                    combined.affected_versions
                )

                return combined

        return ImpactAnalysis(
            event_id=event.event_id,
            source_version_id=event.entity_id,
        )

    def build_re_evaluation_plan(
        self,
        analysis: ImpactAnalysis,
    ) -> List[ReEvaluationTarget]:

        plan: List[ReEvaluationTarget] = []

        for item in analysis.affected_versions:

            if item.critical and item.direct:
                priority = "critical"

            elif item.critical:
                priority = "high"

            elif item.direct:
                priority = "normal"

            else:
                priority = "low"

            plan.append(
                ReEvaluationTarget(
                    version_id=item.version_id,
                    asset_id=item.asset_id,
                    version=item.version,
                    environment=item.environment,
                    priority=priority,
                    critical=item.critical,
                    reason=item.reason,
                )
            )

        priority_order = {
            "critical": 0,
            "high": 1,
            "normal": 2,
            "low": 3,
        }

        plan.sort(
            key=lambda item: (
                priority_order[item.priority],
                item.version_id,
            )
        )

        return plan

    def _dependency_from_event(
        self,
        event: AuditEvent,
    ) -> Dependency | None:

        dependency_id = (
            event.payload or {}
        ).get("dependency_id")

        if dependency_id:

            dependency = (
                self.control_plane.store.get_dependency(
                    dependency_id
                )
            )

            if dependency:
                return dependency

        dependencies = (
            self.control_plane.store.list_dependencies(
                event.entity_id
            )
        )

        if not dependencies:
            return None

        target_version_id = (
            event.payload or {}
        ).get("target_version_id")

        if target_version_id:

            for dependency in dependencies:

                if (
                    dependency.target_version_id
                    == target_version_id
                ):
                    return dependency

        return dependencies[-1]

    @staticmethod
    def _deduplicate_impacts(
        impacts: List[ImpactedVersion],
    ) -> List[ImpactedVersion]:

        merged: Dict[str, ImpactedVersion] = {}

        for item in impacts:

            existing = merged.get(
                item.version_id
            )

            if existing is None:
                merged[item.version_id] = item
                continue

            existing.critical = (
                existing.critical
                or item.critical
            )

            existing.direct = (
                existing.direct
                or item.direct
            )

            existing.depth = min(
                existing.depth,
                item.depth,
            )

            if existing.critical:
                existing.reason = (
                    "critical_dependency_impact"
                )

        return sorted(
            merged.values(),
            key=lambda item: (
                not item.critical,
                not item.direct,
                item.depth,
                item.asset_id,
                item.version,
            ),
        )
