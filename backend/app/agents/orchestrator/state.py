"""GenerationState — shared state for the v3 LangGraph agent pipeline.

Each agent node reads from and writes to this state dict.
Per-format streaming via FormatTask dict + Send fan-out.
"""

from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field, field_validator


def _keep_first(a: str, b: str) -> str:
    return a if a else b


def _keep_first_list(a: list, b: list) -> list:
    return a if a else b


def _keep_first_dict(a: dict, b: dict) -> dict:
    return a if a else b


def _merge_dicts(a: dict, b: dict) -> dict:
    merged = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


class FormatTask(TypedDict):
    status: str
    copy: str
    html: str | None
    html_path: str | None
    quality_score: int
    quality_issues: list[str]
    refinement_count: int
    error: str | None
    template_id: str | None


def merge_format_tasks(
    a: dict[str, FormatTask], b: dict[str, FormatTask]
) -> dict[str, FormatTask]:
    merged = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


class SlideOutline(BaseModel):
    """One frame of a planned carousel — what it should say and hook with."""

    focus: str = ""
    headline_hint: str = ""


class PostPlan(BaseModel):
    """Structural plan for a post (Planner node output).

    ``post_type`` single|carousel|story; ``ratio`` square|portrait (meaningful
    for carousels); ``slides`` 2-10 for carousels (0 otherwise);
    ``platforms`` the concrete platforms to build (resolved from "auto");
    ``slides_outline`` a per-frame outline for carousels.
    """

    post_type: str = "single"
    ratio: str = "square"
    slides: int = 0
    platforms: list[str] = Field(default_factory=list)
    slides_outline: list[SlideOutline] = Field(default_factory=list)

    @field_validator("post_type")
    @classmethod
    def _vt(cls, v: str) -> str:
        return v if v in ("single", "carousel", "story") else "single"

    @field_validator("ratio")
    @classmethod
    def _vr(cls, v: str) -> str:
        return v if v in ("square", "portrait") else "square"

    @field_validator("slides")
    @classmethod
    def _vs(cls, v: int) -> int:
        if v == 0:
            return 0
        return max(2, min(int(v), 10))


class GenerationState(TypedDict):
    # Input
    content: Annotated[str, _keep_first]
    title: Annotated[str, _keep_first]
    excerpt: Annotated[str, _keep_first]
    tags: Annotated[list[str], _keep_first_list]
    platforms: Annotated[list[str], _keep_first_list]
    # Slide count for instagram-carousel (0 = not a carousel / undecided)
    slides: Annotated[int, _keep_first]
    # Carousel aspect: "square" (1080x1080) or "portrait" (1080x1350);
    # "auto" leaves the choice to the planner.
    ratio: Annotated[str, _keep_first]
    # Opt-in: run the sequence vision audit on a carousel's slide set
    sequence_audit: Annotated[bool, _keep_first]
    # Keep the source content verbatim (carousels split raw text across slides)
    verbatim: Annotated[bool, _keep_first]

    # Configuration
    _task_id: Annotated[str, _keep_first]
    design_system_id: Annotated[str, _keep_first]
    design_tokens: Annotated[dict[str, Any], _keep_first_dict]
    token_roles: Annotated[dict[str, Any], _keep_first_dict]
    brand_info: Annotated[dict[str, Any], _keep_first_dict]
    campaign: Annotated[dict[str, Any], _keep_first_dict]
    campaign_name: Annotated[str, _keep_first]
    overrides: Annotated[dict[str, str], _keep_first_dict]
    images: Annotated[list[dict[str, Any]], _keep_first_list]
    footer: Annotated[dict[str, Any], _keep_first_dict]
    categories: Annotated[list[dict[str, Any]], _keep_first_list]
    category: Annotated[str, _keep_first]
    ground: Annotated[str, _keep_first]
    design_instruction: Annotated[dict[str, Any], _keep_first_dict]
    logo: Annotated[str, _keep_first]
    # User-selected template override (auto-fallback for other families)
    template_id: Annotated[str, _keep_first]
    # Illustration style override: "compose" | "procedural" | DiceBear id | "".
    # Empty → the media plan (or DS default) decides.
    illustration_style: Annotated[str, _keep_first]
    # The design system's templates, loaded once before the graph runs
    ds_templates: Annotated[list[dict[str, Any]], _keep_first_list]

    # Agent Outputs
    strategic_brief: Annotated[dict[str, Any], _keep_first_dict]

    # Planner output — structural plan (post_type / ratio / slides / outline)
    post_plan: Annotated[dict[str, Any], _keep_first_dict]
    # Deterministic (always) + opt-in vision (sequence_audit) carousel check
    sequence_check: Annotated[dict[str, Any], _keep_first_dict]

    format_tasks: Annotated[dict[str, FormatTask], merge_format_tasks]

    _processing_format_id: Annotated[str, _keep_first]

    verification: Annotated[dict[str, dict], _merge_dicts]
    retry_count: Annotated[dict[str, int], _merge_dicts]
    # Carousel slides: {slide_id: {"index": i, "total": n}} (populated by
    # process_all_formats when expanding instagram-carousel).
    slide_context: Annotated[dict[str, dict], _merge_dicts]

    # Auto-distributed user images per slide/format (image i → slide i).
    _slide_images: Annotated[dict[str, list[dict]], _merge_dicts]
    # The media plan: {target_id: {kind, ...}} (one LLM session per post).
    media_plan: Annotated[dict[str, dict], _merge_dicts]

    # Output
    output_paths: Annotated[dict[str, str], _merge_dicts]

    # Auto-media attribution (photos/illustrations fetched by the media tools).
    # Set once per post by process_all_formats (concatenated across branches).
    media_credits: Annotated[list[dict], _keep_first_list]


