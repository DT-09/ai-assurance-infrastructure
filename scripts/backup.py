#!/usr/bin/env python3
"""Create a production backup of the AI Assurance database."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database import is_postgres_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("ASSURANCE_DATABASE_URL"))
    parser.add_argument("--output-dir", default="backups")
    parser.add_argument("--sqlite-path", default="data/control_plane.db")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if args.database_url and is_postgres_url(args.database_url):
        if shutil.which("pg_dump") is None:
            raise SystemExit("pg_dump is required for PostgreSQL backups.")
        target = out / f"assurance-{stamp}.dump"
        subprocess.run(
            ["pg_dump", "--format=custom", "--file", str(target), args.database_url],
            check=True,
        )
        print(target)
        return

    source = Path(args.sqlite_path)
    if not source.exists():
        raise SystemExit(f"SQLite database not found: {source}")

    target = out / f"assurance-{stamp}.db"
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    print(target)


if __name__ == "__main__":
    main()
