from app.database import is_postgres_url, normalize_postgres_url


def test_postgres_url_variants_are_supported():
    assert is_postgres_url("postgresql://db/aai")
    assert is_postgres_url("postgres://db/aai")
    assert is_postgres_url("postgresql+psycopg://db/aai")
    assert normalize_postgres_url("postgresql+psycopg://db/aai") == "postgresql://db/aai"


def test_production_middleware_module_imports():
    import app.production as production
    from app.config import Settings

    assert production.RequestContextMiddleware
    assert production.SecurityHeadersMiddleware
    assert Settings().trusted_hosts
