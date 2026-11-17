from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .models import RuntimeDecisionRecord


class RuntimeStore:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("AAI_RUNTIME_DB", "aai_runtime.db")
        self._init()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS runtime_contracts(
              agent_id TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(agent_id, version)
            );
            CREATE TABLE IF NOT EXISTS runtime_decisions(
              decision_id TEXT PRIMARY KEY, decision TEXT NOT NULL, payload TEXT NOT NULL,
              evidence_hash TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_approvals(
              decision_id TEXT PRIMARY KEY, approver TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_approval_grants(
              decision_id TEXT PRIMARY KEY, payload TEXT NOT NULL, consumed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS runtime_outcomes(
              decision_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """)

    def save_contract(self, contract):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runtime_contracts VALUES (?,?,?)",
                (contract.agent_id, contract.version, json.dumps(contract.to_dict(), sort_keys=True)),
            )

    def get_contract(self, agent_id: str, version: str):
        from .models import AuthorityContract
        with self._conn() as c:
            row = c.execute(
                "SELECT payload FROM runtime_contracts WHERE agent_id=? AND version=?",
                (agent_id, version),
            ).fetchone()
        return AuthorityContract.from_dict(json.loads(row[0])) if row else None

    def save_decision(self, record: RuntimeDecisionRecord):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runtime_decisions VALUES (?,?,?,?,?)",
                (
                    record.decision_id,
                    record.decision.value,
                    json.dumps(record.to_dict(), sort_keys=True),
                    record.evidence_hash,
                    record.created_at,
                ),
            )

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT payload FROM runtime_decisions WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_approval_grant(self, grant: dict[str, Any]):
        with self._conn() as c:
            c.execute(
                "INSERT INTO runtime_approval_grants(decision_id,payload,consumed_at) VALUES (?,?,NULL)",
                (grant["decision_id"], json.dumps(grant, sort_keys=True)),
            )

    def get_approval_grant(self, decision_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT payload,consumed_at FROM runtime_approval_grants WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row[0])
        payload["consumed_at"] = row[1]
        return payload

    def consume_approval_grant(self, decision_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            cursor = c.execute(
                "UPDATE runtime_approval_grants SET consumed_at=? WHERE decision_id=? AND consumed_at IS NULL",
                (now, decision_id),
            )
            return cursor.rowcount == 1

    def save_approval(self, decision_id: str, approver: str):
        # Legacy compatibility; new runtime approvals use bound grants above.
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runtime_approvals VALUES (?,?,?)",
                (decision_id, approver, now),
            )

    def save_outcome(self, decision_id: str, payload: dict[str, Any]):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runtime_outcomes VALUES (?,?,?)",
                (decision_id, json.dumps(payload, sort_keys=True), now),
            )

    def list_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT payload FROM runtime_decisions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def verify_evidence(self, decision: dict[str, Any]) -> bool:
        payload = {
            "request": decision["action"],
            "decision": decision["decision"],
            "reasons": decision["reasons"],
            "contract_hash": decision["contract_hash"],
            "policy_version": decision["policy_version"],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest() == decision["evidence_hash"]
