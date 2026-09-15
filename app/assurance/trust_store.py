from __future__ import annotations

import json
from app.database import connect_database
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from .trust_state import (
    TrustState,
    TrustTransition,
)


class TrustStateStore:
    def __init__(
        self,
        db_path: Optional[str] = None,
    ):
        self.db_path = (
            db_path
            or "data/trust_state.db"
        )

        Path(
            self.db_path
        ).parent.mkdir(
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
                CREATE TABLE IF NOT EXISTS trust_states (
                    asset_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(asset_id, version_id)
                );

                CREATE TABLE IF NOT EXISTS trust_transitions (
                    transition_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    previous_state TEXT NOT NULL,
                    new_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    assurance_id TEXT,
                    trigger_event_id TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_trust_transitions_version
                    ON trust_transitions(
                        asset_id,
                        version_id,
                        created_at
                    );
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

    def save_transition(
        self,
        transition: TrustTransition,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO trust_transitions
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transition.transition_id,
                    transition.asset_id,
                    transition.version_id,
                    transition.previous_state.value,
                    transition.new_state.value,
                    transition.reason,
                    transition.assurance_id,
                    transition.trigger_event_id,
                    self._json(
                        transition.metadata
                    ),
                    transition.created_at,
                ),
            )

            db.execute(
                """
                INSERT INTO trust_states
                VALUES (?, ?, ?, ?)
                ON CONFLICT(asset_id, version_id)
                DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (
                    transition.asset_id,
                    transition.version_id,
                    transition.new_state.value,
                    transition.created_at,
                ),
            )

    def get_state(
        self,
        asset_id: str,
        version_id: str,
    ) -> TrustState:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT state
                FROM trust_states
                WHERE asset_id = ?
                  AND version_id = ?
                """,
                (
                    asset_id,
                    version_id,
                ),
            ).fetchone()

        if not row:
            return TrustState.UNKNOWN

        return TrustState(row[0])

    def history(
        self,
        asset_id: str,
        version_id: str,
    ) -> List[TrustTransition]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM trust_transitions
                WHERE asset_id = ?
                  AND version_id = ?
                ORDER BY created_at
                """,
                (
                    asset_id,
                    version_id,
                ),
            ).fetchall()

        return [
            TrustTransition(
                transition_id=row[0],
                asset_id=row[1],
                version_id=row[2],
                previous_state=TrustState(row[3]),
                new_state=TrustState(row[4]),
                reason=row[5],
                assurance_id=row[6],
                trigger_event_id=row[7],
                metadata=self._dict(row[8]),
                created_at=row[9],
            )
            for row in rows
        ]
