"""GenerationState — shared state for the v3 LangGraph agent pipeline.

Each agent node reads from and writes to this state dict.
Per-format streaming via FormatTask dict + Send fan-out.
"""

from typing import Annotated, Any, Optional, TypedDict


class FormatTask(TypedDict):
    status: str
    copy: str
    html: str | None
    html_path: str | None
    quality_score: int
    quality_issues: list[str]
    refinement_count: int
    error: str | None


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


class GenerationState(TypedDict):
    # Input
    content: str
    title: str
    url: str
    excerpt: str
    tags: list[str]
    platforms: list[str]
    source_url: Optional[str]

    # Configuration
    _task_id: str
    design_tokens: dict[str, Any]
    brand_info: dict[str, Any]
    campaign: dict[str, Any]
    campaign_name: str
    overrides: dict[str, str]
    images: list[dict[str, Any]]

    # Agent Outputs
    strategic_brief: dict[str, Any]

    format_tasks: Annotated[dict[str, FormatTask], merge_format_tasks]

    _processing_format_id: str

    verification: dict[str, dict]
    retry_count: dict[str, int]

    # Output
    output_paths: dict[str, str]


def initial_state(
    title: str,
    content: str,
    platforms: list[str],
    _task_id: str = "",
    design_tokens: dict[str, Any] | None = None,
    brand_info: dict[str, Any] | None = None,
    campaign: dict[str, Any] | None = None,
    campaign_name: str = "",
    overrides: dict[str, str] | None = None,
    images: list[dict[str, Any]] | None = None,
    url: str = "",
    excerpt: str = "",
    tags: list[str] | None = None,
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
        )

    return {
        "title": title,
        "content": content,
        "url": url or kwargs.get("url", ""),
        "excerpt": excerpt or kwargs.get("excerpt", ""),
        "tags": tags or kwargs.get("tags", []),
        "platforms": platforms,
        "source_url": kwargs.get("source_url"),
        "_task_id": _task_id,
        "design_tokens": design_tokens or {},
        "brand_info": brand_info or {},
        "campaign": campaign or {},
        "campaign_name": campaign_name or kwargs.get("campaign", ""),
        "overrides": overrides or {},
        "images": images or kwargs.get("images", []),
        "strategic_brief": {},
        "format_tasks": format_tasks,
        "_processing_format_id": "",
        "verification": {},
        "retry_count": {},
        "output_paths": {},
    }
