"""Typed editorial decisions shared by planning, copy, design and review.

These helpers never resolve design tokens. User copy and structural pins remain
authoritative; model judgments supplement deterministic checks, not replace them.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class NarrativeBeat(BaseModel):
    role: Literal["hook", "context", "explanation", "example", "takeaway", "action"] = "explanation"
    focus: str = Field(default="", max_length=500)
    headline_hint: str = Field(default="", max_length=120)
    connects_to_next: str = Field(default="", max_length=300)


def narrative_roles(count: int) -> list[str]:
    if count < 2:
        return ["hook"] if count else []
    if count == 2:
        return ["hook", "takeaway"]
    if count == 3:
        return ["hook", "example", "takeaway"]
    if count == 4:
        return ["hook", "explanation", "example", "takeaway"]
    return ["hook", "context", *(["explanation"] * (count - 5)), "example", "takeaway", "action"]


def narrative_outline(outline: list[dict], count: int, focus: str = "") -> list[dict]:
    """Normalize to the pinned slide count without inventing source facts."""
    result = []
    for i, role in enumerate(narrative_roles(count)):
        raw = outline[i] if i < len(outline) and isinstance(outline[i], dict) else {}
        try:
            beat = NarrativeBeat.model_validate({**raw, "role": role})
        except ValidationError:
            beat = NarrativeBeat(role=role)
        if not beat.focus:
            beat.focus = f"{role}: {focus[:400]}"
        result.append(beat.model_dump())
    return result


class HookCandidate(BaseModel):
    headline: str = Field(min_length=1, max_length=60)
    angle: Literal["claim", "question", "contrast", "finding", "practical"] = "claim"
    source_support: str = Field(default="", max_length=400)
    specificity: int = Field(default=0, ge=0, le=5)
    relevance: int = Field(default=0, ge=0, le=5)
    faithfulness: int = Field(default=0, ge=0, le=5)


_GENERIC = re.compile(
    r"\b(unlock|game[- ]changer|revolutioni[sz]e|ultimate guide|power of|ever[- ]evolving|delve)\b",
    re.I,
)
_WORDS = re.compile(r"[\w'-]+", re.UNICODE)
_NUMBERS = re.compile(r"\d+(?:[.,]\d+)*(?:%|[kKmMbB])?")


def choose_hook(candidates: list[HookCandidate], source: str, original: str) -> dict:
    """Rank bounded candidates; reject invented figures and unsupported hooks."""
    words = {w.lower() for w in _WORDS.findall(source) if len(w) > 3}
    numbers = set(_NUMBERS.findall(source))
    ranked = []
    seen = set()
    for candidate in candidates[:4]:
        headline = candidate.headline.strip()
        if headline.casefold() in seen:
            continue
        seen.add(headline.casefold())
        tokens = {w.lower() for w in _WORDS.findall(headline) if len(w) > 3}
        overlap = len(tokens & words) / max(1, len(tokens))
        invented = sorted(set(_NUMBERS.findall(headline)) - numbers)
        support = " ".join(candidate.source_support.casefold().split())
        grounded = bool(support) and support in " ".join(source.casefold().split())
        eligible = (
            not invented
            and overlap > 0
            and candidate.faithfulness >= 3
            and grounded
            and not _GENERIC.search(headline)
        )
        score = (
            candidate.specificity
            + candidate.relevance
            + candidate.faithfulness
            + overlap * 5
            - (8 if _GENERIC.search(headline) else 0)
        )
        ranked.append(
            {
                **candidate.model_dump(),
                "score": round(score, 2),
                "eligible": eligible,
                "unsupported_figures": invented,
            }
        )
    eligible = [item for item in ranked if item["eligible"]]
    selected = max(eligible, key=lambda item: item["score"]) if eligible else None
    return {
        "headline": selected["headline"] if selected else original,
        "candidates": ranked,
        "selected": bool(selected),
    }


class ContentProfile(BaseModel):
    composition: Literal["statement", "editorial", "comparison", "quote", "steps", "media"]
    density: Literal["light", "medium", "dense"]
    body_budget: int
    body_chars: int
    headline_chars: int
    needs_rewrite: bool


def content_profile(
    copy: dict,
    width: int = 1080,
    height: int = 1080,
    post_type: str = "default",
    has_media: bool = False,
) -> ContentProfile:
    headline = str(copy.get("headline") or "")
    body = str(copy.get("body") or "")
    # Character budgets describe editorial density, never request smaller type.
    budget = 240 if width / max(height, 1) > 1.4 else (500 if height / max(width, 1) > 1.5 else 420)
    total = len(body) + len(str(copy.get("subhead") or ""))
    density = "dense" if total > budget * 0.8 else ("medium" if total > budget * 0.35 else "light")
    composition = {"quote": "quote", "comparison": "comparison", "tutorial": "steps"}.get(post_type)
    if composition is None:
        composition = "editorial" if density == "dense" else ("media" if has_media else "statement")
    return ContentProfile(
        composition=composition,
        density=density,
        body_budget=budget,
        body_chars=len(body),
        headline_chars=len(headline),
        needs_rewrite=len(body) > budget or len(headline) > 60,
    )


def layout_guidance(profile: ContentProfile) -> str:
    return (
        f"CONTENT COMPOSITION: {profile.composition}; density={profile.density}. "
        f"Readable body budget: {profile.body_budget} characters. "
        "Give each idea its own hierarchy; preserve the design system's minimum readable type. "
        "Dense copy needs a text-first composition. A comparison needs distinct sides; "
        "a quotation needs source attribution; steps need an ordered progression. "
        "Never shrink type to conceal a copy-fit problem."
    )


class Correction(BaseModel):
    target: Literal["copy", "layout", "media"]
    element: str = Field(min_length=1, max_length=100)
    problem: str = Field(min_length=1, max_length=500)
    action: str = Field(min_length=1, max_length=500)
    priority: int = Field(default=2, ge=1, le=3)


def corrections_from_review(review: dict, copy: dict | None = None) -> list[dict]:
    corrections = []
    raw_corrections = review.get("corrections") or []
    if not isinstance(raw_corrections, list):
        raw_corrections = []
    for raw in raw_corrections[:6]:
        try:
            corrections.append(Correction.model_validate(raw).model_dump())
        except (ValidationError, TypeError):
            continue
    if corrections or review.get("pass"):
        return sorted(corrections, key=lambda item: item["priority"])
    raw_issues = review.get("issues") or []
    if not isinstance(raw_issues, list):
        raw_issues = [str(raw_issues)]
    for issue in raw_issues[:4]:
        text = str(issue)[:500]
        if not text.strip():
            continue
        lower = text.lower()
        if any(word in lower for word in ("irrelevant", "unrelated", "photo", "image relevance")):
            target, element, action = (
                "media",
                "media slot",
                "Remove irrelevant media or choose media that explains the slide's actual claim.",
            )
        elif any(
            word in lower
            for word in ("repetit", "unsupported", "generic", "wordy", "too much text")
        ) or ("overflow" in lower and len(str((copy or {}).get("body") or "")) > 240):
            target, element, action = (
                "copy",
                "body",
                "Tighten to one complete, source-supported point; preserve pins and readable type.",
            )
        else:
            target, element, action = (
                "layout",
                "composition",
                "Correct geometry or hierarchy while preserving copy and minimum readable type.",
            )
        corrections.append(
            Correction(target=target, element=element, problem=text, action=action).model_dump()
        )
    return corrections


def correction_brief(corrections: list[dict], target: str | None = None) -> str:
    return "\n".join(
        f"{c['element']}: {c['problem']} → {c['action']}"
        for c in corrections
        if target is None or c.get("target") == target
    )


class SequenceReview(BaseModel):
    passed: bool = Field(strict=True)
    flow: int = Field(ge=0, le=5)
    distinctness: int = Field(ge=0, le=5)
    terminology: int = Field(ge=0, le=5)
    promise_delivered: int = Field(ge=0, le=5)
    issues: list[str] = Field(default_factory=list, max_length=8)
    critique: str = Field(default="", max_length=2000)


def repeated_slide_issues(slides: list[dict]) -> list[str]:
    issues = []
    for i, slide in enumerate(slides):
        text = re.sub(r"\W+", " ", str(slide.get("body") or "")).strip().casefold()
        if len(text) < 40:
            continue
        for j, previous in enumerate(slides[:i]):
            other = re.sub(r"\W+", " ", str(previous.get("body") or "")).strip().casefold()
            if other and SequenceMatcher(None, text, other).ratio() > 0.9:
                issues.append(
                    f"Slides {j + 1} and {i + 1} repeat substantially the same body point"
                )
    return issues


def parse_copy(raw: str) -> dict:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}
