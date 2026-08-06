"""Planner node — Aria Sol — decides post structure (type, ratio, slides).

Hybrid gating (user intent wins):
  - The LLM plans when the structure is undecided: ``platforms`` contains
    "auto", or a carousel was requested without a pinned slides/ratio.
  - Otherwise the plan is synthesized deterministically from the request so
    the trace always has a PostPlan with zero extra LLM cost.
"""

from __future__ import annotations

import json
import logging
import re

from app.agents.orchestrator.state import GenerationState, PostPlan
from app.services.agents import get_agent_config
from app.services.formats import (
    CAROUSEL_FORMAT,
    is_carousel_base,
)
from app.services.llm import call_llm

log = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not extract JSON from planner output: {text[:200]}")


def _known_platforms() -> list[str]:
    from app.services.platforms import list_platforms

    return [r["id"] for r in list_platforms(include_inactive=True)]


def _structure_undecided(platforms: list[str], slides: int, ratio: str) -> bool:
    """True when a carousel is requested but slides/ratio are unpinned."""
    has_carousel = any(is_carousel_base(p) for p in platforms)
    if not has_carousel:
        return False
    if slides <= 0:
        return True
    if ratio in ("square", "portrait"):
        return False
    return True


def _synthesize_plan(platforms: list[str], slides: int, ratio: str) -> PostPlan:
    """Deterministic plan when the user pinned the structure (no LLM)."""
    if any(is_carousel_base(p) for p in platforms):
        return PostPlan(
            post_type="carousel",
            ratio=ratio if ratio in ("square", "portrait") else "square",
            slides=max(2, min(int(slides or 3), 10)),
            platforms=platforms,
            slides_outline=[],
        )
    if "instagram-story" in platforms:
        return PostPlan(
            post_type="story", ratio="portrait", slides=0, platforms=platforms
        )
    return PostPlan(post_type="single", ratio="square", slides=0, platforms=platforms)


def _build_user_prompt(state: GenerationState, auto: bool, platforms: list[str], ratio: str) -> str:
    brief = state.get("strategic_brief", {})
    title = state.get("title", "")
    known = _known_platforms()
    platform_block = (
        "PLATFORMS: auto — choose the best 1-3 from these:\n"
        f"  {', '.join(known)}\n"
        if auto
        else f"TARGET PLATFORMS: {', '.join(platforms) or '(auto)'}\n"
    )
    ratio_block = (
        "RATIO: auto — choose square or portrait\n"
        if ratio not in ("square", "portrait")
        else f"RATIO: {ratio} (pinned)\n"
    )
    return (
        f"STRATEGIC ANGLE: {brief.get('angle', '')}\n"
        f"AUDIENCE: {brief.get('audience', '')}\n"
        f"VISUAL DIRECTION: {brief.get('visual_direction', '')}\n\n"
        f"{platform_block}"
        f"{ratio_block}"
        f"SOURCE TITLE: {title}\n"
        f"SOURCE CONTENT (excerpt):\n{(state.get('content') or '')[:1500]}"
    )


async def planner_node(state: GenerationState) -> dict:
    """Resolve the post plan (LLM when undecided, else deterministic)."""
    # Retry-from-failure: the plan is already present from the failed run.
    if state.get("post_plan"):
        return {}
    prompt_cfg = await get_agent_config("planner")
    raw_platforms = state.get("platforms", [])
    auto = "auto" in raw_platforms
    platforms = [p for p in raw_platforms if p != "auto"]
    slides_in = int(state.get("slides", 0) or 0)
    ratio_in = str(state.get("ratio", "auto") or "auto")

    needs_llm = auto or _structure_undecided(platforms, slides_in, ratio_in)

    if needs_llm:
        try:
            user_prompt = _build_user_prompt(state, auto, platforms, ratio_in)
            raw = await call_llm(
                agent_role="planner",
                system_prompt=prompt_cfg.system_prompt,
                user_prompt=user_prompt,
                temperature=prompt_cfg.temperature,
                max_tokens=prompt_cfg.max_tokens,
            )
            plan = PostPlan(**_extract_json(raw))
        except Exception as e:
            log.warning("[planner] LLM plan failed (%s) — deterministic plan", e)
            plan = _synthesize_plan(platforms, slides_in, ratio_in)
        # Clamp planner output to reality.
        known = set(_known_platforms())
        plan.platforms = [p for p in plan.platforms if p in known]
        if not plan.platforms:
            plan.platforms = list(platforms) or (["instagram-square"] if not auto else [])
        if plan.post_type == "carousel":
            if plan.slides < 2:
                plan.slides = 3
        else:
            plan.slides = 0
            plan.slides_outline = []
    else:
        plan = _synthesize_plan(platforms, slides_in, ratio_in)

    # Resolve the concrete platform set. The user's chosen carousel platform id
    # is authoritative for its aspect (instagram-carousel = square,
    # instagram-carousel-portrait = portrait) — `ratio` never overrides it.
    # Only a carousel planned without an explicit platform gets the square base.
    resolved = [p for p in plan.platforms if p != "auto"]
    if plan.post_type == "carousel":
        if not any(is_carousel_base(p) for p in resolved):
            resolved.insert(0, CAROUSEL_FORMAT)
    elif plan.post_type == "story":
        if "instagram-story" not in resolved:
            resolved.insert(0, "instagram-story")
    if not resolved:
        resolved = ["instagram-square"]

    task_id = state.get("_task_id", "")
    if task_id:
        from app.services.audit import record_audit

        await record_audit(
            task_id,
            "planner",
            decision={
                "post_type": plan.post_type,
                "ratio": plan.ratio,
                "slides": plan.slides,
                "platforms": resolved,
                "llm": needs_llm,
            },
        )

    log.info(
        "[planner] post_type=%s ratio=%s slides=%d platforms=%s (llm=%s)",
        plan.post_type, plan.ratio, plan.slides, resolved, needs_llm,
    )
    return {
        "post_plan": plan.model_dump(),
        "platforms": resolved,
        "slides": plan.slides,
    }
