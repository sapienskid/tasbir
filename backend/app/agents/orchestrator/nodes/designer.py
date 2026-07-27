"""Designer agent (Marcus Chen) — generates HTML per format in parallel.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() and
injects design tokens as Tailwind config + Google Fonts.
"""

import asyncio
import re
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
from app.services.token_exchange import build_config_html, flatten_tokens

_tools = [search_templates, fetch_design_tokens, svg_illustration]
_tool_node = ToolNode(_tools)


async def _resolve_tokens(state: GenerationState) -> tuple[dict, dict]:
    """Resolve the full token set + brand with logo_url from DB.

    Lookup order:
    1. Tokens already passed in state (caller-supplied).
    2. Tokens stored in ``brands.data["tokens"]`` (matched by brand name).
    3. Tokens stored in the ``design_tokens`` table (matched by brand name).

    Returns (tokens, brand) tuple — brand is enriched with metadata from DB.
    """
    import logging
    log = logging.getLogger(__name__)

    tokens = dict(state.get("design_tokens", {}) or {})
    brand = dict(state.get("brand", {}) or {})

    brand_name = brand.get("name") or ""
    if brand_name:
        try:
            from app.db.repositories.brands import BrandRepository
            from app.db.session import get_shared_session_factory

            pool = await get_shared_session_factory()
            async with pool() as session:
                repo = BrandRepository(session)
                db_brand = await repo.get_by_name(brand_name)
                if db_brand and db_brand.data:
                    data = dict(db_brand.data)
                    # Merge brand.data["tokens"] (primary source)
                    db_tokens = data.get("tokens", {})
                    if db_tokens:
                        for category, category_data in db_tokens.items():
                            if isinstance(category_data, dict):
                                if category not in tokens:
                                    tokens[category] = {}
                                if isinstance(tokens[category], dict):
                                    for k, v in category_data.items():
                                        if k not in tokens[category]:
                                            tokens[category][k] = v
                    # Merge brand metadata from DB
                    for key in ("primary_color", "secondary_color", "tone", "logo_url", "style_notes"):
                        if not brand.get(key) and data.get(key):
                            brand[key] = data[key]

                # Also load from the standalone design_tokens table (secondary source).
                # This covers tokens saved via POST /tokens or /tokens/generate.
                if not tokens:
                    from sqlalchemy import select
                    from app.models.tokens import DesignToken
                    result = await session.execute(
                        select(DesignToken).where(
                            DesignToken.name == brand_name.lower()
                        )
                    )
                    dt = result.scalar_one_or_none()
                    if dt and dt.data:
                        tokens = dict(dt.data)
                        log.debug("[designer] Loaded tokens from design_tokens table for brand '%s'", brand_name)

        except Exception as exc:
            log.warning("[designer] DB token lookup failed for brand '%s': %s", brand_name, exc)

    return tokens, brand


