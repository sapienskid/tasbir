"""Cover workspace API; artifacts use the normal task delivery and retention."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.ratelimit import interactive
from app.db.repositories.tasks import TaskRepository
from app.services.covers import (
    COVER_HEIGHT,
    COVER_MOTIFS,
    COVER_SIZES,
    COVER_WIDTH,
    CoverRequest,
    build_cover_svg,
    cover_html,
)
from app.services.decisions import providers_configured
from app.services.ds_context import DSResolutionError, resolve_ds_context_strict
from app.tasks.covers import cover_task

router = APIRouter()


@router.get("/meta")
async def cover_meta():
    from app.services.art import CONCEPTS, FIELDS, RELATIONS, SUBJECTS

    return {
        "width": COVER_WIDTH,
        "height": COVER_HEIGHT,
        "sizes": COVER_SIZES,
        "motifs": [{"id": key, "label": label} for key, label in COVER_MOTIFS.items()],
        "concepts": [{"id": k, "label": v["label"]} for k, v in CONCEPTS.items()],
        "subjects": [{"id": k, "label": v["label"]} for k, v in SUBJECTS.items()],
        "relations": [{"id": k, "label": v["label"]} for k, v in RELATIONS.items()],
        "fields": [{"id": k, "label": v["label"]} for k, v in FIELDS.items()],
        "ai_available": providers_configured(),
    }


@router.post("/preview")
@interactive
async def preview_cover(request: CoverRequest, db: AsyncSession = Depends(get_db)):
    if request.engine != "procedural":
        raise HTTPException(status_code=422, detail="Generate AI artwork to see its preview")
    try:
        ctx = await resolve_ds_context_strict(db, request.design_system_id)
    except DSResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request.seed = request.seed.strip() or "cover-preview"
    return {"html": cover_html(build_cover_svg(request, ctx, 0), request.width, request.height)}


@router.post("", status_code=202)
async def create_covers(request: CoverRequest, db: AsyncSession = Depends(get_db)):
    try:
        await resolve_ds_context_strict(db, request.design_system_id)
    except DSResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if request.engine == "ai" and not providers_configured():
        raise HTTPException(status_code=422, detail="Cloudflare Workers AI is not configured")
    request.seed = request.seed.strip() or uuid.uuid4().hex
    source = {**request.model_dump(), "mode": "cover"}
    repo = TaskRepository(db)
    task = await repo.create(source_data=source)
    try:
        cover_task.delay(str(task.id))
    except Exception as exc:
        await repo.update_status(str(task.id), "failed", error="Cover queue unavailable")
        raise HTTPException(status_code=503, detail="Cover queue unavailable; try again") from exc
    return {"task_id": str(task.id), "status": "pending"}
