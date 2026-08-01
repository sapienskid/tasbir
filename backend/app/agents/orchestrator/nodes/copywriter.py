"""Copywriter node — Julian Sterling — produces structured copy per platform.

Uses asyncio.gather with a Semaphore to process all platforms in parallel
while respecting Gemini free-tier rate limits.

Input (from GenerationState):
  - strategic_brief: dict
  - content: str
  - title: str
  - platforms: list[str]

Output (to GenerationState via merge_format_tasks):
  - format_tasks: {platform_id: FormatTask with copy set}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, field_validator

from app.agents.orchestrator.state import FormatTask, GenerationState
from app.agents.prompts.registry import load_prompt
from app.services.formats import get_format_info
from app.services.llm import call_llm

log = logging.getLogger(__name__)

# Semaphore: max 2 concurrent LLM calls (Gemini free tier limit)
_COPY_SEMAPHORE = asyncio.Semaphore(2)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------


class PlatformCopy(BaseModel):
    headline: str
    subhead: str
    body: str
    tagline: str
    badge: str | None = None

    @field_validator("headline")
    @classmethod
    def trim_headline(cls, v: str) -> str:
        if len(v) > 60:
            idx = v.rfind(" ", 0, 60)
            log.warning("headline truncated from %d to 60 chars", len(v))
            return v[:idx] if idx > 0 else v[:60]
        return v

    @field_validator("subhead")
    @classmethod
    def trim_subhead(cls, v: str) -> str:
        if len(v) > 100:
            idx = v.rfind(" ", 0, 100)
            log.warning("subhead truncated from %d to 100 chars", len(v))
            return v[:idx] if idx > 0 else v[:100]
        return v

    @field_validator("body")
    @classmethod
    def trim_body(cls, v: str) -> str:
        # Body sits in a ~600px measure at 28px serif (~45 chars/line, 5 lines)
        if len(v) > 230:
            idx = v.rfind(" ", 0, 230)
            log.warning("body truncated from %d to 230 chars", len(v))
            return v[:idx] if idx > 0 else v[:230]
        return v

    @field_validator("tagline")
    @classmethod
    def trim_tagline(cls, v: str) -> str:
        if len(v) > 40:
            idx = v.rfind(" ", 0, 40)
            log.warning("tagline truncated from %d to 40 chars", len(v))
            return v[:idx] if idx > 0 else v[:40]
        return v

    @field_validator("badge")
    @classmethod
    def trim_badge(cls, v: str | None) -> str | None:
        if v and len(v) > 30:
            log.warning("badge truncated from %d to 30 chars", len(v))
            return v[:30]
        return v


def _extract_json(text: str) -> dict:
    """Extract the first valid JSON object from LLM output."""
    text = text.strip()

    # Detect truncation — JSON must end with }
    stripped = text.rstrip()
    if stripped and not stripped.endswith("}"):
        log.warning("[copywriter] JSON output appears truncated (no closing brace) — %d chars", len(stripped))

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON: {text[:200]}")


async def _write_copy_for_platform(
    platform_id: str,
    brief: dict,
    content: str,
    title: str,
    prompt_cfg: Any,
    brand_info: dict | None = None,
    campaign: dict | None = None,
    overrides: dict | None = None,
) -> tuple[str, PlatformCopy]:
    """Write copy for a single platform with rate-limit semaphore."""
    fmt = get_format_info(platform_id)
    platform_note = brief.get("platform_notes", {}).get(platform_id, "")

    overrides = overrides or {}
    has_headline_override = bool(overrides.get("headline"))
    has_badge_override = bool(overrides.get("badge"))
    has_tagline_override = bool(overrides.get("tagline"))
    has_subhead_override = bool(overrides.get("subhead"))
    has_body_override = bool(overrides.get("body"))
    all_overridden = has_headline_override and has_subhead_override and has_body_override and has_tagline_override

    if all_overridden:
        log.info("[copywriter] All fields overridden for %s — skipping LLM", platform_id)
        return platform_id, PlatformCopy(
            headline=overrides.get("headline", title[:50]),
            subhead=overrides.get("subhead", ""),
            body=overrides.get("body", ""),
            tagline=overrides.get("tagline", ""),
            badge=overrides.get("badge") or None,
        )

    if has_headline_override or has_badge_override or has_tagline_override:
        log.info("[copywriter] Partial overrides for %s — filling rest via LLM", platform_id)

    # Build brand + campaign context
    brand_block = ""
    if brand_info and brand_info.get("name"):
        brand_block = (
            f"BRAND: {brand_info.get('name', '')}\n"
            f"TAGLINE: {brand_info.get('tagline', '')}\n"
        )

    campaign_block = ""
    if campaign and campaign.get("name"):
        campaign_block = f"CAMPAIGN: {campaign.get('name', '')}\n"
        if campaign.get("series_name"):
            campaign_block += (
                f"SERIES: {campaign.get('series_name', '')} "
                f"(Part {campaign.get('series_part', 0)} of {campaign.get('series_total', 0)})\n"
            )

    user_prompt = (
        f"PLATFORM: {platform_id} ({fmt.width}x{fmt.height}px)\n"
        f"{brand_block}"
        f"{campaign_block}"
        f"STRATEGIC ANGLE: {brief.get('angle', '')}\n"
        f"AUDIENCE: {brief.get('audience', '')}\n"
        f"TONE: {brief.get('tone', 'professional')}\n"
        f"PLATFORM NOTE: {platform_note}\n\n"
        f"SOURCE TITLE: {title}\n"
        f"SOURCE CONTENT (excerpt):\n{content[:2000]}"
    )

    async with _COPY_SEMAPHORE:
        log.info("[copywriter] Writing copy for %s", platform_id)
        raw = await call_llm(
            agent_role="copywriter",
            system_prompt=prompt_cfg.system_prompt,
            user_prompt=user_prompt,
            temperature=prompt_cfg.temperature,
            max_tokens=prompt_cfg.max_tokens,
        )

    try:
        data = _extract_json(raw)
        copy = PlatformCopy(**data)

        # Apply partial overrides on top of LLM output
        if overrides:
            overrides_applied = []
            if has_headline_override:
                copy.headline = overrides["headline"]
                overrides_applied.append("headline")
            if has_subhead_override:
                copy.subhead = overrides["subhead"]
                overrides_applied.append("subhead")
            if has_body_override:
                copy.body = overrides["body"]
                overrides_applied.append("body")
            if has_tagline_override:
                copy.tagline = overrides["tagline"]
                overrides_applied.append("tagline")
            if has_badge_override:
                copy.badge = overrides["badge"] or None
                overrides_applied.append("badge")
            if overrides_applied:
                log.info("[copywriter] Overrides applied for %s: %s", platform_id, overrides_applied)

        log.info("[copywriter] Copy ready for %s — headline: %s", platform_id, copy.headline[:40])
        return platform_id, copy
    except Exception as e:
        log.warning("[copywriter] Parse failed for %s: %s — using fallback", platform_id, e)
        fallback_body = content[:300].strip() if content else "No content available"
        fallback = PlatformCopy(
            headline=title[:50],
            subhead="",
            body=fallback_body,
            tagline="",
            badge=None,
        )
        return platform_id, fallback


async def copywriter_node(state: GenerationState) -> dict:
    """Write platform-optimized copy for all requested platforms in parallel."""
    prompt_cfg = load_prompt("copywriter")
    brief = state.get("strategic_brief", {})
    content = state.get("content", "")
    title = state.get("title", "")
    platforms = state.get("platforms", [])
    brand_info = state.get("brand_info")
    campaign = state.get("campaign")
    overrides = state.get("overrides")

    # Process all platforms in parallel
    tasks = [
        _write_copy_for_platform(platform_id, brief, content, title, prompt_cfg,
                                 brand_info, campaign, overrides)
        for platform_id in platforms
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    format_tasks: dict[str, dict] = {}
    for result in results:
        if isinstance(result, Exception):
            log.error("[copywriter] Task failed: %s", result)
            continue
        platform_id, copy = result
        # Copy is serialized as JSON string in format_tasks
        copy_json = copy.model_dump_json()
        format_tasks[platform_id] = FormatTask(
            status="copy_ready",
            copy=copy_json,
            html=None,
            html_path=None,
            quality_score=0,
            quality_issues=[],
            refinement_count=0,
            error=None,
        )

    log.info("[copywriter] Copy written for %d platforms", len(format_tasks))
    return {"format_tasks": format_tasks}
