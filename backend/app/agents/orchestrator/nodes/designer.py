"""Designer node — Marcus Chen — creates HTML layout per platform.

Takes the copy and strategic brief, produces a complete standalone HTML
document with CSS variables (var(--color-*)) for colors. Never receives
actual brand hex values — only CSS variable names and their semantic roles.

The HTML document will be:
  1. Saved to the output directory
  2. Rendered to PNG by the Verifier for multimodal QC

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].copy: JSON string (PlatformCopy)
  - strategic_brief: dict
  - design_tokens: dict (CSS var → value, for CSS injection reference only)
  - design-instruction.yaml (style, type scale, spacing, formats, do/don't)
  - category, ground, footer (resolved upstream)
  - verification[fmt_id].critique: str (if this is a retry)

Output (to GenerationState):
  - format_tasks[fmt_id].html: str (complete HTML document)
  - format_tasks[fmt_id].status: "html_ready"
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.agents.prompts.registry import load_prompt
from app.services.design_instruction import (
    build_google_fonts_link,
    format_design_instruction_block,
    format_format_layout_block,
    load_design_instruction,
)
from app.services.formats import get_format_info
from app.services.llm import call_llm
from app.services.tokens import build_css_var_reference

log = logging.getLogger(__name__)


def _clean_html(raw: str) -> str:
    """Strip markdown fences and extract the HTML document."""
    raw = raw.strip()

    # Remove ```html ... ``` fences
    raw = re.sub(r"^```(?:html)?\s*\n?", "", raw, flags=re.MULTILINE | re.IGNORECASE)
    raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE)

    # Ensure it starts with <!DOCTYPE or <html
    if "<!DOCTYPE" in raw.upper():
        idx = raw.upper().index("<!DOCTYPE")
        return raw[idx:].strip()
    if "<html" in raw.lower():
        idx = raw.lower().index("<html")
        return raw[idx:].strip()

    return raw.strip()


def _parse_copy(copy_json: str) -> dict:
    """Parse the copy JSON string from FormatTask.copy."""
    if not copy_json:
        return {
            "headline": "Untitled",
            "subhead": "",
            "body": "",
            "tagline": "",
            "badge": None,
        }
    try:
        return json.loads(copy_json)
    except Exception:
        stripped = copy_json.strip().strip("'\"")
        return {
            "headline": "Untitled",
            "subhead": "",
            "body": stripped[:300] if stripped else "No body copy available",
            "tagline": "",
            "badge": None,
        }


def _ground_css_vars(ground: str) -> str:
    """Map the resolved ground to the correct token variables (no hex)."""
    if ground == "black":
        return (
            "GROUND VARIABLES (black-ground):\n"
            "  background → var(--color-bg-inverted)\n"
            "  primary text → var(--color-text-inverted)\n"
            "  hairline rules → var(--color-border-inverted)\n"
            "  secondary text → var(--color-text-secondary) (same on both grounds)"
        )
    return (
        "GROUND VARIABLES (white-ground):\n"
        "  background → var(--color-bg)\n"
        "  primary text → var(--color-text)\n"
        "  hairline rules → var(--color-border)\n"
        "  secondary text → var(--color-text-secondary) (same on both grounds)"
    )


async def designer_node_single(state: GenerationState) -> dict:
    """Create HTML layout for a single platform."""
    from app.config import get_settings

    prompt_cfg = load_prompt("designer")
    fmt_id = state.get("_processing_format_id", "")
    fmt = get_format_info(fmt_id)

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    copy_data = _parse_copy(task.get("copy", ""))
    brief = state.get("strategic_brief", {})

    verification = state.get("verification", {})
    fmt_verification = verification.get(fmt_id, {})
    critique = fmt_verification.get("critique", "")
    retry_count = state.get("retry_count", {}).get(fmt_id, 0)

    # Load design-instruction YAML
    settings = get_settings()
    di_path = Path(settings.design_system_dir) / "design-instruction.yaml"
    di_config = load_design_instruction(di_path)
    di_block = format_design_instruction_block(di_config)
    layout_block = format_format_layout_block(di_config, fmt_id, fmt.width, fmt.height)

    # Design tokens (variable names + semantic roles only — never values)
    design_tokens = state.get("design_tokens", {})
    css_var_reference = build_css_var_reference(design_tokens)

    # Layout archetype — deterministic per post so designs vary across runs
    from app.services.design_instruction import (
        format_layout_archetype_block,
        pick_layout_archetype,
    )
    seed = f"{state.get('title', '')}|{fmt_id}|{state.get('category', '')}|{retry_count}"
    archetype_key, archetype_desc = pick_layout_archetype(di_config, seed)
    archetype_block = format_layout_archetype_block(archetype_key, archetype_desc)

    # Build template context: CSS vars + design instruction + format layout
    template_context = f"{css_var_reference}\n\n{di_block}\n\n{layout_block}"
    if retry_count > 0 and critique:
        template_context += f"\n\nVERIFIER CRITIQUE (PREVIOUS ATTEMPT):\n{critique}\nFix ALL issues listed above."

    system_prompt = prompt_cfg.system_prompt.replace("{TEMPLATE_CONTEXT}", template_context)
    system_prompt = system_prompt.replace("{WIDTH}", str(fmt.width))
    system_prompt = system_prompt.replace("{HEIGHT}", str(fmt.height))

    # Parse copy
    headline = copy_data.get("headline", "")
    subhead = copy_data.get("subhead", "")
    body = copy_data.get("body", "")
    tagline = copy_data.get("tagline", "")

    brand_info = state.get("brand_info", {})
    campaign = state.get("campaign", {})
    images_list = state.get("images", [])

    # Resolved design decisions (deterministic — set upstream, not by the LLM)
    ground = state.get("ground", "white")
    category = state.get("category", "")
    footer = state.get("footer", {})
    footer_left = footer.get("left", "")
    footer_right = footer.get("right", "")

    brand_prefix = f"BRAND: {brand_info.get('name', '')}\n" if brand_info.get("name") else ""

    campaign_block = ""
    if campaign:
        label = campaign.get("label", "")
        tone = campaign.get("tone", "")
        language = campaign.get("language", "")
        campaign_block = (
            f"CAMPAIGN: {label}\n"
            f"TONE: {tone}\n"
            f"LANGUAGE: {language}\n"
        )

    ground_block = _ground_css_vars(ground)

    category_block = (
        f"CATEGORY LABEL (EXACT — tracked uppercase, category role size): {category}\n"
        if category
        else "CATEGORY LABEL: none\n"
    )

    footer_block = "FOOTER ROW (REQUIRED on every format):\n"
    if footer_left and footer_right:
        footer_block += (
            f"  Left (SIGNATURE WORDMARK): {footer_left} — display face "
            "(var(--font-display)), ~24px, weight 500, tight tracking, uppercase\n"
            f"  Right: {footer_right} — metadata style (Inter, tracked uppercase, secondary gray)\n"
            "  1px hairline rule above, then 24px gap, bottom-anchored\n"
        )
    else:
        footer_block += "  (footer text not configured — omit)\n"

    # Image metadata with data-image-key markers and placement
    images_block = ""
    if images_list:
        img_descs = []
        for idx, img in enumerate(images_list):
            alt = img.get("alt", "")
            desc = img.get("description", "")
            placement = img.get("placement", "auto")
            label = alt or desc or f"Image {idx}"
            img_descs.append(f"  data-image-key=\"{idx}\" | \"{label}\" | placement=\"{placement}\"")
        if img_descs:
            images_block = (
                "AVAILABLE IMAGES (place in layout using <img data-image-key=\"N\">):\n"
                + "\n".join(img_descs)
                + "\n"
            )

    # Image placement guidelines
    placement_guide = (
        "\nIMAGE PLACEMENT GUIDE:\n"
        "  placement=\"background\" → full-bleed background with text overlay\n"
        "  placement=\"full-width\" → full-width banner between content sections\n"
        "  placement=\"half-top\" → top half of canvas, content overlays or sits below\n"
        "  placement=\"half-bottom\" → bottom half of canvas\n"
        "  placement=\"half-left\" → left half, text on right\n"
        "  placement=\"half-right\" → right half, text on left\n"
        "  placement=\"center\" → centered content block\n"
        "  placement=\"auto\" → you decide what looks best\n"
        "  When placement is \"background\", use CSS to pin the image behind content.\n"
        "  Do NOT put images in a separate card/box — integrate them into the layout.\n"
    )

    copy_block = f"""HEADLINE: {headline}
