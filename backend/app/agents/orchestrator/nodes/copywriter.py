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

from pydantic import BaseModel, Field, field_validator

from app.agents.orchestrator.state import FormatTask, GenerationState
from app.services.agents import get_agent_config
from app.services.formats import get_format_info, is_carousel
from app.services.llm import call_llm

log = logging.getLogger(__name__)

# Copywriter concurrency (Gemini free tier limit) — from runtime settings,
# created lazily so a Studio edit takes effect without a restart. Scoped per
# event loop: under Celery prefork each task runs a fresh loop, so a shared
# module-level semaphore would bind to the first loop and break the next task.
_copy_semaphores: dict[int, asyncio.Semaphore] = {}
_copy_semaphore_size = 0


async def _get_copy_semaphore() -> asyncio.Semaphore:
    from app.services.settings import get_runtime_setting

    global _copy_semaphore_size
    size = int(await get_runtime_setting("copywriter.concurrency", 2))
    loop = asyncio.get_running_loop()
    if _copy_semaphore_size != size:
        _copy_semaphores.clear()
        _copy_semaphore_size = size
    sem = _copy_semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(size)
        _copy_semaphores[loop] = sem
    return sem


# ---------------------------------------------------------------------------
# Pydantic output model
# ---------------------------------------------------------------------------


class _CopyFields(BaseModel):
    headline: str
    subhead: str
    body: str
    tagline: str = ""  # legacy field, never rendered — kept for stored-copy compat
    badge: str | None = None
    # Optional post-type extras (price/date/location/stat/cta/source) — filled
    # only when the post type calls for them; rendered by templates that opt in.
    extra: dict[str, str] = Field(default_factory=dict)

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
        # Hard ceiling: ~500 chars fits the square canvas's body measure at
        # readable size (~10 lines of 30px serif). Verbatim slides target this
        # too; LLM slides are tightened further by _finalize_slides.
        if len(v) > 520:
            idx = v.rfind(" ", 0, 520)
            log.warning("body truncated from %d to 520 chars", len(v))
            return v[:idx] if idx > 0 else v[:520]
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
    """Copy for one frame of a carousel.

    ``headline`` is optional: the LLM may legitimately return a slide without
    one (e.g. a text-heavy interior slide), and a missing key must never
    discard the whole slide set via validation. Blank headlines are filled by
    the AI repair pass (``_repair_slide_headlines``); only if that fails do we
    fall back to a sentence-complete deterministic derivation.
    """

    headline: str = ""


class PlatformCopy(_CopyFields):
    """Per-platform copy. Carousels fill ``slides``; other formats use the top fields."""

    slides: list[SlideCopy] = []


def _extract_json(text: str) -> dict:
    """Extract the first valid JSON object from LLM output."""
    text = text.strip()

    # Detect truncation — JSON must end with }
    stripped = text.rstrip()
    if stripped and not stripped.endswith("}"):
        log.warning(
            "[copywriter] JSON output appears truncated (no closing brace) — %d chars",
            len(stripped),
        )

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


