"""Designer node — Marcus Chen — creates HTML layout per platform.

Takes the copy and strategic brief, produces a complete standalone HTML
document with CSS variables (var(--color-*)) for colors. Never receives
actual brand hex values — only CSS variable names.

The HTML document will be:
  1. Saved to the output directory
  2. Rendered to PNG by the Verifier for multimodal QC

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].copy: JSON string (PlatformCopy)
  - strategic_brief: dict
  - design_tokens: dict (CSS var → value, for CSS injection reference only)
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
    format_design_instruction_block,
    load_design_instruction,
)
from app.services.formats import get_format_info
from app.services.llm import call_llm

log = logging.getLogger(__name__)

# CSS variable declarations injected into every Designer prompt
# (variable NAMES only — not values — so the LLM knows what to use)
CSS_VARS_REFERENCE = """
Available CSS variables (use ONLY these for colors — never hardcode hex):
  var(--color-bg)            — primary background
  var(--color-bg-secondary)  — secondary background
  var(--color-text)          — primary text
  var(--color-text-secondary)— secondary/muted text
  var(--color-primary)       — accent/brand primary
  var(--color-secondary)     — secondary accent
  var(--color-accent)        — highlight color
  var(--color-border)        — dividers/borders
  var(--font-sans)           — sans-serif font stack
  var(--font-serif)          — serif font stack
  var(--font-mono)           — monospace font stack
  var(--radius-sm)           — small border radius (4px)
  var(--radius-md)           — medium border radius (8px)
""".strip()


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


def _build_google_fonts_link(copy_data: dict) -> str:
    """Build a Google Fonts <link> tag for the fonts needed."""
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?'
        "family=Inter:wght@400;500;600;700;800;900&"
        "family=Instrument+Serif&"
        "family=JetBrains+Mono:wght@400;500&"
        'display=swap" rel="stylesheet">'
    )


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

    # Build template context: CSS vars + design instruction
    template_context = f"{CSS_VARS_REFERENCE}\n\n{di_block}"
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
    badge = copy_data.get("badge")

    brand_info = state.get("brand_info", {})
    campaign = state.get("campaign", {})
    images_list = state.get("images", [])
    brand_prefix = f"BRAND: {brand_info.get('name', '')}\n" if brand_info.get("name") else ""

    campaign_block = ""
    if campaign:
        label = campaign.get("label", "")
        visuals = campaign.get("visual_style", "")
        bg = campaign.get("background", "")
        illustrations = campaign.get("illustrations", "")
        campaign_block = (
            f"CAMPAIGN: {label}\n"
            f"VISUAL STYLE: {visuals}\n"
            f"BACKGROUND: {bg}\n"
            f"ILLUSTRATIONS: {illustrations}\n"
        )

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
        "  placement=\"background\" → full-bleed background with gradient/text overlay\n"
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
    if badge:
        copy_block += f"\nBADGE: {badge}"

    fonts_link = _build_google_fonts_link(copy_data)

    user_prompt = (
        f"{brand_prefix}{campaign_block}"
        f"PLATFORM: {fmt_id}\n"
        f"CANVAS: {fmt.width}px × {fmt.height}px\n"
        f"VISUAL STYLE: {brief.get('visual_direction', 'editorial')}\n"
        f"TONE: {brief.get('tone', 'professional')}\n\n"
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
        fallback_html = _build_fallback_html(fmt, copy_data)
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


def _build_fallback_html(fmt: object, copy_data: dict) -> str:
    """Build a minimal fallback HTML when the LLM fails."""
    headline = copy_data.get("headline", "Untitled")
    subhead = copy_data.get("subhead", "")
    body = copy_data.get("body", "")
    tagline = copy_data.get("tagline", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root {{
  --color-bg: #0f172a;
  --color-bg-secondary: #1e293b;
  --color-text: #ffffff;
  --color-text-secondary: #94a3b8;
  --color-primary: #667eea;
  --color-secondary: #764ba2;
  --color-accent: #6366f1;
  --color-border: #334155;
  --font-sans: 'Inter', sans-serif;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  width: {fmt.width}px;
  height: {fmt.height}px;
  overflow: hidden;
  margin: 0;
  background: var(--color-bg);
  font-family: var(--font-sans);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px;
  text-align: center;
}}
.headline {{
  font-size: 48px;
  font-weight: 800;
  color: var(--color-text);
  line-height: 1.1;
  margin-bottom: 24px;
}}
.subhead {{
  font-size: 24px;
  font-weight: 500;
  color: var(--color-primary);
  margin-bottom: 24px;
}}
.body-text {{
  font-size: 18px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 32px;
  max-width: 80%;
}}
.tagline {{
  font-size: 16px;
  color: var(--color-accent);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}}
.accent-bar {{
  width: 60px;
  height: 4px;
  background: var(--color-primary);
  margin: 24px auto;
}}
</style>
</head>
<body>
  <div class="headline">{headline}</div>
  <div class="accent-bar"></div>
  <div class="subhead">{subhead}</div>
  <div class="body-text">{body}</div>
  <div class="tagline">{tagline}</div>
</body>
</html>"""
