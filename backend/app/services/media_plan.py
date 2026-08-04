"""Media Plan Director — one LLM planning session decides media per slide.

Instead of the old "one photo/illustration per post" model (which put the same
image on every carousel slide), the director produces a **structured plan** in
one multi-turn tool-calling session: for every slide/format it picks photo,
illustration, or none, and records the concrete choices (search query, icon
names, archetype, DiceBear style, Highlights accents).

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
        "choose_photo), a composed illustration (icon_search then illustrate "
        "with style='compose'), or no media.\n\n"
        "Rules:\n"
        "- Media is OPTIONAL — prefer none over weak media.\n"
        "- One media kind per slide. Never the same image/art on two slides.\n"
        "- Photos: SHORT, BROAD queries (1-3 words) from the slide's content.\n"
        "- Illustrations: prefer style='procedural' (a single clean organic "
        "mark — editorial and premium). Only use style='compose' for a SINGLE "
        "bold hero element; NEVER scatter multiple icons or marks.\n"
        "- Cover slide (slide 1) may get the strongest media; interior slides "
        "vary so the sequence breathes.\n"
        "- STOP SEARCHING once you have enough. Call icon_search at most 2-3 "
        "times total, then output the plan. Do NOT keep refining queries — "
        "imperfect motifs are fine.\n\n"
        "Final answer: output ONLY a JSON array of plan entries:\n"
        '[{"target": "<slide_or_format_id>", "kind": "photo|illustration|none", '
        '"query": "1-3 word search (photo only)", "motif_names": ["icon", "..."], '
        '"style": "compose|procedural|open-peeps|lorelei|notionists|bottts|blobs|'
        'initials|shapes|waves|landscape", "archetype": "optional", '
        '"highlights": ["arrow-1", ...], "theme": "short theme"}]'
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
    from app.services.tools.icon_search import ICON_SEARCH_TOOL, format_icon_shortlist, search_icons
    from app.services.tools.illustrator import ILLUSTRATE_TOOL
    from app.services.tools.photo import (
        CHOOSE_PHOTO_TOOL,
        FIND_PHOTO_TOOL,
        format_shortlist,
        search_photo_candidates,
    )

    task_id = state.get("_task_id", "")

    async def _handler_icon(args: dict) -> str:
        q = str(args.get("keywords") or "")
        return format_icon_shortlist(search_icons(q, 10))

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
        # The model may call illustrate to preview a style; we don't execute
        # media here — the plan entry records the choice and branches execute.
        style = str(args.get("style") or "compose")
        return (
            f"Style '{style}' accepted. Include this illustration in the plan "
            "for the current slide."
        )

    async def loader() -> str:
        handlers = {
            ICON_SEARCH_TOOL["function"]["name"]: _handler_icon,
            FIND_PHOTO_TOOL["function"]["name"]: _handler_photo,
            CHOOSE_PHOTO_TOOL["function"]["name"]: _handler_photo_pick,
            ILLUSTRATE_TOOL["function"]["name"]: _handler_illustrate,
        }
        tools = [FIND_PHOTO_TOOL, CHOOSE_PHOTO_TOOL, ICON_SEARCH_TOOL, ILLUSTRATE_TOOL]
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
    log.info("[media_plan] planned %d targets (%d entries)", len(llm_targets), len(parsed))
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
            "style": str(entry.get("style") or "compose")[:40],
            "archetype": str(entry.get("archetype") or "")[:40],
            "motif_names": [str(m)[:40] for m in (entry.get("motif_names") or [])][:6],
            "highlights": [str(h)[:40] for h in (entry.get("highlights") or [])][:5],
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
    from app.services.tools.composer import compose_scene
    from app.services.tools.illustrator import run_illustrate

    style = plan_entry.get("style") or api_style or "compose"
    if style == "compose":
        return compose_scene(
            seed,
            ground=ground,
            archetype=plan_entry.get("archetype") or None,
            motif_names=plan_entry.get("motif_names") or [],
            highlights=plan_entry.get("highlights") or [],
            style="compose",
            theme=plan_entry.get("theme") or "",
            category=category,
        )
    return run_illustrate(
        {"style": style, "theme": plan_entry.get("theme") or "", "ground": ground},
        seed=seed,
    )


__all__ = [
    "build_media_plan",
    "execute_slide_illustration",
    "execute_slide_photo",
]