def _post_type_block(post_type: str) -> str:
    """Instruction on which optional extras to fill for a post type."""
    spec = {
        "default": {},
        "quote": {"source": "the author/source of the quote"},
        "promo": {"cta": "a short call to action (e.g. 'Pre-order now')"},
        "event": {"date": "date/time", "location": "venue or link"},
        "product": {"price": "price", "cta": "call to action"},
        "comparison": {"stat": "the key figure being compared"},
        "tutorial": {"stat": "count or metric (e.g. '5 steps')"},
    }[post_type]
    if not spec:
        return ""
    lines = [f"POST TYPE: {post_type}"]
    if spec:
        lines.append(
            "  Fill ONLY these optional extras from the source content (omit any "
            "that aren't present):"
        )
        for key, hint in spec.items():
            lines.append(f"    extra.{key} — {hint}")
        lines.append(
            "  extras go in the 'extra' object; keep each under ~40 characters. "
            "Do not invent values not in the source."
        )
    return "\n".join(lines) + "\n"


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
    verbatim: bool = False,
    allow_emoji: bool = False,
    post_type: str = "default",
) -> tuple[str, PlatformCopy]:
    """Write copy for a single platform with rate-limit semaphore."""
    fmt = get_format_info(platform_id)
    platform_note = brief.get("platform_notes", {}).get(platform_id, "")
    is_carousel = slides_count > 0

    # Verbatim mode: keep the source text intact (no LLM paraphrase) —
    # carousels split the raw content across slides, ideal for essays/stories/
    # poems. Slide 1 carries the title as its headline.
    if verbatim:
        if is_carousel:
            slides = _verbatim_slides(content, title, slides_count)
            cover = slides[0] if slides else SlideCopy(headline=title[:50], body="")
            return platform_id, PlatformCopy(
                headline=cover.headline,
                subhead="",
                body=cover.body,
                tagline="",
                badge=None,
                slides=slides,
            )
        return platform_id, PlatformCopy(
            headline=title[:60],
            subhead="",
            body=(content or "").strip()[:1200],
            tagline="",
            badge=None,
            slides=[],
        )

    overrides = overrides or {}
    has_headline_override = bool(overrides.get("headline"))
    has_badge_override = bool(overrides.get("badge"))
    has_tagline_override = bool(overrides.get("tagline"))
    has_subhead_override = bool(overrides.get("subhead"))
    has_body_override = bool(overrides.get("body"))
    all_overridden = (
        has_headline_override
        and has_subhead_override
        and has_body_override
        and has_tagline_override
    )

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
        brand_block = f"BRAND: {brand_info.get('name', '')}\n"

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
            f"CAROUSEL: {slides_count} slides — {fmt.width}x{fmt.height}, swipeable, "
            f"one frame per slide.\n"
            f"Produce EXACTLY {slides_count} entries in the 'slides' array. "
            f"Slide 1 is the COVER — a strong standalone headline + hook. "
            f"Slides 2..{slides_count} continue the story progressively, each a "
            f"self-contained frame with its own mini-headline and one body point "
            f"from the source content. Keep the sequence cohesive — no repetition.\n"
        )

    post_type_block = _post_type_block(post_type)

    user_prompt = (
        f"PLATFORM: {platform_id} ({fmt.width}x{fmt.height}px)\n"
        f"{brand_block}"
        f"{campaign_block}"
        f"{carousel_block}"
        f"{post_type_block}"
        f"STRATEGIC ANGLE: {brief.get('angle', '')}\n"
        f"AUDIENCE: {brief.get('audience', '')}\n"
        f"TONE: {brief.get('tone', 'professional')}\n"
        f"PLATFORM NOTE: {platform_note}\n\n"
        f"SOURCE TITLE: {title}\n"
        f"SOURCE CONTENT (excerpt):\n{content[:2000]}"
    )
    if allow_emoji:
        user_prompt += (
            "\n\nEMOJI: this design language allows emoji. You may use them "
            "sparingly for tone — never in the headline."
        )

    sem = await _get_copy_semaphore()
    raw = None
    async with sem:
        log.info("[copywriter] Writing copy for %s", platform_id)
        try:
            raw = await call_llm(
                agent_role="copywriter",
                system_prompt=prompt_cfg.system_prompt,
                user_prompt=user_prompt,
                temperature=prompt_cfg.temperature,
                max_tokens=prompt_cfg.max_tokens,
            )
        except Exception as e:
            # Never drop a platform — a failed call falls back to title-based
            # copy so the format still renders real content (no "Untitled").
            log.warning("[copywriter] LLM failed for %s: %s — using fallback", platform_id, e)
            raw = None

    if raw is None:
        copy = _fallback_copy(content, title, slides_count, is_carousel)
        if is_carousel:
            copy.slides = await _repair_slide_headlines(copy.slides, title, content, prompt_cfg)
            copy.slides = _finalize_slides(copy.slides, title)
        return platform_id, copy

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
                log.info(
                    "[copywriter] Overrides applied for %s: %s", platform_id, overrides_applied
                )

        # Carousels must return exactly N slides — top fields become slide 1 if missing.
        if is_carousel and not copy.slides:
            copy.slides = _fallback_slides(content, title, slides_count)
        elif is_carousel and len(copy.slides) < slides_count:
            copy.slides = _pad_slides(copy.slides, content, slides_count)
        if is_carousel:
            # AI-authored mini-headlines for any slide the LLM left blank, then
            # a sentence-complete deterministic fallback for whatever is left.
            copy.slides = await _repair_slide_headlines(copy.slides, title, content, prompt_cfg)
            copy.slides = _finalize_slides(copy.slides, title)

        log.info("[copywriter] Copy ready for %s — headline: %s", platform_id, copy.headline[:40])
        return platform_id, copy
    except Exception as e:
        log.warning("[copywriter] Parse failed for %s: %s — using fallback", platform_id, e)
        copy = _fallback_copy(content, title, slides_count, is_carousel)
        if is_carousel:
            copy.slides = await _repair_slide_headlines(copy.slides, title, content, prompt_cfg)
            copy.slides = _finalize_slides(copy.slides, title)
        return platform_id, copy


