"""Free-tier model registry API — powers the Agents page model dropdowns."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.ratelimit import interactive_rate_limiter
from app.services import models as model_service

router = APIRouter(dependencies=[Depends(interactive_rate_limiter)])


@router.get("")
async def list_models():
    return {"models": model_service.list_models()}