def initial_state(
    title: str,
    content: str,
    platforms: list[str],
    _task_id: str = "",
    slides: int = 0,
    ratio: str = "auto",
    sequence_audit: bool = False,
    design_tokens: dict[str, Any] | None = None,
    brand_info: dict[str, Any] | None = None,
    campaign: dict[str, Any] | None = None,
    campaign_name: str = "",
    overrides: dict[str, str] | None = None,
    images: list[dict[str, Any]] | None = None,
    footer: dict[str, Any] | None = None,
    categories: list[dict[str, Any]] | None = None,
    category: str = "",
    ground: str = "",
    excerpt: str = "",
    tags: list[str] | None = None,
    design_system_id: str = "default",
    token_roles: dict[str, Any] | None = None,
    design_instruction: dict[str, Any] | None = None,
    logo: str = "",
    template_id: str = "",
    ds_templates: list[dict[str, Any]] | None = None,
    **kwargs,
) -> GenerationState:
    format_tasks: dict[str, FormatTask] = {}
    for fmt in platforms:
        format_tasks[fmt] = FormatTask(
            status="waiting",
            copy="",
            html=None,
            html_path=None,
            quality_score=0,
            quality_issues=[],
            refinement_count=0,
            error=None,
            template_id=None,
        )

    return {
        "title": title,
        "content": content,
        "excerpt": excerpt or kwargs.get("excerpt", ""),
        "tags": tags or kwargs.get("tags", []),
        "platforms": platforms,
        "slides": int(slides or kwargs.get("slides", 0)),
        "ratio": ratio or kwargs.get("ratio", "auto"),
        "sequence_audit": bool(sequence_audit or kwargs.get("sequence_audit", False)),
        "verbatim": bool(kwargs.get("verbatim", False)),
        "_task_id": _task_id,
        "design_system_id": design_system_id,
        "design_tokens": design_tokens or {},
        "token_roles": token_roles or {},
        "brand_info": brand_info or {},
        "campaign": campaign or {},
        "campaign_name": campaign_name or kwargs.get("campaign", ""),
        "overrides": overrides or {},
        "images": images or kwargs.get("images", []),
        "footer": footer or {},
        "categories": categories or [],
        "category": category or kwargs.get("category", ""),
        "ground": ground or kwargs.get("ground", ""),
        "design_instruction": design_instruction or {},
        "logo": logo,
        "template_id": template_id,
        "illustration_style": str(kwargs.get("illustration_style") or ""),
        "ds_templates": ds_templates or [],
        "strategic_brief": {},
        "post_plan": {},
        "sequence_check": {},
        "format_tasks": format_tasks,
        "_processing_format_id": "",
        "verification": {},
        "retry_count": {},
        "slide_context": {},
        "_slide_images": {},
        "media_plan": {},
        "output_paths": {},
    }
