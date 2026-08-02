"""Free-tier model registry API — powers the Agents page model dropdowns."""

from __future__ import annotations

from fastapi import APIRouter

from app.services import models as model_service

router = APIRouter()


@router.get("")
async def list_models():
    return {"models": model_service.list_models()}
