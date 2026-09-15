from __future__ import annotations

import json
from app.database import connect_database, database_backend
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    AIAsset,
    AssetVersion,
    AuditEvent,
    Dependency,
    Organization,
    Project,
)


class ControlPlaneStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "data/control_plane.db"

        Path(self.db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(self):
        return connect_database(self.db_path)

    def _initialize(self):
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    organization_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (organization_id)
                        REFERENCES organizations(organization_id)
                );

                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    owner TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id)
                        REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS asset_versions (
                    version_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    model TEXT,
                    framework TEXT,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(asset_id, version, environment),
                    FOREIGN KEY (asset_id)
                        REFERENCES assets(asset_id)
                );

                CREATE TABLE IF NOT EXISTS dependencies (
                    dependency_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    dependency_type TEXT NOT NULL,
                    dependency_name TEXT NOT NULL,
                    dependency_version TEXT,
                    critical INTEGER NOT NULL,
                    target_asset_id TEXT,
                    target_version_id TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (asset_id)
                        REFERENCES assets(asset_id),
                    FOREIGN KEY (version_id)
                        REFERENCES asset_versions(version_id),
                    FOREIGN KEY (target_asset_id)
                        REFERENCES assets(asset_id),
                    FOREIGN KEY (target_version_id)
                        REFERENCES asset_versions(version_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_projects_org
                    ON projects(organization_id);

                CREATE INDEX IF NOT EXISTS idx_assets_project
                    ON assets(project_id);

                CREATE INDEX IF NOT EXISTS idx_versions_asset
                    ON asset_versions(asset_id);

                CREATE INDEX IF NOT EXISTS idx_dependencies_version
                    ON dependencies(version_id);

                CREATE INDEX IF NOT EXISTS idx_dependencies_target_asset
                    ON dependencies(target_asset_id);

                CREATE INDEX IF NOT EXISTS idx_dependencies_target_version
                    ON dependencies(target_version_id);

                CREATE INDEX IF NOT EXISTS idx_audit_entity
                    ON audit_events(entity_type, entity_id);
                """
            )

            self._migrate_dependencies(db)

    @staticmethod
    def _migrate_dependencies(db):
        if database_backend(db.db_path if hasattr(db, "db_path") else "") == "postgresql":
            columns = {
                row["column_name"]
                for row in db.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'dependencies'
                    """
                ).fetchall()
            }
        else:
            columns = {
                row[1]
                for row in db.execute(
                    "PRAGMA table_info(dependencies)"
                ).fetchall()
            }

        if "target_asset_id" not in columns:
            db.execute(
                """
                ALTER TABLE dependencies
                ADD COLUMN target_asset_id TEXT
                """
            )

        if "target_version_id" not in columns:
            db.execute(
                """
                ALTER TABLE dependencies
                ADD COLUMN target_version_id TEXT
                """
            )

        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dependencies_target_asset
            ON dependencies(target_asset_id)
            """
        )

        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dependencies_target_version
            ON dependencies(target_version_id)
            """
        )

    @staticmethod
    def _json(value: Dict[str, Any]) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _dict(value: str) -> Dict[str, Any]:
        return json.loads(value) if value else {}

    def save_organization(self, item: Organization):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO organizations
                VALUES (?, ?, ?, ?)
                """,
                (
                    item.organization_id,
                    item.name,
                    self._json(item.metadata),
                    item.created_at,
                ),
            )

    def get_organization(
        self,
        organization_id: str,
    ) -> Optional[Organization]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT *
                FROM organizations
                WHERE organization_id = ?
                """,
                (organization_id,),
            ).fetchone()

        if not row:
            return None

        return Organization(
            organization_id=row[0],
            name=row[1],
            metadata=self._dict(row[2]),
            created_at=row[3],
        )

    def save_project(self, item: Project):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO projects
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.project_id,
                    item.organization_id,
                    item.name,
                    self._json(item.metadata),
                    item.created_at,
                ),
            )

    def get_project(
        self,
        project_id: str,
    ) -> Optional[Project]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT *
                FROM projects
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()

        if not row:
            return None

        return Project(
            project_id=row[0],
            organization_id=row[1],
            name=row[2],
            metadata=self._dict(row[3]),
            created_at=row[4],
        )

    def save_asset(self, item: AIAsset):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO assets
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.asset_id,
                    item.project_id,
                    item.name,
                    item.asset_type,
                    item.owner,
                    self._json(item.metadata),
                    item.created_at,
                ),
            )

    def get_asset(
        self,
        asset_id: str,
    ) -> Optional[AIAsset]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT *
                FROM assets
                WHERE asset_id = ?
                """,
                (asset_id,),
            ).fetchone()

        if not row:
            return None

        return AIAsset(
            asset_id=row[0],
            project_id=row[1],
            name=row[2],
            asset_type=row[3],
            owner=row[4],
            metadata=self._dict(row[5]),
            created_at=row[6],
        )

    def save_version(self, item: AssetVersion):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO asset_versions
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.version_id,
                    item.asset_id,
                    item.version,
                    item.environment,
                    item.model,
                    item.framework,
                    item.status,
                    self._json(item.metadata),
                    item.created_at,
                ),
            )

    def get_version(
        self,
        version_id: str,
    ) -> Optional[AssetVersion]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT *
                FROM asset_versions
                WHERE version_id = ?
                """,
                (version_id,),
            ).fetchone()

        if not row:
            return None

        return AssetVersion(
            version_id=row[0],
            asset_id=row[1],
            version=row[2],
            environment=row[3],
            model=row[4],
            framework=row[5],
            status=row[6],
            metadata=self._dict(row[7]),
            created_at=row[8],
        )

    def list_versions(
        self,
        asset_id: str,
    ) -> List[AssetVersion]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM asset_versions
                WHERE asset_id = ?
                ORDER BY created_at
                """,
                (asset_id,),
            ).fetchall()

        return [
            AssetVersion(
                version_id=row[0],
                asset_id=row[1],
                version=row[2],
                environment=row[3],
                model=row[4],
                framework=row[5],
                status=row[6],
                metadata=self._dict(row[7]),
                created_at=row[8],
            )
            for row in rows
        ]

    def save_dependency(self, item: Dependency):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO dependencies (
                    dependency_id,
                    asset_id,
                    version_id,
                    dependency_type,
                    dependency_name,
                    dependency_version,
                    critical,
                    target_asset_id,
                    target_version_id,
                    metadata,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.dependency_id,
                    item.asset_id,
                    item.version_id,
                    item.dependency_type,
                    item.dependency_name,
                    item.dependency_version,
                    int(item.critical),
                    item.target_asset_id,
                    item.target_version_id,
                    self._json(item.metadata),
                    item.created_at,
                ),
            )

    def get_dependency(
        self,
        dependency_id: str,
    ) -> Optional[Dependency]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    dependency_id,
                    asset_id,
                    version_id,
                    dependency_type,
                    dependency_name,
                    dependency_version,
                    critical,
                    target_asset_id,
                    target_version_id,
                    metadata,
                    created_at
                FROM dependencies
                WHERE dependency_id = ?
                """,
                (dependency_id,),
            ).fetchone()

        if not row:
            return None

        return Dependency(
            dependency_id=row[0],
            asset_id=row[1],
            version_id=row[2],
            dependency_type=row[3],
            dependency_name=row[4],
            dependency_version=row[5],
            critical=bool(row[6]),
            target_asset_id=row[7],
            target_version_id=row[8],
            metadata=self._dict(row[9]),
            created_at=row[10],
        )

    def list_dependencies(
        self,
        version_id: str,
    ) -> List[Dependency]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    dependency_id,
                    asset_id,
                    version_id,
                    dependency_type,
                    dependency_name,
                    dependency_version,
                    critical,
                    target_asset_id,
                    target_version_id,
                    metadata,
                    created_at
                FROM dependencies
                WHERE version_id = ?
                ORDER BY created_at
                """,
                (version_id,),
            ).fetchall()

        return [
            Dependency(
                dependency_id=row[0],
                asset_id=row[1],
                version_id=row[2],
                dependency_type=row[3],
                dependency_name=row[4],
                dependency_version=row[5],
                critical=bool(row[6]),
                target_asset_id=row[7],
                target_version_id=row[8],
                metadata=self._dict(row[9]),
                created_at=row[10],
            )
            for row in rows
        ]

    def list_dependents(
        self,
        target_asset_id: str | None = None,
        target_version_id: str | None = None,
    ) -> List[Dependency]:
        if not target_asset_id and not target_version_id:
            return []

        conditions = []
        params: List[str] = []

        if target_version_id:
            conditions.append("target_version_id = ?")
            params.append(target_version_id)

        if target_asset_id:
            conditions.append("target_asset_id = ?")
            params.append(target_asset_id)

        where = " OR ".join(conditions)

        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT
                    dependency_id,
                    asset_id,
                    version_id,
                    dependency_type,
                    dependency_name,
                    dependency_version,
                    critical,
                    target_asset_id,
                    target_version_id,
                    metadata,
                    created_at
                FROM dependencies
                WHERE {where}
                ORDER BY created_at
                """,
                params,
            ).fetchall()

        return [
            Dependency(
                dependency_id=row[0],
                asset_id=row[1],
                version_id=row[2],
                dependency_type=row[3],
                dependency_name=row[4],
                dependency_version=row[5],
                critical=bool(row[6]),
                target_asset_id=row[7],
                target_version_id=row[8],
                metadata=self._dict(row[9]),
                created_at=row[10],
            )
            for row in rows
        ]

    def save_event(self, event: AuditEvent):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO audit_events
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.entity_type,
                    event.entity_id,
                    event.event_type,
                    self._json(event.payload),
                    event.created_at,
                ),
            )

    def list_events(
        self,
        entity_type: str,
        entity_id: str,
    ) -> List[AuditEvent]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM audit_events
                WHERE entity_type = ?
                  AND entity_id = ?
                ORDER BY created_at
                """,
                (entity_type, entity_id),
            ).fetchall()

        return [
            AuditEvent(
                event_id=row[0],
                entity_type=row[1],
                entity_id=row[2],
                event_type=row[3],
                payload=self._dict(row[4]),
                created_at=row[5],
            )
            for row in rows
        ]

    def update_version_status(
        self,
        version_id: str,
        status: str,
    ) -> AssetVersion:
        with self._connect() as db:
            db.execute(
                """
                UPDATE asset_versions
                SET status = ?
                WHERE version_id = ?
                """,
                (status, version_id),
            )

        version = self.get_version(version_id)

        if not version:
            raise ValueError("Asset version not found")

        return version