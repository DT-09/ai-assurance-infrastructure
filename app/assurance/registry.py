from __future__ import annotations

import json
import os
from app.database import connect_database
from contextlib import contextmanager
from typing import Iterator, Optional

from .models import SystemRecord


class AssuranceRegistry:
    """
    Persistent registry of AI systems and their versions.

    Every SQLite connection is explicitly closed so the store is safe
    on Windows, including temporary database cleanup in tests.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            "data",
            "assurance.db",
        )

        parent = os.path.dirname(
            os.path.abspath(self.db_path)
        )

        if parent:
            os.makedirs(parent, exist_ok=True)

        self._initialize()

    def _connect(self):
        return connect_database(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS systems (
                    system_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    system_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    environment TEXT,
                    model TEXT,
                    framework TEXT,
                    owner TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (system_id, version)
                )
                """
            )

    def register(
        self,
        system: SystemRecord,
    ) -> SystemRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO systems (
                    system_id,
                    name,
                    system_type,
                    version,
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
                    system.name,
                    system.system_type,
                    system.version,
                    system.environment,
                    system.model,
                    system.framework,
                    system.owner,
                    _json_dumps(system.metadata),
                    system.created_at,
                ),
            )

        return system

    def get(
        self,
        system_id: str,
        version: Optional[str] = None,
    ) -> Optional[SystemRecord]:

        with self._connect() as connection:
            if version is not None:
                row = connection.execute(
                    """
                    SELECT *
                    FROM systems
                    WHERE system_id = ?
                      AND version = ?
                    """,
                    (
                        system_id,
                        version,
                    ),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM systems
                    WHERE system_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (system_id,),
                ).fetchone()

        if row is None:
            return None

        return _row_to_system(row)

    def exists(
        self,
        system_id: str,
        version: Optional[str] = None,
    ) -> bool:

        with self._connect() as connection:
            if version is not None:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM systems
                    WHERE system_id = ?
                      AND version = ?
                    LIMIT 1
                    """,
                    (
                        system_id,
                        version,
                    ),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM systems
                    WHERE system_id = ?
                    LIMIT 1
                    """,
                    (system_id,),
                ).fetchone()

        return row is not None


def _json_dumps(value) -> str:
    return json.dumps(
        value or {},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _json_loads(value):
    if not value:
        return {}

    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def _row_to_system(
    row: Any,
) -> SystemRecord:

    return SystemRecord(
        system_id=row["system_id"],
        name=row["name"],
        system_type=row["system_type"],
        version=row["version"],
        environment=row["environment"],
        model=row["model"],
        framework=row["framework"],
        owner=row["owner"],
        metadata=_json_loads(row["metadata"]),
        created_at=row["created_at"],
    )