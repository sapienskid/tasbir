"""Runtime settings API — read/update the DB-backed tuning knobs.

The Studio edits these instead of hardcoded constants. Env vars still own
infra/secrets; this table owns behavioral tuning.

``GET /meta`` publishes the vocabularies the Studio needs (platform families,
font roles) so the frontend derives its dropdowns instead of redeclaring them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.ratelimit import interactive_rate_limiter
from app.services import settings as settings_service

router = APIRouter(dependencies=[Depends(interactive_rate_limiter)])


class SettingsUpdate(BaseModel):
    values: dict


@router.get("")
async def get_settings():
    settings = await settings_service.get_runtime_settings()
    return {"defaults": settings_service.DEFAULT_APP_SETTINGS, "values": settings}


@router.put("")
async def update_settings(body: SettingsUpdate):
    try:
        values = await settings_service.update_runtime_settings(body.values)
    except settings_service.SettingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "defaults": settings_service.DEFAULT_APP_SETTINGS,
        "values": values,
    }


@router.post("/reset")
async def reset_settings():
    values = await settings_service.reset_runtime_settings()
    return {
        "defaults": settings_service.DEFAULT_APP_SETTINGS,
        "values": values,
    }


@router.get("/meta")
async def settings_meta():
    """Vocabularies shared with the Studio (single source of truth)."""
    from app.services.fonts import VALID_ROLES
    from app.services.platforms import VALID_FAMILIES

    return {
        "families": sorted(VALID_FAMILIES),
        "font_roles": list(VALID_ROLES),
    }
