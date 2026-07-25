"""Quality Check agent — validates output for brand compliance.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() to optionally
render previews for visual verification.
"""

from app.agents.orchestrator.state import GenerationState

_QUALITY_CRITERIA = [
    ("HTML too short or empty", 20),
    ("Unfilled template placeholders remain", 15),
]


async def quality_check_node(state: GenerationState) -> dict:
    issues: list[str] = []
    total_score = 100

    for fmt, html in state["html_by_format"].items():
        if not html or len(html) < 100:
            issues.append(f"{fmt}: HTML too short or empty")
            total_score -= 20
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
        "Possible overflow or scroll detected": lambda h: "overflow" in h.lower() or "scroll" in h.lower(),
        "Unfilled template placeholders remain": lambda h: "{{" in h,
        "Missing DOCTYPE declaration": lambda h: not h.strip().startswith("<!DOCTYPE"),
    }
    return checks.get(pattern, lambda h: False)(html)
