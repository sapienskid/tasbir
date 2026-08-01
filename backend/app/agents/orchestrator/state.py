"""GenerationState — shared state for the v3 LangGraph agent pipeline.

Each agent node reads from and writes to this state dict.
Per-format streaming via FormatTask dict + Send fan-out.
"""

from typing import Annotated, Any, Optional, TypedDict


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
    content: Annotated[str, _keep_first]
    title: Annotated[str, _keep_first]
    url: Annotated[str, _keep_first]
    excerpt: Annotated[str, _keep_first]
    tags: Annotated[list[str], _keep_first_list]
    platforms: Annotated[list[str], _keep_first_list]
    source_url: Annotated[Optional[str], _keep_first]

    # Configuration
    _task_id: Annotated[str, _keep_first]
    design_tokens: Annotated[dict[str, Any], _keep_first_dict]
    brand_info: Annotated[dict[str, Any], _keep_first_dict]
    campaign: Annotated[dict[str, Any], _keep_first_dict]
    campaign_name: Annotated[str, _keep_first]
    overrides: Annotated[dict[str, str], _keep_first_dict]
    images: Annotated[list[dict[str, Any]], _keep_first_list]
    footer: Annotated[dict[str, Any], _keep_first_dict]
    categories: Annotated[list[dict[str, Any]], _keep_first_list]
    category: Annotated[str, _keep_first]
    ground: Annotated[str, _keep_first]

    # Agent Outputs
    strategic_brief: Annotated[dict[str, Any], _keep_first_dict]

    format_tasks: Annotated[dict[str, FormatTask], merge_format_tasks]

    _processing_format_id: Annotated[str, _keep_first]

    verification: Annotated[dict[str, dict], _merge_dicts]
    retry_count: Annotated[dict[str, int], _merge_dicts]

    # Output
    output_paths: Annotated[dict[str, str], _merge_dicts]


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
    footer: dict[str, Any] | None = None,
    categories: list[dict[str, Any]] | None = None,
    category: str = "",
    ground: str = "",
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
        "footer": footer or {},
        "categories": categories or [],
        "category": category or kwargs.get("category", ""),
        "ground": ground or kwargs.get("ground", ""),
        "strategic_brief": {},
        "format_tasks": format_tasks,
        "_processing_format_id": "",
        "verification": {},
        "retry_count": {},
        "output_paths": {},
    }
