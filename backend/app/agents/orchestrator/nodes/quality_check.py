"""Quality Check agent — validates output for brand compliance.

Input:  html_by_format, design_tokens
Output: quality_score, quality_issues, refinement_count

If quality_score < 70 and refinements remain, loops back to designer.
"""

from app.agents.orchestrator.state import GenerationState
from app.services.llm import call_llm
from app.agents.prompts.registry import get_prompt


async def quality_check_node(state: GenerationState) -> dict:
    prompt = await get_prompt("quality_check")
    issues: list[str] = []
    total_score = 100

    for fmt, html in state["html_by_format"].items():
        if not html or len(html) < 100:
            issues.append(f"{fmt}: HTML too short or empty")
            total_score -= 20
            continue

        if "overflow" in html.lower() or "scroll" in html.lower():
            issues.append(f"{fmt}: Possible overflow/scroll detected")
            total_score -= 15

        if "{{" in html:
            issues.append(f"{fmt}: Unfilled template placeholders remain")
            total_score -= 15

        if not html.strip().startswith("<!DOCTYPE"):
            issues.append(f"{fmt}: Missing DOCTYPE declaration")
            total_score -= 5

    # Use AI to check quality of one format as sample
    sample_fmt = state["requested_formats"][0]
    sample_html = state["html_by_format"].get(sample_fmt, "")
    if sample_html:
        ai_check = await call_llm(
            agent_role="quality_check",
            system_prompt=prompt.system_prompt,
            user_prompt=(
                f"HTML:\n{sample_html[:3000]}\n\n"
                f"Check this HTML for quality issues. "
                f"Output: PASS or FAIL with reason."
            ),
            temperature=0.3,
            max_tokens=200,
        )
        if "FAIL" in ai_check.upper():
            issues.append(f"AI check failed: {ai_check[:200]}")
            total_score -= 25

    score = max(0, total_score)
    return {
        "quality_score": score,
        "quality_issues": issues,
        "refinement_count": state.get("refinement_count", 0) + 1,
    }
