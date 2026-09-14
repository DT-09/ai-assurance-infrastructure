from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .models import EvidenceRecord


class EvidenceStore:
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
            conn.commit()

    @staticmethod
    def hash_payload(payload: Dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def create(
        self,
        evidence_id: str,
        evidence_type: str,
        system_id: str,
        system_version: str,
        source: str,
        payload: Dict[str, Any],
    ) -> EvidenceRecord:

        content_hash = self.hash_payload(payload)

        record = EvidenceRecord(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            system_id=system_id,
            system_version=system_version,
            source=source,
            payload=payload,
            content_hash=content_hash,
        )

        with self._connect() as conn:
            conn.execute(
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
                    json.dumps(record.payload, sort_keys=True, default=str),
                    record.content_hash,
                    record.created_at.isoformat(),
                ),
            )
            conn.commit()

        return record

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    evidence_id,
                    evidence_type,
                    system_id,
                    system_version,
                    source,
                    payload,
                    content_hash,
                    created_at
                FROM evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if not row:
            return None

        return EvidenceRecord(
            evidence_id=row[0],
            evidence_type=row[1],
            system_id=row[2],
            system_version=row[3],
            source=row[4],
            payload=json.loads(row[5]),
            content_hash=row[6],
            created_at=row[7],
        )

    def verify(self, evidence_id: str) -> bool:
        record = self.get(evidence_id)

        if record is None:
            return False

        return self.hash_payload(record.payload) == record.content_hash

    def list_for_system(
        self,
        system_id: str,
        system_version: str,
    ) -> List[EvidenceRecord]:

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    evidence_id,
                    evidence_type,
                    system_id,
                    system_version,
                    source,
                    payload,
                    content_hash,
                    created_at
                FROM evidence
                WHERE system_id = ?
                  AND system_version = ?
                ORDER BY created_at ASC
                """,
                (system_id, system_version),
            ).fetchall()

        return [
            EvidenceRecord(
                evidence_id=row[0],
                evidence_type=row[1],
                system_id=row[2],
                system_version=row[3],
                source=row[4],
                payload=json.loads(row[5]),
                content_hash=row[6],
                created_at=row[7],
            )
            for row in rows
        ]