SUBHEAD: {subhead}
BODY: {body}
TAGLINE: {tagline}"""

    fonts_link = build_google_fonts_link(design_tokens, di_config)

    user_prompt = (
        f"{brand_prefix}{campaign_block}"
        f"PLATFORM: {fmt_id}\n"
        f"CANVAS: {fmt.width}px × {fmt.height}px\n"
        f"VISUAL DIRECTION: {brief.get('visual_direction', 'clean editorial')}\n"
        f"TONE: {brief.get('tone', 'professional')}\n\n"
        f"{archetype_block}\n\n"
        f"{ground_block}\n\n"
        f"{category_block}\n"
        f"{footer_block}\n"
        f"COPY TO USE:\n{copy_block}\n\n"
        f"{images_block}\n"
        f"{placement_guide}\n"
        f"GOOGLE FONTS LINK (include in <head>):\n{fonts_link}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Canvas must be EXACTLY {fmt.width}px × {fmt.height}px\n"
        f"- Body style: width:{fmt.width}px;height:{fmt.height}px;overflow:hidden;margin:0\n"
        f"- Use ONLY the copy provided above — no additional text\n"
        f"- Do NOT invent random numbers, version strings, or fake identifiers\n"
    )

    if retry_count > 0:
        user_prompt += f"\n\nATTEMPT {retry_count + 1}: Fix the following issues:\n{critique}"

    log.info("[designer] Creating HTML for %s (attempt %d)", fmt_id, retry_count + 1)

    try:
        raw = await call_llm(
            agent_role="designer",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=prompt_cfg.temperature,
            max_tokens=prompt_cfg.max_tokens,
        )

        html = _clean_html(raw)

        # Validate it's a real HTML document
        if len(html) < 100 or "<body" not in html.lower():
            raise ValueError(f"Invalid HTML output: {html[:100]}")

        log.info("[designer] HTML ready for %s (%d bytes)", fmt_id, len(html))

        # Update retry count
        new_retry_count = dict(state.get("retry_count", {}))
        new_retry_count[fmt_id] = retry_count

        return {
            "format_tasks": {
                fmt_id: {
                    **task,
                    "html": html,
                    "status": "html_ready",
                }
            },
            "retry_count": new_retry_count,
        }

    except Exception as e:
        log.error("[designer] Failed for %s: %s", fmt_id, e, exc_info=True)

        # Generate emergency fallback HTML
        fallback_html = _build_fallback_html(
            fmt,
            copy_data,
            ground=ground,
            category=category,
            footer_left=footer_left,
            footer_right=footer_right,
        )
        return {
            "format_tasks": {
                fmt_id: {
                    **task,
                    "html": fallback_html,
                    "status": "html_ready",
                    "error": str(e),
                }
            },
        }


def _build_fallback_html(
    fmt: object,
    copy_data: dict,
    ground: str = "white",
    category: str = "",
    footer_left: str = "",
    footer_right: str = "",
) -> str:
    """Build a minimal Swiss-style fallback HTML when the LLM fails.

    Uses only var(--color-*) references — the pipeline injects the token
    block before rendering, so no hex values live in this code.
    """
    headline = copy_data.get("headline", "Untitled")
    subhead = copy_data.get("subhead", "")
    body = copy_data.get("body", "")
    tagline = copy_data.get("tagline", "")

    is_story = fmt.width == 1080 and fmt.height == 1920
    pad_vertical = 160 if is_story else 64
    body_block = f'<div class="body-text">{body}</div>' if body else ""
    subhead_block = f'<div class="subhead">{subhead}</div>' if subhead else ""
    tagline_block = f'<div class="tagline">{tagline}</div>' if tagline else ""
    category_block = f'<div class="kicker">{category}</div>' if category else ""
    footer_block = (
        f'<div class="rule"></div>\n'
        f'  <div class="footer"><span class="wordmark">{footer_left}</span>'
        f'<span class="handle">{footer_right}</span></div>'
        if footer_left and footer_right
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500&family=Space+Grotesk:wght@500;700&family=Source+Serif+4:wght@400&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  width: {fmt.width}px;
  height: {fmt.height}px;
  overflow: hidden;
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  padding: {pad_vertical}px 64px;
  display: flex;
  flex-direction: column;
}}
.kicker {{
  font-size: 22px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 24px;
}}
.headline {{
  font-family: var(--font-display);
  font-size: 76px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.0;
  margin-bottom: 32px;
}}
.subhead {{
  font-family: var(--font-serif);
  font-size: 36px;
  font-weight: 400;
  line-height: 1.3;
  margin-bottom: 32px;
  max-width: 600px;
}}
.body-text {{
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 400;
  line-height: 1.4;
  margin-bottom: 32px;
  max-width: 600px;
}}
.tagline {{
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
  margin-bottom: 32px;
}}
.spacer {{ flex: 1; }}
.rule {{ border-top: 1px solid var(--color-border); }}
.footer {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-top: 24px;
}}
.wordmark {{
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 500;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}}
.handle {{
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}}
</style>
</head>
<body>
  {category_block}
  <div class="headline">{headline}</div>
  {subhead_block}
  {body_block}
  {tagline_block}
  <div class="spacer"></div>
  {footer_block}
</body>
</html>"""
