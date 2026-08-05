"""Media Plan Director — one LLM planning session decides media per slide.

Instead of the old "one photo/illustration per post" model (which put the same
image on every carousel slide), the director produces a **structured plan** in
one multi-turn tool-calling session: for every slide/format it picks photo,
illustration, or none, and records the concrete choices (search query, style,
theme). The ``illustrate`` tool call actually renders a preview and returns
structural feedback (element count, bounding box, safe-frame compliance) so
the director can iterate to a distinct, non-overlapping figure.

The plan is cached once per post (``post_cached("media_plan")``) and executed
in parallel by the per-format branches. Slides already filled by a user image
are skipped (``filled`` targets get kind ``skip``).

Execution model:
  - ``kind == "photo"``         → search + download a stock photo (LLM pick)
  - ``kind == "illustration"``  → compose a scene (offline, deterministic)
  - ``kind == "skip"``          → user image fills this slide
  - ``kind == "none"``          → leave the slide clean

The LLM's final text is the plan JSON — validated here into typed entries, so
a malformed plan degrades to ``none`` rather than crashing the pipeline.
"""

from __future__ import annotations

import json
import logging

from app.agents.orchestrator.state import GenerationState

log = logging.getLogger(__name__)

_PLAN_CACHE_KEY = "media_plan"

# Hard caps so a run-away plan can't exhaust the budget.
MAX_TARGETS = 14
MAX_TURNS = 16
MIN_WIDTH = 800


def _plan_system_prompt() -> str:
    return (
        "You are the media director for a strict monochrome editorial design "
        "system. Decide the media for EVERY slide of the post in ONE planning "
        "session. For each slide choose exactly one: a photo (find_photo then "
        "choose_photo), an illustration (illustrate), or no media.\n\n"
        "DECIDE BY SUBJECT — photo first, illustration only when a photo is "
        "wrong:\n"
        "- PHOTO (STRONGLY preferred) when the post is about something concrete "
        "and visual: a place, object, person, animal, building, product, "
        "landscape, city, event, food, device. A real photo is the strongest "
        "media this system has — use it unless the subject is purely abstract.\n"
        "- ILLUSTRATION (procedural abstract mark) only when the subject is "
        "abstract and has no concrete visual: an idea, a process, a metric, "
        "a feeling, a concept, math, code. Prefer style='procedural' (a single "
        "clean organic mark). Use a DiceBear style only when the slide is "
        "genuinely about people or a robot.\n"
        "- NONE when the slide reads best as pure typography (a quote, a "
        "statistic, a callout) — media would dilute it.\n\n"
        "Rules:\n"
        "- One media kind per slide. Never the same image/art on two slides.\n"
        "- Photos: SHORT, BROAD queries (1-3 words) from the slide's concrete "
        "subject — e.g. 'mountain river', 'city street', 'coffee cup'. Never "
        "a sentence.\n"
        "- When in doubt between photo and illustration, choose PHOTO.\n"
        "- Cover slide (slide 1) may get the strongest media; interior slides "
        "vary so the sequence breathes.\n"
        "- STOP SEARCHING once you have enough. Call illustrate at most 2-3 "
        "times total to preview a style, look at the feedback the tool "
        "returns, then output the plan. Do NOT keep re-calling tools — "
        "imperfect media is fine.\n\n"
        "Final answer: output ONLY a JSON array of plan entries:\n"
        '[{"target": "<slide_or_format_id>", "kind": "photo|illustration|none", '
        '"query": "1-3 word search (photo only)", '
        '"style": "procedural|open-peeps|lorelei|notionists|bottts|blobs|'
        'initials|shapes|waves|landscape", "theme": "short theme (procedural '
        'only)"}]'
    )


def _build_user_prompt(state: GenerationState, targets: list[dict]) -> str:
    """Assemble the per-slide context: content summary + each slide's copy."""
    brief = state.get("strategic_brief") or {}
    summary = str(brief.get("content_summary") or "")
    lines = [
        f"TITLE: {state.get('title', '') or '(untitled)'}",
        f"CATEGORY: {state.get('category', '') or '(none)'}",
        f"GROUND: {state.get('ground', 'white')}",
        f"CONTENT SUMMARY: {summary or '(none)'}",
        "",
        "SLIDES TO PLAN:",
    ]
    for t in targets:
        tid = t["id"]
        copy = t.get("copy") or {}
        lines.append(
            f"- {tid} | headline: {copy.get('headline', '') or '(none)'} | "
            f"body: {(copy.get('body') or '')[:120]}"
        )
    return "\n".join(lines)


