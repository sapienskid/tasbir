"""Quality Check agent — validates output for brand compliance.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() to optionally
render previews for visual verification.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from app.agents.orchestrator.state import GenerationState
from app.agents.orchestrator.tools.render_preview import render_preview
from app.agents.prompts.registry import get_prompt
from app.services.llm import get_llm

_tools = [render_preview]
_tool_node = ToolNode(_tools)

_DIMS = {
    "instagram-square": (1080, 1080),
    "instagram-portrait": (1080, 1350),
    "instagram-story": (1080, 1920),
    "linkedin-post": (1200, 627),
    "twitter-card": (1200, 675),
    "facebook-post": (1200, 630),
    "pinterest-pin": (1000, 1500),
    "carousel-post": (1080, 1350),
}

_QUALITY_CRITERIA = [
    ("HTML too short or empty", 20),
    ("Possible overflow or scroll detected", 15),
    ("Unfilled template placeholders remain", 15),
    ("Missing DOCTYPE declaration", 5),
]


async def quality_check_node(state: GenerationState) -> dict:
    prompt = await get_prompt("quality_check")
    issues: list[str] = []
    total_score = 100

    llm = get_llm(agent_role="quality_check", temperature=0.3, max_tokens=500).bind_tools(_tools)

    for fmt, html in state["html_by_format"].items():
        if not html or len(html) < 100:
            issues.append(f"{fmt}: HTML too short or empty")
            total_score -= 20
            continue

        for pattern, penalty in _QUALITY_CRITERIA:
            if _check_issue(html, pattern):
                issues.append(f"{fmt}: {pattern}")
                total_score -= penalty

        w, h = _DIMS.get(fmt, (1080, 1080))
        messages = [
            SystemMessage(content=prompt.system_prompt),
            HumanMessage(
                content=(
                    f"Format: {fmt}\n"
                    f"HTML preview available via render_preview ({w}x{h}).\n"
                    f"HTML snippet:\n{html[:2000]}\n\n"
                    f"Check this HTML for quality issues."
                )
            ),
        ]

        response = await llm.ainvoke(messages)
        if response.tool_calls:
            tool_result = await _tool_node.ainvoke({"messages": [response]})
            for msg in tool_result["messages"]:
                if hasattr(msg, "content") and "Failed" in str(msg.content):
                    issues.append(f"{fmt}: Render failed")
                    total_score -= 10

        if "FAIL" in str(response.content).upper():
            issues.append(f"{fmt}: AI quality check flagged issues")
            total_score -= 20

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
