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
from html import escape

from app.agents.orchestrator.state import GenerationState
from app.services.agents import get_agent_config
from app.services.design_instruction import (
    build_google_fonts_link,
    format_design_instruction_block,
    format_format_layout_block,
)
from app.services.formats import get_format_info
from app.services.llm import call_llm
from app.services.sanitizer import sanitize_html
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


def _parse_copy(copy_json: str, fallback_headline: str = "") -> dict:
    """Parse the copy JSON string from FormatTask.copy.

    When copy is missing/empty (e.g. a failed copywriter step), falls back to
    the post title so the design never renders a bare "Untitled".
    """
    fallback = fallback_headline.strip() or "Untitled"
    if not copy_json:
        return {
            "headline": fallback,
            "subhead": "",
            "body": "",
            "tagline": "",
            "badge": None,
        }
    try:
        data = json.loads(copy_json)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    stripped = copy_json.strip().strip("'\"")
    return {
        "headline": fallback,
        "subhead": "",
        "body": stripped[:300] if stripped else "No body copy available",
        "tagline": "",
        "badge": None,
    }


def _ground_css_vars(
    ground: str,
    tokens: dict | None = None,
    roles: dict | None = None,
) -> str:
    """Map the resolved ground to the design system's token variables.

    Resolved through ``resolve_ground_vars`` (the token service) so no token
    names are hardcoded here — a custom design system's variables win.
    """
    from app.services.tokens import resolve_ground_vars

    v = resolve_ground_vars(ground, tokens or {}, roles or {})
    return (
        f"GROUND VARIABLES ({ground}-ground):\n"
        f"  background → var({v['background']})\n"
        f"  primary text → var({v['text']})\n"
        f"  hairline rules → var({v['border']})\n"
        f"  secondary text → var({v['secondary']}) (same on both grounds)"
    )


async def _designer_media_director(state: GenerationState, fmt) -> None:
    """Apply the media plan to an LLM-designed post (per-slide, cached).

    The media plan (one LLM session per post, built in the graph) decides this
    slide's media. A chosen photo is downloaded and appended to the slide's
    image list; a chosen illustration is composed offline and stored in
    ``state["_designer_figure"]`` for marker injection after generation.
    """
    if state.get("_designer_media_applied"):
        return

    fmt_id = state.get("_processing_format_id", "")
    plan = (state.get("media_plan") or {}).get(fmt_id) or {}
    kind = plan.get("kind") or "none"

    # User media already present for this slide (auto-distributed) — skip.
    slide_images = (state.get("_slide_images") or {}).get(fmt_id)
    if slide_images is not None and slide_images:
        state["_designer_media_applied"] = True
        return
    if state.get("images") and kind != "illustration":
        return

    title = state.get("title", "")
    fmt_id = state.get("_processing_format_id", "")
    category = state.get("category", "")
    ground = state.get("ground", "white")
    orientation = (
        "landscape" if fmt.width > fmt.height
        else ("portrait" if fmt.height > fmt.width else "square")
    )

    state["_designer_media_applied"] = True

    if kind == "illustration":
        from app.agents.orchestrator.post_cache import post_cached
        from app.services.media_plan import execute_slide_illustration

        async def ill_loader() -> str:
            return execute_slide_illustration(
                plan,
                seed=f"{title or ''}|illustration|{fmt_id}",
                ground=ground,
                category=category,
                api_style=state.get("illustration_style") or "",
            )

        fig = await post_cached(state.get("_task_id", ""), f"illustration:{fmt_id}", ill_loader)
        if fig:
            state["_designer_figure"] = fig
        return

    if kind == "chart":
        from app.services.media_plan import execute_slide_chart

        fig = execute_slide_chart(plan, ground)
        if fig:
            state["_designer_figure"] = fig
        return

    if kind == "photo":
        from app.agents.orchestrator.post_cache import post_cached
        from app.services.media_plan import execute_slide_photo

        async def photo_loader() -> dict | None:
            return await execute_slide_photo(
                plan, orientation, seed=f"{title or ''}|photo|{fmt_id}"
            )

        media = await post_cached(state.get("_task_id", ""), f"photo:{fmt_id}", photo_loader)
        if not media:
            return
        image = media["image"]
        candidate = media.get("candidate") or {}
        images = list(state.get("images") or [])
        images.append({
            **image,
            "description": candidate.get("attribution", ""),
            "placement": "auto",
        })
        state["images"] = images
        credits = list(state.get("media_credits") or [])
        credits.append({
            "kind": "photo",
            "provider": candidate.get("provider"),
            "photographer": candidate.get("photographer"),
            "license": candidate.get("license"),
            "credit": candidate.get("attribution", ""),
        })
        state["media_credits"] = credits


