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
from app.services.formats import get_format_info, parse_carousel_slide
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
    """Return this slide/format's illustration (LLM director, cached per slide).

    Runs the illustration director (the unified ``illustrate`` tool — Anthropic
    procedural or vendored CC0 hand-drawn kits) once per carousel slide (cached
    per format id) so each slide may get its own figure — the director decides
    a cover figure and "necessary" interior figures, or declines.
    """
    cached = state.get(_ILLUSTRATION_CACHE_KEY)
    if cached:
        return cached

    from app.agents.orchestrator.post_cache import post_cached

    fmt_id = state.get("_processing_format_id", "")

    async def loader() -> str:
        title = state.get("title", "")
        task = (state.get("format_tasks") or {}).get(fmt_id, {})
        copy = _parse_copy(task.get("copy", ""))
        category = state.get("category", "")
        from app.services.illustration import illustration_via_tool

        return await illustration_via_tool(
            agent_role="designer",
            title=title,
            headline=copy.get("headline", ""),
            category=category,
            ground=ground,
            seed=f"{title or ''}|illustration|{fmt_id}",
        )

    svg = await post_cached(state.get("_task_id", ""), f"illustration:{fmt_id}", loader) or ""
    state[_ILLUSTRATION_CACHE_KEY] = svg
    return svg


def _orientation_for(fmt) -> str:
    if fmt.width > fmt.height:
        return "landscape"
    if fmt.height > fmt.width:
        return "portrait"
    return "square"


_PHOTO_DIRECTOR_SEARCH = (
    "You are the image director for a strict monochrome editorial design "
    "system. A photo is OPTIONAL — add one only if it genuinely strengthens "
    "this post (minimal, typographic, architectural, texture subjects work "
    "best). If you decide a photo helps, call find_photo with a SHORT, BROAD "
    "query (1-3 words). If no photo helps, do NOT call the tool. Photos "
    "render grayscale with a small credit caption."
)

_PHOTO_DIRECTOR_SEARCH_REQUIRED = (
    "You are the image director for a strict monochrome editorial design "
    "system. This slide's layout REQUIRES a photo. Call find_photo with a "
    "SHORT, BROAD query (1-3 words) matching the post's subject, then review "
    "the shortlist and call choose_photo with the best index. If the first "
    "search is poor, try one simpler query. Do not decline unless no photo "
    "can be found. Photos render grayscale with a small credit caption."
)

_PHOTO_DIRECTOR_PICK = (
    "You are the image director for a strict monochrome editorial design "
    "system. A shortlist of photo candidates is provided below. Call "
    "choose_photo with the index of the single best fit for the post. If none "
    "of them work, do NOT call the tool (decline the photo)."
)


