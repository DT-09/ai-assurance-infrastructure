from __future__ import annotations

import json
import os
from app.database import connect_database
from contextlib import contextmanager
from typing import Iterator, List, Optional

from .models import AssuranceRecord


class AssuranceStore:
    """
    Persistent store for issued AssuranceRecords.

    All SQLite connections are explicitly closed. This is important
    on Windows because an unclosed SQLite handle prevents temporary
    database files from being deleted.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
    ):
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

    def save(
        self,
        record: AssuranceRecord,
    ) -> AssuranceRecord:

        with self._connect() as connection:
            connection.execute(
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
                    (
                        record.verdict.value
                        if hasattr(
                            record.verdict,
                            "value",
                        )
                        else str(record.verdict)
                    ),
                    _json_dumps(
                        record.evaluation_ids
                    ),
                    _json_dumps(
                        record.evidence_ids
                    ),
                    record.policy_id,
                    _json_dumps(
                        record.metrics
                    ),
                    _json_dumps(
                        record.reasons
                    ),
                    record.created_at,
                    record.engine_version,
                ),
            )

        return record

    def get(
        self,
        assurance_id: str,
    ) -> Optional[AssuranceRecord]:

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM assurance_records
                WHERE assurance_id = ?
                """,
                (assurance_id,),
            ).fetchone()

        if row is None:
            return None

        return _row_to_record(row)

    def list_for_system(
        self,
        system_id: str,
        system_version: Optional[str] = None,
    ) -> List[AssuranceRecord]:

        with self._connect() as connection:
            if system_version is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM assurance_records
                    WHERE system_id = ?
                    ORDER BY created_at ASC
                    """,
                    (system_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM assurance_records
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
            _row_to_record(row)
            for row in rows
        ]


def _json_dumps(value) -> str:
    return json.dumps(
        value if value is not None else [],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _json_loads(
    value,
    default,
):
    if value is None or value == "":
        return default

    try:
        return json.loads(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _row_to_record(
    row: Any,
) -> AssuranceRecord:

    from .models import Verdict

    verdict_value = row["verdict"]

    try:
        verdict = Verdict(
            verdict_value
        )
    except ValueError:
        verdict = verdict_value

    return AssuranceRecord(
        assurance_id=row["assurance_id"],
        system_id=row["system_id"],
        system_version=row["system_version"],
        environment=row["environment"],
        verdict=verdict,
        evaluation_ids=_json_loads(
            row["evaluation_ids"],
            [],
        ),
        evidence_ids=_json_loads(
            row["evidence_ids"],
            [],
        ),
        policy_id=row["policy_id"],
        metrics=_json_loads(
            row["metrics"],
            {},
        ),
        reasons=_json_loads(
            row["reasons"],
            [],
        ),
        created_at=row["created_at"],
        engine_version=row["engine_version"],
    )