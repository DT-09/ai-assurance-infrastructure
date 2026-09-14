from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import SystemRecord


class AssuranceRegistry:
    def __init__(self, database_path: str = "data/assurance.db"):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS systems (
                    system_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    system_type TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    model TEXT,
                    framework TEXT,
                    owner TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (system_id, version)
                )
                """
            )
            conn.commit()

    def register(self, system: SystemRecord) -> SystemRecord:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO systems (
                    system_id,
                    version,
                    name,
                    system_type,
                    environment,
                    model,
                    framework,
                    owner,
                    metadata,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    system.system_id,
                    system.version,
                    system.name,
                    system.system_type,
                    system.environment,
                    system.model,
                    system.framework,
                    system.owner,
                    json.dumps(system.metadata, sort_keys=True),
                    system.created_at.isoformat(),
                ),
            )
            conn.commit()

        return system

    def get(
        self,
        system_id: str,
        version: Optional[str] = None,
    ) -> Optional[SystemRecord]:
        with self._connect() as conn:
            if version:
                row = conn.execute(
                    """
                    SELECT
                        system_id, version, name, system_type,
                        environment, model, framework, owner,
                        metadata, created_at
                    FROM systems
                    WHERE system_id = ? AND version = ?
                    """,
                    (system_id, version),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT
                        system_id, version, name, system_type,
                        environment, model, framework, owner,
                        metadata, created_at
                    FROM systems
                    WHERE system_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (system_id,),
                ).fetchone()

        if not row:
            return None

        return SystemRecord(
            system_id=row[0],
            version=row[1],
            name=row[2],
            system_type=row[3],
            environment=row[4],
            model=row[5],
            framework=row[6],
            owner=row[7],
            metadata=json.loads(row[8]),
            created_at=row[9],
        )

    def exists(self, system_id: str, version: str) -> bool:
        return self.get(system_id, version) is not None
