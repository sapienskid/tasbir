"""Health check endpoint."""

import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    from app.config import get_settings

    settings = get_settings()

    # Check if design system file exists
    ds_path = Path(settings.design_system_path)
    ds_exists = ds_path.exists()

    return {
        "status": "ok",
        "version": "0.3.0",
        "service": "tasbir",
        "design_system": {
            "path": str(ds_path),
            "exists": ds_exists,
            "size_bytes": ds_path.stat().st_size if ds_exists else 0,
        },
        "llm_configured": bool(settings.gemini_api_key),
    }