async def designer_node_single(state: GenerationState) -> dict:
    fmt_id = state["_processing_format_id"]
    prompt = await get_prompt("designer")
    task = dict(state["format_tasks"].get(fmt_id, {}))

    fmt_info = await get_format_info(fmt_id)
    llm = get_llm(
        agent_role="designer",
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    ).bind_tools(_tools)

    copy_text = task.get("copy", "")
    bg = task.get("background", {})
    tokens, brand = await _resolve_tokens(state)
    fmt_context = f"\n**FORMAT INSTRUCTION (follow this layout exactly)**: {fmt_info.ai_instruction}" if fmt_info.ai_instruction else ""

    system_prompt = prompt.system_prompt.replace("{WIDTH}", str(fmt_info.width)).replace("{HEIGHT}", str(fmt_info.height))

    brand_vibe_parts = []
    if brand.get("description"):
        brand_vibe_parts.append(brand["description"])
    elif brand.get("style_notes"):
        brand_vibe_parts.append(brand["style_notes"])
    brand_vibe = " ".join(brand_vibe_parts) if brand_vibe_parts else f"Tone: {brand.get('tone', 'professional')}"

    brand_primary = brand.get("primary_color", "")
    brand_secondary = brand.get("secondary_color", "")

    # Dynamically calculate aspect ratio for custom or standard formats
    ratio = fmt_info.width / fmt_info.height if fmt_info.height > 0 else 1.0
    if ratio < 0.85:
        orientation_hint = f"TALL / VERTICAL canvas ({fmt_info.width}x{fmt_info.height}, ratio {ratio:.2f}). Use vertical flex layout (flex flex-col justify-between h-full). Padding p-8 to p-14."
    elif ratio > 1.15:
        orientation_hint = f"WIDE / HORIZONTAL canvas ({fmt_info.width}x{fmt_info.height}, ratio {ratio:.2f}). Use 2-column horizontal grid (grid grid-cols-12 gap-8 h-full) or left-aligned flex row."
    else:
        orientation_hint = f"SQUARE / BALANCED canvas ({fmt_info.width}x{fmt_info.height}, ratio {ratio:.2f}). Padding p-8 to p-12 max. Max headline font text-4xl."

    # Background hint for contrast guidance
    bg_hint = bg.get("description", bg.get("css", "")[:80]) or "dark gradient background"

    system_prompt = prompt.system_prompt.replace("{WIDTH}", str(fmt_info.width)).replace("{HEIGHT}", str(fmt_info.height))

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Craft a standalone HTML visual graphic poster for {fmt_info.name} ({fmt_info.id}).\n"
                f"EXACT CANVAS DIMENSIONS: {fmt_info.width}px width by {fmt_info.height}px height.\n"
                f"CANVAS ORIENTATION: {orientation_hint}{fmt_context}\n\n"
                f"BRAND: {brand.get('name', 'Tasbir')}\n"
                f"Tone: {brand.get('tone', 'professional')}\n"
                f"Vibe: {brand_vibe}\n"
                + (f"Primary color: {brand_primary}\n" if brand_primary else "")
                + (f"Secondary color: {brand_secondary}\n" if brand_secondary else "")
                + f"Contrast hint: {bg_hint}\n\n"
                f"TOPIC: {state.get('title', '')}\n"
                f"Context: {state.get('strategic_brief', '')[:400]}\n\n"
                f"COPY TO RENDER:\n{copy_text[:1200]}\n\n"
                f"BACKGROUND: {bg.get('css', '')}\n\n"
                f"RULES:\n"
                f"- Canvas: {fmt_info.width}x{fmt_info.height}. Body: style=\"width:{fmt_info.width}px;height:{fmt_info.height}px;overflow:hidden;margin:0\"\n"
                f"- Semantic Tailwind classes ONLY (bg-primary, bg-secondary, bg-accent, bg-surface, text-primary, text-secondary, text-white, font-sans, font-serif, font-mono).\n"
                f"- NO raw CSS, inline styles, or <style> blocks.\n"
                f"- NO nav, buttons, links, forms, interactive elements. NO emojis.\n"
                f"- Vary the layout — make it bespoke for this format and brand.\n"
                f"- Output: <!DOCTYPE html> only. No markdown code fences. No explanations."
            )
        ),
    ]

    response = await call_llm_with_retry(llm, messages, agent_role="designer")

    if response.tool_calls:
        tool_result = await _tool_node.ainvoke({"messages": [response]})
        tool_context = "\n".join(
            str(m.content) for m in tool_result["messages"] if hasattr(m, "content")
        )
        messages.append(response)
        for m in tool_result["messages"]:
            messages.append(m)
        messages.append(HumanMessage(content=f"Now generate the HTML. Context: {tool_context[:1000]}"))
        response = await call_llm_with_retry(llm, messages, agent_role="designer")

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

    content_source = state.get("content", "") + "\n" + copy_text
    html = _extract_html(raw_content)
    html = _inject_theme(html, tokens, brand)
    html = _inject_katex(html, content_source)
    html = _inject_mermaid(html, content_source)
    html = fix_all(html, width=fmt_info.width, height=fmt_info.height, brand=state.get("brand"))

    updated_task = dict(task)
    updated_task["html"] = html
    updated_task["status"] = "designed"

    return {"format_tasks": {fmt_id: updated_task}}


