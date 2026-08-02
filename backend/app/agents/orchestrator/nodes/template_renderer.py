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


_ILLUSTRATION_CACHE_KEY = "_post_illustration_svg"
_PHOTO_CACHE_KEY = "_auto_photo"
_PHOTO_CALLS_KEY = "_photo_calls"
_MEDIA_CREDITS_KEY = "media_credits"

_PHOTO_CAP = 3  # max find_photo LLM calls per post


async def _get_post_illustration(state: GenerationState, ground: str, seed: str) -> str:
    """Return the post's shared illustration (LLM tool once per post).

    Runs the illustration director (the unified ``illustrate`` tool — Anthropic
    procedural or vendored CC0 hand-drawn kits) once per post via the shared
    per-post cache, and memoizes it on this branch's state for retries. Falls
    back to the deterministic render if the tool fails.
    """
    cached = state.get(_ILLUSTRATION_CACHE_KEY)
    if cached:
        return cached

    from app.agents.orchestrator.post_cache import post_cached

    async def loader() -> str:
        title = state.get("title", "")
        task = (state.get("format_tasks") or {}).get(state.get("_processing_format_id", ""), {})
        copy = _parse_copy(task.get("copy", ""))
        category = state.get("category", "")
        from app.services.illustration import illustration_via_tool

        return await illustration_via_tool(
            agent_role="designer",
            title=title,
            headline=copy.get("headline", ""),
            category=category,
            ground=ground,
            seed=f"{title or ''}|illustration",
        )

    svg = await post_cached(state.get("_task_id", ""), "illustration", loader) or ""
    state[_ILLUSTRATION_CACHE_KEY] = svg
    return svg


def _orientation_for(fmt) -> str:
    if fmt.width > fmt.height:
        return "landscape"
    if fmt.height > fmt.width:
        return "portrait"
    return "square"


_PHOTO_DIRECTOR_SYSTEM = (
    "You are the image director for a strict monochrome editorial design "
    "system. Call the find_photo tool EXACTLY ONCE with a concrete query that "
    "matches the post's subject. Prefer calm, compositionally clean photos "
    "(minimal, typographic, architectural, texture). The photo will be shown "
    "in grayscale. Never refuse; always call the tool."
)


async def _get_post_photo(state: GenerationState, orientation: str) -> dict | None:
    """Return the post's shared auto-photo: {image, credit, candidate}.

    One LLM ``find_photo`` call per post (shared per-post cache); the result is
    memoized on this branch's state so every format reuses it. Honours a
    per-post cap on external photo searches.
    """
    cached = state.get(_PHOTO_CACHE_KEY)
    if cached:
        return cached

    from app.agents.orchestrator.post_cache import post_cached

    async def loader() -> dict | None:
        if (state.get(_PHOTO_CALLS_KEY) or 0) >= _PHOTO_CAP:
            log.info("[template] photo search cap reached — skipping auto photo")
            return None
        state[_PHOTO_CALLS_KEY] = (state.get(_PHOTO_CALLS_KEY) or 0) + 1

        title = state.get("title", "")
        task = (state.get("format_tasks") or {}).get(state.get("_processing_format_id", ""), {})
        copy = _parse_copy(task.get("copy", ""))
        category = state.get("category", "")

        from app.services.llm import call_llm_for_tool
        from app.services.tools.photo import FIND_PHOTO_TOOL, download_photo, run_find_photo

        user = (
            f"Title: {title or '(untitled)'}\n"
            f"Headline: {copy.get('headline', '') or '(none)'}\n"
            f"Category: {category or '(none)'}\n"
            f"Orientation: {orientation}"
        )
        try:
            args = await call_llm_for_tool(
                agent_role="designer",
                system_prompt=_PHOTO_DIRECTOR_SYSTEM,
                user_prompt=user,
                tool=FIND_PHOTO_TOOL,
                temperature=0.6,
                max_tokens=256,
            )
            args["orientation"] = orientation
            candidate = await run_find_photo(args)
        except Exception as e:  # noqa: BLE001
            log.warning("[template] find_photo tool call failed (%s)", e)
            return None

        if not candidate.get("ok"):
            log.info("[template] find_photo: %s", candidate.get("error", "no results"))
            return None

        image = await download_photo(candidate)
        if not image:
            return None
        return {
            "image": image,
            "credit": candidate.get("attribution", ""),
            "candidate": candidate,
        }

    result = await post_cached(state.get("_task_id", ""), "photo", loader)
    if result:
        state[_PHOTO_CACHE_KEY] = result
    return result


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
        # illustration (unified tool); everything else stays static.
        illustration: str | None = None
        if "{{ illustration" in html:
            illustration = await _get_post_illustration(state, ground, seed)

        # Auto-fill a single empty image slot with a searched photo when the
        # user provided no media.
        image_slots = entry.get("image_slots") or []
        has_user_images = bool(state.get("images", []))
        auto_photo: dict | None = None
        if not has_user_images and len(image_slots) == 1:
            auto_photo = await _get_post_photo(state, _orientation_for(fmt))

        context = build_template_context(
            copy,
            category,
            ground,
            state.get("footer", {}),
            fmt.width,
            fmt.height,
            has_user_images or bool(auto_photo),
            seed=seed,
            family=family,
            logo=state.get("logo", ""),
            di_config=state.get("design_instruction") or {},
            illustration=illustration,
        )
        rendered = render_template_html(html, context)
        if auto_photo:
            from app.services.tools.photo import embed_photo_into_html

            rendered = embed_photo_into_html(
                rendered, auto_photo["image"], auto_photo.get("credit", "")
            )
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
    if auto_photo:
        update[_PHOTO_CACHE_KEY] = auto_photo
        credits = list(state.get(_MEDIA_CREDITS_KEY) or [])
        cand = auto_photo.get("candidate") or {}
        credits.append({
            "kind": "photo",
            "provider": cand.get("provider"),
            "photographer": cand.get("photographer"),
            "license": cand.get("license"),
            "credit": auto_photo.get("credit", ""),
        })
        update[_MEDIA_CREDITS_KEY] = credits
    return update