def _extract_targets(state: GenerationState) -> list[dict]:
    """Collect plan targets (formats + carousel slides) from format_tasks.

    Each target carries its copy so the director can make per-slide decisions.
    ``filled`` slides (already given a user image) are marked skip.
    """
    targets: list[dict] = []
    filled = set((state.get("_slide_images") or {}).keys())
    for fmt_id, task in (state.get("format_tasks") or {}).items():
        if not isinstance(task, dict):
            continue
        if not task.get("copy") and not task.get("html"):
            continue
        if task.get("status") in ("verified", "html_ready", "html_saved", "error", "failed"):
            continue
        copy = {}
        if task.get("copy"):
            try:
                parsed = json.loads(task["copy"])
                if isinstance(parsed, dict):
                    copy = parsed
            except Exception:  # noqa: BLE001
                copy = {}
        targets.append({
            "id": fmt_id,
            "copy": copy,
            "filled": fmt_id in filled,
        })
    return targets[:MAX_TARGETS]


async def build_media_plan(state: GenerationState) -> dict:
    """Return the media plan for the post (cached once per task).

    Returns ``{target_id: {kind, ...}}``. Slides filled by user images map to
    ``{kind: 'skip'}`` without an LLM call. A failed/declined planning session
    returns an empty plan (slides simply get no auto media).
    """
    targets = _extract_targets(state)
    if not targets:
        return {}

    # Pre-seed skip entries for user-filled slides (never overwritten).
    plan: dict[str, dict] = {}
    llm_targets: list[dict] = []
    for t in targets:
        if t["filled"]:
            plan[t["id"]] = {"kind": "skip"}
        else:
            llm_targets.append(t)
    if not llm_targets:
        return plan

    from app.agents.orchestrator.post_cache import post_cached
    from app.services.llm import call_llm_tool_loop
    from app.services.tools.illustrator import ILLUSTRATE_TOOL, run_illustrate
    from app.services.tools.photo import (
        CHOOSE_PHOTO_TOOL,
        FIND_PHOTO_TOOL,
        format_shortlist,
        search_photo_candidates,
    )

    task_id = state.get("_task_id", "")

    async def _handler_photo(args: dict) -> str:
        q = str(args.get("query") or "").strip()
        if not q:
            return "No query."
        orient = str(args.get("orientation") or "landscape")
        if orient not in ("landscape", "portrait", "square"):
            orient = "landscape"
        shortlist = await search_photo_candidates(q, orient, args.get("min_width"))
        return format_shortlist(shortlist)

    async def _handler_photo_pick(args: dict) -> str:
        # The model picked a photo from a shortlist; the plan entry records the
        # choice and the branch downloads it later. Never hit "Unknown tool".
        idx = args.get("index")
        return f"Photo #{idx} recorded. Include this photo in the plan for the current slide."

    async def _handler_illustrate(args: dict) -> str:
        """Execute the illustrate call and give the director real feedback.

        Instead of a no-op acceptance string, we actually render the figure and
        return structural metrics (arcaype, element count, bounding box,
        safe-frame compliance). The director sees what it picked and can
        iterate to a distinct, non-overlapping figure before committing the plan.
        """
        from app.services.illustration import generate_figure_metrics

        style = str(args.get("style") or "procedural")
        theme = str(args.get("theme") or "")[:60]
        ground = str(args.get("ground") or state.get("ground") or "white")
        if ground not in ("white", "black"):
            ground = "white"
        preview_seed = f"{task_id or 'plan'}|preview|{style}|{theme or 'none'}"

        fragment = run_illustrate(
            {"style": style, "theme": theme, "ground": ground}, seed=preview_seed
        )
        metrics: dict = {}
        if style in ("procedural", "anthropic"):
            metrics = generate_figure_metrics(preview_seed, ground, theme)
        # DiceBear figures can't be measured the same way, so report what we know.
        el_count = fragment.count("<path") + fragment.count("<circle") if fragment else 0

        box = metrics.get("box")
        box_str = (
            f"bbox x0={box['x0']} y0={box['y0']} x1={box['x1']} y1={box['y1']}"
            if box
            else "bbox n/a (DiceBear)"
        )
        return (
            f"Rendered style='{style}' theme='{theme or ''}' on {ground} ground.\n"
            f"Archetype: {metrics.get('archetype') or '(DiceBear)'}\n"
            f"Element count: {metrics.get('element_count') or el_count}\n"
            f"{box_str}\n"
            f"Within safe slot: {metrics.get('within_safe', 'n/a')}\n"
            "Record this style/theme in the plan entry for the current slide if "
            "it fits the post; otherwise try a different theme or style."
        )

    async def loader() -> str:
        handlers = {
            FIND_PHOTO_TOOL["function"]["name"]: _handler_photo,
            CHOOSE_PHOTO_TOOL["function"]["name"]: _handler_photo_pick,
            ILLUSTRATE_TOOL["function"]["name"]: _handler_illustrate,
        }
        tools = [FIND_PHOTO_TOOL, CHOOSE_PHOTO_TOOL, ILLUSTRATE_TOOL]
        return await call_llm_tool_loop(
            agent_role="designer",
            system_prompt=_plan_system_prompt(),
            user_prompt=_build_user_prompt(state, llm_targets),
            tools=tools,
            handlers=handlers,
            max_turns=MAX_TURNS,
            temperature=0.8,
            max_tokens=2048,
        )

    raw = await post_cached(task_id, _PLAN_CACHE_KEY, loader)
    parsed = _parse_plan(raw or "")
    for entry in parsed:
        tid = entry.get("target")
        if tid in plan:
            continue  # never overwrite a skip entry
        if tid in {t["id"] for t in llm_targets}:
            plan[tid] = entry
    log.info(
        "[media_plan] planned %d targets (%d entries): %s",
        len(llm_targets), len(parsed), parsed,
    )
    return plan


