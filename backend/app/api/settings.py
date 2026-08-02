"""Runtime settings API — read/update the DB-backed tuning knobs.

The Studio edits these instead of hardcoded constants. Env vars still own
infra/secrets; this table owns behavioral tuning.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import settings as settings_service

router = APIRouter()


class SettingsUpdate(BaseModel):
    values: dict


@router.get("")
async def get_settings():
    settings = await settings_service.get_runtime_settings()
    return {
        "defaults": settings_service.DEFAULT_APP_SETTINGS,
        "values": settings,
    }


@router.put("")
async def update_settings(body: SettingsUpdate):
    values = await settings_service.update_runtime_settings(body.values)
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
