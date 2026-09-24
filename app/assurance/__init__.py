from __future__ import annotations

import sqlite3
from datetime import datetime


def _adapt_datetime(value: datetime) -> str:
    """
    Explicit SQLite adapter for datetime values.

    Python 3.12+ deprecated sqlite3's implicit datetime adapter.
    Storing ISO-8601 strings preserves the existing database behavior
    while eliminating the deprecation warning.
    """
    return value.isoformat()


sqlite3.register_adapter(
    datetime,
    _adapt_datetime,
)