def _parse_plan(raw: str) -> list[dict]:
    """Extract and validate a JSON array of plan entries from LLM output."""
    if not raw:
        return []
    text = raw.strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        log.warning("[media_plan] unparseable plan (%s)", e)
        return []
    if not isinstance(data, list):
        return []
    valid_kinds = {"photo", "illustration", "none"}
    out: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("target") or "")
        kind = str(entry.get("kind") or "none")
        if not tid or kind not in valid_kinds:
            continue
        out.append({
            "target": tid,
            "kind": kind,
            "query": str(entry.get("query") or "")[:80],
            "style": str(entry.get("style") or "procedural")[:40],
            "theme": str(entry.get("theme") or "")[:60],
        })
    return out


# ---------------------------------------------------------------------------
# Per-slide execution — the branches call these to materialize media.
# ---------------------------------------------------------------------------


async def execute_slide_photo(plan_entry: dict, orientation: str, seed: str) -> dict | None:
    """Execute a photo plan entry → {image, credit, candidate} or None."""
    from app.services.llm import call_llm_for_tool
    from app.services.tools.photo import (
        CHOOSE_PHOTO_TOOL,
        download_photo,
        format_shortlist,
        pick_candidate,
        search_photo_candidates,
    )

    query = str(plan_entry.get("query") or "").strip()
    if not query:
        return None
    shortlist = await search_photo_candidates(query, orientation)
    if not shortlist:
        return None
    user = f"Choose the single best photo from the shortlist for query: {query!r}"
    try:
        args = await call_llm_for_tool(
            agent_role="designer",
            system_prompt=(
                "You are the photo director for a strict monochrome editorial "
                "system. Pick the single best photo from the shortlist."
            ),
            user_prompt=user + "\n\n" + format_shortlist(shortlist),
            tool=CHOOSE_PHOTO_TOOL,
            temperature=0.3,
            max_tokens=96,
        )
    except Exception:  # noqa: BLE001
        return None
    chosen = pick_candidate(shortlist, args.get("index"))
    if not chosen:
        return None
    image = await download_photo(chosen)
    if not image:
        return None
    return {"image": image, "credit": chosen.get("attribution", ""), "candidate": chosen}


def execute_slide_illustration(
    plan_entry: dict,
    seed: str,
    ground: str,
    category: str,
    api_style: str = "",
) -> str:
    """Execute an illustration plan entry → figure HTML fragment (offline)."""
    from app.services.tools.illustrator import run_illustrate

    style = plan_entry.get("style") or api_style or "procedural"
    return run_illustrate(
        {"style": style, "theme": plan_entry.get("theme") or "", "ground": ground},
        seed=seed,
    )


__all__ = [
    "build_media_plan",
    "execute_slide_illustration",
    "execute_slide_photo",
]
