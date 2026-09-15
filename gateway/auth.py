from fastapi import Header, HTTPException

from .storage import SQLiteStorage


API_KEY_HEADER = "X-API-Key"


def require_api_key(
    x_api_key: str | None = Header(default=None),
) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key",
        )

    storage = SQLiteStorage()

    organization_id = storage.authenticate_api_key(
        x_api_key
    )

    if organization_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key",
        )

    return organization_id