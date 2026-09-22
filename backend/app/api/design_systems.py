"""Design systems API — CRUD, logo, preview, and agentic creation jobs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.templates import TemplateRepository
from app.services import design_systems as ds_service
from app.services.uploads import validate_upload

log = logging.getLogger(__name__)

router = APIRouter()


class DesignSystemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)


class DesignSystemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    brand: dict | None = None
    footer: dict | None = None
    categories: list | None = None
    overrides: dict | None = None
    tokens: dict | None = None
    token_roles: dict | None = None
    campaigns: dict | None = None
    design_instruction: dict | None = None
    is_active: bool | None = None


class DesignSystemStyleRequest(BaseModel):
    style_language: str = Field(min_length=1, max_length=64)


async def _count_templates(db: AsyncSession, ds_id: str) -> int:
    rows = await TemplateRepository(db).list(ds_id, include_inactive=True)
    return len(rows)


@router.get("")
async def list_design_systems(
    include_inactive: bool = False, db: AsyncSession = Depends(get_db)
):
    repo = DesignSystemRepository(db)
    systems = await repo.list(include_inactive=include_inactive)
    result = []
    for ds in systems:
        item = ds_service.ds_to_dict(ds, template_count=await _count_templates(db, ds.id))
        result.append(item)
    return result


@router.post("")
async def create_design_system(
    request: DesignSystemCreate, db: AsyncSession = Depends(get_db)
):
    repo = DesignSystemRepository(db)
    base = ds_service.slugify(request.name)
    ds_id = base
    suffix = 2
    while await repo.get_by_id(ds_id):
        ds_id = f"{base}-{suffix}"
        suffix += 1

    ds = await repo.create(
        ds_id,
        {
            "name": request.name,
            "description": request.description,
            "source": "manual",
            "is_active": True,
            **ds_service.new_design_system_defaults(request.name),
        },
    )
    from app.services.seeding import seed_starter_templates

    count = await seed_starter_templates(
        db, ds_id, {str(c.get("name")) for c in (ds.categories or []) if c.get("name")}
    )
    return ds_service.ds_to_dict(ds, template_count=count)


@router.get("/styles")
async def list_style_languages(db: AsyncSession = Depends(get_db)):
    """List the design languages (built-in presets + user-created customs)."""
    from app.services.design_languages import list_languages

    langs = await list_languages(db)
    return [
        {
            "id": d.id,
            "label": d.name,
            "description": d.description,
            "emoji": d.emoji,
            "accent": d.accent,
            "grayscale": d.grayscale,
            "media_policy": d.media_policy,
            "accent_tokens": d.accent_tokens,
            "palette_tokens": d.palette_tokens,
        }
        for d in langs
    ]


@router.post("/{ds_id}/style")
async def apply_design_system_style(
    ds_id: str, request: DesignSystemStyleRequest, db: AsyncSession = Depends(get_db)
):
    """Switch a design system to a design language (preset or custom).

    Applies the language's rules to the design_instruction (preserving the
    user's type scale/spacing/footer), replaces the core color tokens with the
    language's palette, provisions accent tokens, and seeds starter templates
    for families the system lacks. See ``apply_language_to_system``.
    """
    from app.services.design_languages import apply_language_to_system, get_language

    if await get_language(db, request.style_language) is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown design language {request.style_language!r}",
        )

    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")

    updated, seeded = await apply_language_to_system(db, ds, request.style_language)
    return {
        **ds_service.ds_to_dict(updated, template_count=await _count_templates(db, ds_id)),
        "seeded_templates": seeded,
    }


@router.get("/{ds_id}")
async def get_design_system(ds_id: str, db: AsyncSession = Depends(get_db)):
    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")
    return ds_service.ds_to_dict(ds, template_count=await _count_templates(db, ds.id))


@router.put("/{ds_id}")
async def update_design_system(
    ds_id: str, request: DesignSystemUpdate, db: AsyncSession = Depends(get_db)
):
    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")

    data = request.model_dump(exclude_unset=True)
    # A blank token value means "unset" (the Studio token editor sends the
    # whole map) — drop it rather than persisting an invalid ``--x: ;``.
    # Every other malformed/unsafe value is rejected with 422 below.
    if isinstance(data.get("tokens"), dict):
        data["tokens"] = {
            k: v
            for k, v in data["tokens"].items()
            if not (isinstance(v, str) and not v.strip())
        }
    # Only allow patching the fields supplied; keep the rest.
    issues = ds_service.validate_design_system(data)
    if issues:
        raise HTTPException(status_code=422, detail="; ".join(issues))

    # A style_language that names no known language would silently render
    # with the base instruction — reject it here (needs the DB).
    di = data.get("design_instruction")
    if isinstance(di, dict):
        language = di.get("style_language") or ""
        if language:
            from app.services.design_languages import get_language

            if await get_language(db, language) is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown design language {language!r}",
                )

    # Editing the default system hands ownership from the seed to the Studio —
    # the startup seed-sync must not revert the change on the next restart.
    if ds.id == ds_service.DEFAULT_ID and ds.source == "seed":
        data.setdefault("source", "manual")

    updated = await repo.update(ds_id, data)
    return ds_service.ds_to_dict(updated, template_count=await _count_templates(db, ds_id))


@router.delete("/{ds_id}", status_code=204)
async def delete_design_system(ds_id: str, db: AsyncSession = Depends(get_db)):
    if ds_id == ds_service.DEFAULT_ID:
        raise HTTPException(status_code=422, detail="The default design system cannot be deleted")
    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")
    # Atomic: templates + design system in one transaction.
    deleted = await repo.delete_cascade(ds_id)
    log.info("[design-systems] Deleted %s (+%d templates)", ds_id, deleted)


@router.post("/{ds_id}/logo")
async def upload_logo(
    ds_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    from app.services.uploads import validate_logo_upload

    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")
    raw = await file.read()
    try:
        mime, b64 = validate_logo_upload(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    logo = {
        "mime": mime,
        "data": b64,
        "filename": file.filename or "logo",
    }
    # A primary re-upload must not destroy per-ground variants.
    grounds = (ds.logo or {}).get("grounds")
    if isinstance(grounds, dict) and grounds:
        logo["grounds"] = grounds
    await repo.update(ds_id, {"logo": logo})
    return {"id": ds_id, "has_logo": True, "mime": mime, "size": len(raw)}


async def _logo_grounds_variant(
    ds_id: str, ground: str, file: UploadFile, db: AsyncSession,
):
    """Store a per-ground logo variant (``white`` | ``black``)."""
    from app.services.uploads import validate_logo_upload

    if ground not in ("white", "black"):
        raise HTTPException(status_code=422, detail="ground must be 'white' or 'black'")
    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")
    raw = await file.read()
    try:
        mime, b64 = validate_logo_upload(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    logo = dict(ds.logo or {})
    grounds = dict(logo.get("grounds") or {})
    grounds[ground] = {
        "mime": mime,
        "data": b64,
        "filename": file.filename or f"logo-{ground}",
    }
    logo["grounds"] = grounds
    await repo.update(ds_id, {"logo": logo})
    return {"id": ds_id, "ground": ground, "mime": mime, "size": len(raw)}


@router.post("/{ds_id}/logo/grounds/{ground}")
async def upload_logo_variant(
    ds_id: str, ground: str, file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a per-ground logo variant (e.g. a light mark for dark grounds)."""
    return await _logo_grounds_variant(ds_id, ground, file, db)


