from __future__ import annotations

import hashlib
import json
import os
from app.database import connect_database
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

from .models import EvidenceRecord


class EvidenceStore:
    """
    Persistent, tamper-evident evidence store.

    Every SQLite connection is explicitly closed to prevent Windows
    file-handle leaks during temporary database cleanup.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
    ):
        self.db_path = db_path or os.path.join(
            "data",
            "evidence.db",
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
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evidence_type TEXT NOT NULL,
                    system_id TEXT NOT NULL,
                    system_version TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create(
        self,
        evidence_id: str,
        evidence_type: str,
        system_id: str,
        system_version: str,
        source: str,
        payload: Dict[str, Any],
    ) -> EvidenceRecord:

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        content_hash = hashlib.sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest()

        record = EvidenceRecord(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            system_id=system_id,
            system_version=system_version,
            source=source,
            payload=payload,
            content_hash=content_hash,
            created_at=created_at,
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evidence (
                    evidence_id,
                    evidence_type,
                    system_id,
                    system_version,
                    source,
                    payload,
                    content_hash,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evidence_id,
                    record.evidence_type,
                    record.system_id,
                    record.system_version,
                    record.source,
                    canonical_payload,
                    record.content_hash,
                    record.created_at,
                ),
            )

        return record

    def get(
        self,
        evidence_id: str,
    ) -> Optional[EvidenceRecord]:

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def list_for_system(
        self,
        system_id: str,
        system_version: Optional[str] = None,
    ) -> list[EvidenceRecord]:

        with self._connect() as connection:
            if system_version is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM evidence
                    WHERE system_id = ?
                    ORDER BY created_at ASC
                    """,
                    (system_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM evidence
                    WHERE system_id = ?
                      AND system_version = ?
                    ORDER BY created_at ASC
                    """,
                    (
                        system_id,
                        system_version,
                    ),
                ).fetchall()

        return [
            self._row_to_record(row)
            for row in rows
        ]

    def verify(
        self,
        evidence_id: str,
    ) -> bool:

        record = self.get(evidence_id)

        if record is None:
            return False

        canonical_payload = json.dumps(
            record.payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        calculated_hash = hashlib.sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest()

        return (
            calculated_hash
            == record.content_hash
        )

    @staticmethod
    def _row_to_record(
        row: Any,
    ) -> EvidenceRecord:

        payload = json.loads(
            row["payload"]
        )

        return EvidenceRecord(
            evidence_id=row["evidence_id"],
            evidence_type=row["evidence_type"],
            system_id=row["system_id"],
            system_version=row["system_version"],
            source=row["source"],
            payload=payload,
            content_hash=row["content_hash"],
            created_at=row["created_at"],
        )