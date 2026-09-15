from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


def is_postgres_url(value: str) -> bool:
    return value.startswith(("postgresql://", "postgres://"))


def resolve_database_url(value: Optional[str]) -> Optional[str]:
    if value and is_postgres_url(value):
        return value

    env = os.getenv("ASSURANCE_DATABASE_URL", "").strip()
    return env or None


class CompatibleRow(dict):
    """
    PostgreSQL row compatible with both:
        row["column"]
    and:
        row[0]

    This preserves the access pattern already used by the
    SQLite-backed stores.
    """

    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        super().__init__(zip(columns, values))
        self._columns = columns
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def _compatible_row_factory(cursor):
    columns = [column.name for column in cursor.description]
    return lambda values: CompatibleRow(columns, values)


class DatabaseConnection:
    """
    Small DB-API compatibility layer supporting SQLite in development
    and PostgreSQL in production.

    Existing stores intentionally continue to use SQLite-style qmark
    placeholders and SQL.
    """

    def __init__(self, raw: Any, postgres: bool, target: str):
        self.raw = raw
        self.postgres = postgres
        self.db_path = target

    def _sql(self, sql: str) -> str:
        if not self.postgres:
            return sql

        return sql.replace("?", "%s")

    def execute(self, sql: str, parameters: Any = None):
        normalized = (
            _postgres_sql(self._sql(sql))
            if self.postgres
            else sql
        )

        if parameters is None:
            return self.raw.execute(normalized)

        return self.raw.execute(normalized, parameters)

    def executemany(self, sql: str, parameters):
        normalized = (
            _postgres_sql(self._sql(sql))
            if self.postgres
            else sql
        )
        return self.raw.executemany(normalized, parameters)

    def executescript(self, script: str):
        if not self.postgres:
            return self.raw.executescript(script)

        for statement in _split_sql_script(script):
            self.raw.execute(
                _postgres_sql(statement)
            )

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
    """
    Translate the limited SQLite-specific SQL constructs used by
    the existing application into PostgreSQL-compatible SQL.
    """

    # SQLite PRAGMA statements have no PostgreSQL equivalent.
    sql = re.sub(
        r"^\s*PRAGMA\s+[^;]+;?",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    # SQLite binary type.
    sql = re.sub(
        r"\bBLOB\b",
        "BYTEA",
        sql,
        flags=re.IGNORECASE,
    )

    # INSERT OR IGNORE.
    if re.search(
        r"INSERT\s+OR\s+IGNORE\s+INTO\s+identities\b",
        sql,
        flags=re.IGNORECASE,
    ):
        sql = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )

        sql = (
            sql.rstrip()
            .rstrip(";")
            + " ON CONFLICT (organization_id) DO NOTHING"
        )

    # Generic INSERT OR IGNORE fallback.
    elif re.search(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        sql,
        flags=re.IGNORECASE,
    ):
        sql = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )

        sql = (
            sql.rstrip()
            .rstrip(";")
            + " ON CONFLICT DO NOTHING"
        )

    # INSERT OR REPLACE.
    match = re.search(
        r"INSERT\s+OR\s+REPLACE\s+INTO\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        sql,
        flags=re.IGNORECASE,
    )

    if match:
        table = match.group(1)

        sql = re.sub(
            r"INSERT\s+OR\s+REPLACE\s+INTO",
            "INSERT INTO",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )

        pk_map = {
            "assurance_records": [
                "assurance_id"
            ],
            "evidence": [
                "evidence_id"
            ],
            "systems": [
                "system_id",
                "version",
            ],
        }

        keys = pk_map.get(table.lower())

        if keys:
            columns_match = re.search(
                r"INSERT\s+INTO\s+"
                + re.escape(table)
                + r"\s*\((.*?)\)",
                sql,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if columns_match:
                columns = [
                    column.strip()
                    for column in columns_match.group(1).split(",")
                ]

                assignments = [
                    f"{column} = EXCLUDED.{column}"
                    for column in columns
                    if column not in keys
                ]

                sql = (
                    sql.rstrip()
                    .rstrip(";")
                    + f" ON CONFLICT ({', '.join(keys)})"
                    + " DO UPDATE SET "
                    + ", ".join(assignments)
                )

    return sql


def _split_sql_script(script: str) -> list[str]:
    """
    Split the application's simple DDL scripts into statements.

    The current schemas do not contain procedural PostgreSQL blocks,
    so semicolon splitting is sufficient.
    """

    statements = []

    for part in script.split(";"):
        statement = part.strip()

        if statement:
            statements.append(statement)

    return statements


def _postgres_connect(url: str):
    if psycopg is None:
        raise RuntimeError(
            "PostgreSQL support requires psycopg. "
            "Install requirements.txt."
        )

    timeout = float(
        os.getenv(
            "ASSURANCE_DB_CONNECT_TIMEOUT",
            "10",
        )
    )

    connection = psycopg.connect(
        url,
        connect_timeout=timeout,
        row_factory=_compatible_row_factory,
    )

    return connection


@contextmanager
def connect_database(
    target: str,
) -> Iterator[DatabaseConnection]:

    url = resolve_database_url(target)

    if url:
        raw = _postgres_connect(url)

        connection = DatabaseConnection(
            raw,
            postgres=True,
            target=target,
        )

    else:
        path = str(target)

        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///"):]

        Path(path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        raw = sqlite3.connect(
            path,
            timeout=float(
                os.getenv(
                    "ASSURANCE_DB_CONNECT_TIMEOUT",
                    "30",
                )
            ),
        )

        raw.row_factory = sqlite3.Row

        connection = DatabaseConnection(
            raw,
            postgres=False,
            target=target,
        )

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def database_backend(target: str) -> str:
    return (
        "postgresql"
        if resolve_database_url(target)
        else "sqlite"
    )


def database_health(target: str) -> dict[str, Any]:
    with connect_database(target) as db:
        db.execute("SELECT 1").fetchone()

    return {
        "backend": database_backend(target),
        "status": "ok",
    }
