from __future__ import annotations

import hashlib
import json
import os
import sqlite3
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
            CREATE TABLE IF NOT EXISTS runtime_outcomes(
              decision_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """)

    def save_contract(self, contract):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO runtime_contracts VALUES (?,?,?)", (contract.agent_id, contract.version, json.dumps(contract.to_dict(), sort_keys=True)))

    def get_contract(self, agent_id: str, version: str):
        from .models import AuthorityContract
        with self._conn() as c:
            row = c.execute("SELECT payload FROM runtime_contracts WHERE agent_id=? AND version=?", (agent_id, version)).fetchone()
        return AuthorityContract.from_dict(json.loads(row[0])) if row else None

    def save_decision(self, record: RuntimeDecisionRecord):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO runtime_decisions VALUES (?,?,?,?,?)", (record.decision_id, record.decision.value, json.dumps(record.to_dict(), sort_keys=True), record.evidence_hash, record.created_at))

    def save_approval(self, decision_id: str, approver: str):
        from datetime import datetime, timezone
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO runtime_approvals VALUES (?,?,?)", (decision_id, approver, datetime.now(timezone.utc).isoformat()))

    def save_outcome(self, decision_id: str, payload: dict[str, Any]):
        from datetime import datetime, timezone
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO runtime_outcomes VALUES (?,?,?)", (decision_id, json.dumps(payload, sort_keys=True), datetime.now(timezone.utc).isoformat()))

    def list_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT payload FROM runtime_decisions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def verify_evidence(self, decision: dict[str, Any]) -> bool:
        payload = {"request": decision["action"], "decision": decision["decision"], "reasons": decision["reasons"], "contract_hash": decision["contract_hash"], "policy_version": decision["policy_version"]}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == decision["evidence_hash"]
