"""Designer agent (Marcus Chen) — generates HTML per format in parallel using dynamic DB formats.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() to optionally
fetch templates and design tokens before generating HTML.
"""

import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from app.agents.orchestrator.state import GenerationState
from app.agents.orchestrator.tools.fetch_design_tokens import fetch_design_tokens
from app.agents.orchestrator.tools.search_templates import search_templates
from app.agents.prompts.registry import PromptVersion, get_prompt
from app.services.formats import get_format_info
from app.services.llm import get_llm
from app.services.token_exchange import tailwind_config_html

_tools = [search_templates, fetch_design_tokens]
_tool_node = ToolNode(_tools)


async def _generate_html_for_format(
    fmt_id: str,
    state: GenerationState,
    prompt: PromptVersion,
) -> tuple[str, str]:
    fmt_info = await get_format_info(fmt_id)
    llm = get_llm(
        agent_role="designer",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    ).bind_tools(_tools)

    copy_text = state["copy_by_format"].get(fmt_id, "")
    bg = state["background_by_format"].get(fmt_id, {})
    tokens = state.get("design_tokens", {})
    fmt_context = f"\nFORMAT NARRATIVE INSTRUCTION: {fmt_info.ai_instruction}" if fmt_info.ai_instruction else ""

    messages = [
        SystemMessage(content=prompt.system_prompt),
        HumanMessage(
            content=(
                f"As Marcus Chen, craft a standalone HTML visual graphic poster for {fmt_info.name} ({fmt_info.id}).\n"
                f"EXACT CANVAS DIMENSIONS: {fmt_info.width}px width by {fmt_info.height}px height.{fmt_context}\n\n"
                f"COPY TEXT TO RENDER:\n{copy_text[:1200]}\n\n"
                f"BACKGROUND STYLE:\n{bg.get('css', '')}\n\n"
                f"DESIGN SYSTEM TOKENS AVAILABLE:\n{tokens}\n\n"
                f"CRITICAL CANVAS REQUIREMENTS:\n"
                f"- Create purely a graphic image canvas fitting EXACTLY {fmt_info.width}x{fmt_info.height}\n"
                f"- DO NOT create website UI layouts, navigation headers, search bars, URL bars, or interactive <button> elements\n"
                f"- DO NOT include raw Unicode emojis anywhere\n"
                f"- Include Tailwind CDN & Google Fonts (Instrument Serif & Inter)\n"
                f"- Use translucent glass cards, badge accents, gradient text, dynamic glows, and high-contrast typography\n"
                f"- ZERO overflow, ZERO scrollbars (`overflow-hidden`)\n"
                f"- Start with <!DOCTYPE html> and output ONLY the clean HTML"
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

    return fmt_id, html


async def designer_node(state: GenerationState) -> dict:
    prompt = await get_prompt("designer")
    formats = state["requested_formats"]

    tasks = [_generate_html_for_format(fmt, state, prompt) for fmt in formats]
    results = await asyncio.gather(*tasks)

    html_by_format = {fmt: html for fmt, html in results}
    return {"html_by_format": html_by_format, "next_node": "quality_check"}


def _extract_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
