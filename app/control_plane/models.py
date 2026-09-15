from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Organization:
    organization_id: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class Project:
    project_id: str
    organization_id: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class AIAsset:
    asset_id: str
    project_id: str
    name: str
    asset_type: str
    owner: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class AssetVersion:
    version_id: str
    asset_id: str
    version: str
    environment: str
    model: str | None = None
    framework: str | None = None
    status: str = "registered"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class Dependency:
    dependency_id: str
    asset_id: str
    version_id: str
    dependency_type: str
    dependency_name: str
    dependency_version: str | None = None
    critical: bool = False
    target_asset_id: str | None = None
    target_version_id: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class AuditEvent:
    event_id: str
    entity_type: str
    entity_id: str
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)