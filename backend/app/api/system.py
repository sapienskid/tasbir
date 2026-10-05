"""System export/import API — portable config backup & restore.

GET  /api/system/info   → the environment actually in force (no secrets).
GET  /api/system/export  → full config snapshot (design systems, templates,
                           design languages, platforms, fonts, agents, runtime
                           settings) as JSON.
POST /api/system/import  → upsert that snapshot back into the DB (merge, not
                           replace). Rows absent from the payload are untouched.

Runtime data (tasks/audit/chat) is intentionally not part of the snapshot.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.ratelimit import interactive_rate_limiter
from app.db.session import get_shared_session_factory
from app.models.agent import Agent
from app.models.app_setting import AppSetting
from app.models.design_language import DesignLanguage
from app.models.design_system import DesignSystem
from app.models.font import Font
from app.models.platform import Platform
from app.models.template import Template
from app.services import system_export

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(interactive_rate_limiter)])


class SystemImport(BaseModel):
    payload: dict = Field(..., description="A document produced by GET /api/system/export")


@router.get("/info")
async def system_info():
    """The effective environment + config row counts.

    Secret-shaped settings are reported as booleans only — no key, token, or
    connection string is ever echoed back.
    """
    from app.config import get_settings, get_version

    cfg = get_settings()
    counts: dict[str, int] = {}
    async with (await get_shared_session_factory())() as session:
        for name, model in (
            ("design_systems", DesignSystem),
            ("templates", Template),
            ("design_languages", DesignLanguage),
            ("platforms", Platform),
            ("fonts", Font),
            ("agents", Agent),
            ("app_settings", AppSetting),
        ):
            res = await session.execute(select(func.count()).select_from(model))
            counts[name] = int(res.scalar_one())

    model_count = 0
    try:
        from app.services.models import MODEL_REGISTRY

        model_count = len(MODEL_REGISTRY)
    except Exception as e:  # noqa: BLE001
        log.warning("[system-info] model registry unavailable: %s", e)

    return {
        "version": get_version(),
        "llm_configured": bool(cfg.cloudflare_ai_gateway_token or cfg.cf_aig_token),
        "gateway_id": cfg.cf_gateway_id,
        "decision_provider_order": cfg.decision_provider_order,
        "redis_configured": bool(cfg.redis_url),
        "renderer_url": cfg.renderer_url,
        "output_ttl_hours": cfg.output_ttl_hours,
        "delete_on_download": cfg.delete_on_download,
        "rate_limit_per_min": cfg.rate_limit_per_min,
        "rate_limit_interactive_per_min": cfg.rate_limit_interactive_per_min,
        "skip_verify": cfg.skip_verify,
        "copy_qa_enforce": cfg.copy_qa_enforce,
        "image_max_bytes": cfg.image_max_bytes,
        "photo_keys_configured": bool(cfg.pexels_api_key or cfg.pixabay_api_key),
        "counts": {**counts, "models": model_count},
        "schema_version": system_export.SCHEMA_VERSION,
    }


@router.get("/export")
async def export_system():
    pool = await get_shared_session_factory()
    doc = await system_export.export_system(pool)
    log.info(
        "[system-export] snapshot: %s",
        {t: len(v) for t, v in doc.items() if isinstance(v, list)},
    )
    return doc


@router.post("/import")
async def import_system(body: SystemImport):
    issues = system_export.validate_payload(body.payload)
    if issues:
        raise HTTPException(status_code=422, detail="; ".join(issues))

    pool = await get_shared_session_factory()
    counts = await system_export.import_system(pool, body.payload)
    log.info("[system-import] applied: %s", counts)
    return {"applied": counts}
