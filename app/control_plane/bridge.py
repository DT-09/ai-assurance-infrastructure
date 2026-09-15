from __future__ import annotations

from typing import Any, Dict, Optional

from app.assurance.engine import AssuranceEngine
from app.assurance.models import (
    AssuranceRecord,
    EvaluationResult,
    Policy,
    SystemRecord,
)

from .service import ControlPlaneService


class AssuranceControlPlaneBridge:
    """
    Connects canonical Control Plane assets to Assurance Core.

    Control Plane owns:
        organization
        project
        AI asset
        version
        environment
        dependencies
        lifecycle

    Assurance Core owns:
        evidence
        evaluation
        policy
        assurance
        passport
        verification
        provenance
    """

    def __init__(
        self,
        control_plane: ControlPlaneService,
        assurance_engine: AssuranceEngine,
    ):
        self.control_plane = control_plane
        self.assurance_engine = assurance_engine

    def build_system_record(
        self,
        asset_id: str,
        version: str,
        environment: str,
    ) -> SystemRecord:
        asset = self.control_plane.store.get_asset(asset_id)

        if not asset:
            raise ValueError("AI asset not found")

        versions = self.control_plane.store.list_versions(asset_id)

        matching = next(
            (
                item
                for item in versions
                if item.version == version
                and item.environment == environment
            ),
            None,
        )

        if not matching:
            raise ValueError(
                "Asset version/environment not found"
            )

        return SystemRecord(
            system_id=asset.asset_id,
            name=asset.name,
            system_type=asset.asset_type,
            version=matching.version,
            environment=matching.environment,
            model=matching.model,
            framework=matching.framework,
            owner=asset.owner,
            metadata={
                **asset.metadata,
                "project_id": asset.project_id,
                "control_plane_version_id": matching.version_id,
            },
        )

    def issue_assurance(
        self,
        asset_id: str,
        version: str,
        environment: str,
        evaluations: list[EvaluationResult],
        policy: Optional[Policy] = None,
    ) -> AssuranceRecord:
        system = self.build_system_record(
            asset_id=asset_id,
            version=version,
            environment=environment,
        )

        return self.assurance_engine.issue(
            system=system,
            evaluations=evaluations,
            policy=policy,
        )

    def get_control_plane_context(
        self,
        asset_id: str,
    ) -> Dict[str, Any]:
        asset = self.control_plane.store.get_asset(asset_id)

        if not asset:
            raise ValueError("AI asset not found")

        versions = self.control_plane.store.list_versions(asset_id)

        result = {
            "asset": asset,
            "versions": [],
        }

        for version in versions:
            result["versions"].append(
                {
                    "version": version,
                    "dependencies": (
                        self.control_plane.store.list_dependencies(
                            version.version_id
                        )
                    ),
                }
            )

        return result
