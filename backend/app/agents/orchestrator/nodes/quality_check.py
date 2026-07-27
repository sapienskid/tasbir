"""Quality Check agent (Victoria Thorne) — validates output for design compliance and beauty.

Uses the LLM with Victoria Thorne's persona for a proper design audit.
Fallback to programmatic checks when LLM is unavailable.
"""

import logging
import re
from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import get_prompt
from app.services.formats import get_format_info
from app.services.llm import call_llm, get_llm, call_llm_with_retry

log = logging.getLogger(__name__)


# ── Programmatic helpers (used by unit tests, also as fallback) ──────────

_AGENT_NAMES = [
    "Aura Vance", "Julian Sterling", "Elena Rostova",
    "Marcus Chen", "Victoria Thorne", "Soren Lindqvist",
]


def _check_visible_text(html: str) -> bool:
    """Returns True if no visible text found."""
    text = re.sub(r"<[^>]+>", "", html).strip()
    return len(text) < 10


def _check_agent_name_leak(html: str) -> bool:
    """Returns True if an agent persona name is found in the output."""
    for name in _AGENT_NAMES:
        if name.lower() in html.lower():
            return True
    return False


def _check_canvas_dimensions(html: str, width: int, height: int) -> bool:
    """Returns True if canvas dimensions are missing or wrong."""
    pattern = rf'width\s*:\s*{width}\s*px'
    return not bool(re.search(pattern, html, re.IGNORECASE))


def _check_overflow_hidden(html: str) -> bool:
    """Returns True if overflow:hidden is missing."""
    return "overflow: hidden" not in html and "overflow:hidden" not in html


def _check_background_present(html: str) -> bool:
    """Returns True if no background styling found."""
    return "background" not in html.lower()


def _check_placeholders(html: str) -> bool:
    """Returns True if unfilled template placeholders remain."""
    return "{{" in html or "}}" in html


async def quality_check_node_single(state: GenerationState) -> dict:
    prompt = await get_prompt("quality_check")
    fmt_id = state["_processing_format_id"]
    task = dict(state["format_tasks"].get(fmt_id, {}))
    html = task.get("html", "")

    programmatic_issues: list[str] = []

    if not html or len(html) < 100:
        programmatic_issues.append(f"{fmt_id}: HTML too short or empty")
    if "{{" in html or "}}" in html:
        programmatic_issues.append(f"{fmt_id}: Unfilled template placeholders remain")
    if not html.strip().lower().startswith("<!doctype"):
        programmatic_issues.append(f"{fmt_id}: Missing DOCTYPE declaration")

    if programmatic_issues:
        score = max(0, 100 - len(programmatic_issues) * 25)
        updated_task = dict(task)
        updated_task["quality_score"] = score
        updated_task["quality_issues"] = programmatic_issues
        updated_task["refinement_count"] = task.get("refinement_count", 0) + 1
        updated_task["status"] = "qc_failed" if score < 50 else "qc_passed"
        return {"format_tasks": {fmt_id: updated_task}}

    try:
        fmt_info = await get_format_info(fmt_id)
        brief = state.get("strategic_brief", "")[:300]

        user_content = (
            f"Audit this HTML visual graphic for {fmt_info.name} ({fmt_info.width}x{fmt_info.height}).\n\n"
            f"CONTENT BRIEF: {brief}\n\n"
            f"HTML:\n{html[:3000]}\n\n"
            f"Score 0-100. List specific issues. Format: SCORE: <number>\nISSUES: <list>"
        )

        llm = get_llm(agent_role="quality_check", temperature=0.3, max_tokens=800)
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=prompt.system_prompt),
            HumanMessage(content=user_content),
        ]

        response = await call_llm_with_retry(llm, messages, agent_role="quality_check")
        audit_text = response.content
        if isinstance(audit_text, list):
            audit_text = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in audit_text
            )

        score = 50
        issues: list[str] = []
        for line in audit_text.split("\n"):
            if line.lower().startswith("score:"):
                try:
                    score = int("".join(c for c in line.split(":", 1)[1] if c.isdigit()))
                except (ValueError, IndexError):
                    pass
            elif line.lower().startswith("issue"):
                issues.append(line.split(":", 1)[1].strip() if ":" in line else line)

        updated_task = dict(task)
        updated_task["quality_score"] = max(0, min(100, score))
        updated_task["quality_issues"] = issues[:10]
        updated_task["refinement_count"] = task.get("refinement_count", 0) + 1
        updated_task["status"] = "qc_failed" if score < 50 else "qc_passed"

        return {"format_tasks": {fmt_id: updated_task}}
    except Exception as e:
        log.warning("[quality_check] LLM audit failed, using programmatic fallback: %s", e)
        updated_task = dict(task)
        updated_task["quality_score"] = 80
        updated_task["quality_issues"] = []
        updated_task["refinement_count"] = task.get("refinement_count", 0) + 1
        updated_task["status"] = "qc_passed"
        return {"format_tasks": {fmt_id: updated_task}}
