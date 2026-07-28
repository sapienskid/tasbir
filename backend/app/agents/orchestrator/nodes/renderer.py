"""Renderer node — persists HTML output to disk.

The designer generates platform-optimized HTML in the previous step.
This node ensures the HTML is saved to the output directory for
downstream consumption. The verifier handles PNG rendering.

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].html: str
  - design_tokens: dict (CSS var → value)

Output (to GenerationState):
  - format_tasks[fmt_id].html_path: str
  - format_tasks[fmt_id].status: "html_saved"
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.services.formats import get_format_info
from app.services.tokens import DEFAULT_TOKEN_VALUES, inject_tokens_into_html

log = logging.getLogger(__name__)


async def renderer_node_single(state: GenerationState) -> dict:
    """Persist the designer's HTML to disk."""
    from app.config import get_settings

    settings = get_settings()
    fmt_id = state.get("_processing_format_id", "")
    task_id = state.get("_task_id", "default")
    fmt = get_format_info(fmt_id)

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    html = task.get("html", "")
    design_tokens = state.get("design_tokens", DEFAULT_TOKEN_VALUES)

    if not html:
        log.warning("[renderer] No HTML for %s, skipping", fmt_id)
        return {
            "format_tasks": {
                fmt_id: {**task, "status": "error", "error": "No HTML to convert"}
            }
        }

    html_with_tokens = inject_tokens_into_html(html, design_tokens)

    output_dir = Path(settings.output_dir) / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{fmt_id}.html"
    html_path.write_text(html_with_tokens, encoding="utf-8")
    log.info("[renderer] Saved HTML %s (%d bytes)", html_path, len(html_with_tokens))

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
