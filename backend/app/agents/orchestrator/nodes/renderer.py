"""Renderer node — persists HTML output with KaTeX, images, and tokens.

The designer generates platform-optimized HTML. This node:
  1. Injects design tokens as CSS :root variables
  2. Injects KaTeX CDN + auto-render for math rendering
  3. Embeds base64 images if provided
  4. Saves to data/output/{task_id}/{fmt_id}.html
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.services.design_instruction import (
    build_google_fonts_link,
    inject_fonts_into_html,
    substitute_image_keys,
    substitute_logo,
)
from app.services.sanitizer import sanitize_html
from app.services.tokens import (
    DEFAULT_TOKEN_VALUES,
    inject_katex_into_html,
    inject_tokens_into_html,
)

log = logging.getLogger(__name__)


def _inject_slide_counter(html: str, state: GenerationState, fmt_id: str) -> str:
    """Add a ``i/N`` slide counter to carousel slides whose template lacks one.

    Templates may opt in to their own counter with ``data-slot="counter"``
    (e.g. ``square-slide``); for every other carousel slide a small metadata
    counter is injected top-right. ``position: fixed`` against the fixed-size
    canvas never overflows, and only ``var(--color-*)`` tokens are used so the
    deterministic checks stay green.
    """
    from app.services.formats import parse_carousel_slide

    parsed = parse_carousel_slide(fmt_id)
    if not parsed:
        return html
    if 'data-slot="counter"' in html:
        return html
    index = parsed[1]
    total = int((state.get("slide_context") or {}).get(fmt_id, {}).get("total", 0))
    if total < 1:
        return html

    style = (
        "<style>.tasbir-slide-counter{position:fixed;top:48px;right:48px;z-index:50;"
        "font-family:var(--font-sans);font-size:20px;font-weight:500;"
        "letter-spacing:0.08em;color:var(--color-text-secondary);"
        "background:var(--color-bg);padding:2px 8px}"
        'body[data-ground="black"] .tasbir-slide-counter{'
        "color:var(--color-text-secondary);background:var(--color-bg-inverted)}</style>"
    )
    counter = f'<span class="tasbir-slide-counter" data-slot="counter">{index}/{total}</span>'
    if "<body" in html:
        return re.sub(
            r"<body\b[^>]*>",
            lambda m: m.group(0) + style + counter,
            html,
            count=1,
        )
    return style + counter + html


async def renderer_node_single(state: GenerationState) -> dict:
    """Persist the designer's HTML with KaTeX, images, and tokens."""
    from app.config import get_settings

    settings = get_settings()
    fmt_id = state.get("_processing_format_id", "")
    task_id = state.get("_task_id", "default")

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    html = task.get("html", "")
    design_tokens = state.get("design_tokens", DEFAULT_TOKEN_VALUES)
    # Per-slide user images (auto-distributed in the graph); fall back to the
    # post-wide list for single formats.
    slide_images = (state.get("_slide_images") or {}).get(fmt_id)
    images = slide_images if slide_images is not None else state.get("images", [])
    logo = state.get("logo", "")

    if not html:
        log.warning("[renderer] No HTML for %s, skipping", fmt_id)
        return {
            "format_tasks": {
                fmt_id: {**task, "status": "error", "error": "No HTML to convert"}
            }
        }

    # Defense in depth: re-sanitize before anything is injected or persisted.
    html = sanitize_html(html, mode="strict")

    # 1. Inject CSS tokens
    html = inject_tokens_into_html(html, design_tokens)

    # 1b. Guarantee the Google Fonts link (system-controlled, not left to LLM).
    #     Empty-state (tests / edge) falls back to the DB default design system.
    di_config = state.get("design_instruction") or {}
    if not di_config:
        from app.services.design_systems import default_design_system_payload

        payload = await default_design_system_payload()
        di_config = payload.get("design_instruction") or {}
        design_tokens = payload.get("design_tokens") or design_tokens
    html = inject_fonts_into_html(html, build_google_fonts_link(design_tokens, di_config))

    # 2. Inject KaTeX for math rendering
    html = inject_katex_into_html(html)

    # 3. Embed images as base64 via data-image-key markers
    html = substitute_image_keys(html, images)

    # 3b. Embed the design system logo via data-logo markers
    html = substitute_logo(html, logo)

    # 3c. Universal carousel slide counter — every slide shows i/N. Templates
    #     that already render a counter (data-slot="counter") are left alone.
    html = _inject_slide_counter(html, state, fmt_id)

    output_dir = Path(settings.output_dir) / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{fmt_id}.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("[renderer] Saved HTML %s (%d bytes, %d images)",
             html_path, len(html), len(images))

    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "html_path": str(html_path),
                "status": "html_saved",
            }
        },
        "html_path": str(html_path),
    }
