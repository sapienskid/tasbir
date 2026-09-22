"""Manual Compose API — operator-built posts, zero LLM calls (ADR-0021).

The operator picks a design system + language + ground once per batch, then
for every post a template, copy, and media (upload / stock photo / offline
illustration / none). Each post becomes its own GenerationTask
(``source_data.mode == "manual"``) rendered by the deterministic
``compose_task``; tasks of one batch share ``source_data.batch_id``.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.core.ratelimit import interactive
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.tasks import TaskRepository
from app.db.repositories.templates import TemplateRepository
from app.services.formats import (
    carousel_slide_id,
    get_format_info,
    is_carousel_base,
    parse_carousel_slide,
    validate_platforms,
)

log = logging.getLogger(__name__)

router = APIRouter()
# Mounted under /api/tasks — the per-task composition edit endpoint.
tasks_router = APIRouter()

MAX_POSTS = 20
MIN_CAROUSEL_SLIDES = 2
MAX_CAROUSEL_SLIDES = 10
MAX_UPLOAD_B64 = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Request shapes (see the Manual Compose spec / ADR-0021)
# ---------------------------------------------------------------------------


class ComposeExtra(BaseModel):
    price: str = Field(default="", max_length=200)
    cta: str = Field(default="", max_length=200)
    date: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    stat: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=200)


class ComposeCopy(BaseModel):
    kicker: str = Field(default="", max_length=120)
    headline: str = Field(default="", max_length=300)
    subhead: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=3000)
    tagline: str = Field(default="", max_length=120)
    extra: ComposeExtra = Field(default_factory=ComposeExtra)


class MediaNone(BaseModel):
    kind: Literal["none"] = "none"


class MediaUpload(BaseModel):
    kind: Literal["upload"]
    data: str = Field(min_length=1, max_length=MAX_UPLOAD_B64)
    mime: str = Field(default="image/png", max_length=32)
    alt: str = Field(default="", max_length=300)


class MediaPhoto(BaseModel):
    kind: Literal["photo"]
    url: str = Field(min_length=1, max_length=2048)
    credit: str = Field(default="", max_length=300)
    provider: str = Field(default="", max_length=32)
    photographer: str = Field(default="", max_length=200)
    license: str = Field(default="", max_length=200)


class MediaIllustration(BaseModel):
    kind: Literal["illustration"]
    style: str = Field(default="procedural", max_length=64)
    seed: str = Field(default="", max_length=128)


MediaSpec = Annotated[
    MediaNone | MediaUpload | MediaPhoto | MediaIllustration,
    Field(discriminator="kind"),
]


class SlideSpec(BaseModel):
    # ``copy`` would shadow BaseModel.copy — stored as ``copy_``, (de)serialized
    # as "copy" so the wire/storage shape is unchanged.
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    template_id: str = Field(min_length=1, max_length=64)
    copy_: ComposeCopy = Field(default_factory=ComposeCopy, alias="copy")
    # Element toggles; null = the template's own default hidden elements.
    hidden: list[Annotated[str, Field(max_length=64)]] | None = Field(
        default=None, max_length=32
    )
    media_position: Literal["auto", "left", "right", "top", "bottom"] = "auto"
    media: MediaSpec = Field(default_factory=MediaNone)


class PostSpec(BaseModel):
    platform: str = Field(min_length=1, max_length=64)
    slides: list[SlideSpec] = Field(min_length=1, max_length=MAX_CAROUSEL_SLIDES)


class ComposeBatchRequest(BaseModel):
    design_system_id: str = Field(default="default", max_length=64)
    style_language: str = Field(default="", max_length=64)
    ground: Literal["white", "black"] = "white"
    title: str = Field(default="", max_length=300)
    posts: list[PostSpec] = Field(min_length=1, max_length=MAX_POSTS)


class CompositionUpdate(BaseModel):
    design_system_id: str = Field(default="default", max_length=64)
    style_language: str = Field(default="", max_length=64)
    ground: Literal["white", "black"] = "white"
    post: PostSpec


class ComposePreviewRequest(BaseModel):
    design_system_id: str = Field(default="default", max_length=64)
    style_language: str = Field(default="", max_length=64)
    ground: Literal["white", "black"] = "white"
    platform: str = Field(min_length=1, max_length=64)
    slide_index: int = Field(default=1, ge=1, le=MAX_CAROUSEL_SLIDES)
    slide_total: int = Field(default=1, ge=1, le=MAX_CAROUSEL_SLIDES)
    slide: SlideSpec


class TemplateMapRequest(BaseModel):
    from_design_system_id: str = Field(max_length=64)
    to_design_system_id: str = Field(max_length=64)
    template_ids: list[Annotated[str, Field(max_length=64)]] = Field(max_length=200)
    platform: str = Field(min_length=1, max_length=64)


# ---------------------------------------------------------------------------
# Validation (422 with a clear detail — nothing is created on failure)
# ---------------------------------------------------------------------------


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


async def _validate_system(db: AsyncSession, ds_id: str, style_language: str) -> None:
    from app.services.design_languages import get_language

    row = await DesignSystemRepository(db).get_by_id(ds_id)
    if row is None:
        raise _unprocessable(f"Unknown design system {ds_id!r}")
    if not row.is_active:
        raise _unprocessable(f"Design system {ds_id!r} is inactive")
    if style_language and await get_language(db, style_language) is None:
        raise _unprocessable(f"Unknown design language {style_language!r}")


def _validate_platform(platform: str) -> str:
    """A known platform id — a carousel base or a single-post platform (not a slide id)."""
    platform = validate_platforms([platform])[0]
    if parse_carousel_slide(platform):
        raise _unprocessable(
            f"Use the carousel base platform, not a slide id ({platform!r})"
        )
    return platform


def _illustration_styles() -> list[str]:
    from app.services.tools.illustrator import ILLUSTRATE_TOOL

    return ILLUSTRATE_TOOL["function"]["parameters"]["properties"]["style"]["enum"]


def _validate_media(slide: SlideSpec, where: str) -> None:
    """Validate (and normalize) a slide's media in place."""
    media = slide.media
    if isinstance(media, MediaUpload):
        from app.services.uploads import validate_upload

        try:
            data = re.sub(r"^data:[^,]*;base64,", "", media.data.strip())
            raw = base64.b64decode(re.sub(r"\s+", "", data), validate=True)
            mime, b64 = validate_upload(raw)
        except (binascii.Error, ValueError) as e:
            raise _unprocessable(f"{where}: invalid upload — {e}")
        # The sniffed type wins over the declared one (it lands in a data: URI).
        media.mime = mime
        media.data = b64
    elif isinstance(media, MediaPhoto):
        if not media.url.startswith("https://"):
            raise _unprocessable(f"{where}: photo url must be https")
    elif isinstance(media, MediaIllustration):
        if media.style not in _illustration_styles():
            raise _unprocessable(
                f"{where}: unknown illustration style {media.style!r}"
            )


