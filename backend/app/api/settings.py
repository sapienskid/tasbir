from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.dependencies import get_db
from app.db.repositories.settings import SettingsRepository

router = APIRouter()

SENSITIVE_KEYS = {
    "gemini_api_key", "openrouter_api_key",
    "minio_access_key", "minio_secret_key",
    "ghost_admin_api_key", "ghost_webhook_secret",
    "penpot_access_token", "unsplash_access_key",
    "api_keys",
}


class SettingsUpdate(BaseModel):
    data: dict


@router.get("")
async def get_settings_route(settings: Settings = Depends(get_settings)):
    excluded = SENSITIVE_KEYS
    return {"ok": True, "data": settings.model_dump(exclude=excluded)}


@router.put("")
async def update_settings_route(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    for key in body.data:
        if key in SENSITIVE_KEYS:
            raise HTTPException(
                status_code=422,
                detail=f"'{key}' is a sensitive key managed via environment variables. Set it in your .env file instead.",
            )
    repo = SettingsRepository(db)
    result = await repo.upsert(body.data)
    return {"ok": True, "data": result.data}
