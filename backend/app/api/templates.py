"""Templates API — DB-backed CRUD, validation, live preview, and from-image jobs."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.core.time import iso_utc
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.templates import TemplateRepository
from app.services.design_systems import DEFAULT_ID, logo_data_uri
from app.services.templates import (
    build_template_context,
    render_template_html,
    scan_template_features,
)
from app.services.tokens import DEFAULT_TOKEN_VALUES

log = logging.getLogger(__name__)

router = APIRouter()

# A monochrome placeholder injected into previews that declare image slots.
_PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800">'
    '<rect width="800" height="800" fill="#D9D9D9"/>'
    '<rect x="340" y="340" width="120" height="120" fill="#6E6E6E"/></svg>'
)
_PLACEHOLDER_B64 = base64.b64encode(_PLACEHOLDER_SVG.encode("utf-8")).decode("ascii")

SAMPLE_COPY = {
    "headline": "The quiet discipline of a well-set column of type",
    "subhead": "White space is the rhythm between ideas; a grid gives it a voice.",
    "body": "A grid sets order and a measure sets pace. Constrain the line, free "
    "the reader, and let the whitespace do its work.",
    "badge": None,
}

DIMS = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
    "landscape": (1200, 627),
}


def _entry(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "design_system_id": row.design_system_id,
        "family": row.family,
        "grounds": row.grounds,
        "categories": row.categories,
        "hint_tags": row.hint_tags,
        "weight": row.weight,
        "description": row.description,
        "image_slots": row.image_slots,
        "has_logo_slot": bool(row.has_logo_slot),
        "supports_text": "{{ body" in (row.html or ""),
        "has_illustration_slot": "{{ illustration" in (row.html or ""),
        "source": row.source,
        "is_active": bool(row.is_active),
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
    }


class TemplateCreate(BaseModel):
    id: str = Field(default="", max_length=64)
    name: str = Field(default="", max_length=128)
    design_system_id: str = Field(default=DEFAULT_ID, max_length=64)
    family: str = Field(default="square", pattern="^(square|portrait|story|landscape)$")
    grounds: list[str] = Field(default_factory=lambda: ["white", "black"])
    categories: list[str] = Field(default_factory=list)
    hint_tags: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.1, le=10.0)
    description: str = Field(default="", max_length=2000)
    html: str = Field(min_length=50, max_length=500_000)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    family: str | None = Field(default=None, pattern="^(square|portrait|story|landscape)$")
    grounds: list[str] | None = None
    categories: list[str] | None = None
    hint_tags: list[str] | None = None
    weight: float | None = Field(default=None, ge=0.1, le=10.0)
    description: str | None = Field(default=None, max_length=2000)
    html: str | None = Field(default=None, min_length=50, max_length=500_000)
    is_active: bool | None = None


async def _validate_render(
    db: AsyncSession, html: str, family: str, grounds: list[str]
) -> list[str]:
    """Render with sample copy + overflow check. Returns issues ([] = ok)."""
    from app.services.design_instruction import (
        build_google_fonts_link,
        inject_fonts_into_html,
    )
    from app.services.dom_extractor import detect_overflow
    from app.services.tokens import inject_tokens_into_html

    width, height = DIMS.get(family, DIMS["square"])
    tokens = dict(DEFAULT_TOKEN_VALUES)
    # Neutral sample footer (a handle only) — never a hardcoded brand identity.
    footer = {"left": "", "right": "@handle"}
    ground = grounds[0] if grounds and grounds[0] in ("white", "black") else "white"

    context = build_template_context(
        dict(SAMPLE_COPY), "WRITING", ground, footer, width, height, False,
        seed="validate", family=family,
    )
    try:
        rendered = render_template_html(html, context)
    except Exception as e:
        return [f"Jinja2 render failed: {e}"]
    rendered = inject_tokens_into_html(rendered, tokens)
    rendered = inject_fonts_into_html(rendered, build_google_fonts_link(tokens, {}))
    try:
        overflow = await detect_overflow(rendered, width, height)
    except Exception as e:
        log.warning("[templates] overflow check skipped (render service): %s", e)
        overflow = []
    return overflow


@router.get("")
async def list_templates(
    design_system_id: str = DEFAULT_ID,
    family: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    repo = TemplateRepository(db)
    rows = await repo.list(design_system_id, family=family, include_inactive=include_inactive)
    return [_entry(r) for r in rows]


@router.post("")
async def create_template(request: TemplateCreate, db: AsyncSession = Depends(get_db)):
    repo = TemplateRepository(db)
    ds_repo = DesignSystemRepository(db)
    if not await ds_repo.get_by_id(request.design_system_id):
        raise HTTPException(status_code=422, detail="Design system not found")

    tid = request.id or request.name
    slug = "".join(c for c in tid.lower() if c.isalnum() or c in "-_").strip("-")
    if not slug:
        raise HTTPException(status_code=422, detail="Provide a template id or name")
    template_id = slug if request.family in slug or "-" in slug else f"{request.family}-{slug}"
    if await repo.get_by_id(template_id):
        raise HTTPException(status_code=409, detail=f"Template {template_id!r} already exists")

    bad_grounds = [g for g in request.grounds if g not in ("white", "black")]
    if bad_grounds:
        raise HTTPException(status_code=422, detail=f"Invalid grounds: {bad_grounds}")

    issues = await _validate_render(db, request.html, request.family, request.grounds)
    if issues:
        raise HTTPException(status_code=422, detail="Template overflows: " + "; ".join(issues))

    image_slots, has_logo = scan_template_features(request.html)
    row = await repo.create({
        "id": template_id,
        "design_system_id": request.design_system_id,
        "name": request.name or template_id,
        "family": request.family,
        "grounds": request.grounds,
        "categories": request.categories,
        "hint_tags": request.hint_tags,
        "weight": request.weight,
        "description": request.description,
        "html": request.html,
        "image_slots": image_slots,
        "has_logo_slot": has_logo,
        "source": "manual",
        "is_active": True,
    })
    return _entry(row)


@router.get("/{template_id}")
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    repo = TemplateRepository(db)
    row = await repo.get_by_id(template_id)
    if not row:
        raise NotFoundError(f"Template {template_id!r} not found")
    data = _entry(row)
    data["html"] = row.html
    return data


@router.put("/{template_id}")
async def update_template(
    template_id: str, request: TemplateUpdate, db: AsyncSession = Depends(get_db)
):
    repo = TemplateRepository(db)
    row = await repo.get_by_id(template_id)
    if not row:
        raise NotFoundError(f"Template {template_id!r} not found")

    data = request.model_dump(exclude_unset=True)
    html = data.get("html", row.html)
    family = data.get("family", row.family)
    grounds = data.get("grounds", row.grounds)

    if "html" in data or "family" in data or "grounds" in data:
        issues = await _validate_render(db, html, family, grounds)
        if issues:
            raise HTTPException(status_code=422, detail="Template overflows: " + "; ".join(issues))
        image_slots, has_logo = scan_template_features(html)
        data["image_slots"] = image_slots
        data["has_logo_slot"] = has_logo

    updated = await repo.update(template_id, data)
    return _entry(updated)


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str, db: AsyncSession = Depends(get_db)):
    repo = TemplateRepository(db)
    if not await repo.get_by_id(template_id):
        raise NotFoundError(f"Template {template_id!r} not found")
    await repo.delete(template_id)


@router.post("/{template_id}/render")
async def validate_template(template_id: str, db: AsyncSession = Depends(get_db)):
    repo = TemplateRepository(db)
    row = await repo.get_by_id(template_id)
    if not row:
        raise NotFoundError(f"Template {template_id!r} not found")
    issues = await _validate_render(db, row.html, row.family, row.grounds)
    return {"id": template_id, "ok": not issues, "issues": issues}


@router.post("/{template_id}/preview")
async def preview_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """Render the template with sample copy + real tokens/fonts → {html}."""
    repo = TemplateRepository(db)
    row = await repo.get_by_id(template_id)
    if not row:
        raise NotFoundError(f"Template {template_id!r} not found")
    html = await _render_preview_html(
        db, row.html, row.family, row.design_system_id,
        row.grounds[0] if row.grounds else "white",
    )
    return {"id": template_id, "html": html}


class DraftPreviewRequest(BaseModel):
    html: str = Field(min_length=50, max_length=500_000)
    family: str = Field(default="square", pattern="^(square|portrait|story|landscape)$")
    design_system_id: str = Field(default=DEFAULT_ID, max_length=64)
    ground: str = Field(default="", max_length=16)


@router.post("/preview-draft")
async def preview_draft(request: DraftPreviewRequest, db: AsyncSession = Depends(get_db)):
    """Render arbitrary (draft) template HTML with sample copy → {html}.

    Used by the template editor's live preview pane so edits are visible
    without saving.
    """
    ground = request.ground if request.ground in ("white", "black") else "white"
    html = await _render_preview_html(
        db, request.html, request.family, request.design_system_id, ground
    )
    return {"html": html}


async def _render_preview_html(
    db: AsyncSession,
    html: str,
    family: str,
    design_system_id: str,
    ground: str,
) -> str:
    """Render a template string with sample copy + tokens/fonts/logo."""
    from app.services.design_instruction import (
        build_google_fonts_link,
        inject_fonts_into_html,
        substitute_image_keys,
        substitute_logo,
    )
    from app.services.tokens import inject_tokens_into_html

    ds_repo = DesignSystemRepository(db)
    ds = await ds_repo.get_by_id(design_system_id)

    width, height = DIMS.get(family, DIMS["square"])
    tokens = dict(DEFAULT_TOKEN_VALUES)
    di = {}
    footer = {"left": "", "right": "@handle"}
    logo = ""
    image_slots: list[dict] = []
    if ds:
        tokens.update(ds.tokens or {})
        di = ds.design_instruction or {}
        footer = ds.footer or {}
        logo = logo_data_uri(ds)
        image_slots, _ = scan_template_features(html)

    context = build_template_context(
        dict(SAMPLE_COPY), "WRITING", ground, footer, width, height,
        bool(image_slots), seed="preview", family=family, logo=logo,
    )
    try:
        rendered = render_template_html(html, context)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Template render failed: {e}")

    rendered = inject_tokens_into_html(rendered, tokens)
    rendered = inject_fonts_into_html(rendered, build_google_fonts_link(tokens, di))
    rendered = substitute_logo(rendered, logo)
    if image_slots:
        placeholders = [{"data": _PLACEHOLDER_B64, "mime": "image/svg+xml", "alt": "placeholder"}]
        rendered = substitute_image_keys(rendered, placeholders)
    return rendered


@router.post("/from-image")
async def create_template_from_image(
    file: UploadFile = File(...),
    design_system_id: str = Form(DEFAULT_ID),
    db: AsyncSession = Depends(get_db),
):
    """Start the template-from-image job; returns a job id to poll."""
    from app.db.repositories.agent_jobs import AgentJobRepository
    from app.services.uploads import validate_upload
    from app.tasks.agent_jobs import run_template_from_image

    ds_repo = DesignSystemRepository(db)
    if not await ds_repo.get_by_id(design_system_id):
        raise HTTPException(status_code=422, detail="Design system not found")

    raw = await file.read()
    try:
        mime, b64 = validate_upload(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    payload = {"image": b64, "mime": mime, "design_system_id": design_system_id}
    job = await AgentJobRepository(db).create("template", payload)
    run_template_from_image.delay(str(job.id), payload)
    return {"job_id": str(job.id), "status": "pending"}


@router.post("/from-input")
async def create_template_from_input(
    design_system_id: str = Form(DEFAULT_ID),
    message: str = Form(""),
    html: str = Form(""),
    family: str = Form("square"),
    ground: str = Form("white"),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Start a one-shot template build from image / HTML / text context.

    Creates an AgentJob (kind ``template``) that authors + validates + saves a
    template in the background. Returns a job id to poll.
    """
    from app.db.repositories.agent_jobs import AgentJobRepository
    from app.services.uploads import validate_upload
    from app.tasks.agent_jobs import run_template_build_task

    ds_repo = DesignSystemRepository(db)
    if not await ds_repo.get_by_id(design_system_id):
        raise HTTPException(status_code=422, detail="Design system not found")
    family = family if family in ("square", "portrait", "story", "landscape") else "square"
    ground = ground if ground in ("white", "black") else "white"
    if not message and not html and not file:
        raise HTTPException(status_code=422, detail="Provide an image, HTML, or a description")

    payload: dict = {
        "design_system_id": design_system_id,
        "family": family,
        "ground": ground,
    }
    if message:
        payload["message"] = message
    if html:
        payload["html"] = html
    if file:
        raw = await file.read()
        try:
            mime, b64 = validate_upload(raw)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        payload["image"] = b64
        payload["mime"] = mime

    job = await AgentJobRepository(db).create("template", payload)
    run_template_build_task.delay(str(job.id), payload)
    return {"job_id": str(job.id), "status": "pending"}
