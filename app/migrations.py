from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Iterable

from .database import connect_database, database_backend


MIGRATION_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate_database(target: str, component: str) -> dict:
    """Record and verify the idempotent schema baseline for a database.

    Store constructors own their table DDL so existing APIs remain stable.
    This runner provides an explicit, durable migration ledger and is the
    extension point for future ALTER TABLE migrations.
    """
    with connect_database(target) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                component TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        row = db.execute(
            "SELECT version FROM schema_migrations WHERE component = ?",
            (component,),
        ).fetchone()
        if row is None:
            db.execute(
                """
                INSERT INTO schema_migrations(component, version, applied_at)
                VALUES (?, ?, ?)
                """,
                (component, MIGRATION_VERSION, _now()),
            )
            version = MIGRATION_VERSION
            action = "applied"
        else:
            version = int(row["version"] if isinstance(row, dict) else row[0])
            if version < MIGRATION_VERSION:
                db.execute(
                    """
                    UPDATE schema_migrations
                    SET version = ?, applied_at = ?
                    WHERE component = ?
                    """,
                    (MIGRATION_VERSION, _now(), component),
                )
                version = MIGRATION_VERSION
                action = "upgraded"
            else:
                action = "current"

    return {
        "component": component,
        "version": version,
        "action": action,
        "backend": database_backend(target),
    }


def migrate_all(targets: Iterable[tuple[str, str]]) -> list[dict]:
    return [migrate_database(target, component) for target, component in targets]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI Assurance database migrations.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--component", default="assurance-platform")
    args = parser.parse_args()
    print(migrate_database(args.database_url, args.component))


if __name__ == "__main__":
    main()
