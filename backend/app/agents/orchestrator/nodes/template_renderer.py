"""Template renderer node — fills a human-authored Jinja2 template with copy.

Runs before the LLM designer. If a matching template exists it produces the
HTML (status ``html_ready`` + the chosen ``template_id``). If nothing matches
it returns no update, and the per-format chain falls back to the designer.

Templates are DB-backed (v0.5) and scoped to the task's design system; the
list is loaded once into ``state.ds_templates`` before the graph runs. A
user-chosen ``state.template_id`` is honored for its own family + a supported
ground, falling back to normal selection for other families (auto-fallback).
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.agents.orchestrator.state import GenerationState
from app.services.formats import get_format_info
from app.services.templates import (
    build_template_context,
    format_family,
    get_recent_template_ids,
    push_recent_template_id,
    render_template_html,
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


_ILLUSTRATION_LOCK_KEY = "_illustration_lock"
_ILLUSTRATION_CACHE_KEY = "_post_illustration_svg"


async def _get_post_illustration(state: GenerationState, ground: str, seed: str) -> str:
    """Return the post's shared illustration (LLM tool once, then cached).

    Runs the illustration director (the generator as an LLM tool) a single
    time per post and caches the SVG in state so every format reuses it. If the
    tool fails, falls back to the deterministic render. An ``asyncio.Lock`` in
    state guards concurrent per-format branches from calling the LLM twice.
    """
    cached = state.get(_ILLUSTRATION_CACHE_KEY)
    if cached:
        return cached

    lock: asyncio.Lock = state.get(_ILLUSTRATION_LOCK_KEY)
    if lock is None:
        lock = asyncio.Lock()
        state[_ILLUSTRATION_LOCK_KEY] = lock
    async with lock:
        if state.get(_ILLUSTRATION_CACHE_KEY):
            return state[_ILLUSTRATION_CACHE_KEY]
        title = state.get("title", "")
        task = (state.get("format_tasks") or {}).get(state.get("_processing_format_id", ""), {})
        copy = _parse_copy(task.get("copy", ""))
        category = state.get("category", "")
        from app.services.illustration import illustration_via_tool

        svg = await illustration_via_tool(
            agent_role="designer",
            title=title,
            headline=copy.get("headline", ""),
            category=category,
            ground=ground,
            seed=f"{title or ''}|illustration",
        )
        state[_ILLUSTRATION_CACHE_KEY] = svg
        return svg


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

    templates = state.get("ds_templates") or []
    if not templates:
        return {}

    user_template_id = (state.get("template_id") or "").strip()

    # User override: honor the chosen template for its family + a supported
    # ground; otherwise fall back to deterministic selection.
    selected: tuple[str, dict] | None = None
    if user_template_id:
        entry = next(
            (t for t in templates if t.get("id") == user_template_id), None
        )
        if (
            entry
            and entry.get("family") == family
            and ground in entry.get("grounds", ["white", "black"])
        ):
            selected = (user_template_id, entry)

    if selected is None:
        exclude = await get_recent_template_ids()
        selected = select_template(family, ground, category, hint, seed, templates, exclude)

    if selected is None:
        log.info("[template] No template for %s (%s / %s)", fmt_id, family, ground)
        return {}

    tid, entry = selected
    html = entry.get("html", "")
    try:
        # Templates that opt in to the illustration slot get an LLM-directed
        # illustration (generator as a tool); everything else stays static.
        illustration: str | None = None
        if "{{ illustration" in html:
            illustration = await _get_post_illustration(state, ground, seed)
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
            logo=state.get("logo", ""),
            di_config=state.get("design_instruction") or {},
            illustration=illustration,
        )
        rendered = render_template_html(html, context)
    except Exception as e:
        log.warning("[template] Render failed for %s (%s): %s", fmt_id, tid, e)
        return {}

    await push_recent_template_id(tid)
    log.info("[template] Filled %s for %s (%s×%s)", tid, fmt_id, fmt.width, fmt.height)
    update: dict = {
        "format_tasks": {
            fmt_id: {
                **task,
                "html": rendered,
                "status": "html_ready",
                "template_id": tid,
            }
        }
    }
    if illustration is not None:
        update[_ILLUSTRATION_CACHE_KEY] = illustration
    return update
