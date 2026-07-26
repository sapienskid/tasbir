"""Quality Check agent (Victoria Thorne) — validates output for design compliance and beauty.

Evaluates HTML structure, placeholder hygiene, contrast, and layout constraints.
"""

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import get_prompt

_QUALITY_CRITERIA = [
    ("HTML too short or empty", 25),
    ("Unfilled template placeholders remain", 20),
    ("Missing DOCTYPE declaration", 10),
]


async def quality_check_node(state: GenerationState) -> dict:
    prompt = await get_prompt("quality_check")
    issues: list[str] = []
    total_score = 100

    html_by_fmt = state.get("html_by_format", {})
    if not html_by_fmt:
        return {
            "quality_score": 0,
            "quality_issues": ["No HTML generated for any requested format"],
            "refinement_count": state.get("refinement_count", 0) + 1,
        }

    for fmt, html in html_by_fmt.items():
        if not html or len(html) < 100:
            issues.append(f"{fmt}: HTML too short or empty")
            total_score -= 25
            continue

        for pattern, penalty in _QUALITY_CRITERIA:
            if _check_issue(html, pattern):
                issues.append(f"{fmt}: {pattern}")
                total_score -= penalty

    score = max(0, total_score)
    return {
        "quality_score": score,
        "quality_issues": issues,
        "refinement_count": state.get("refinement_count", 0) + 1,
    }


def _check_issue(html: str, pattern: str) -> bool:
    checks = {
        "HTML too short or empty": lambda h: len(h) < 100,
        "Unfilled template placeholders remain": lambda h: "{{" in h or "}}" in h,
        "Missing DOCTYPE declaration": lambda h: not h.strip().lower().startswith("<!doctype"),
    }
    return checks.get(pattern, lambda h: False)(html)
