"""System export/import API — portable config backup & restore.

GET  /api/system/export  → full config snapshot (design systems, templates,
                           platforms, fonts, agents, runtime settings) as JSON.
POST /api/system/import  → upsert that snapshot back into the DB (merge, not
                           replace). Rows absent from the payload are untouched.

Runtime data (tasks/audit/chat) is intentionally not part of the snapshot.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import system_export

log = logging.getLogger(__name__)

router = APIRouter()


class SystemImport(BaseModel):
    payload: dict = Field(..., description="A document produced by GET /api/system/export")


@router.get("/export")
async def export_system():
    from app.db.session import get_shared_session_factory

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

    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    counts = await system_export.import_system(pool, body.payload)
    log.info("[system-import] applied: %s", counts)
    return {"applied": counts}
