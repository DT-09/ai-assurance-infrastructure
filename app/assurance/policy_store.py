from __future__ import annotations

import json
from app.database import connect_database
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Policy, PolicyRule


class PolicyStore:
    def __init__(
        self,
        db_path: Optional[str] = None,
    ):
        self.db_path = (
            db_path
            or "data/policies.db"
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
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    rules TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_bindings (
                    binding_id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    version_id TEXT,
                    environment TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(
                        policy_id,
                        asset_id,
                        version_id,
                        environment
                    )
                )
                """
            )

            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_policy_bindings_asset
                ON policy_bindings(
                    asset_id
                )
                """
            )

            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_policy_bindings_version
                ON policy_bindings(
                    version_id
                )
                """
            )

    @staticmethod
    def _rules_json(
        policy: Policy,
    ) -> str:
        rules = [
            {
                "metric": rule.metric,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "severity": rule.severity,
                "description": rule.description,
            }
            for rule in policy.rules
        ]

        return json.dumps(
            rules,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _metadata_json(
        metadata: Dict[str, Any],
    ) -> str:
        return json.dumps(
            metadata,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def save(
        self,
        policy: Policy,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO policies
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.policy_id,
                    policy.name,
                    policy.version,
                    self._rules_json(policy),
                    self._metadata_json(
                        policy.metadata
                    ),
                    policy.created_at.isoformat()
                    if hasattr(
                        policy.created_at,
                        "isoformat",
                    )
                    else str(policy.created_at),
                ),
            )

    def upsert(
        self,
        policy: Policy,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO policies
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(policy_id)
                DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    rules = excluded.rules,
                    metadata = excluded.metadata,
                    created_at = excluded.created_at
                """,
                (
                    policy.policy_id,
                    policy.name,
                    policy.version,
                    self._rules_json(policy),
                    self._metadata_json(
                        policy.metadata
                    ),
                    policy.created_at.isoformat()
                    if hasattr(
                        policy.created_at,
                        "isoformat",
                    )
                    else str(policy.created_at),
                ),
            )

    def get(
        self,
        policy_id: str,
    ) -> Optional[Policy]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT *
                FROM policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            ).fetchone()

        if not row:
            return None

        raw_rules = json.loads(
            row[3]
        )

        rules = [
            PolicyRule(
                metric=item["metric"],
                operator=item["operator"],
                threshold=item["threshold"],
                severity=item.get(
                    "severity",
                    "blocking",
                ),
                description=item.get(
                    "description"
                ),
            )
            for item in raw_rules
        ]

        return Policy(
            policy_id=row[0],
            name=row[1],
            version=row[2],
            rules=rules,
            metadata=json.loads(row[4]),
            created_at=row[5],
        )

    def list(
        self,
    ) -> List[Policy]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT policy_id
                FROM policies
                ORDER BY created_at
                """
            ).fetchall()

        result = []

        for row in rows:
            policy = self.get(row[0])

            if policy is not None:
                result.append(policy)

        return result

    def bind(
        self,
        binding_id: str,
        policy_id: str,
        asset_id: str,
        version_id: Optional[str],
        environment: Optional[str],
        created_at: str,
    ) -> None:
        if self.get(policy_id) is None:
            raise ValueError(
                "Policy not found"
            )

        with self._connect() as db:
            db.execute(
                """
                INSERT INTO policy_bindings
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    binding_id,
                    policy_id,
                    asset_id,
                    version_id,
                    environment,
                    created_at,
                ),
            )

    def unbind(
        self,
        binding_id: str,
    ) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                """
                DELETE FROM policy_bindings
                WHERE binding_id = ?
                """,
                (binding_id,),
            )

        return cursor.rowcount > 0

    def resolve(
        self,
        asset_id: str,
        version_id: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> Optional[Policy]:
        """
        Resolve the most specific policy binding.

        Priority:
            1. asset + version + environment
            2. asset + version
            3. asset + environment
            4. asset-wide
        """

        candidates = []

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    binding_id,
                    policy_id,
                    asset_id,
                    version_id,
                    environment,
                    created_at
                FROM policy_bindings
                WHERE asset_id = ?
                """,
                (asset_id,),
            ).fetchall()

        for row in rows:
            binding = {
                "binding_id": row[0],
                "policy_id": row[1],
                "asset_id": row[2],
                "version_id": row[3],
                "environment": row[4],
                "created_at": row[5],
            }

            if (
                binding["version_id"] is not None
                and binding["version_id"] != version_id
            ):
                continue

            if (
                binding["environment"] is not None
                and binding["environment"] != environment
            ):
                continue

            specificity = 0

            if binding["version_id"] is not None:
                specificity += 2

            if binding["environment"] is not None:
                specificity += 1

            candidates.append(
                (
                    specificity,
                    binding,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1]["created_at"],
            ),
            reverse=True,
        )

        selected = candidates[0][1]

        return self.get(
            selected["policy_id"]
        )

    def list_bindings(
        self,
        asset_id: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                binding_id,
                policy_id,
                asset_id,
                version_id,
                environment,
                created_at
            FROM policy_bindings
        """

        params = []
        conditions = []

        if asset_id is not None:
            conditions.append(
                "asset_id = ?"
            )
            params.append(asset_id)

        if version_id is not None:
            conditions.append(
                "version_id = ?"
            )
            params.append(version_id)

        if conditions:
            query += (
                " WHERE "
                + " AND ".join(
                    conditions
                )
            )

        query += " ORDER BY created_at"

        with self._connect() as db:
            rows = db.execute(
                query,
                params,
            ).fetchall()

        return [
            {
                "binding_id": row[0],
                "policy_id": row[1],
                "asset_id": row[2],
                "version_id": row[3],
                "environment": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]