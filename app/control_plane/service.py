from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

from .events import ControlPlaneEventBus
from .models import (
    AIAsset,
    AssetVersion,
    AuditEvent,
    Dependency,
    Organization,
    Project,
)
from .store import ControlPlaneStore


class ControlPlaneService:
    def __init__(
        self,
        store: ControlPlaneStore | None = None,
        event_bus: ControlPlaneEventBus | None = None,
    ):
        self.store = store or ControlPlaneStore()
        self.event_bus = event_bus or ControlPlaneEventBus()

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    def record_event(
        self,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=self._id("evt"),
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            payload=payload,
        )

        self.store.save_event(event)
        self.event_bus.publish(event)

        return event

    def _event(
        self,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> AuditEvent:
        return self.record_event(
            entity_type,
            entity_id,
            event_type,
            payload,
        )

    def create_organization(
        self,
        name: str,
        metadata: Dict[str, Any] | None = None,
        organization_id: str | None = None,
    ) -> Organization:
        if organization_id and self.store.get_organization(organization_id):
            raise ValueError("Organization already exists")

        item = Organization(
            organization_id=organization_id or self._id("org"),
            name=name,
            metadata=metadata or {},
        )

        self.store.save_organization(item)

        self.record_event(
            "organization",
            item.organization_id,
            "organization.created",
            {"name": item.name},
        )

        return item

    def create_project(
        self,
        organization_id: str,
        name: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Project:
        if not self.store.get_organization(organization_id):
            raise ValueError("Organization not found")

        item = Project(
            project_id=self._id("prj"),
            organization_id=organization_id,
            name=name,
            metadata=metadata or {},
        )

        self.store.save_project(item)

        self.record_event(
            "project",
            item.project_id,
            "project.created",
            {
                "organization_id": organization_id,
                "name": name,
            },
        )

        return item

    def create_asset(
        self,
        project_id: str,
        name: str,
        asset_type: str,
        owner: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> AIAsset:
        if not self.store.get_project(project_id):
            raise ValueError("Project not found")

        item = AIAsset(
            asset_id=self._id("ast"),
            project_id=project_id,
            name=name,
            asset_type=asset_type,
            owner=owner,
            metadata=metadata or {},
        )

        self.store.save_asset(item)

        self.record_event(
            "asset",
            item.asset_id,
            "asset.created",
            {
                "project_id": project_id,
                "name": name,
                "asset_type": asset_type,
            },
        )

        return item

    def create_version(
        self,
        asset_id: str,
        version: str,
        environment: str,
        model: str | None = None,
        framework: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> AssetVersion:
        if not self.store.get_asset(asset_id):
            raise ValueError("AI asset not found")

        item = AssetVersion(
            version_id=self._id("ver"),
            asset_id=asset_id,
            version=version,
            environment=environment,
            model=model,
            framework=framework,
            metadata=metadata or {},
        )

        self.store.save_version(item)

        self.record_event(
            "asset_version",
            item.version_id,
            "asset.version_registered",
            {
                "asset_id": asset_id,
                "version": version,
                "environment": environment,
            },
        )

        return item

    def add_dependency(
        self,
        asset_id: str,
        version_id: str,
        dependency_type: str,
        dependency_name: str,
        dependency_version: str | None = None,
        critical: bool = False,
        metadata: Dict[str, Any] | None = None,
        target_asset_id: str | None = None,
        target_version_id: str | None = None,
    ) -> Dependency:
        asset = self.store.get_asset(asset_id)

        if not asset:
            raise ValueError("AI asset not found")

        version = self.store.get_version(version_id)

        if not version:
            raise ValueError("Asset version not found")

        if version.asset_id != asset_id:
            raise ValueError("Version does not belong to asset")

        if target_asset_id:
            target_asset = self.store.get_asset(target_asset_id)

            if not target_asset:
                raise ValueError("Target AI asset not found")

        if target_version_id:
            target_version = self.store.get_version(target_version_id)

            if not target_version:
                raise ValueError("Target asset version not found")

            if (
                target_asset_id
                and target_version.asset_id != target_asset_id
            ):
                raise ValueError(
                    "Target version does not belong to target asset"
                )

        if target_version_id and target_version:
            target_asset_id = target_version.asset_id

        item = Dependency(
            dependency_id=self._id("dep"),
            asset_id=asset_id,
            version_id=version_id,
            dependency_type=dependency_type,
            dependency_name=dependency_name,
            dependency_version=dependency_version,
            critical=critical,
            target_asset_id=target_asset_id,
            target_version_id=target_version_id,
            metadata=metadata or {},
        )

        self.store.save_dependency(item)

        self.record_event(
            "asset_version",
            version_id,
            "dependency.added",
            {
                "dependency_id": item.dependency_id,
                "dependency_type": dependency_type,
                "dependency_name": dependency_name,
                "dependency_version": dependency_version,
                "critical": critical,
                "target_asset_id": target_asset_id,
                "target_version_id": target_version_id,
            },
        )

        return item

    def get_asset(
        self,
        asset_id: str,
    ) -> Dict[str, Any]:
        asset = self.store.get_asset(asset_id)

        if not asset:
            raise ValueError("AI asset not found")

        versions = self.store.list_versions(asset_id)

        return {
            "asset": asset,
            "versions": [
                {
                    "version": version,
                    "dependencies": self.store.list_dependencies(
                        version.version_id
                    ),
                }
                for version in versions
            ],
        }

    def get_timeline(
        self,
        asset_id: str,
    ) -> List[AuditEvent]:
        if not self.store.get_asset(asset_id):
            raise ValueError("AI asset not found")

        events: List[AuditEvent] = []

        events.extend(
            self.store.list_events(
                "asset",
                asset_id,
            )
        )

        for version in self.store.list_versions(asset_id):
            events.extend(
                self.store.list_events(
                    "asset_version",
                    version.version_id,
                )
            )

        return sorted(
            events,
            key=lambda event: event.created_at,
        )

    def get_dependencies(
        self,
        asset_id: str,
    ):
        if not self.store.get_asset(asset_id):
            raise ValueError("AI asset not found")

        result = []

        for version in self.store.list_versions(asset_id):
            result.append(
                {
                    "version": version,
                    "dependencies": self.store.list_dependencies(
                        version.version_id
                    ),
                }
            )

        return result