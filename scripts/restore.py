#!/usr/bin/env python3
"""Restore a PostgreSQL custom dump or replace a SQLite database file."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sqlite3
from pathlib import Path

from app.database import is_postgres_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("--database-url", default=os.getenv("ASSURANCE_DATABASE_URL"))
    parser.add_argument("--sqlite-path", default="data/control_plane.db")
    args = parser.parse_args()

    backup = Path(args.backup)
    if not backup.exists():
        raise SystemExit(f"Backup not found: {backup}")

    if args.database_url and is_postgres_url(args.database_url):
        if shutil.which("pg_restore") is None:
            raise SystemExit("pg_restore is required for PostgreSQL recovery.")
        subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                f"--dbname={args.database_url}",
                str(backup),
            ],
            check=True,
        )
        print("PostgreSQL restore completed.")
        return

    target = Path(args.sqlite_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Validate before replacing the live file.
    check = sqlite3.connect(backup)
    try:
        check.execute("PRAGMA integrity_check").fetchone()
    finally:
        check.close()
    shutil.copy2(backup, target)
    print(f"SQLite restore completed: {target}")


if __name__ == "__main__":
    main()
