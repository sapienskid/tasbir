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

from app.agents.orchestrator.state import GenerationState, platform_cfg
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
    """Return this slide/format's illustration from the media plan (cached).

    The media plan (built once per post by the media-plan director) decides
    which slides get an illustration and with what style/theme. This executes
    the plan entry for the current slide, offline, cached per slide id.

    If the plan produced no illustration but the template renders an
    ``{{ illustration }}`` slot, a deterministic procedural figure (seeded by
    title+format, no LLM) fills it so a layout never ships an empty art block.
    """
    cached = state.get(_ILLUSTRATION_CACHE_KEY)
    if cached:
        return cached

    fmt_id = state.get("_processing_format_id", "")
    plan = (state.get("media_plan") or {}).get(fmt_id) or {}

    from app.agents.orchestrator.post_cache import post_cached
    from app.services.media_plan import execute_slide_illustration

    async def loader() -> str:
        if plan.get("kind") == "illustration":
            return execute_slide_illustration(
                plan,
                seed=f"{seed or ''}|illustration|{fmt_id}",
                ground=ground,
                category=state.get("category", ""),
                api_style=state.get("illustration_style") or "",
            )
        if plan.get("kind") == "chart":
            from app.services.media_plan import execute_slide_chart

            return execute_slide_chart(plan, ground)
        # If the plan asked for a photo (or no media) but the template still
        # renders an illustration slot, DON'T inject a procedural figure on top
        # of a real photo. If the photo failed to materialize (empty search /
        # no keys), fill the slot with a procedural figure so the layout never
        # ships an empty art block.
        if plan.get("kind") == "photo":
            if state.get(_PHOTO_CACHE_KEY):
                return ""
            from app.services.illustration import generate_illustration_svg

            return generate_illustration_svg(
                f"{seed or ''}|{fmt_id}",
                ground=ground,
                theme=state.get("category", "") or None,
            )
        # Deterministic fallback — no plan entry at all, but the template has
        # the slot, so a seeded procedural figure fills it (never an empty art
        # block).
        from app.services.illustration import generate_illustration_svg

        return generate_illustration_svg(
            f"{seed or ''}|{fmt_id}",
            ground=ground,
            theme=state.get("category", "") or None,
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


async def _get_post_photo(state: GenerationState, orientation: str, required: bool = False) -> dict | None:
    """Return the slide's auto-photo per the media plan: {image, credit, candidate}.

    The media plan decides which slides get a photo (and the query). This
    executes the plan entry for the current slide — search + LLM pick +
    SSRF-guarded download — cached per slide. ``required`` (media templates)
    falls back to a plain search for the slide's headline when the plan has no
    photo, so a media layout is never a broken half-image.
    """
    cached = state.get(_PHOTO_CACHE_KEY)
    if cached:
        return cached

    fmt_id = state.get("_processing_format_id", "")
    plan = (state.get("media_plan") or {}).get(fmt_id) or {}
    query = str(plan.get("query") or "") if plan.get("kind") == "photo" else ""

    from app.agents.orchestrator.post_cache import post_cached

    async def loader() -> dict | None:
        if (state.get(_PHOTO_CALLS_KEY) or 0) >= _PHOTO_CAP:
            log.info("[template] photo search cap reached — skipping auto photo")
            return None

        title = state.get("title", "")
        task = (state.get("format_tasks") or {}).get(fmt_id, {})
        copy = _parse_copy(task.get("copy", ""))
        category = state.get("category", "")

        from app.services.llm import call_llm_for_tool
        from app.services.media_plan import _photo_grayscale, execute_slide_photo
        from app.services.tools.photo import (
            CHOOSE_PHOTO_TOOL,
            FIND_PHOTO_TOOL,
            download_photo,
            format_shortlist,
            pick_candidate,
            search_photo_candidates,
        )

        grayscale = _photo_grayscale(state)

        user = (
            f"Title: {title or '(untitled)'}\n"
            f"Headline: {copy.get('headline', '') or '(none)'}\n"
            f"Category: {category or '(none)'}\n"
            f"Orientation: {orientation}"
        )

        def _query(args: dict) -> str:
            return str(args.get("query") or "").strip()

        # Preferred path: execute the media plan's photo entry.
        if query:
            result = await execute_slide_photo(
                plan,
                orientation,
                seed=f"{title or ''}|photo|{fmt_id}",
                grayscale=grayscale,
            )
            if result:
                return result
            # Plan photo failed to materialize — retry with the fallback below.

        # Fallback (required media templates only): a bounded one-shot search.
        if not required or (state.get(_PHOTO_CALLS_KEY) or 0) >= _PHOTO_CAP:
            return None
        state[_PHOTO_CALLS_KEY] = (state.get(_PHOTO_CALLS_KEY) or 0) + 1
        try:
            args = await call_llm_for_tool(
                agent_role="designer",
                system_prompt=(
                    "You are the image director for this design system. This "
                    "slide's layout REQUIRES a photo. Call find_photo with a "
                    "SHORT, BROAD query (1-3 words) matching the post's "
                    "subject, then review the shortlist and call choose_photo "
                    "with the best index. If the first search is poor, try one "
                    "simpler query. Do not decline unless no photo can be found."
                ),
                user_prompt=user,
                tool=FIND_PHOTO_TOOL,
                temperature=0.5,
                max_tokens=128,
            )
        except Exception:  # noqa: BLE001 — declined or failed
            return None
        if not _query(args):
            return None
        shortlist = await search_photo_candidates(
            _query(args), orientation, args.get("min_width"), grayscale=grayscale
        )
        if not shortlist:
            return None
        try:
            pick_args = await call_llm_for_tool(
                agent_role="designer",
                system_prompt=(
                    "You are the image director for this design system. Pick "
                    "the single best photo from the shortlist."
                ),
                user_prompt=user + "\n\n" + format_shortlist(shortlist),
                tool=CHOOSE_PHOTO_TOOL,
                temperature=0.4,
                max_tokens=96,
            )
        except Exception:  # noqa: BLE001 — declined to pick
            return None
        chosen = pick_candidate(shortlist, pick_args.get("index"))
        if not chosen:
            return None
        image = await download_photo(chosen)
        if not image:
            return None
        return {"image": image, "credit": chosen.get("attribution", ""), "candidate": chosen}

    result = await post_cached(state.get("_task_id", ""), f"photo:{fmt_id}", loader)
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
    style_language = (state.get("design_instruction") or {}).get("style_language") or ""

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    copy = _parse_copy(task.get("copy", ""))
    if not copy.get("headline") and not copy.get("body"):
        log.info("[template] No copy for %s — skipping", fmt_id)
        return {}

    templates = state.get("ds_templates") or []
    if not templates:
        return {}

    user_template_id = platform_cfg(state, fmt_id, "template_id").strip()

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

    # When the media plan chose an illustration for this slide, prefer a
    # template that actually renders an {{ illustration }} slot, so the
    # composed figure lands on the post. When it chose a photo, prefer a
    # template with a real image slot (data-image-key) so the photo actually
    # lands on the post instead of being dropped for a procedural fallback.
    plan_entry = (state.get("media_plan") or {}).get(fmt_id) or {}
    plan_kind = plan_entry.get("kind") or ""
    # When the copy carries post-type extras (price/cta/date/location), prefer a
    # template that renders {{ extra.* }} so they appear as styled elements
    # rather than only inside the body copy. ad-card hosts both extras and the
    # illustration slot, so a planned figure/chart is not lost.
    extra_keys = [k for k, v in (copy.get("extra") or {}).items() if v]
    if extra_keys:
        prefer_slot = "{{ extra"
    elif plan_kind == "illustration":
        prefer_slot = "{{ illustration"
    elif plan_kind == "photo":
        prefer_slot = "data-image-key"
    elif plan_kind == "chart":
        # Charts render into the illustration slot — route to a slot template
        # so the bar chart actually lands on the post.
        prefer_slot = "{{ illustration"
    else:
        prefer_slot = None

    # When the user asked for a full-bleed background image (placement:
    # "background"), route to a template with a cover/background slot (e.g.
    # square-cover-bg) so the image actually fills the frame. A template_id
    # override still wins below.
    slide_images = (state.get("_slide_images") or {}).get(fmt_id)
    user_images = slide_images if slide_images is not None else state.get("images", [])
    prefer_background = any(
        str(img.get("placement") or "").strip().lower() == "background"
        for img in (user_images or [])
    )

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
            family, ground, category, hint, seed, templates, exclude,
            prefer=("background" if prefer_background else layout_pref),
            prefer_slot=prefer_slot,
            style_language=style_language or None,
        )

    if selected is None:
        log.info("[template] No template for %s (%s / %s)", fmt_id, family, ground)
        return {}

    tid, entry = selected
    html = entry.get("html", "")
    image_slots = entry.get("image_slots") or []
    # Per-slide user images (auto-distributed in the graph); fall back to the
    # post-wide list for single formats.
    slide_images = (state.get("_slide_images") or {}).get(fmt_id)
    user_images = slide_images if slide_images is not None else state.get("images", [])
    has_user_images = bool(user_images)

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
                select_template(family, ground, category, hint, seed, text_tpls, exclude,
                                prefer="text", style_language=style_language or None)
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
            media_position=entry.get("media_position") or "auto",
            hidden=entry.get("hidden_elements") or [],
        )
        rendered = render_template_html(html, context)
        if auto_photo:
            from app.services.media_plan import _photo_grayscale
            from app.services.tools.photo import embed_photo_into_html

            rendered = embed_photo_into_html(
                rendered,
                auto_photo["image"],
                auto_photo.get("credit", ""),
                grayscale=_photo_grayscale(state),
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