def _split_sentences(text: str, n: int) -> list[str]:
    """Roughly split source text into n chunks on sentence boundaries."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return [text[:200]] * n
    chunks: list[str] = []
    bucket_size = max(1, len(sentences) // n)
    for i in range(n):
        part = sentences[i * bucket_size : (i + 1) * bucket_size]
        if not part:
            break
        chunks.append(" ".join(part))
    while len(chunks) < n:
        chunks.append(sentences[-1][:200])
    return chunks


def _verbatim_pieces(blocks: list[str], target: float, body_cap: int) -> list[str]:
    """Turn blocks into order-preserving pieces small enough to pack evenly.

    Multi-line blocks (poem stanzas) stay whole when they fit the cap; long
    single-line prose paragraphs are split at sentence boundaries so the minimax
    partition can distribute the text evenly across slides.
    """
    pieces: list[str] = []
    for b in blocks:
        if "\n" in b:
            pieces.append(b if len(b) <= body_cap else b)  # stanza intact
        elif len(b) > max(target, 160):
            parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", b) if s.strip()]
            pieces.extend(parts if len(parts) > 1 else [b])
        else:
            pieces.append(b)
    return pieces


def _proportional_partition(pieces: list[str], n: int) -> list[list[str]]:
    """Assign pieces to n ordered buckets proportionally to total length.

    Each piece goes to the bucket whose ``i/n`` target-window its midpoint falls
    in, so buckets end up roughly equal, none is empty (given pieces >= n), and
    the original order is preserved.
    """
    total = sum(len(p) + 1 for p in pieces)
    target = max(1.0, total / n)
    buckets: list[list[str]] = [[] for _ in range(n)]
    cur = 0.0
    for p in pieces:
        add = len(p) + 1
        bi = min(int((cur + add / 2.0) / target), n - 1)
        buckets[bi].append(p)
        cur += add
    return buckets


def _fill_empty_buckets(buckets: list[list[str]]) -> list[list[str]]:
    """Guarantee no empty slide: each empty bucket takes the tail piece of the
    nearest non-empty bucket before it (order preserved)."""
    for i in range(len(buckets) - 1, -1, -1):
        if buckets[i]:
            continue
        j = i - 1
        while j >= 0 and not buckets[j]:
            j -= 1
        if j >= 0 and buckets[j]:
            buckets[i].append(buckets[j].pop())
    return buckets


def _verbatim_slides(content: str, title: str, n: int, body_cap: int = 500) -> list[SlideCopy]:
    """Split the source text into n slides VERBATIM, preserving paragraph breaks.

    The text is cut into units on BLANK lines first (stanzas / paragraphs keep
    their internal line breaks). Oversized prose paragraphs are pre-split at
    sentence boundaries, then a minimax linear partition distributes the pieces
    evenly across slides — no near-empty middle slides, order preserved, and
    the whole text is kept whenever the canvas allows. Slide 1 uses the title
    as its headline.
    """
    text = (content or "").strip()
    if not text or n < 1:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    if len(blocks) < n:
        blocks = [b.strip() for b in re.split(r"\n+", text) if b.strip()]
    if len(blocks) < n:
        blocks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()] or [text]

    total = sum(len(b) for b in blocks)
    target = max(1, total / n)
    pieces = _verbatim_pieces(blocks, target, body_cap)
    buckets = _proportional_partition(pieces, n) if len(pieces) > n else [[p] for p in pieces]
    buckets = _fill_empty_buckets(buckets)

    slides: list[SlideCopy] = []
    for i, bucket in enumerate(buckets):
        body = "\n\n".join(bucket).strip()
        if len(body) > body_cap:
            cut = body.rfind(" ", 0, body_cap)
            body = (body[:cut] + "…") if cut > 0 else body[:body_cap]
        # Cover slide carries the complete title; later slides show only the
        # text (no truncated per-slide headlines).
        headline = title[:60] if i == 0 else ""
        slides.append(SlideCopy(headline=headline, subhead="", body=body, tagline="", badge=None))
    return slides


def _derive_mini_headline(body: str, title: str, max_len: int = 42) -> str:
    """Turn a slide's body into a COMPLETE, sentence-case mini-headline.

    Never truncates mid-sentence: takes the first sentence of the body and
    cuts it only at a sentence/clause boundary within ``max_len``. Trailing
    punctuation is stripped so a clause cut reads as a complete statement
    ("Retention follows daily habits") rather than a dangling "…,". If no
    boundary exists inside the cap (or the body is empty), the full first
    sentence is returned — the verifier's overflow check is the arbiter, not a
    word-boundary chop that produces a meaningless fragment.
    """
    body = (body or "").strip()
    if not body:
        return (title or "Frame")[:max_len]
    first = re.split(r"(?<=[.!?])\s+", body)[0].strip().rstrip(".")
    first = re.sub(r"\s+", " ", first)  # collapse internal newlines/indent
    if len(first) > max_len:
        # Cut at the LAST clause/sentence boundary inside the cap (respecting
        # commas/colons/semicolons as soft breaks so we never halve a clause).
        boundaries = [m.end() for m in re.finditer(r"(?<=[,.!?;:])\s+", first)]
        cut = next((b for b in boundaries if b >= int(max_len * 0.5) and b <= max_len), None)
        if cut:
            first = first[:cut].rstrip(" ,;:.")
    return first


def _truncate_sentence_aware(body: str, cap: int) -> str:
    """Keep as many COMPLETE sentences as fit within ``cap``.

    Cuts at the LAST sentence boundary that fits, so the body ends on a
    complete thought (the next slide continues the story) instead of a single
    dangling sentence. A trailing ellipsis is added only when the text is a
    single run-on block with no sentence boundary to cut at. Returns the text
    unchanged when it already fits.
    """
    body = (body or "").strip()
    if len(body) <= cap:
        return body
    candidates = [m.end() for m in re.finditer(r"(?<=[.!?])\s+", body)]
    cut = next((c for c in reversed(candidates) if c <= cap), None)
    if cut is None:
        idx = body.rfind(" ", 0, cap)
        cut = idx if idx > 0 else cap
        return body[:cut].rstrip() + "…"
    return body[:cut].rstrip()


def _finalize_slides(slides: list[SlideCopy], title: str, body_cap: int = 420) -> list[SlideCopy]:
    """Guarantee every carousel slide is self-contained:
    - a non-empty mini-headline (derived from the body if the LLM left it blank)
    - a body long enough to teach its point but short enough to avoid clipping

    ``body_cap`` is generous (~2-4 sentences, the same order as the top-level
    body cap of 520) — the verifier's DOM overflow check, not a tight character
    budget, is the arbiter of what fits a given canvas. Long bodies are cut at
    the LAST sentence boundary that fits so slides read as complete thoughts,
    never dangling fragments.

    The body is truncated FIRST, then any blank headline is derived from the
    *truncated* body — so a derived headline always equals
    ``_derive_mini_headline(body, title)`` on the slide's final body. That
    invariant lets ``_repair_slide_headlines`` reliably detect padded/fallback
    "first words of the body" titles and replace them with AI-authored ones.
    """
    out: list[SlideCopy] = []
    for s in slides:
        body = _truncate_sentence_aware(s.body, body_cap)
        headline = s.headline.strip() or _derive_mini_headline(body, title)
        out.append(s.model_copy(update={"headline": headline, "body": body}))
    return out


async def _repair_slide_headlines(
    slides: list[SlideCopy],
    title: str,
    content: str,
    prompt_cfg: Any,
) -> list[SlideCopy]:
    """Write COMPLETE, AI-authored mini-headlines for weak slide titles.

    A slide's headline needs repair when it is:
      - blank / missing a ``headline`` key (the LLM skipped it), or
      - a deterministic derivation of its own body (padded/fallback slides
        whose "title" is just the first words of the body text).

    Rather than fabricate truncated titles deterministically, one bounded
    copywriter call writes proper sentence-case mini-headlines for just those
    slides, given their bodies. Slides with a real, authored headline are
    passed through untouched. On any failure the slides are returned as-is
    (``_finalize_slides`` then fills a sentence-complete deterministic title as
    a last resort).
    """

    def _needs_repair(i: int) -> bool:
        s = slides[i]
        headline = (s.headline or "").strip()
        if not headline:
            return True
        # A padded/fallback "title" is literally the body's opening words
        # (the old _derive_mini_headline chop), not an authored hook. Detect it
        # by asking whether the body starts with the headline text.
        body = re.sub(r"\s+", " ", (s.body or "")).strip()
        probe = re.escape(headline.rstrip("…")).replace(r"\ ", r"\s+")
        return bool(re.match(probe, body, re.IGNORECASE))

    targets = [i for i in range(len(slides)) if _needs_repair(i)]
    if not targets or not slides:
        return slides

    lines = [
        "Write a COMPLETE, self-contained mini-headline (sentence case, "
        "4-8 words, max 50 chars, no trailing ellipsis) for each slide below. "
        "Each headline must read as a real hook on its own — never a fragment "
        "of the body, never a bare noun.",
        f"POST TITLE: {title or '(untitled)'}",
        "",
    ]
    for i in targets:
        body = re.sub(r"\s+", " ", (slides[i].body or "")).strip()
        lines.append(f"slide {i + 1} body: {body[:200] or '(none)'}")
    lines.append(
        "Return ONLY a JSON object mapping slide numbers to headlines, e.g. "
        '{"2": "The data changes the bet", "4": "Why less review retains more"}.'
    )
    system_prompt = (
        "You are a sharp editorial copywriter. Your only job: turn a slide's "
        "body into a COMPLETE, sentence-case mini-headline that reads on its "
        "own as a hook. Never truncate, never echo a fragment of the body "
        "verbatim, never use an ellipsis. Output ONLY a JSON object mapping "
        "slide numbers to headlines."
    )

    sem = await _get_copy_semaphore()
    async with sem:
        try:
            raw = await call_llm(
                agent_role="copywriter",
                system_prompt=system_prompt,
                user_prompt="\n".join(lines),
                temperature=0.6,
                max_tokens=300,
            )
        except Exception as e:
            log.warning("[copywriter] headline repair failed: %s", e)
            return slides

    try:
        data = _extract_json(raw)
    except Exception:
        log.warning("[copywriter] headline repair output unparseable — keeping derived titles")
        return slides

    out = list(slides)
    for key, value in data.items():
        try:
            i = int(key) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(out) and isinstance(value, str) and value.strip():
            out[i] = out[i].model_copy(update={"headline": value.strip()[:60]})
    return out


def _fallback_copy(content: str, title: str, slides_count: int, is_carousel: bool) -> PlatformCopy:
    """Title-based fallback copy when the LLM call fails — never empty."""
    fallback_body = _truncate_sentence_aware(content, 300) if content else "No content available"
    return PlatformCopy(
        headline=title[:50],
        subhead="",
        body=fallback_body,
        tagline="",
        badge=None,
        slides=_finalize_slides(_fallback_slides(content, title, slides_count), title)
        if is_carousel
        else [],
    )


def _fallback_slides(content: str, title: str, n: int, body_cap: int = 420) -> list[SlideCopy]:
    """Build N self-contained slides from source content (LLM-independent)."""
    chunks = _split_sentences(content or "", n)
    slides: list[SlideCopy] = []
    for i in range(n):
        raw = chunks[i] if i < len(chunks) else chunks[-1]
        body = _truncate_sentence_aware(raw, body_cap)
        headline = title[:50] if i == 0 else _derive_mini_headline(body, title)
        slides.append(
            SlideCopy(
                headline=headline,
                subhead="",
                body=body,
                tagline="",
                badge=None,
            )
        )
    return slides


def _pad_slides(slides: list[SlideCopy], content: str, n: int) -> list[SlideCopy]:
    """Pad an LLM slide list up to N with content-derived slides."""
    chunks = _split_sentences(content or "", max(0, n - len(slides)))
    out = list(slides)
    for i in range(n - len(slides)):
        raw = chunks[i] if i < len(chunks) else content
        body = _truncate_sentence_aware(raw, 420)
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
    # Retry-from-failure: copy for every platform is already present.
    if state.get("resume_mode") and all(
        (ft.get("copy") or "") for ft in state.get("format_tasks", {}).values()
    ):
        return {}
    prompt_cfg = await get_agent_config("copywriter")
    brief = state.get("strategic_brief", {})
    content = state.get("content", "")
    title = state.get("title", "")
    platforms = state.get("platforms", [])
    brand_info = state.get("brand_info")
    campaign = state.get("campaign")
    overrides = state.get("overrides")
    slides_count = int(state.get("slides", 0) or 0)
    verbatim = bool(state.get("verbatim"))
    allow_emoji = bool((state.get("design_instruction") or {}).get("style", {}).get("emoji"))
    post_type = str(state.get("post_type") or "default")
    platforms_config = state.get("platforms_config") or {}

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
            verbatim=verbatim,
            allow_emoji=allow_emoji,
            post_type=(platforms_config.get(platform_id, {}) or {}).get("post_type") or post_type,
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
        # One audit row per platform so the trace + progress endpoint show
        # each format as its copy is produced (not one opaque row).
        from app.services.audit import record_audit

        for platform_id in format_tasks:
            await record_audit(
                task_id,
                "copywriter",
                decision={"format": platform_id, "status": "copy_ready"},
            )

    return {"format_tasks": format_tasks}
