"""GenerationState — shared state for the LangGraph agent pipeline.

Each agent node reads from and writes to this state dict.
"""

from typing import Annotated, Any, Optional

from langgraph.graph import add_messages


class GenerationState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────
    content: str
    title: str
    excerpt: str
    tags: list[str]
    source_url: Optional[str]
    feature_image: Optional[str]

    # ── Configuration ──────────────────────────────────────────────────
    brand: dict[str, Any]
    campaign: dict[str, Any]
    requested_formats: list[str]
    design_tokens: dict[str, Any]
    settings: dict[str, Any]

    # ── Agent Outputs ──────────────────────────────────────────────────
    strategic_brief: str
    copy_by_format: dict[str, str]
    background_by_format: dict[str, dict[str, str]]
    html_by_format: dict[str, str]
    assets_by_format: dict[str, str]

    # ── Quality ────────────────────────────────────────────────────────
    quality_score: int
    quality_issues: list[str]
    refinement_count: int
    max_refinements: int

    # ── Flow Control ───────────────────────────────────────────────────
    messages: Annotated[list, add_messages]
    next_node: str


def initial_state(
    title: str,
    content: str,
    requested_formats: list[str],
    brand: dict[str, Any] | None = None,
    campaign: dict[str, Any] | None = None,
    **kwargs,
) -> GenerationState:
    return {
        "title": title,
        "content": content,
        "excerpt": kwargs.get("excerpt", ""),
        "tags": kwargs.get("tags", []),
        "source_url": kwargs.get("source_url"),
        "feature_image": kwargs.get("feature_image"),
        "brand": brand or {},
        "campaign": campaign or {},
        "requested_formats": requested_formats,
        "design_tokens": kwargs.get("design_tokens", {}),
        "settings": kwargs.get("settings", {}),
        "strategic_brief": "",
        "copy_by_format": {},
        "background_by_format": {},
        "html_by_format": {},
        "assets_by_format": {},
        "quality_score": 0,
        "quality_issues": [],
        "refinement_count": 0,
        "max_refinements": 2,
        "messages": [],
        "next_node": "strategist",
    }