@router.delete("/{ds_id}/logo/grounds/{ground}", status_code=204)
async def remove_logo_variant(
    ds_id: str, ground: str, db: AsyncSession = Depends(get_db)
):
    """Remove a per-ground logo variant (falls back to the primary logo)."""
    if ground not in ("white", "black"):
        raise HTTPException(status_code=422, detail="ground must be 'white' or 'black'")
    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")
    logo = dict(ds.logo or {})
    grounds = dict(logo.get("grounds") or {})
    grounds.pop(ground, None)
    if grounds:
        logo["grounds"] = grounds
    else:
        logo.pop("grounds", None)
    await repo.update(ds_id, {"logo": logo})


@router.delete("/{ds_id}/logo", status_code=204)
async def remove_logo(ds_id: str, db: AsyncSession = Depends(get_db)):
    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")
    await repo.update(ds_id, {"logo": None})


@router.post("/{ds_id}/preview")
async def preview_design_system(ds_id: str, db: AsyncSession = Depends(get_db)):
    """Render a sample layout with the design system's current tokens."""
    from app.db.session import get_shared_session_factory

    repo = DesignSystemRepository(db)
    ds = await repo.get_by_id(ds_id)
    if not ds:
        raise NotFoundError(f"Design system {ds_id!r} not found")

    pool = await get_shared_session_factory()
    preview = await ds_service.render_ds_preview(ds, pool)
    return {"id": ds_id, **preview}


@router.post("/from-input")
async def create_from_input(
    name: str = Form(...),
    tagline: str = Form(default=""),
    mission: str = Form(default=""),
    industry: str = Form(default=""),
    audience: str = Form(default=""),
    style: str = Form(default=""),
    handle: str = Form(default=""),
    reference_image: UploadFile | None = File(default=None),
    logo_image: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Start the brand-builder job from a form (+ optional reference/logo images)."""
    from app.db.repositories.agent_jobs import AgentJobRepository
    from app.services.uploads import validate_logo_upload, validate_upload
    from app.tasks.agent_jobs import run_design_system_from_input

    payload: dict = {
        "name": name,
        "tagline": tagline,
        "mission": mission,
        "industry": industry,
        "audience": audience,
        "style": style,
        "handle": handle,
    }
    if reference_image is not None:
        raw = await reference_image.read()
        try:
            mime, b64 = validate_upload(raw)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"reference_image: {e}")
        payload["reference_image"] = b64
        payload["reference_mime"] = mime
    if logo_image is not None:
        raw = await logo_image.read()
        try:
            mime, b64 = validate_logo_upload(raw)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"logo_image: {e}")
        payload["logo_image"] = b64
        payload["logo_mime"] = mime

    job = await AgentJobRepository(db).create("design_system", payload)
    run_design_system_from_input.delay(str(job.id), payload)
    return {"job_id": str(job.id), "status": "pending"}
