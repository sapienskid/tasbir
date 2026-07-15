from fastapi import APIRouter, Depends

from app.config import get_settings, Settings

router = APIRouter()


@router.get("")
async def get_settings_route(settings: Settings = Depends(get_settings)):
    return {"ok": True, "data": settings.model_dump(exclude={"gemini_api_key", "openrouter_api_key"})}
