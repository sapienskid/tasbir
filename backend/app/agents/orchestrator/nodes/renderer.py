"""Renderer node — persists HTML output with KaTeX, images, and tokens.

The designer generates platform-optimized HTML. This node:
  1. Injects design tokens as CSS :root variables
  2. Injects KaTeX CDN + auto-render for math rendering
  3. Embeds base64 images if provided
  4. Saves to data/output/{task_id}/{fmt_id}.html
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.services.design_instruction import (
    build_google_fonts_link,
    inject_fonts_into_html,
    load_design_instruction,
    substitute_image_keys,
)
from app.services.sanitizer import sanitize_html
from app.services.tokens import (
    DEFAULT_TOKEN_VALUES,
    inject_katex_into_html,
    inject_tokens_into_html,
)

log = logging.getLogger(__name__)


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
    images = state.get("images", [])

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

    # 1b. Guarantee the Google Fonts link (system-controlled, not left to LLM)
    di_config = load_design_instruction(
        Path(get_settings().design_system_dir) / "design-instruction.yaml"
    )
    html = inject_fonts_into_html(html, build_google_fonts_link(design_tokens, di_config))

    # 2. Inject KaTeX for math rendering
    html = inject_katex_into_html(html)

    # 3. Embed images as base64 via data-image-key markers
    html = substitute_image_keys(html, images)

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
