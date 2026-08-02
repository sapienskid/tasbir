"""Prompt preview — reconstruct the assembled system + user prompt for an agent.

User prompts are assembled dynamically inside each node/service, so they are
NOT stored in the DB. This module reconstructs a *representative* assembly
from the current design system so the Studio can show exactly what reaches
the LLM — the system prompt and the user prompt built for a sample post.
"""

from __future__ import annotations

import json

from app.services.agents import get_agent_config, get_shared_session_factory
from app.services.design_instruction import (
    build_google_fonts_link,
    format_design_instruction_block,
    format_format_layout_block,
    format_layout_archetype_block,
    pick_layout_archetype,
)
from app.services.formats import get_format_info
from app.services.tokens import build_css_var_reference

_SAMPLE_PLATFORM = "instagram-square"
_SAMPLE_TITLE = "The measure of a well-set column"
_SAMPLE_CONTENT = (
    "A grid sets order and a measure sets pace. Constrain the line, free the "
    "reader, and let the whitespace do its work. The key finding is that "
    "generous margins improve reading flow. $E=mc^2$ appears once."
)
_SAMPLE_EXCERPT = "White space is the rhythm between ideas; a grid gives it a voice."
_SAMPLE_TAGS = ["typography", "grids", "editorial"]


async def _load_payload(design_system_id: str) -> dict:
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_systems import (
        build_pipeline_payload,
        get_or_create_default,
    )

    pool = await get_shared_session_factory()
    async with pool() as session:
        ds = await DesignSystemRepository(session).get_by_id(design_system_id)
    if ds is None:
        await get_or_create_default(pool)
        async with pool() as session:
            ds = await DesignSystemRepository(session).get_by_id(design_system_id)
    return build_pipeline_payload(ds) if ds else {}


def _sample_brief(payload: dict) -> dict:
    campaign = payload.get("campaigns", {})
    campaign_name = list(campaign)[0] if campaign else "default"
    campaign_cfg = campaign.get(campaign_name, {})
    return {
        "angle": "The quiet discipline of a well-set column",
        "audience": "Designers and writers who care about typography",
        "tone": campaign_cfg.get("tone", "professional"),
        "visual_direction": "clean editorial",
        "category": "WRITING",
        "ground": campaign_cfg.get("ground", "white"),
        "template_hint": "",
        "platform_notes": {_SAMPLE_PLATFORM: "Optimized for the square format"},
    }


def _resolve_system_prompt(name: str, system_prompt: str, payload: dict) -> str:
    """Substitute designer placeholders so the preview shows the real prompt."""
    if "{TEMPLATE_CONTEXT}" not in system_prompt:
        return system_prompt

    tokens = payload.get("design_tokens", {})
    token_roles = payload.get("token_roles", {})
    di = payload.get("design_instruction", {})
    fmt = get_format_info(_SAMPLE_PLATFORM)
    css_var_reference = build_css_var_reference(tokens, token_roles or None)
    di_block = format_design_instruction_block(di)
    layout_block = format_format_layout_block(di, _SAMPLE_PLATFORM, fmt.width, fmt.height)
    template_context = f"{css_var_reference}\n\n{di_block}\n\n{layout_block}"

    return (
        system_prompt.replace("{TEMPLATE_CONTEXT}", template_context)
        .replace("{WIDTH}", str(fmt.width))
        .replace("{HEIGHT}", str(fmt.height))
    )


def _ds_context(payload: dict) -> str:
    from app.agents.orchestrator.nodes.quality_check import _build_design_system_context

    tokens = payload.get("design_tokens", {})
    di = payload.get("design_instruction", {})
    footer = payload.get("footer", {"left": "", "right": ""})
    category = (payload.get("categories") or [{}])[0].get("name", "WRITING")
    ground = payload.get("campaigns", {}).get("default", {}).get("ground", "white")
    return _build_design_system_context(tokens, di, footer, category, ground)