async def _validate_slide_template(
    db: AsyncSession, ds_id: str, platform: str, slide: SlideSpec, where: str
):
    from app.services.templates import format_family

    row = await TemplateRepository(db).get_by_id(slide.template_id)
    if row is None or row.design_system_id != ds_id or not row.is_active:
        raise _unprocessable(
            f"{where}: unknown template {slide.template_id!r} for design system {ds_id!r}"
        )
    family = format_family(platform)
    if row.family != family:
        raise _unprocessable(
            f"{where}: template {slide.template_id!r} is a {row.family} template — "
            f"{platform} needs a {family} template"
        )
    return row


async def _validate_post(db: AsyncSession, ds_id: str, post: PostSpec, where: str) -> None:
    post.platform = _validate_platform(post.platform)
    n = len(post.slides)
    if is_carousel_base(post.platform):
        if not MIN_CAROUSEL_SLIDES <= n <= MAX_CAROUSEL_SLIDES:
            raise _unprocessable(
                f"{where}: a carousel needs {MIN_CAROUSEL_SLIDES}–{MAX_CAROUSEL_SLIDES} "
                f"slides (got {n})"
            )
    elif n != 1:
        raise _unprocessable(f"{where}: {post.platform} takes exactly 1 slide (got {n})")
    for i, slide in enumerate(post.slides, 1):
        slide_where = f"{where} slide {i}"
        await _validate_slide_template(db, ds_id, post.platform, slide, slide_where)
        _validate_media(slide, slide_where)


def _composition(ds_id: str, style_language: str, ground: str, post: PostSpec) -> dict:
    return {
        "design_system_id": ds_id,
        "style_language": style_language,
        "ground": ground,
        "post": post.model_dump(),
    }


def _source_data(
    batch_id: str, ds_id: str, style_language: str, ground: str, platform: str, title: str
) -> dict:
    return {
        "mode": "manual",
        "batch_id": batch_id,
        "design_system_id": ds_id,
        "style_language": style_language,
        "ground": ground,
        "platforms": [platform],
        "title": title,
    }


def _post_title(title: str, post: PostSpec) -> str:
    """The batch label, else the post's first headline (task lists need a name)."""
    if title:
        return title
    headline = post.slides[0].copy_.headline.strip() if post.slides else ""
    return headline[:120] or "Manual post"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/preview")
@interactive
async def preview_slide(request: ComposePreviewRequest, db: AsyncSession = Depends(get_db)):
    """Fully finalized HTML for one slide (tokens/fonts/logo/media) — no PNG, no LLM."""
    from app.services.composer import compose_slide
    from app.services.ds_context import resolve_ds_context

    await _validate_system(db, request.design_system_id, request.style_language)
    platform = _validate_platform(request.platform)
    row = await _validate_slide_template(
        db, request.design_system_id, platform, request.slide, "slide"
    )
    _validate_media(request.slide, "slide")

    carousel = is_carousel_base(platform)
    fmt_id = carousel_slide_id(platform, request.slide_index) if carousel else platform
    fmt = get_format_info(fmt_id)
    ctx = await resolve_ds_context(db, request.design_system_id, request.style_language)
    try:
        html = await compose_slide(
            ctx,
            row,
            fmt_id,
            request.slide.model_dump(),
            request.slide_index,
            max(request.slide_total, request.slide_index),
            request.ground,
        )
    except Exception as e:  # noqa: BLE001 — a broken template is the operator's to fix
        raise _unprocessable(f"Template render failed: {e}")
    return {"html": html, "width": fmt.width, "height": fmt.height}


@router.post("")
async def create_batch(request: ComposeBatchRequest, db: AsyncSession = Depends(get_db)):
    """Validate a batch up front, create one task per post, enqueue compose jobs."""
    from app.tasks.compose import compose_task

    await _validate_system(db, request.design_system_id, request.style_language)
    for i, post in enumerate(request.posts, 1):
        await _validate_post(db, request.design_system_id, post, f"post {i}")

    batch_id = str(uuid.uuid4())
    repo = TaskRepository(db)
    task_ids: list[str] = []
    for post in request.posts:
        task = await repo.create(
            source_data=_source_data(
                batch_id,
                request.design_system_id,
                request.style_language,
                request.ground,
                post.platform,
                _post_title(request.title, post),
            ),
            composition=_composition(
                request.design_system_id, request.style_language, request.ground, post
            ),
        )
        task_ids.append(str(task.id))
    for task_id in task_ids:
        compose_task.delay(task_id)
    return {"batch_id": batch_id, "task_ids": task_ids}


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    tasks = await TaskRepository(db).list_by_batch(batch_id)
    if not tasks:
        raise NotFoundError(f"Batch {batch_id} not found")
    out = []
    for t in tasks:
        composition = t.composition or {}
        platform = (composition.get("post") or {}).get("platform") or next(
            iter((t.source_data or {}).get("platforms") or []), ""
        )
        out.append(
            {
                "task_id": t.id,
                "status": t.status,
                "platform": platform,
                "composition": t.composition,
            }
        )
    return {"batch_id": batch_id, "tasks": out}


