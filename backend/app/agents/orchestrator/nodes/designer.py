"""Designer agent — generates HTML per format.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() to optionally
fetch templates and design tokens before generating HTML.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from app.agents.orchestrator.state import GenerationState
from app.agents.orchestrator.tools.search_templates import search_templates
from app.agents.orchestrator.tools.fetch_design_tokens import fetch_design_tokens
from app.agents.prompts.registry import get_prompt
from app.services.llm import get_llm

_tools = [search_templates, fetch_design_tokens]
_tool_node = ToolNode(_tools)


async def designer_node(state: GenerationState) -> dict:
    prompt = await get_prompt("designer")
    html_by_format: dict[str, str] = {}

    llm = get_llm(agent_role="designer", temperature=prompt.temperature, max_tokens=prompt.max_tokens).bind_tools(_tools)

    for fmt in state["requested_formats"]:
        copy_text = state["copy_by_format"].get(fmt, "")
        bg = state["background_by_format"].get(fmt, {})
        tokens = state.get("design_tokens", {})

        messages = [
            SystemMessage(content=prompt.system_prompt),
            HumanMessage(
                content=(
                    f"Format: {fmt}\n"
                    f"Dimensions: {_get_format_dimensions(fmt)}\n"
                    f"Copy: {copy_text}\n"
                    f"Background CSS: {bg.get('css', '')}\n"
                    f"Design tokens: {tokens}\n\n"
                    f"Before generating HTML, you may search_templates and "
                    f"fetch_design_tokens if needed. Then generate a complete "
                    f"HTML document for a social media post. "
                    f"Use Tailwind CSS via CDN. Apply the background CSS. "
                    f"Embed the copy text. No overflow, no scrollbars."
                )
            ),
        ]

        response = await llm.ainvoke(messages)

        if response.tool_calls:
            tool_result = await _tool_node.ainvoke({"messages": [response]})
            tool_context = "\n".join(
                str(m.content) for m in tool_result["messages"] if hasattr(m, "content")
            )
            messages.append(response)
            for m in tool_result["messages"]:
                messages.append(m)
            messages.append(HumanMessage(content=f"Now generate the HTML. Context: {tool_context[:1000]}"))
            response = await llm.ainvoke(messages)

        html = _extract_html(response.content if isinstance(response.content, str) else str(response.content))
        html_by_format[fmt] = html

    return {"html_by_format": html_by_format, "next_node": "quality_check"}


def _get_format_dimensions(fmt: str) -> str:
    dims = {
        "instagram-square": "1080x1080",
        "instagram-portrait": "1080x1350",
        "instagram-story": "1080x1920",
        "twitter-card": "1200x675",
        "linkedin-post": "1200x627",
        "facebook-post": "1200x630",
        "pinterest-pin": "1000x1500",
        "carousel-post": "1080x1350",
    }
    return dims.get(fmt, "1080x1080")


def _extract_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
