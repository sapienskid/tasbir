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
from app.services.agents import get_agent_config
from app.services.formats import get_format_info, is_carousel
from app.services.llm import call_llm

log = logging.getLogger(__name__)

# Semaphore: max 2 concurrent LLM calls (Gemini free tier limit)
_COPY_SEMAPHORE = asyncio.Semaphore(2)


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------


class _CopyFields(BaseModel):
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


class SlideCopy(_CopyFields):
    """Copy for one frame of a carousel."""


class PlatformCopy(_CopyFields):
    """Per-platform copy. Carousels fill ``slides``; other formats use the top fields."""

    slides: list[SlideCopy] = []


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
    slides_count: int = 0,
) -> tuple[str, PlatformCopy]:
    """Write copy for a single platform with rate-limit semaphore."""
    fmt = get_format_info(platform_id)
    platform_note = brief.get("platform_notes", {}).get(platform_id, "")
    is_carousel = slides_count > 0

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
            slides=_slides_from_overrides(overrides, content, title, slides_count)
            if is_carousel
            else [],
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

    carousel_block = ""
    if is_carousel:
        carousel_block = (
            f"CAROUSEL: {slides_count} slides — square (1080x1080), swipeable, "
            f"one frame per slide.\n"
            f"Produce EXACTLY {slides_count} entries in the 'slides' array. "
            f"Slide 1 is the COVER — a strong standalone headline + hook. "
            f"Slides 2..{slides_count} continue the story progressively, each a "
            f"self-contained frame with its own mini-headline and one body point "
            f"from the source content. Keep the sequence cohesive — no repetition.\n"
        )

    user_prompt = (
        f"PLATFORM: {platform_id} ({fmt.width}x{fmt.height}px)\n"
        f"{brand_block}"
        f"{campaign_block}"
        f"{carousel_block}"
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

        # Carousels must return exactly N slides — top fields become slide 1 if missing.
        if is_carousel and not copy.slides:
            copy.slides = _fallback_slides(content, title, slides_count)
        elif is_carousel and len(copy.slides) < slides_count:
            copy.slides = _pad_slides(copy.slides, content, slides_count)
        if is_carousel:
            copy.slides = _finalize_slides(copy.slides, title)

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
            slides=_finalize_slides(_fallback_slides(content, title, slides_count), title)
            if is_carousel
            else [],
        )
        return platform_id, fallback


def _split_sentences(text: str, n: int) -> list[str]:
    """Roughly split source text into n chunks on sentence boundaries."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return [text[:200]] * n
    chunks: list[str] = []
    bucket_size = max(1, len(sentences) // n)
    for i in range(n):
        part = sentences[i * bucket_size:(i + 1) * bucket_size]
        if not part:
            break
        chunks.append(" ".join(part))
    while len(chunks) < n:
        chunks.append(sentences[-1][:200])
    return chunks


def _derive_mini_headline(body: str, title: str, max_len: int = 42) -> str:
    """Turn a slide's body into a short, sentence-case mini-headline."""
    body = (body or "").strip()
    if not body:
        return (title or "Frame")[:max_len]
    first = re.split(r"(?<=[.!?])\s+", body)[0].strip().rstrip(".")
    if len(first) > max_len:
        idx = first.rfind(" ", 0, max_len)
        first = first[:idx] if idx > 0 else first[:max_len]
    return first


def _finalize_slides(slides: list[SlideCopy], title: str, body_cap: int = 160) -> list[SlideCopy]:
    """Guarantee every carousel slide is self-contained:
    - a non-empty mini-headline (derived from the body if the LLM left it blank)
    - a body short enough to fit the square canvas without clipping
    """
    out: list[SlideCopy] = []
    for s in slides:
        headline = s.headline.strip() or _derive_mini_headline(s.body, title)
        body = s.body or ""
        if len(body) > body_cap:
            idx = body.rfind(" ", 0, body_cap)
            body = body[:idx] if idx > 0 else body[:body_cap]
        out.append(s.model_copy(update={"headline": headline, "body": body}))
    return out


def _fallback_slides(content: str, title: str, n: int) -> list[SlideCopy]:
    """Build N self-contained slides from source content (LLM-independent)."""
    chunks = _split_sentences(content or "", n)
    slides: list[SlideCopy] = []
    for i in range(n):
        body = chunks[i][:230] if i < len(chunks) else chunks[-1][:230]
        headline = title[:50] if i == 0 else _derive_mini_headline(body, title)
        slides.append(SlideCopy(
            headline=headline,
            subhead="",
            body=body,
            tagline="",
            badge=None,
        ))
    return slides


def _pad_slides(slides: list[SlideCopy], content: str, n: int) -> list[SlideCopy]:
    """Pad an LLM slide list up to N with content-derived slides."""
    chunks = _split_sentences(content or "", max(0, n - len(slides)))
    out = list(slides)
    for i in range(n - len(slides)):
        body = chunks[i][:230] if i < len(chunks) else content[:200]
        headline = _derive_mini_headline(body, "")
        out.append(SlideCopy(headline=headline, subhead="", body=body, tagline="", badge=None))
    return out


def _slides_from_overrides(overrides: dict, content: str, title: str, n: int) -> list[SlideCopy]:
    """Build a carousel from fully-overridden copy: slide 1 = overrides, rest from content."""
    base = _fallback_slides(content, title, n)
    if base:
        base[0] = SlideCopy(
            headline=overrides.get("headline", title[:50]),
            subhead=overrides.get("subhead", ""),
            body=overrides.get("body", ""),
            tagline=overrides.get("tagline", ""),
            badge=overrides.get("badge") or None,
        )
    return base


async def copywriter_node(state: GenerationState) -> dict:
    """Write platform-optimized copy for all requested platforms in parallel."""
    prompt_cfg = await get_agent_config("copywriter")
    brief = state.get("strategic_brief", {})
    content = state.get("content", "")
    title = state.get("title", "")
    platforms = state.get("platforms", [])
    brand_info = state.get("brand_info")
    campaign = state.get("campaign")
    overrides = state.get("overrides")
    slides_count = int(state.get("slides", 0) or 0)

    # Process all platforms in parallel
    tasks = [
        _write_copy_for_platform(
            platform_id,
            brief,
            content,
            title,
            prompt_cfg,
            brand_info,
            campaign,
            overrides,
            slides_count=slides_count if is_carousel(platform_id) else 0,
        )
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

    task_id = state.get("_task_id", "")
    if task_id:
        from app.services.audit import record_audit

        await record_audit(
            task_id,
            "copywriter",
            decision={"platforms": list(format_tasks.keys())},
            critique="",
        )

    return {"format_tasks": format_tasks}
