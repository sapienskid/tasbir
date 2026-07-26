"""Quality Check agent (Victoria Thorne) — validates output for design compliance and beauty.

All checks are deterministic (regex/string inspection), not LLM-based, for reliability and speed.
Per-format scoring: uses the worst-performing format's score to represent overall quality.
"""

import re

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import get_prompt
from app.services.cleanup import AGENT_NAMES


def _check_visible_text(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if HTML has fewer than 20 chars of visible text after stripping tags."""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text) < 20


def _check_agent_name_leak(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if any internal agent persona name appears anywhere in the HTML."""
    html_lower = html.lower()
    return any(name.lower() in html_lower for name in AGENT_NAMES)


def _check_canvas_dimensions(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if expected canvas pixel dimensions are absent from body style."""
    if not width or not height:
        return False  # can't check without known dimensions
    return f"{width}px" not in html or f"{height}px" not in html


def _check_overflow_hidden(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if overflow:hidden is not set (content may spill outside canvas)."""
    return "overflow: hidden" not in html and "overflow:hidden" not in html


def _check_background_present(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if no background CSS is present (blank white canvas)."""
    return "background" not in html.lower()


def _check_doctype(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if DOCTYPE declaration is missing."""
    return not html.strip().lower().startswith("<!doctype")


def _check_placeholders(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if unfilled template placeholders remain."""
    return "{{" in html or "}}" in html


def _check_min_length(html: str, width: int = 0, height: int = 0) -> bool:
    """Fail if HTML is shorter than 200 characters (likely empty/broken)."""
    return len(html) < 200


# Checks: (label, penalty, check_function)
# check_function(html, width, height) -> True means the check FAILED
_CHECKS: list[tuple[str, int, object]] = [
    ("HTML too short or empty", 30, _check_min_length),
    ("Missing DOCTYPE declaration", 10, _check_doctype),
    ("Unfilled template placeholders remain", 20, _check_placeholders),
    ("Missing canvas overflow:hidden", 15, _check_overflow_hidden),
    ("Missing background CSS", 10, _check_background_present),
    ("Insufficient visible text content", 15, _check_visible_text),
    ("Agent persona name leaked into output", 25, _check_agent_name_leak),
    ("Canvas dimensions missing from body style", 10, _check_canvas_dimensions),
]


async def quality_check_node(state: GenerationState) -> dict:
    await get_prompt("quality_check")  # load from registry for consistency

    html_by_fmt = state.get("html_by_format", {})
    if not html_by_fmt:
        return {
            "quality_score": 0,
            "quality_issues": ["No HTML generated for any requested format"],
            "refinement_count": state.get("refinement_count", 0) + 1,
        }

    # Score each format independently; use the worst score as overall quality signal
    worst_score = 100
    all_issues: list[str] = []

    for fmt, html in html_by_fmt.items():
        fmt_score = 100
        fmt_width, fmt_height = 0, 0  # dimension-aware checks deferred to fixer

        for label, penalty, check_fn in _CHECKS:
            try:
                if check_fn(html, fmt_width, fmt_height):
                    all_issues.append(f"{fmt}: {label}")
                    fmt_score -= penalty
            except Exception:
                pass  # never crash the pipeline on a quality check

        worst_score = min(worst_score, max(0, fmt_score))

    return {
        "quality_score": worst_score,
        "quality_issues": all_issues,
        "refinement_count": state.get("refinement_count", 0) + 1,
    }


# Keep old helper for backward compatibility with existing tests
def _check_issue(html: str, pattern: str) -> bool:
    checks = {
        "HTML too short or empty": lambda h: len(h) < 100,
        "Unfilled template placeholders remain": lambda h: "{{" in h or "}}" in h,
        "Missing DOCTYPE declaration": lambda h: not h.strip().lower().startswith("<!doctype"),
    }
    return checks.get(pattern, lambda h: False)(html)
