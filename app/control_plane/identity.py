from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from app.database import connect_database
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


class IdentityStore:
    """Persistent API-key identity service with tenant isolation."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv(
            "ASSURANCE_IDENTITY_DB", "data/identity.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return connect_database(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS identities (
                    organization_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    salt BLOB NOT NULL,
                    key_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    last_used_at TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_id)"
            )
            try:
                db.execute("ALTER TABLE api_keys ADD COLUMN last_used_at TEXT")
            except Exception:
                # Column already exists on current databases.
                pass

    @staticmethod
    def _hash(raw_key: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", raw_key.encode("utf-8"), salt, 600_000
        ).hex()

    def ensure_identity(self, organization_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO identities VALUES (?, ?)",
                (organization_id, datetime.now(timezone.utc).isoformat()),
            )

    def create_key(self, organization_id: str, name: str = "default") -> dict:
        self.ensure_identity(organization_id)
        key_id = "key_" + secrets.token_hex(16)
        raw_key = "aap_" + secrets.token_urlsafe(32)
        salt = os.urandom(32)
        created_at = datetime.now(timezone.utc).isoformat()
        key_hash = self._hash(raw_key, salt)
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO api_keys
                (key_id, organization_id, name, salt, key_hash, created_at, revoked_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (key_id, organization_id, name, salt, key_hash, created_at),
            )
        return {
            "key_id": key_id,
            "organization_id": organization_id,
            "name": name,
            "created_at": created_at,
            "api_key": raw_key,
        }

    def authenticate(self, raw_key: str) -> Optional[str]:
        if not raw_key:
            return None
        with self._connect() as db:
            rows = db.execute(
                "SELECT key_id, organization_id, salt, key_hash FROM api_keys WHERE revoked_at IS NULL"
            ).fetchall()
            for row in rows:
                actual = self._hash(raw_key, bytes(row["salt"]))
                if hmac.compare_digest(actual, row["key_hash"]):
                    db.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                        (datetime.now(timezone.utc).isoformat(), row["key_id"]),
                    )
                    return str(row["organization_id"])
        return None

    def revoke(self, key_id: str, organization_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE api_keys SET revoked_at = ?
                WHERE key_id = ? AND organization_id = ? AND revoked_at IS NULL
                """,
                (datetime.now(timezone.utc).isoformat(), key_id, organization_id),
            )
        return cursor.rowcount > 0

    def list_keys(self, organization_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT key_id, organization_id, name, created_at, revoked_at, last_used_at
                FROM api_keys WHERE organization_id = ? ORDER BY created_at
                """,
                (organization_id,),
            ).fetchall()
        return [dict(row) for row in rows]