async def designer_node_single(state: GenerationState) -> dict:
    """Create HTML layout for a single platform."""
    prompt_cfg = await get_agent_config("designer")
    fmt_id = state.get("_processing_format_id", "")
    fmt = get_format_info(fmt_id)

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    copy_data = _parse_copy(task.get("copy", ""), state.get("title", ""))
    brief = state.get("strategic_brief", {})

    verification = state.get("verification", {})
    fmt_verification = verification.get(fmt_id, {})
    critique = fmt_verification.get("critique", "")
    retry_count = state.get("retry_count", {}).get(fmt_id, 0)

    # Load design-instruction — per-design-system (state); empty-state (tests /
    # edge) falls back to the DB default design system.
    di_config = state.get("design_instruction") or {}
    design_tokens = state.get("design_tokens", {})
    token_roles = state.get("token_roles", {})
    if not di_config:
        from app.services.design_systems import default_design_system_payload

        payload = await default_design_system_payload()
        di_config = payload.get("design_instruction") or {}
        design_tokens = payload.get("design_tokens") or design_tokens
        token_roles = payload.get("token_roles") or token_roles
    di_block = format_design_instruction_block(di_config)
    layout_block = format_format_layout_block(di_config, fmt_id, fmt.width, fmt.height)

    # Design tokens (variable names + semantic roles only — never values)
    css_var_reference = build_css_var_reference(design_tokens, token_roles or None)

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

    brand_info = state.get("brand_info", {})
    campaign = state.get("campaign", {})
    # Auto media (photo/illustration) may add to state["images"] before the
    # image block is assembled below.
    await _designer_media_director(state, fmt)
    images_list = list(state.get("images", []))
    # Per-slide user images (auto-distributed in the graph) take precedence for
    # this slide; single formats fall back to the post-wide list.
    fmt_id = state.get("_processing_format_id", "")
    slide_images = (state.get("_slide_images") or {}).get(fmt_id)
    if slide_images is not None:
        images_list = list(slide_images) or images_list

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

    ground_block = _ground_css_vars(ground, design_tokens, token_roles)

    # Carousel slide context — this frame's position in a swipeable sequence.
    slide_block = ""
    slide_ctx = (state.get("slide_context") or {}).get(fmt_id)
    if slide_ctx:
        i = slide_ctx.get("index", 1)
        n = slide_ctx.get("total", 1)
        cover_note = " This is the COVER — make the headline the strongest hook." if i == 1 else ""
        slide_block = (
            f"CAROUSEL SLIDE {i} of {n} — this is ONE frame of a swipeable "
            f"multi-slide post ({fmt.width}x{fmt.height}).{cover_note} Make this frame self-contained "
            f"(readable on its own) while continuing the sequence: give it a clear "
            f"mini-headline in the display voice, keep the body short, and NEVER let "
            f"text clip at the canvas edge. Include a small '{i}/{n}' counter in "
            f"metadata style at a bottom corner.\n\n"
        )

    category_block = (
        f"CATEGORY LABEL (EXACT — tracked uppercase, category role size): {category}\n"
        if category
        else "CATEGORY LABEL: none\n"
    )

    footer_block = "FOOTER (handle only):\n"
    if footer_right:
        footer_block += (
            f"  {footer_right} — metadata style (var(--font-sans), tracked uppercase, "
            "secondary gray), small and quiet at the very bottom. It must fit fully "
            "inside the canvas — never overflow the right or bottom edge. "
            "Never the brand name, never a wordmark.\n"
        )
    else:
        footer_block += "  (footer handle not configured — omit)\n"

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

    # Brand logo marker (injected at render) — only when the DS has a logo.
    logo_block = ""
    if state.get("logo"):
        logo_block = (
            "\nBRAND LOGO (place exactly once):\n"
            "  Add <div class=\"logo\" data-logo></div> where the brand logo belongs "
            "(usually a top corner or the footer). The system injects the actual "
            "image at render time — do NOT put a real <img> here.\n"
        )

    # Prepared illustration (from the media director) — injected after
    # generation via a placeholder marker.
    figure_block = ""
    if state.get("_designer_figure"):
        figure_block = (
            "\nPREPARED ILLUSTRATION:\n"
            "  The system has prepared an illustration for this post. "
            "Place this marker exactly once where it fits best (a balanced corner "
            "or side, keeping text dominant):\n"
            "  <div data-illustration></div>\n"
            "  The actual artwork is injected automatically — do NOT draw your own "
            "SVG/illustration.\n"
        )

    copy_block = f"""HEADLINE: {headline}
SUBHEAD: {subhead}
BODY: {body}"""
    extra = copy_data.get("extra") or {}
    if isinstance(extra, dict) and extra:
        extra_block = "\n".join(
            f"{k.upper()}: {v}" for k, v in extra.items() if v
        )
        if extra_block:
            copy_block += f"\n{extra_block}"

    fonts_link = build_google_fonts_link(design_tokens, di_config)

    user_prompt = (
        f"{slide_block}"
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
        f"{logo_block}\n"
        f"{figure_block}\n"
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

        # Sanitize LLM output before it can reach the renderer — strips any
        # script/frame/event-handler the model was steered into emitting.
        html = sanitize_html(html, mode="strict")

        # Inject the prepared illustration where the designer placed its marker.
        figure = state.get("_designer_figure")
        if figure:
            marker_re = re.compile(
                r'<div[^>]*data-illustration[^>]*></div>|<span[^>]*data-illustration[^>]*></span>',
                re.IGNORECASE,
            )
            html, n = marker_re.subn(figure, html, count=1)
            if n:
                log.info("[designer] injected illustration into %s", fmt_id)

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
            design_tokens=design_tokens,
            token_roles=token_roles,
            di_config=di_config,
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
    design_tokens: dict | None = None,
    token_roles: dict | None = None,
    di_config: dict | None = None,
) -> str:
    """Build a minimal Swiss-style fallback HTML when the LLM fails.

    Fully design-system-driven — the Google Fonts link, type sizes, margins,
    and ground variables all come from the active design system (tokens +
    design-instruction), never from literals. Uses only var(--color-*) /
    var(--font-*) references so the pipeline injects real values at render.
    """
    from app.services.design_instruction import scaled_type_sizes
    from app.services.tokens import resolve_ground_vars

    tokens = design_tokens or {}
    di = di_config or {}
    v = resolve_ground_vars(ground, tokens, token_roles or {})
    scaled = scaled_type_sizes(di, fmt.width)
    ts_category = scaled.get("category", {}).get("size", 22)
    ts_headline = scaled.get("headline", {}).get("size", 76)
    ts_subhead = scaled.get("subhead", {}).get("size", 36)
    ts_body = scaled.get("body", {}).get("size", 28)
    ts_metadata = scaled.get("metadata", {}).get("size", 20)
    spacing = di.get("spacing", {})
    margin = spacing.get("margin", 64)
    gap = spacing.get("gap_headline_body", 32)
    is_story = fmt.width == 1080 and fmt.height == 1920
    pad_vertical = spacing.get("margin_story_vertical", 160) if is_story else margin
    measure = (
        scaled.get("subhead", {}).get("measure_px")
        or scaled.get("body", {}).get("measure_px")
        or 600
    )
    fonts_link = build_google_fonts_link(tokens, di)

    headline = escape(copy_data.get("headline", "Untitled"))
    subhead = escape(copy_data.get("subhead", ""))
    body = escape(copy_data.get("body", ""))
    category = escape(category)
    footer_left = escape(footer_left)
    footer_right = escape(footer_right)

    body_block = f'<div class="body-text">{body}</div>' if body else ""
    subhead_block = f'<div class="subhead">{subhead}</div>' if subhead else ""
    category_block = f'<div class="kicker">{category}</div>' if category else ""
    footer_block = (
        f'<div class="footer"><span class="handle">{footer_right}</span></div>'
        if footer_right
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{fonts_link}
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  width: {fmt.width}px;
  height: {fmt.height}px;
  overflow: hidden;
  margin: 0;
  background: var({v['background']});
  color: var({v['text']});
  font-family: var(--font-sans);
  padding: {pad_vertical}px {margin}px;
  display: flex;
  flex-direction: column;
}}
.kicker {{
  font-size: {ts_category}px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var({v['secondary']});
  margin-bottom: {spacing.get('gap_category_label', 24)}px;
}}
.headline {{
  font-family: var(--font-display);
  font-size: {ts_headline}px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.0;
  margin-bottom: {gap}px;
}}
.subhead {{
  font-family: var(--font-serif);
  font-size: {ts_subhead}px;
  font-weight: 400;
  line-height: 1.3;
  margin-bottom: {gap}px;
  max-width: {measure}px;
}}
.body-text {{
  font-family: var(--font-serif);
  font-size: {ts_body}px;
  font-weight: 400;
  line-height: 1.4;
  margin-bottom: {gap}px;
  max-width: {measure}px;
}}
.spacer {{ flex: 1; }}
.footer {{
  display: flex;
  justify-content: flex-start;
  align-items: baseline;
  padding-top: {spacing.get('gap_footer_rule', 24)}px;
}}
.handle {{
  font-size: {ts_metadata}px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var({v['secondary']});
}}
</style>
</head>
<body>
  {category_block}
  <div class="headline">{headline}</div>
  {subhead_block}
  {body_block}
  <div class="spacer"></div>
  {footer_block}
</body>
</html>"""
