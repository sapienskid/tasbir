"""Designer agent (Marcus Chen) — generates HTML per format in parallel using dynamic DB formats.

Uses LangChain ChatGoogleGenerativeAI with bind_tools() to optionally
fetch templates and design tokens before generating HTML.
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
from app.services.token_exchange import tailwind_config_html

_tools = [search_templates, fetch_design_tokens, svg_illustration]
_tool_node = ToolNode(_tools)

# Default fallback fonts used when brand provides none
_DEFAULT_HEADING_FONT = "Instrument Serif"
_DEFAULT_BODY_FONT = "Inter"
_DEFAULT_MONO_FONT = "JetBrains Mono"


def _extract_brand_fonts(tokens: dict, brand: dict) -> dict[str, str]:
    """Extract brand font families from design tokens or brand metadata.

    Priority order:
    1. Design tokens (DTCG fontFamily group)
    2. Brand metadata font_* fields
    3. Fallback defaults (Instrument Serif / Inter / JetBrains Mono)

    Returns dict with keys: heading, body, mono
    """
    fonts: dict[str, str] = {}

    # 1. Try design tokens — look for fontFamily/heading, fontFamily/body, fontFamily/mono
    font_group = tokens.get("fontFamily", tokens.get("typography", {}).get("fontFamily", {}))
    if isinstance(font_group, dict):
        for alias in ("heading", "display", "serif"):
            entry = font_group.get(alias)
            if isinstance(entry, dict):
                fonts["heading"] = entry.get("$value", entry.get("value", ""))
            elif isinstance(entry, str):
                fonts["heading"] = entry
            if fonts.get("heading"):
                break
        for alias in ("body", "sans", "base"):
            entry = font_group.get(alias)
            if isinstance(entry, dict):
                fonts["body"] = entry.get("$value", entry.get("value", ""))
            elif isinstance(entry, str):
                fonts["body"] = entry
            if fonts.get("body"):
                break
        for alias in ("mono", "code", "monospace"):
            entry = font_group.get(alias)
            if isinstance(entry, dict):
                fonts["mono"] = entry.get("$value", entry.get("value", ""))
            elif isinstance(entry, str):
                fonts["mono"] = entry
            if fonts.get("mono"):
                break

    # 2. Fall back to brand metadata fields
    if not fonts.get("heading") and brand.get("font_heading"):
        fonts["heading"] = brand["font_heading"]
    if not fonts.get("body") and brand.get("font_body"):
        fonts["body"] = brand["font_body"]
    if not fonts.get("mono") and brand.get("font_mono"):
        fonts["mono"] = brand["font_mono"]

    # 3. Apply defaults
    fonts.setdefault("heading", _DEFAULT_HEADING_FONT)
    fonts.setdefault("body", _DEFAULT_BODY_FONT)
    fonts.setdefault("mono", _DEFAULT_MONO_FONT)

    return fonts


def _build_google_fonts_url(fonts: dict[str, str]) -> str:
    """Build a Google Fonts CDN URL from brand font names.

    Requests variable weight ranges (300-800) for body/heading.
    Falls back gracefully for unknown fonts.
    """
    families = []
    heading = fonts.get("heading", _DEFAULT_HEADING_FONT)
    body = fonts.get("body", _DEFAULT_BODY_FONT)
    mono = fonts.get("mono", _DEFAULT_MONO_FONT)

    # Encode each unique family name with weight variants
    seen = set()
    for name, weights in [
        (heading, "ital,wght@0,400;0,700;1,400;1,700"),
        (body, "wght@300;400;500;600;700;800"),
        (mono, "wght@400;500;600"),
    ]:
        if name and name not in seen:
            seen.add(name)
            encoded = name.replace(" ", "+")
            families.append(f"family={encoded}:{weights}")

    if not families:
        return (
            "https://fonts.googleapis.com/css2?"
            "family=Instrument+Serif:ital@0;1"
            "&family=Inter:wght@300;400;500;600;700;800"
            "&family=JetBrains+Mono:wght@400;500&display=swap"
        )
    return "https://fonts.googleapis.com/css2?" + "&".join(families) + "&display=swap"


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

    # ── Brand fonts: extract from tokens then brand metadata ──────────────
    brand_fonts = _extract_brand_fonts(tokens, brand)
    fonts_are_custom = (
        brand_fonts["heading"] != _DEFAULT_HEADING_FONT
        or brand_fonts["body"] != _DEFAULT_BODY_FONT
    )
    google_fonts_url = _build_google_fonts_url(brand_fonts)
    brand_fonts_instruction = (
        f"BRAND FONTS (USE THESE — do NOT use Instrument Serif or Inter):\n"
        f"  Heading / Display font: {brand_fonts['heading']}\n"
        f"  Body / Paragraph font:  {brand_fonts['body']}\n"
        f"  Mono / Accent font:     {brand_fonts['mono']}\n"
        f"  Google Fonts URL: {google_fonts_url}"
        if fonts_are_custom
        else (
            f"FONTS (fallback defaults — no brand fonts specified):\n"
            f"  Heading: {brand_fonts['heading']}\n"
            f"  Body: {brand_fonts['body']}\n"
            f"  Mono: {brand_fonts['mono']}\n"
            f"  Google Fonts URL: {google_fonts_url}"
        )
    )

    # ── Build brand vibe from description, style notes, and tone ──────────
    brand_vibe_parts = []
    if brand.get("description"):
        brand_vibe_parts.append(brand["description"])
    elif brand.get("style_notes"):
        brand_vibe_parts.append(brand["style_notes"])
    brand_vibe = " ".join(brand_vibe_parts) if brand_vibe_parts else f"Tone: {brand.get('tone', 'professional')}"

    logo_url = brand.get("logo_url")
    logo_instruction = (
        f"BRAND LOGO URL: {logo_url} (CRITICAL: You MUST include this brand logo in the graphic, e.g. <img src=\"{logo_url}\" class=\"h-8 max-w-[160px] object-contain\" alt=\"{brand.get('name', 'Brand')} Logo\" />)"
        if logo_url
        else "BRAND LOGO: None provided"
    )

    feature_img = state.get("feature_image")
    image_embeds = state.get("image_embeds", [])
    img_instruction = (
        f"IMAGE EMBEDDINGS AVAILABLE: Feature Image: {feature_img}, Embeds: {image_embeds}. "
        f"Integrate imagery into the graphic (e.g. split editorial photo panel, background photo with gradient tint overlay, or framed image card)."
        if (feature_img or image_embeds)
        else "IMAGE EMBEDDINGS: None provided"
    )

    user_badge = state.get("badge_tag") or state.get("badge")
    badge_rule = (
        f"BADGE RULE: Render the user's badge tag '{user_badge}' as a clean capsule accent."
        if user_badge
        else "BADGE RULE: No badge specified by user. STRICTLY DO NOT render any badge, tag, or pill element in the HTML."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Craft a standalone HTML visual graphic poster for {fmt_info.name} ({fmt_info.id}).\n"
                f"EXACT CANVAS DIMENSIONS: {fmt_info.width}px width by {fmt_info.height}px height.{fmt_context}\n\n"
                f"BRAND VIBE (let this guide every visual choice — color mood, typography attitude, spacing, shape language):\n"
                f"  Brand: {brand.get('name', '')} — {brand_vibe}\n"
                f"  {logo_instruction}\n\n"
                f"{brand_fonts_instruction}\n\n"
                f"ARTICLE TOPIC (the graphic must visually reflect this subject, not be generic):\n"
                f"  {state.get('title', '')}\n"
                f"  {state.get('strategic_brief', '')[:800]}\n\n"
                f"COPY TEXT TO RENDER:\n{copy_text[:1500]}\n\n"
                f"BACKGROUND STYLE:\n{bg.get('css', '')}\n\n"
                f"{img_instruction}\n\n"
                f"{badge_rule}\n\n"
                f"CRITICAL CANVAS REQUIREMENTS:\n"
                f"- Create purely a human-designed social media graphic image canvas fitting EXACTLY {fmt_info.width}x{fmt_info.height}\n"
                f"- DO NOT create website layouts, navigation, headers, search bars, buttons, links, or interactive elements\n"
                f"- DO NOT include raw Unicode emojis anywhere\n"
                f"- Apply safe zone padding: minimum 5% margin on all edges (never place text at canvas border)\n"
                f"- Include Tailwind CDN & Google Fonts link tag using the URL provided in BRAND FONTS above\n"
                f"- Use standard Tailwind utility classes only\n"
                f"- Let the brand vibe above guide every visual decision — color choices, typography weight, shape language, spacing\n"
                f"- Use translucent glass cards, gradient text, dynamic glows, and high-contrast typography\n"
                f"- If brand logo URL is provided above, render it cleanly in the header or watermark position\n"
                f"- If badge tag was NOT requested, DO NOT render any badge capsule element\n"
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

    content_source = state.get("content", "") + "\n" + copy_text
    html = _extract_html(raw_content)
    html = _inject_theme(html, tokens)
    html = _inject_google_fonts(html, google_fonts_url)
    html = _inject_katex(html, content_source)
    html = _inject_mermaid(html, content_source)
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


def _inject_google_fonts(html: str, url: str) -> str:
    """Ensure exactly one Google Fonts <link> tag is present and points to the correct URL.

    If the designer already included a Google Fonts link (with different font families),
    replace it with the brand-correct URL. If none present, inject it.
    """
    existing_pattern = re.compile(
        r'<link[^>]+href=["\']https://fonts\.googleapis\.com[^"\']*["\'][^>]*/?>',
        re.IGNORECASE,
    )
    canonical_link = f'<link rel="stylesheet" href="{url}">'

    if existing_pattern.search(html):
        # Replace the first occurrence; remove duplicates
        html = existing_pattern.sub("", html, count=99)
        if "</head>" in html:
            html = html.replace("</head>", f"{canonical_link}\n</head>", 1)
    elif "</head>" in html:
        html = html.replace("</head>", f"{canonical_link}\n</head>", 1)
    return html


def _inject_katex(html: str, content: str) -> str:
    """Inject KaTeX CDN if content or copy contains LaTeX math."""
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
    """Inject Mermaid.js CDN if content or copy contains a mermaid code block.

    Uses startOnLoad: false + mermaid.run() pattern so diagrams are fully
    rendered before Playwright captures the screenshot. Sets a
    data-mermaid-ready sentinel attribute on <body> when complete so the
    renderer can wait for it.
    """
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


def _extract_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
