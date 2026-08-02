"""Template renderer node — fills a human-authored Jinja2 template with copy.

Runs before the LLM designer. If a matching template exists it produces the
HTML (status ``html_ready`` + the chosen ``template_id``). If nothing matches
it returns no update, and the per-format chain falls back to the designer.
"""

from __future__ import annotations

import json
import logging

from app.agents.orchestrator.state import GenerationState
from app.services.formats import get_format_info
from app.services.templates import (
    build_template_context,
    format_family,
    get_recent_template_ids,
    push_recent_template_id,
    render_template_file,
    select_template,
)

log = logging.getLogger(__name__)


def _parse_copy(copy_json: str) -> dict:
    if not copy_json:
        return {}
    try:
        data = json.loads(copy_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def template_node_single(state: GenerationState) -> dict:
    """Fill a matching template with the format's copy; {} if no template fits."""
    fmt_id = state.get("_processing_format_id", "")
    if not fmt_id:
        return {}

    fmt = get_format_info(fmt_id)
    family = format_family(fmt_id)
    ground = state.get("ground", "white")
    category = state.get("category", "")
    brief = state.get("strategic_brief", {})
    hint = str(brief.get("template_hint", "") or "")
    seed = f"{state.get('title', '')}|{fmt_id}"

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    copy = _parse_copy(task.get("copy", ""))
    if not copy.get("headline"):
        log.info("[template] No copy for %s — skipping", fmt_id)
        return {}

    exclude = await get_recent_template_ids()
    selection = select_template(family, ground, category, hint, seed, exclude)
    if selection is None:
        log.info("[template] No template for %s (%s / %s)", fmt_id, family, ground)
        return {}

    tid, entry = selection
    try:
        context = build_template_context(
            copy,
            category,
            ground,
            state.get("footer", {}),
            fmt.width,
            fmt.height,
            bool(state.get("images", [])),
            seed=seed,
            family=family,
        )
        html = render_template_file(entry["file"], context)
    except Exception as e:
        log.warning("[template] Render failed for %s (%s): %s", fmt_id, tid, e)
        return {}

    await push_recent_template_id(tid)
    log.info("[template] Filled %s for %s (%s×%s)", tid, fmt_id, fmt.width, fmt.height)
    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "html": html,
                "status": "html_ready",
                "template_id": tid,
            }
        }
    }
