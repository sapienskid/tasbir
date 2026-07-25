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
from app.services.token_exchange import tailwind_config_html
from app.db.session import create_pool
from app.config import get_settings
from sqlalchemy import select

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
        fmt_instruction = await _get_format_instruction(fmt)
        fmt_context = f"\nFormat narrative: {fmt_instruction}" if fmt_instruction else ""

        messages = [
            SystemMessage(content=prompt.system_prompt),
            HumanMessage(
                content=(
                    f"Generate a complete HTML document for a {fmt} post "
                    f"({_get_format_dimensions(fmt)}).{fmt_context}\n\n"
                    f"Copy text to include:\n{copy_text[:800]}\n\n"
                    f"Background: {bg.get('css', '')}\n"
                    f"Tailwind classes like bg-primary, text-secondary, "
                    f"font-sans, rounded-md, shadow-sm will resolve "
                    f"to the brand's design tokens automatically.\n\n"
                    f"Requirements:\n"
                    f"- Use Tailwind CSS via CDN\n"
                    f"- Must be a FULLY VISIBLE design with the copy text "
                    f"rendered prominently in the body\n"
                    f"- The entire {_get_format_dimensions(fmt)} canvas "
                    f"must be filled with design elements\n"
                    f"- High contrast, readable text, striking visual\n"
                    f"- No overflow, no scrollbars\n"
                    f"- Start with <!DOCTYPE html> and output ONLY the "
                    f"complete HTML document"
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

        raw_content = response.content
        if isinstance(raw_content, list):
            texts = [b.get("text", "") for b in raw_content if b.get("type") == "text"]
            raw_content = "".join(texts)
        elif not isinstance(raw_content, str):
            raw_content = str(raw_content)
        html = _extract_html(raw_content)
        if tokens:
            tw_script = tailwind_config_html(tokens)
            html = html.replace("</head>", f"{tw_script}</head>") if "</head>" in html else tw_script + "\n" + html
        html_by_format[fmt] = html

    return {"html_by_format": html_by_format, "next_node": "quality_check"}


async def _get_format_instruction(fmt_id: str) -> str:
    try:
        from app.models.format import Format
        s = get_settings()
        engine, pool = await create_pool(s.database_url)
        async with pool() as session:
            result = await session.execute(select(Format).where(Format.id == fmt_id))
            fmt = result.scalar_one_or_none()
            await engine.dispose()
            return fmt.ai_instruction if fmt and fmt.ai_instruction else ""
    except Exception:
        return ""


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