async def _build_user_prompt(name: str, payload: dict) -> str:
    fmt = get_format_info(_SAMPLE_PLATFORM)
    brief = _sample_brief(payload)
    brand = payload.get("brand_info", {})
    footer = payload.get("footer", {"left": "", "right": ""})
    campaign_cfg = (payload.get("campaigns") or {}).get("default", {})

    if name == "strategist":
        cat_lines = "\n".join(
            f"  {c.get('name', '')} — {c.get('description', '')}"
            + (f" [ground: {c.get('ground')}]" if c.get("ground") else "")
            for c in (payload.get("categories") or [])
        )
        categories_block = (
            "APPROVED CATEGORY LABELS (choose exactly one):\n" + cat_lines + "\n"
            if cat_lines
            else ""
        )
        brand_block = (
            f"BRAND: {brand.get('name', '')}\nTAGLINE: {brand.get('tagline', '')}\n"
            f"MISSION: {brand.get('mission', '')}\nSTORY: {brand.get('story', '')}\n"
            if brand.get("name")
            else ""
        )
        campaign_block = (
            f"CAMPAIGN: default\nTONE: {campaign_cfg.get('tone', '')}\n"
            f"GROUND: {campaign_cfg.get('ground', '')}\n"
            f"LANGUAGE: {campaign_cfg.get('language', '')}\n"
            if campaign_cfg
            else ""
        )
        return (
            f"TITLE: {_SAMPLE_TITLE}\n\n"
            f"{brand_block}\n{campaign_block}\n{categories_block}\n"
            f"TARGET PLATFORMS: {_SAMPLE_PLATFORM}\n"
            f"TAGS: {', '.join(_SAMPLE_TAGS)}\nEXCERPT: {_SAMPLE_EXCERPT}\n\n"
            f"CONTENT:\n{_SAMPLE_CONTENT}"
        )

    if name == "copywriter":
        brand_block = (
            f"BRAND: {brand.get('name', '')}\nTAGLINE: {brand.get('tagline', '')}\n"
            if brand.get("name")
            else ""
        )
        campaign_block = "CAMPAIGN: default\n" if campaign_cfg else ""
        return (
            f"PLATFORM: {_SAMPLE_PLATFORM} ({fmt.width}x{fmt.height}px)\n"
            f"{brand_block}{campaign_block}"
            f"STRATEGIC ANGLE: {brief.get('angle', '')}\n"
            f"AUDIENCE: {brief.get('audience', '')}\n"
            f"TONE: {brief.get('tone', 'professional')}\n"
            f"PLATFORM NOTE: {brief.get('platform_notes', {}).get(_SAMPLE_PLATFORM, '')}\n\n"
            f"SOURCE TITLE: {_SAMPLE_TITLE}\n"
            f"SOURCE CONTENT (excerpt):\n{_SAMPLE_CONTENT[:2000]}"
        )

    if name == "designer":
        from app.agents.orchestrator.nodes.designer import _ground_css_vars

        di = payload.get("design_instruction", {})
        tokens = payload.get("design_tokens", {})
        archetype_key, archetype_desc = pick_layout_archetype(
            di, f"{_SAMPLE_TITLE}|{_SAMPLE_PLATFORM}|WRITING|0"
        )
        archetype_block = format_layout_archetype_block(archetype_key, archetype_desc)
        brand_prefix = f"BRAND: {brand.get('name', '')}\n" if brand.get("name") else ""
        campaign_block = (
            f"CAMPAIGN: default\nTONE: {campaign_cfg.get('tone', '')}\n"
            f"LANGUAGE: {campaign_cfg.get('language', '')}\n"
            if campaign_cfg
            else ""
        )
        ground = brief.get("ground", "white")
        category = brief.get("category", "")
        footer_left = footer.get("left", "")
        footer_right = footer.get("right", "")
        footer_block = (
            "FOOTER ROW (REQUIRED on every format):\n"
            f"  Left (SIGNATURE WORDMARK): {footer_left} — display face "
            "(var(--font-display)), ~24px, weight 500, tight tracking, uppercase\n"
            f"  Right: {footer_right} — metadata style (tracked uppercase, secondary gray)\n"
            "  1px hairline rule above, then 24px gap, bottom-anchored\n"
            if footer_left and footer_right
            else "FOOTER ROW: (footer text not configured — omit)\n"
        )
        category_block = (
            f"CATEGORY LABEL (EXACT — tracked uppercase, category role size): {category}\n"
            if category
            else "CATEGORY LABEL: none\n"
        )
        copy_block = (
            "HEADLINE: The measure of a well-set column\n"
            "SUBHEAD: White space is the rhythm between ideas\n"
            "BODY: A grid sets order and a measure sets pace.\n"
            "TAGLINE: No. 12 — On grids"
        )
        fonts_link = build_google_fonts_link(tokens, di)
        return (
            f"{brand_prefix}{campaign_block}"
            f"PLATFORM: {_SAMPLE_PLATFORM}\n"
            f"CANVAS: {fmt.width}px × {fmt.height}px\n"
            f"VISUAL DIRECTION: {brief.get('visual_direction', 'clean editorial')}\n"
            f"TONE: {brief.get('tone', 'professional')}\n\n"
            f"{archetype_block}\n\n"
            f"{_ground_css_vars(ground)}\n\n"
            f"{category_block}\n{footer_block}\n"
            f"COPY TO USE:\n{copy_block}\n\n"
            f"GOOGLE FONTS LINK (include in <head>):\n{fonts_link}\n\n"
            f"INSTRUCTIONS:\n- Canvas must be EXACTLY {fmt.width}px × {fmt.height}px\n"
            f"- Use ONLY the copy provided above — no additional text\n"
            f"- Do NOT invent random numbers, version strings, or fake identifiers\n"
        )

    if name == "verifier":
        return (
            f"TARGET PLATFORM: {_SAMPLE_PLATFORM} ({fmt.width}x{fmt.height}px)\n"
            f"EXPECTED GROUND: {brief.get('ground', 'white')}\n"
            f"{_ds_context(payload)}\n\n"
            "Audit this design image. Score it 0-100 and provide actionable critique.\n"
            "Return ONLY valid JSON: "
            '{"pass": bool, "score": int, "issues": [...], "critique": "..."}'
        )

    if name == "editor_chat":
        return (
            f"TARGET PLATFORM: {_SAMPLE_PLATFORM} ({fmt.width}x{fmt.height}px)\n"
            f"EXPECTED GROUND: {brief.get('ground', 'white')}\n"
            f"{_ds_context(payload)}\n\n"
            f"CURRENT HTML DOCUMENT (excerpt):\n<!DOCTYPE html><div class=\"headline\">…</div>\n"
            "USER REQUEST: (your message) — e.g. \"Tighten the headline\"\n"
            'Return ONLY JSON: {"reply": str, "changed": bool, "html": str|null}'
        )

    # Aux agents — representative inputs from their service builders.
    if name == "brand_vision":
        form = {
            "name": brand.get("name", "Sample Brand"),
            "tagline": brand.get("tagline", ""),
            "mission": brand.get("mission", ""),
            "industry": "Technology",
            "audience": "Design-minded builders",
            "style": "Swiss editorial",
            "handle": "@sample",
        }
        return (
            "Brand form:\n" + json.dumps(form, indent=2)
            + "\n\nA reference/moodboard image may be attached — extract palette, "
            "type direction, and mood. Return the brand analysis JSON."
        )

    if name == "brand_tokens":
        brief_payload = {"name": brand.get("name", "Sample Brand"), "style": "Swiss editorial"}
        return (
            f"BRAND BRIEF:\n{json.dumps(brief_payload, indent=2)}\n\n"
            "AVAILABLE FONTS (choose ONLY from these):\n"
            "  sans-serif: Inter, Roboto, Open Sans\n  serif: Source Serif 4, Georgia\n"
            "  display: Space Grotesk, Archivo\n  monospace: JetBrains Mono, IBM Plex Mono\n"
            "Return the token + token_roles + design-instruction overlay JSON."
        )

    if name == "brand_campaigns":
        brief_payload = {"name": brand.get("name", "Sample Brand"), "style": "Swiss editorial"}
        return (
            f"BRAND BRIEF:\n{json.dumps(brief_payload, indent=2)}\n\n"
            "Propose 3-5 campaign presets for this brand. Return the campaigns JSON."
        )

    if name == "template_vision":
        return (
            "Analyze this social media post mockup and produce the layout specification.\n"
            "Image mime: image/png\n"
            "Return ONLY valid JSON per the schema in the system prompt."
        )

    if name == "template_author":
        return (
            "A mockup has been analyzed into the following layout spec:\n"
            f"{{'platform_family': 'square', 'ground': 'white', "
            f"'sections': ['kicker', 'headline', 'subhead', 'footer']}}\n\n"
            f"Design system:\n{json.dumps({'name': brand.get('name', 'Sample Brand')}, indent=2)}\n"
            "Write the Jinja2 template HTML per the system prompt."
        )

    return f"(No representative user prompt for {name} — built from live inputs.)"


async def build_prompt_preview(name: str, design_system_id: str = "default") -> dict:
    """Return {system_prompt, user_prompt} for a representative sample post."""
    cfg = await get_agent_config(name)
    payload = await _load_payload(design_system_id)
    system_prompt = _resolve_system_prompt(name, cfg.system_prompt, payload)
    user_prompt = await _build_user_prompt(name, payload)
    return {
        "agent": name,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }
