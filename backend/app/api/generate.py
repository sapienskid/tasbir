from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.db.repositories.tasks import TaskRepository
from app.services.formats import CAROUSEL_BASES, validate_platforms
from app.tasks.generate import generate_task

router = APIRouter()


class ImageRequest(BaseModel):
    url: str = Field(default="", max_length=2048)
    data: str = Field(default="", max_length=40_000_000)
    mime: str = Field(default="image/png", max_length=32)
    alt: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=500)
    placement: str = Field(default="auto", max_length=32)


class GenerateRequest(BaseModel):
    content: str = Field(max_length=100_000)
    title: str = Field(default="", max_length=300)
    excerpt: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    platforms: list[str] = Field(default_factory=lambda: ["instagram-square"], max_length=12)
    slides: int | None = Field(default=None, ge=2, le=10)
    # Carousel aspect: "square" | "portrait" | "auto" (planner decides).
    # Default "square" keeps the common carousel pick deterministic; the
    # planner runs when the user opts into "auto" (or "auto" platforms).
    ratio: str = Field(default="square", max_length=16)
    # Opt-in vision audit of the whole carousel sequence (one vision call).
    sequence_audit: bool = False
    campaign: str = Field(default="default", max_length=64)
    category: str | None = Field(default=None, max_length=64)
    design_system_id: str = Field(default="default", max_length=64)
    template_id: str = Field(default="", max_length=64)
    # Post type steers copy + which optional extras (price/date/location/cta)
    # the copywriter fills. "default" is the generic editorial post.
    post_type: str = Field(default="default", max_length=32)
    # Per-post design language override: "" = the design system's own language,
    # otherwise a design-language id applied to this post only (never persisted).
    style_language: str = Field(default="", max_length=64)
    # How the per-format chain produces HTML: "auto" (template first, LLM
    # designer fallback), "template" (never call the designer LLM — fail a
    # format if no template matches), "designer" (skip templates, always LLM).
    template_mode: str = Field(default="auto", max_length=16)
    overrides: dict[str, str] = Field(default_factory=dict)
    images: list[ImageRequest] = Field(default_factory=list, max_length=8)
    # Keep the source content verbatim: carousels split the raw text across
    # slides (no LLM paraphrase) — ideal for essays, stories, and poems.
    verbatim: bool = False
    # Illustration style for the media plan: "compose" (default), "procedural",
    # or a curated DiceBear id (open-peeps, lorelei, notionists, bottts, blobs,
    # initials, shapes, waves, landscape). Empty/null → media-plan LLM pick.
    illustration_style: str = Field(default="", max_length=64)

    @field_validator("illustration_style")
    @classmethod
    def _validate_illustration_style(cls, v: str) -> str:
        if not v:
            return ""
        from app.services.tools.illustrator import ILLUSTRATE_TOOL

        enum = ILLUSTRATE_TOOL["function"]["parameters"]["properties"]["style"]["enum"]
        if v not in enum:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown illustration_style {v!r} — choose from {enum}",
            )
        return v

    @field_validator("tags")
    @classmethod
    def _cap_tag_length(cls, v: list[str]) -> list[str]:
        return [t[:100] for t in v]

    @field_validator("template_mode")
    @classmethod
    def _validate_template_mode(cls, v: str) -> str:
        if v not in ("auto", "template", "designer"):
            raise HTTPException(
                status_code=422,
                detail="template_mode must be 'auto', 'template', or 'designer'",
            )
        return v

    @field_validator("post_type")
    @classmethod
    def _validate_post_type(cls, v: str) -> str:
        allowed = {
            "default", "quote", "promo", "event", "product", "comparison", "tutorial",
        }
        if v not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"post_type must be one of {sorted(allowed)}",
            )
        return v

    @field_validator("overrides")
    @classmethod
    def _cap_overrides(cls, v: dict[str, str]) -> dict[str, str]:
        limited = {k[:50]: val[:500] for k, val in v.items()}
        if len(limited) > 8:
            raise HTTPException(status_code=422, detail="Too many overrides (max 8)")
        return limited

    @field_validator("platforms")
    @classmethod
    def _validate_platforms(cls, v: list[str]) -> list[str]:
        """Validate known platform ids; allow the literal "auto" (planner)."""
        cleaned: list[str] = []
        for p in v:
            if p == "auto":
                cleaned.append(p)
                continue
            cleaned.extend(validate_platforms([p]))
        return cleaned

    @model_validator(mode="after")
    def _apply_carousel_slides(self) -> "GenerateRequest":
        platforms = self.platforms or []
        has_carousel = any(p in CAROUSEL_BASES for p in platforms)
        if self.slides is not None and not has_carousel:
            raise HTTPException(
                status_code=422,
                detail="'slides' is only valid when a carousel platform is in platforms",
            )
        if has_carousel:
            if self.slides is None:
                # Pinned ratio → deterministic default; "auto" → planner decides.
                self.slides = 3 if self.ratio in ("square", "portrait") else 0
        return self


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"


@router.post("", response_model=GenerateResponse)
async def generate(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    data = request.model_dump()
    repo = TaskRepository(db)
    task = await repo.create(source_data=data)
    generate_task.delay(str(task.id), data)
    return GenerateResponse(task_id=str(task.id))
