from app.database import _postgres_sql, database_backend, is_postgres_url


def test_postgres_upsert_translation():
    sql = """
    INSERT OR REPLACE INTO systems (
        system_id, name, system_type, version, environment,
        model, framework, owner, metadata, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    translated = _postgres_sql(sql)
    assert "INSERT OR REPLACE" not in translated
    assert "ON CONFLICT (system_id, version) DO UPDATE SET" in translated


def test_postgres_ignore_translation():
    translated = _postgres_sql(
        "INSERT OR IGNORE INTO identities VALUES (?, ?)"
    )
    assert "INSERT OR IGNORE" not in translated
    assert "ON CONFLICT (organization_id) DO NOTHING" in translated


def test_postgres_schema_translation():
    translated = _postgres_sql(
        "CREATE TABLE x (salt BLOB NOT NULL)"
    )
    assert "BYTEA" in translated


def test_backend_detection():
    assert is_postgres_url("postgresql://user:pass@host/db")
    assert database_backend("data/test.db") == "sqlite"