def _inject_theme(html: str, tokens: dict, brand: dict | None = None) -> str:
    """Inject Tailwind config + Google Fonts + CSS vars from design tokens.

    Removes LLM-generated duplicates (CDN, config, fonts) and injects
    our authoritative config. Preserves LLM's inline styles, style blocks,
    and element classes — the LLM builds the visual layout, we just
    ensure the design token system powers the styling.
    """
    import re

    # Remove duplicated CDN/config/fonts the LLM may have included.
    # Strip both the old `tailwind.config = {...}` pattern and the new
    # `window.tailwind = {...}` pattern so we don't end up with two configs.
    html = re.sub(r'<script\s+src="https://cdn\.tailwindcss\.com"[^>]*>\s*</script>', '', html)
    html = re.sub(r'<script[^>]*>\s*(?:window\.)?tailwind(?:\.config)?\s*=\s*\{.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<link[^>]*fonts\.googleapis\.com[^>]*/?>',  '', html)

    cfg_html = build_config_html(tokens=tokens, brand=brand)

    if "</head>" in html:
        # Happy path — LLM produced a proper HTML document.
        html = html.replace("</head>", f"{cfg_html}\n</head>", 1)
    elif "<body" in html:
        # LLM omitted <head> but included <body> — wrap in a minimal document.
        html = (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            f"{cfg_html}\n"
            "</head>\n"
            + html
        )
    else:
        # Bare fragment — wrap everything in a full document skeleton.
        html = (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            f"{cfg_html}\n"
            "</head>\n<body>\n"
            + html
            + "\n</body>\n</html>"
        )

    # Inject brand logo programmatically
    logo_url = (brand or {}).get("logo_url", "")
    if logo_url:
        brand_name = (brand or {}).get("name", "")
        html = re.sub(
            r'(<body[^>]*>)',
            r'\1\n' + (
                f'<img src="{logo_url}" '
                f'class="absolute top-4 left-4 h-8 max-w-[160px] object-contain z-50" '
                f'alt="{brand_name} Logo" />'
            ),
            html, count=1,
        )

    return html


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
        return html.replace("</head>", f"{katex_head}\n</head>")
    return katex_head + "\n" + html


def _inject_mermaid(html: str, content: str) -> str:
    """Inject Mermaid.js CDN if content contains a mermaid code block."""
    has_mermaid = "```mermaid" in content or 'class="mermaid"' in html or "class='mermaid'" in html
    if not has_mermaid:
        return html
    mermaid_head = (
        '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>\n'
        "<script>\n"
        "document.addEventListener('DOMContentLoaded', async function() {\n"
        "  mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });\n"
        "  await mermaid.run();\n"
        "  document.body.setAttribute('data-mermaid-ready', 'true');\n"
        "});\n"
        "</script>"
    )
    if "</head>" in html:
        return html.replace("</head>", f"{mermaid_head}\n</head>")
    return mermaid_head + "\n" + html


def _first_spacing(flat_tokens: dict) -> str:
    for k in flat_tokens:
        if any(s in k.lower() for s in ("spacing", "gap", "padding")):
            return k.split("/")[-1]
    return "4"


def _first_radius(flat_tokens: dict) -> str:
    for k in flat_tokens:
        if any(r in k.lower() for r in ("radius", "rounded")):
            return k.split("/")[-1]
    return "md"


def _first_shadow(flat_tokens: dict) -> str:
    for k in flat_tokens:
        if any(s in k.lower() for s in ("shadow", "boxshadow")):
            return k.split("/")[-1]
    return "md"


def _extract_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
