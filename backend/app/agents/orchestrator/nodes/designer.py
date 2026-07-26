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
from app.agents.orchestrator.tools.svg_illustration import svg_illustration
from app.agents.prompts.registry import PromptVersion, get_prompt
from app.services.fixer import fix_all
from app.services.formats import get_format_info
from app.services.llm import call_llm_with_retry, get_llm
from app.services.token_exchange import tailwind_config_html

_tools = [search_templates, fetch_design_tokens, svg_illustration]
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
    brand = state.get("brand", {})
    fmt_context = f"\n**FORMAT INSTRUCTION (follow this layout exactly)**: {fmt_info.ai_instruction}" if fmt_info.ai_instruction else ""

    system_prompt = prompt.system_prompt.replace("{WIDTH}", str(fmt_info.width)).replace("{HEIGHT}", str(fmt_info.height))

    # Build brand vibe from description, style notes, and tone — qualitative, not technical
    brand_vibe_parts = []
    if brand.get("description"):
        brand_vibe_parts.append(brand["description"])
    elif brand.get("style_notes"):
        brand_vibe_parts.append(brand["style_notes"])
    brand_vibe = " ".join(brand_vibe_parts) if brand_vibe_parts else f"Tone: {brand.get('tone', 'professional')}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"As Marcus Chen, craft a standalone HTML visual graphic poster for {fmt_info.name} ({fmt_info.id}).\n"
                f"EXACT CANVAS DIMENSIONS: {fmt_info.width}px width by {fmt_info.height}px height.{fmt_context}\n\n"
                f"BRAND VIBE (let this guide every visual choice — color mood, typography attitude, spacing, shape language):\n"
                f"  Brand: {brand.get('name', '')} — {brand_vibe}\n\n"
                f"ARTICLE TOPIC (the graphic must visually reflect this subject, not be generic):\n"
                f"  {state.get('title', '')}\n"
                f"  {state.get('strategic_brief', '')[:600]}\n\n"
                f"COPY TEXT TO RENDER:\n{copy_text[:1200]}\n\n"
                f"BACKGROUND STYLE:\n{bg.get('css', '')}\n\n"
                f"CRITICAL CANVAS REQUIREMENTS:\n"
                f"- Create purely a social media graphic image canvas fitting EXACTLY {fmt_info.width}x{fmt_info.height}\n"
                f"- DO NOT create website layouts, navigation, headers, search bars, buttons, links, or interactive elements\n"
                f"- DO NOT include raw Unicode emojis anywhere\n"
                f"- Include Tailwind CDN & Google Fonts (Instrument Serif & Inter)\n"
                f"- Use standard Tailwind utility classes only\n"
                f"- Let the brand vibe above guide every visual decision — color choices, typography weight, shape language, spacing\n"
                f"- Use translucent glass cards, badge accents, gradient text, dynamic glows, and high-contrast typography\n"
                f"- ZERO overflow, ZERO scrollbars — all content must fit within {fmt_info.width}x{fmt_info.height}\n"
                f"- Start with <!DOCTYPE html> and output ONLY the clean HTML"
            )
        ),
    ]

    response = await call_llm_with_retry(llm, messages)

    if response.tool_calls:
        tool_result = await _tool_node.ainvoke({"messages": [response]})
        tool_context = "\n".join(
            str(m.content) for m in tool_result["messages"] if hasattr(m, "content")
        )
        messages.append(response)
        for m in tool_result["messages"]:
            messages.append(m)
        messages.append(HumanMessage(content=f"Now generate the HTML. Context: {tool_context[:1000]}"))
        response = await call_llm_with_retry(llm, messages)

    raw_content = response.content
    if isinstance(raw_content, list):
        texts = []
        for b in raw_content:
            if isinstance(b, str):
                texts.append(b)
            elif isinstance(b, dict) and b.get("type") == "text":
                texts.append(b.get("text", ""))
        raw_content = "".join(texts)
    elif not isinstance(raw_content, str):
        raw_content = str(raw_content)

    html = _extract_html(raw_content)
    html = _inject_theme(html, tokens)
    html = _inject_katex(html, state.get("content", ""))
    html = fix_all(html, width=fmt_info.width, height=fmt_info.height, brand=state.get("brand"))

    return fmt_id, html


async def designer_node(state: GenerationState) -> dict:
    prompt = await get_prompt("designer")
    formats = state["requested_formats"]

    tasks = [_generate_html_for_format(fmt, state, prompt) for fmt in formats]
    results = await asyncio.gather(*tasks)

    html_by_format = {fmt: html for fmt, html in results}
    return {"html_by_format": html_by_format}


def _inject_theme(html: str, tokens: dict) -> str:
    """Inject tailwind.config theme from design tokens."""
    if not tokens:
        return html
    tw_script = tailwind_config_html(tokens)
    if "</head>" in html:
        return html.replace("</head>", f"{tw_script}</head>")
    return tw_script + "\n" + html


def _inject_katex(html: str, content: str) -> str:
    """Inject KaTeX CDN if content contains LaTeX math."""
    has_math = any(marker in content for marker in (r"\(", r"\[", r"$$", r"\frac", r"\sum", r"\int"))
    if not has_math:
        return html
    katex_head = (
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">\n'
        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>\n'
        '<script>document.addEventListener("DOMContentLoaded",function(){renderMathInElement(document.body,{delimiters:[{left:"\\\\[",right:"\\\\]",display:true},{left:"\\\\(",right:"\\\\)",display:false},{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false}]})});</script>'
    )
    if "</head>" in html:
        return html.replace("</head>", f"{katex_head}</head>")
    return katex_head + "\n" + html


def _extract_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
