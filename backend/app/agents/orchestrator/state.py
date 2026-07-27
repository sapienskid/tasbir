"""GenerationState — shared state for the LangGraph agent pipeline.

Each agent node reads from and writes to this state dict.
Per-format streaming supported via FormatTask dict + Send fan-out.
"""

from typing import Annotated, Any, Optional, TypedDict


class FormatTask(TypedDict):
    status: str
    copy: str
    background: dict[str, str]
    html: str | None
    png_url: str | None
    quality_score: int
    quality_issues: list[str]
    refinement_count: int
    error: str | None


def merge_format_tasks(
    a: dict[str, FormatTask], b: dict[str, FormatTask]
) -> dict[str, FormatTask]:
    """Merge two format_tasks dicts (b's keys overwrite a's)."""
    merged = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


class GenerationState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────
    content: str
    title: str
    excerpt: str
    tags: list[str]
    source_url: Optional[str]
    feature_image: Optional[str]
    badge_tag: Optional[str]
    image_embeds: Optional[list[str]]

    # ── Configuration ──────────────────────────────────────────────────
    brand: dict[str, Any]
    campaign: dict[str, Any]
    requested_formats: list[str]
    design_tokens: dict[str, Any]
    settings: dict[str, Any]
    _task_id: str

    # ── Agent Outputs ──────────────────────────────────────────────────
    strategic_brief: str

    # Per-format streaming tasks (replaces monolithic copy_by_format,
    # background_by_format, html_by_format, assets_by_format).
    # Custom reducer enables Send-based fan-out to merge per-format results.
    format_tasks: Annotated[dict[str, FormatTask], merge_format_tasks]

    # Subgraph routing — set by Send() to tell each subgraph branch
    # which format to process.
    _processing_format_id: str

    # ── Quality (aggregated after pipeline for backward compat) ────────
    quality_score: int
    quality_issues: list[str]
    refinement_count: int
    max_refinements: int


def initial_state(
    title: str,
    content: str,
    requested_formats: list[str],
    brand: dict[str, Any] | None = None,
    campaign: dict[str, Any] | None = None,
    **kwargs,
) -> GenerationState:
    format_tasks: dict[str, FormatTask] = {}
    for fmt in requested_formats:
        format_tasks[fmt] = FormatTask(
            status="waiting",
            copy="",
            background={},
            html=None,
            png_url=None,
            quality_score=0,
            quality_issues=[],
            refinement_count=0,
            error=None,
        )

    return {
        "title": title,
        "content": content,
        "excerpt": kwargs.get("excerpt", ""),
        "tags": kwargs.get("tags", []),
        "source_url": kwargs.get("source_url"),
        "feature_image": kwargs.get("feature_image"),
        "badge_tag": kwargs.get("badge_tag") or kwargs.get("badge"),
        "image_embeds": kwargs.get("image_embeds", []),
        "brand": brand or {},
        "campaign": campaign or {},
        "requested_formats": requested_formats,
        "design_tokens": kwargs.get("design_tokens", {}),
        "settings": kwargs.get("settings", {}),
        "_task_id": kwargs.get("_task_id", ""),
        "strategic_brief": "",
        "format_tasks": format_tasks,
        "_processing_format_id": "",
        "quality_score": 0,
        "quality_issues": [],
        "refinement_count": 0,
        "max_refinements": 2,
    }
