from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List

from .models import AssuranceRecord


class AssuranceStore:

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
                CREATE TABLE IF NOT EXISTS assurance_records (
                    assurance_id TEXT PRIMARY KEY,
                    system_id TEXT NOT NULL,
                    system_version TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    evaluation_ids TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    policy_id TEXT,
                    metrics TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    engine_version TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, record: AssuranceRecord) -> AssuranceRecord:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO assurance_records (
                    assurance_id,
                    system_id,
                    system_version,
                    environment,
                    verdict,
                    evaluation_ids,
                    evidence_ids,
                    policy_id,
                    metrics,
                    reasons,
                    created_at,
                    engine_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.assurance_id,
                    record.system_id,
                    record.system_version,
                    record.environment,
                    record.verdict.value,
                    json.dumps(record.evaluation_ids),
                    json.dumps(record.evidence_ids),
                    record.policy_id,
                    json.dumps(record.metrics),
                    json.dumps(record.reasons),
                    record.created_at.isoformat(),
                    record.engine_version,
                ),
            )
            conn.commit()

        return record

    def get(self, assurance_id: str) -> AssuranceRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    assurance_id,
                    system_id,
                    system_version,
                    environment,
                    verdict,
                    evaluation_ids,
                    evidence_ids,
                    policy_id,
                    metrics,
                    reasons,
                    created_at,
                    engine_version
                FROM assurance_records
                WHERE assurance_id = ?
                """,
                (assurance_id,),
            ).fetchone()

        if not row:
            return None

        from .models import Verdict

        return AssuranceRecord(
            assurance_id=row[0],
            system_id=row[1],
            system_version=row[2],
            environment=row[3],
            verdict=Verdict(row[4]),
            evaluation_ids=json.loads(row[5]),
            evidence_ids=json.loads(row[6]),
            policy_id=row[7],
            metrics=json.loads(row[8]),
            reasons=json.loads(row[9]),
            created_at=row[10],
            engine_version=row[11],
        )

    def list_for_system(
        self,
        system_id: str,
        system_version: str,
    ) -> List[AssuranceRecord]:

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    assurance_id,
                    system_id,
                    system_version,
                    environment,
                    verdict,
                    evaluation_ids,
                    evidence_ids,
                    policy_id,
                    metrics,
                    reasons,
                    created_at,
                    engine_version
                FROM assurance_records
                WHERE system_id = ?
                  AND system_version = ?
                ORDER BY created_at DESC
                """,
                (system_id, system_version),
            ).fetchall()

        from .models import Verdict

        return [
            AssuranceRecord(
                assurance_id=row[0],
                system_id=row[1],
                system_version=row[2],
                environment=row[3],
                verdict=Verdict(row[4]),
                evaluation_ids=json.loads(row[5]),
                evidence_ids=json.loads(row[6]),
                policy_id=row[7],
                metrics=json.loads(row[8]),
                reasons=json.loads(row[9]),
                created_at=row[10],
                engine_version=row[11],
            )
            for row in rows
        ]
