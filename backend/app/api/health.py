"""Health check endpoint."""

import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    from app.config import get_settings

    settings = get_settings()

    return {
        "status": "ok",
        "version": "0.5.0",
        "service": "tasbir",
        "llm_configured": bool(settings.gemini_api_key),
    }
