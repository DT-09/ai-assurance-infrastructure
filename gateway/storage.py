import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Agent, Credential, Organization


class SQLiteStorage:
    def __init__(self, database_path: str = "gateway.db"):
        self.database_path = Path(database_path)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    organization_id TEXT PRIMARY KEY,
                    organization_data TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    credential_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    credential_data TEXT NOT NULL,
                    key_salt TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    agent_data TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    approval_data TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_data TEXT NOT NULL
                )
                """
            )

            connection.commit()

    # -------------------------
    # Organizations
    # -------------------------

    def save_organization(
        self,
        organization: Organization,
    ) -> None:
        data = json.dumps(
            organization.model_dump(mode="json")
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO organizations
                (organization_id, organization_data)
                VALUES (?, ?)
                """,
                (
                    organization.organization_id,
                    data,
                ),
            )

            connection.commit()

    def get_organization(
        self,
        organization_id: str,
    ) -> Organization | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT organization_data
                FROM organizations
                WHERE organization_id = ?
                """,
                (organization_id,),
            ).fetchone()

        if row is None:
            return None

        return Organization.model_validate(
            json.loads(row[0])
        )

    def get_all_organizations(
        self,
    ) -> list[Organization]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT organization_data
                FROM organizations
                ORDER BY organization_id
                """
            ).fetchall()

        return [
            Organization.model_validate(json.loads(data))
            for (data,) in rows
        ]

    # -------------------------
    # Credentials
    # -------------------------

    @staticmethod
    def hash_api_key(
        api_key: str,
        salt: bytes,
    ) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            api_key.encode("utf-8"),
            salt,
            600_000,
        ).hex()

    def create_credential(
        self,
        organization_id: str,
        name: str,
    ) -> tuple[Credential, str]:
        credential_id = secrets.token_urlsafe(24)

        api_key = (
            "gw_"
            + secrets.token_urlsafe(32)
        )

        salt = os.urandom(32)

        key_hash = self.hash_api_key(
            api_key,
            salt,
        )

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        credential = Credential(
            credential_id=credential_id,
            organization_id=organization_id,
            name=name,
            created_at=created_at,
        )

        data = json.dumps(
            credential.model_dump(mode="json")
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO credentials
                (
                    credential_id,
                    organization_id,
                    credential_data,
                    key_salt,
                    key_hash,
                    revoked
                )
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    credential_id,
                    organization_id,
                    data,
                    salt.hex(),
                    key_hash,
                ),
            )

            connection.commit()

        return credential, api_key

    def authenticate_api_key(
        self,
        api_key: str,
    ) -> str | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    organization_id,
                    key_salt,
                    key_hash,
                    revoked
                FROM credentials
                """
            ).fetchall()

        for (
            organization_id,
            salt_hex,
            expected_hash,
            revoked,
        ) in rows:
            if revoked:
                continue

            salt = bytes.fromhex(salt_hex)

            actual_hash = self.hash_api_key(
                api_key,
                salt,
            )

            if secrets.compare_digest(
                actual_hash,
                expected_hash,
            ):
                return organization_id

        return None

    def get_credential(
        self,
        credential_id: str,
    ) -> Credential | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT credential_data
                FROM credentials
                WHERE credential_id = ?
                """,
                (credential_id,),
            ).fetchone()

        if row is None:
            return None

        return Credential.model_validate(
            json.loads(row[0])
        )

    def get_credentials_for_organization(
        self,
        organization_id: str,
    ) -> list[Credential]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT credential_data
                FROM credentials
                WHERE organization_id = ?
                ORDER BY rowid
                """,
                (organization_id,),
            ).fetchall()

        return [
            Credential.model_validate(json.loads(data))
            for (data,) in rows
        ]

    def revoke_credential(
        self,
        credential_id: str,
    ) -> Credential | None:
        credential = self.get_credential(
            credential_id
        )

        if credential is None:
            return None

        if credential.revoked_at is not None:
            return credential

        credential.revoked_at = datetime.now(
            timezone.utc
        ).isoformat()

        data = json.dumps(
            credential.model_dump(mode="json")
        )

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE credentials
                SET credential_data = ?,
                    revoked = 1
                WHERE credential_id = ?
                """,
                (
                    data,
                    credential_id,
                ),
            )

            connection.commit()

        return credential

    # -------------------------
    # Agents
    # -------------------------

    def save_agent(
        self,
        agent: Agent,
    ) -> None:
        data = json.dumps(
            agent.model_dump(mode="json")
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO agents
                (agent_id, agent_data)
                VALUES (?, ?)
                """,
                (
                    agent.agent_id,
                    data,
                ),
            )

            connection.commit()

    def get_agent(
        self,
        agent_id: str,
    ) -> Agent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT agent_data
                FROM agents
                WHERE agent_id = ?
                """,
                (agent_id,),
            ).fetchone()

        if row is None:
            return None

        return Agent.model_validate(
            json.loads(row[0])
        )

    def delete_agent(
        self,
        agent_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM agents WHERE agent_id = ?",
                (agent_id,),
            )

            connection.commit()

    def get_all_agents(
        self,
    ) -> dict[str, Agent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT agent_id, agent_data
                FROM agents
                """
            ).fetchall()

        return {
            agent_id: Agent.model_validate(
                json.loads(data)
            )
            for agent_id, data in rows
        }

    # -------------------------
    # Approvals
    # -------------------------

    def save_approval(
        self,
        approval_id: str,
        data: dict,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO approvals
                (approval_id, approval_data)
                VALUES (?, ?)
                """,
                (
                    approval_id,
                    json.dumps(data),
                ),
            )

            connection.commit()

    def get_approval(
        self,
        approval_id: str,
    ) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT approval_data
                FROM approvals
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()

        if row is None:
            return None

        return json.loads(row[0])

    def get_all_approvals(
        self,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT approval_data
                FROM approvals
                ORDER BY rowid
                """
            ).fetchall()

        return [
            json.loads(row[0])
            for row in rows
        ]

    # -------------------------
    # Audit
    # -------------------------

    def save_audit_event(
        self,
        data: dict,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events
                (event_data)
                VALUES (?)
                """,
                (json.dumps(data),),
            )

            connection.commit()

    def get_all_audit_events(
        self,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_data
                FROM audit_events
                ORDER BY event_id
                """
            ).fetchall()

        return [
            json.loads(row[0])
            for row in rows
        ]