async def _get_post_photo(state: GenerationState, orientation: str, required: bool = False) -> dict | None:
    """Return the post's shared auto-photo: {image, credit, candidate}.

    Runs the LLM photo director ONCE per post (shared per-post cache) in a
    bounded two-phase flow: the model searches via ``find_photo`` (one retry if
    the first query finds nothing), then sees the shortlist and picks via
    ``choose_photo``. Nothing is chosen deterministically by the pipeline. When
    ``required`` the layout depends on the photo (media templates) so the model
    is instructed to search rather than decline; a still-empty result means no
    photo (the caller falls back to a text template).
    """
    cached = state.get(_PHOTO_CACHE_KEY)
    if cached:
        return cached

    from app.agents.orchestrator.post_cache import post_cached

    async def loader() -> dict | None:
        if (state.get(_PHOTO_CALLS_KEY) or 0) >= _PHOTO_CAP:
            log.info("[template] photo search cap reached — skipping auto photo")
            return None

        title = state.get("title", "")
        task = (state.get("format_tasks") or {}).get(state.get("_processing_format_id", ""), {})
        copy = _parse_copy(task.get("copy", ""))
        category = state.get("category", "")

        from app.services.llm import call_llm_for_tool
        from app.services.tools.photo import (
            CHOOSE_PHOTO_TOOL,
            FIND_PHOTO_TOOL,
            download_photo,
            format_shortlist,
            pick_candidate,
            search_photo_candidates,
        )

        user = (
            f"Title: {title or '(untitled)'}\n"
            f"Headline: {copy.get('headline', '') or '(none)'}\n"
            f"Category: {category or '(none)'}\n"
            f"Orientation: {orientation}"
        )

        def _query(args: dict) -> str:
            return str(args.get("query") or "").strip()

        search_system = _PHOTO_DIRECTOR_SEARCH if not required else _PHOTO_DIRECTOR_SEARCH_REQUIRED

        # Phase A — decide + search (one bounded retry on an empty result).
        try:
            args = await call_llm_for_tool(
                agent_role="designer",
                system_prompt=search_system,
                user_prompt=user,
                tool=FIND_PHOTO_TOOL,
                temperature=0.5,
                max_tokens=128,
            )
        except Exception as e:  # noqa: BLE001 — model declined or failed
            log.info("[template] photo director declined/failed (%s)", e)
            return None
        if not _query(args):
            return None
        if (state.get(_PHOTO_CALLS_KEY) or 0) < _PHOTO_CAP:
            state[_PHOTO_CALLS_KEY] = (state.get(_PHOTO_CALLS_KEY) or 0) + 1
        shortlist = await search_photo_candidates(_query(args), orientation, args.get("min_width"))
        if not shortlist and (state.get(_PHOTO_CALLS_KEY) or 0) < _PHOTO_CAP:
            state[_PHOTO_CALLS_KEY] = (state.get(_PHOTO_CALLS_KEY) or 0) + 1
            retry_user = user + (
                "\n[NOTE] The previous query returned no photos. Call find_photo "
                "once more with a simpler, broader query — or do NOT call the "
                "tool to decline the photo."
            )
            try:
                args = await call_llm_for_tool(
                    agent_role="designer",
                    system_prompt=search_system,
                    user_prompt=retry_user,
                    tool=FIND_PHOTO_TOOL,
                    temperature=0.5,
                    max_tokens=128,
                )
            except Exception:  # noqa: BLE001 — declined on retry
                return None
            shortlist = await search_photo_candidates(_query(args), orientation, args.get("min_width"))
        if not shortlist:
            log.info("[template] photo director: no results after searches")
            return None

        # Phase B — the LLM picks from the shortlist it now sees.
        try:
            pick_args = await call_llm_for_tool(
                agent_role="designer",
                system_prompt=_PHOTO_DIRECTOR_PICK,
                user_prompt=user + "\n\nSearch results:\n" + format_shortlist(shortlist),
                tool=CHOOSE_PHOTO_TOOL,
                temperature=0.4,
                max_tokens=128,
            )
        except Exception:  # noqa: BLE001 — declined to pick
            log.info("[template] photo director declined the shortlist")
            return None
        chosen = pick_candidate(shortlist, pick_args.get("index"))
        if not chosen:
            log.info("[template] photo director invalid pick")
            return None

        image = await download_photo(chosen)
        if not image:
            return None
        return {"image": image, "credit": chosen.get("attribution", ""), "candidate": chosen}

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
    if not copy.get("headline") and not copy.get("body"):
        log.info("[template] No copy for %s — skipping", fmt_id)
        return {}

    templates = state.get("ds_templates") or []
    if not templates:
        return {}

    user_template_id = (state.get("template_id") or "").strip()

    # Verbatim mode carries long-form text in {{ body }} — only templates that
    # actually render a body slot can host it, or the content would be dropped.
    if state.get("verbatim"):
        body_templates = [t for t in templates if "{{ body" in (t.get("html") or "")]
        if body_templates:
            templates = body_templates

    # Carousel slide layout direction: cover prefers a media template; interior
    # slides alternate text ↔ media so the sequence breathes.
    layout_pref: str | None = None
    parsed = parse_carousel_slide(fmt_id)
    if parsed and not state.get("verbatim"):
        layout_pref = "media" if parsed[1] % 2 == 1 else "text"

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
        # Auto verbatim → prefer the dedicated slide-style text template.
        if state.get("verbatim") and not user_template_id:
            slide_tpl = next(
                (
                    t
                    for t in templates
                    if t.get("family") == family and "slide" in (t.get("hint_tags") or [])
                ),
                None,
            )
            if slide_tpl:
                templates = [slide_tpl]
        exclude = await get_recent_template_ids()
        selected = select_template(
            family, ground, category, hint, seed, templates, exclude, prefer=layout_pref
        )

    if selected is None:
        log.info("[template] No template for %s (%s / %s)", fmt_id, family, ground)
        return {}

    tid, entry = selected
    html = entry.get("html", "")
    image_slots = entry.get("image_slots") or []
    has_user_images = bool(state.get("images", []))

    def _hint_tags(e: dict) -> set[str]:
        return {str(h).lower() for h in e.get("hint_tags", [])}

    # Structural media slot: the photo is required. If the director can't fill
    # it, fall back to a text template so a slide is never a broken half-image.
    auto_photo: dict | None = None
    if not has_user_images and len(image_slots) == 1:
        is_media = "media" in _hint_tags(entry)
        auto_photo = await _get_post_photo(state, _orientation_for(fmt), required=is_media)
        if auto_photo is None and is_media:
            log.info("[template] media template %s has no photo — falling back to text", tid)
            text_tpls = [
                t for t in templates
                if t.get("family") == family and "media" not in _hint_tags(t)
            ]
            reselected = (
                select_template(family, ground, category, hint, seed, text_tpls, exclude, prefer="text")
                if text_tpls else None
            )
            if reselected:
                tid, entry = reselected
                html = entry.get("html", "")
                auto_photo = None

    try:
        # Templates that opt in to the illustration slot get an LLM-directed
        # illustration (unified tool); everything else stays static.
        illustration: str | None = None
        if "{{ illustration" in html:
            illustration = await _get_post_illustration(state, ground, seed)

        # Carousel slide counter (i / N) for slide-style templates.
        slide_index, slide_total = 0, 0
        if parsed:
            slide_index = parsed[1]
            slide_total = int((state.get("slide_context") or {}).get(fmt_id, {}).get("total", 0))

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
            slide_index=slide_index,
            slide_total=slide_total,
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