@router.get("/illustration")
@interactive
async def illustration(style: str = "procedural", seed: str = "", ground: str = "white"):
    """An offline illustration (procedural / DiceBear) for picker thumbnails."""
    from app.services.composer import render_illustration

    if style not in _illustration_styles():
        raise _unprocessable(f"Unknown illustration style {style!r}")
    if ground not in ("white", "black"):
        raise _unprocessable("ground must be 'white' or 'black'")
    return {"svg": render_illustration(style, seed[:128] or "figure", ground)}


def _thumb_url(c: dict) -> str:
    """A small preview URL (Pexels' CDN resizes; other providers are used as-is)."""
    url = c.get("url") or ""
    if c.get("provider") == "pexels":
        url = re.sub(r"([?&])w=\d+", r"\g<1>w=360", url)
        url = re.sub(r"([?&])h=\d+", lambda m: f"{m.group(1)}h=360", url)
    return url


@router.get("/photos")
@interactive
async def search_photos(q: str, orientation: str = "square"):
    """Stock photo search (Pexels → Pixabay → Wikimedia). No LLM pick."""
    from app.services.tools.photo import _attribution, search_photo_candidates

    q = q.strip()[:100]
    if not q:
        raise _unprocessable("q is required")
    if orientation not in ("square", "portrait", "landscape"):
        raise _unprocessable("orientation must be square, portrait, or landscape")
    candidates = await search_photo_candidates(q, orientation, limit=12, grayscale=False)
    return {
        "results": [
            {
                "url": c.get("url") or "",
                "thumb": _thumb_url(c),
                "width": int(c.get("width") or 0),
                "height": int(c.get("height") or 0),
                "provider": c.get("provider") or "",
                "photographer": c.get("photographer") or "",
                "credit": _attribution(c),
                "license": c.get("license") or "",
            }
            for c in candidates
            if c.get("url")
        ]
    }


@router.post("/templates/map")
async def map_templates(request: TemplateMapRequest, db: AsyncSession = Depends(get_db)):
    """Map templates onto another design system (same id, else closest match).

    Closest = same format family, then hint-tag overlap, same media capability,
    shared content fields, and weight. Ids with no same-family candidate in
    the target system are omitted from the mapping.
    """
    from app.services.templates import format_family, match_template, template_to_dict

    platform = _validate_platform(request.platform)
    family = format_family(platform)
    repo = TemplateRepository(db)
    targets = [r for r in await repo.list(request.to_design_system_id) if r.family == family]
    by_id = {r.id: r for r in targets}
    target_dicts = [template_to_dict(r) for r in targets]

    mapping: dict[str, str] = {}
    for tid in request.template_ids:
        if tid in by_id:
            mapping[tid] = tid
            continue
        if not targets:
            continue
        src = await repo.get_by_id(tid)
        best = match_template(
            template_to_dict(src) if src is not None else {"id": tid},
            target_dicts,
        )
        if best is not None:
            mapping[tid] = str(best["id"])
    return {"mapping": mapping}


@tasks_router.put("/{task_id}/composition")
async def update_composition(
    task_id: str, request: CompositionUpdate, db: AsyncSession = Depends(get_db)
):
    """Re-validate + store a manual task's composition, then re-compose it."""
    from app.api.tasks import is_manual_task
    from app.tasks.compose import compose_task

    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    if not is_manual_task(task):
        raise _unprocessable("Only manually composed tasks have a composition")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")

    await _validate_system(db, request.design_system_id, request.style_language)
    await _validate_post(db, request.design_system_id, request.post, "post")

    source = dict(task.source_data or {})
    source.update(
        {
            "design_system_id": request.design_system_id,
            "style_language": request.style_language,
            "ground": request.ground,
            "platforms": [request.post.platform],
        }
    )
    await repo.save_composition(
        task_id,
        _composition(
            request.design_system_id, request.style_language, request.ground, request.post
        ),
        source_data=source,
    )
    compose_task.delay(task_id)
    return {"task_id": task_id, "status": "pending"}
