from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - SQLite-only environments
    psycopg = None
    dict_row = None


def is_postgres_url(value: str) -> bool:
    return value.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))


def normalize_postgres_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def resolve_database_url(value: Optional[str]) -> Optional[str]:
    if value and is_postgres_url(value):
        return value
    env = os.getenv("ASSURANCE_DATABASE_URL", "").strip()
    return env or None


class DatabaseConnection:
    """Small DB-API compatibility layer for SQLite and PostgreSQL.

    Existing stores use qmark SQL and sqlite-style row access. This wrapper
    keeps those store APIs stable while allowing a single PostgreSQL database
    in production.
    """

    def __init__(self, raw: Any, postgres: bool, target: str):
        self.raw = raw
        self.postgres = postgres
        self.db_path = target

    def _sql(self, sql: str) -> str:
        if not self.postgres:
            return sql
        # Existing application SQL uses DB-API qmark placeholders.
        return sql.replace("?", "%s")

    def execute(self, sql: str, parameters: Any = None):
        normalized = _postgres_sql(self._sql(sql)) if self.postgres else sql
        if parameters is None:
            return self.raw.execute(normalized)
        return self.raw.execute(normalized, parameters)

    def executescript(self, script: str):
        if not self.postgres:
            return self.raw.executescript(script)
        statements = _split_sql_script(script)
        for statement in statements:
            self.raw.execute(_postgres_sql(statement))

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def _postgres_sql(sql: str) -> str:
    # SQLite compatibility constructs used by the original stores.
    sql = re.sub(r"^\s*PRAGMA\s+[^;]+;?", "", sql, flags=re.I)
    sql = re.sub(r"\bBLOB\b", "BYTEA", sql, flags=re.I)
    sql = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        "INSERT INTO",
        sql,
        flags=re.I,
    )
    # PostgreSQL equivalent for the identity bootstrap insert.
    if re.search(r"INSERT\s+INTO\s+identities\b", sql, flags=re.I):
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT (organization_id) DO NOTHING"
    # INSERT OR REPLACE is used for records keyed by their primary key.
    match = re.search(
        r"INSERT\s+OR\s+REPLACE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)",
        sql,
        flags=re.I,
    )
    if match:
        table = match.group(1)
        sql = re.sub(
            r"INSERT\s+OR\s+REPLACE\s+INTO",
            "INSERT INTO",
            sql,
            count=1,
            flags=re.I,
        )
        pk_map = {
            "assurance_records": ["assurance_id"],
            "evidence": ["evidence_id"],
            "systems": ["system_id", "version"],
        }
        keys = pk_map.get(table.lower())
        if keys:
            # Extract column list and create a portable upsert.
            cols = re.search(
                r"INSERT\s+INTO\s+" + re.escape(table) + r"\s*\((.*?)\)",
                sql,
                flags=re.I | re.S,
            )
            if cols:
                columns = [c.strip() for c in cols.group(1).split(",")]
                assignments = [
                    f"{c} = EXCLUDED.{c}"
                    for c in columns
                    if c not in keys
                ]
                sql = sql.rstrip().rstrip(";")
                sql += f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET " + ", ".join(assignments)
    return sql


def _split_sql_script(script: str) -> list[str]:
    # Schema scripts contain no procedural PostgreSQL blocks; semicolon
    # splitting is therefore sufficient and keeps the adapter dependency-free.
    statements = []
    for part in script.split(";"):
        statement = part.strip()
        if statement:
            statements.append(statement)
    return statements


@contextmanager
def connect_database(target: str) -> Iterator[DatabaseConnection]:
    url = resolve_database_url(target)
    if url:
        if psycopg is None:
            raise RuntimeError(
                "PostgreSQL support requires psycopg. Install requirements.txt."
            )
        raw = psycopg.connect(normalize_postgres_url(url), row_factory=dict_row)
        connection = DatabaseConnection(raw, postgres=True, target=target)
    else:
        path = str(target)
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///"):]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path, timeout=30)
        raw.row_factory = sqlite3.Row
        connection = DatabaseConnection(raw, postgres=False, target=target)

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def database_backend(target: str) -> str:
    return "postgresql" if resolve_database_url(target) else "sqlite"


def database_health(target: str) -> dict[str, Any]:
    with connect_database(target) as db:
        db.execute("SELECT 1").fetchone()
    return {"backend": database_backend(target), "status": "ok"}
