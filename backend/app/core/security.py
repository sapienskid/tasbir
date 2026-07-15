from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings, Settings

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def verify_api_key(
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_keys:
        return
    valid_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
    if not valid_keys:
        return
    if not api_key or api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
