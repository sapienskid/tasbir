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


def _photo_grayscale(state: GenerationState) -> bool:
    """Whether photos render grayscale for the active design language."""
    di = state.get("design_instruction") or {}
    return bool((di.get("photo") or {}).get("grayscale", True))


def _plan_system_prompt(state: GenerationState) -> str:
    from app.services.art.catalog import CONCEPTS
    from app.services.styles import media_director_guidance

    guidance = media_director_guidance(state.get("design_instruction") or {})
    concepts = "; ".join(
        f"{key} — {spec['label']}" for key, spec in CONCEPTS.items()
    )
    return (
        "You are the media director for this post's design system. Decide the "
        "media for EVERY slide of the post in ONE planning session. For each "
        "slide choose exactly one: a photo (find_photo then choose_photo), an "
        "illustration (illustrate), or no media.\n\n"
        f"STYLE MEDIA GUIDANCE: {guidance}\n\n"
        f"CONCEPTS for illustrations (pick the one that matches the slide's "
        f"argument): {concepts}.\n\n"
        "Rules:\n"
        "- One media kind per slide. Never the same image/art on two slides.\n"
        "- Media must explain the slide's specific claim, evidence or relationship. "
        "A decorative image vaguely matching a keyword is insufficient. If the "
        "subject is conceptual, skip photo search; choose typography-only (none) "
        "unless an illustration communicates a specific relationship. Empty space "
        "is intentional. Never add an illustration merely to fill a slot.\n"
        "- If the post is about numbers/comparison/steps (metrics, rankings, "
        "before/after, counts) and you have 2-6 concrete values, you may use "
        "kind=\"chart\" with a \"chart\" object: "
        '{"values": [<numbers>], "labels": ["A", "B", ...], "title": "<short>"}. '
        "Charts render as a clean monochrome bar chart — great for stat-led posts.\n"
        "- Photos: SHORT, BROAD queries (1-3 words) from the slide's concrete "
        "subject — e.g. 'mountain river', 'city street', 'coffee cup'. Never "
        "a sentence.\n"
        "- Illustrations: pass a concept plus a one-line emphasis naming the "
        "specific relationship to show. Every call returns the subject/relation/"
        "field it composed and the list already used in this post — pick a "
        "DIFFERENT subject and relation for each slide. Two slides must never "
        "share a subject or a relation.\n"
        "- Cover slide (slide 1) may get the strongest media; interior slides "
        "vary so the sequence breathes.\n"
        "- STOP SEARCHING once you have enough. Call illustrate at most 2-3 "
        "times total to preview a concept, look at the feedback, then output the "
        "plan. Do NOT keep re-calling tools — imperfect media is fine.\n\n"
        "Final answer: output ONLY a JSON array of plan entries:\n"
        '[{"target": "<slide_or_format_id>", "kind": "photo|illustration|none", '
        '"rationale": "what this explains, or why typography alone is clearer", '
        '"query": "1-3 word search (photo only)", '
        '"concept": "limit|growth|system|attention|convergence|choice|scale|memory|flow|craft", '
        '"emphasis": "the specific relationship to show", '
        '"subject": "(optional pin)", "relation": "(optional pin)", '
        '"field": "(optional pin)", '
        '"style": "procedural|<curated portrait style>", '
        '"chart": {"values": [..], "labels": [..], "title": ".."}}]'
    )


def _build_user_prompt(state: GenerationState, targets: list[dict]) -> str:
    """Assemble the per-slide context: content summary + each slide's copy."""
    brief = state.get("strategic_brief") or {}
    summary = str(brief.get("content_summary") or "")
    di = state.get("design_instruction") or {}
    language = di.get("style_language") or ""
    lines = [
        f"TITLE: {state.get('title', '') or '(untitled)'}",
        f"CATEGORY: {state.get('category', '') or '(none)'}",
        f"GROUND: {state.get('ground', 'white')}",
        f"STYLE LANGUAGE: {language or 'custom'}",
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
        beat = ((state.get("slide_context") or {}).get(tid) or {}).get("narrative")
        if beat:
            lines.append("  NARRATIVE FUNCTION: " + json.dumps(beat, ensure_ascii=False))
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
    from app.services.tools.illustrator import ILLUSTRATE_TOOL
    from app.services.tools.photo import (
        CHOOSE_PHOTO_TOOL,
        FIND_PHOTO_TOOL,
        format_shortlist,
        search_photo_candidates,
    )

    task_id = state.get("_task_id", "")

    # Pre-gate (one cheap flash call): an independent judgment of what media
    # fits, made BEFORE the director spends up to MAX_TURNS of tool calls. A
    # "none" verdict (or a low photo-worthiness) becomes a hard constraint in
    # the director prompt so abstract subjects never waste turns on photo
    # search — the most common source of empty/generic media slots.
    pre_constraint = ""
    try:
        from app.services.decision_packs import get_pack
        from app.services.decisions import decide, providers_configured

        if providers_configured():
            brief = state.get("strategic_brief") or {}
            pre_res = await decide(
                "media-kind",
                {"title": state.get("title", "") or "(untitled)",
                 "content": str(brief.get("content_summary") or "")[:800]},
                metadata={"agent": "media_plan", "stage": "pregate"},
            )
            pre_answers = pre_res.get("answers", {})
            pre_kind = str((pre_answers.get("kind") or {}).get("choice") or "")
            try:
                pre_photo = float((pre_answers.get("photo_worthy") or {}).get("noul", 0) or 0)
            except (TypeError, ValueError):
                pre_photo = 0.0
            vote_block = float(get_pack("media-kind").get("thresholds", {}).get("photo_vote", 0.4))
            if pre_kind == "none":
                pre_constraint = (
                    "CONSTRAINT from an independent media judge: this post wants "
                    "PURE TYPOGRAPHY. Output an all-\"none\" plan. Do NOT call "
                    "find_photo or illustrate at all."
                )
            elif pre_photo < vote_block:
                pre_constraint = (
                    "CONSTRAINT from an independent media judge: the subject is "
                    "abstract, not photographable. Do NOT call find_photo — use "
                    "illustrate or no media for every slide."
                )
            if task_id:
                from app.services.audit import record_audit

                await record_audit(
                    task_id, "media_plan",
                    decision={"pregate_kind": pre_kind, "pregate_photo_worthy": pre_photo,
                              "pregate_constrained": bool(pre_constraint),
                              "provider": pre_res.get("provider", "")},
                )
    except Exception as e:  # noqa: BLE001
        log.warning("[media_plan] pregate skipped: %s", e)

    _pre_constraint = pre_constraint

    async def _handler_photo(args: dict) -> str:
        q = str(args.get("query") or "").strip()
        if not q:
            return "No query."
        orient = str(args.get("orientation") or "landscape")
        if orient not in ("landscape", "portrait", "square"):
            orient = "landscape"
        shortlist = await search_photo_candidates(
            q, orient, args.get("min_width"), grayscale=_photo_grayscale(state)
        )
        return format_shortlist(shortlist)

    async def _handler_photo_pick(args: dict) -> str:
        # The model picked a photo from a shortlist; the plan entry records the
        # choice and the branch downloads it later. Never hit "Unknown tool".
        idx = args.get("index")
        return f"Photo #{idx} recorded. Include this photo in the plan for the current slide."

    used_subjects: list[str] = []
    used_relations: list[str] = []
    used_pairs: list[str] = []
    used_fingerprints: list[str] = []

    async def _handler_illustrate(args: dict) -> str:
        """Compose the scene and give the director real structural feedback."""
        from app.services.art import compose_scene

        style = str(args.get("style") or "procedural")
        concept = str(args.get("concept") or "")
        emphasis = str(args.get("emphasis") or "")[:60]
        subject = str(args.get("subject") or "")
        relation = str(args.get("relation") or "")
        field = str(args.get("field") or "")
        ground = str(args.get("ground") or state.get("ground") or "white")
        if ground not in ("white", "black"):
            ground = "white"
        preview_seed = f"{task_id or 'plan'}|preview|{concept}|{emphasis}"

        if style != "procedural":
            # Curated portrait styles cannot be measured structurally.
            return (
                f"Portrait style '{style}' selected. Portraits are rendered by "
                "the avatar engine; record this style in the plan."
            )

        scene = compose_scene(
            preview_seed, ground, concept=concept, subject=subject,
            relation=relation, field=field,
            avoid_subjects=tuple(used_subjects),
            avoid_relations=tuple(used_relations),
            avoid_fingerprints=tuple(used_fingerprints),
            avoid_pairs=tuple(used_pairs),
        )
        m = scene.metrics()
        if m["fingerprint"] not in used_fingerprints:
            used_fingerprints.append(m["fingerprint"])
        if f"{m['subject']}|{m['relation']}" not in used_pairs:
            used_pairs.append(f"{m['subject']}|{m['relation']}")
        if m["subject"] not in used_subjects:
            used_subjects.append(m["subject"])
        if m["relation"] not in used_relations:
            used_relations.append(m["relation"])
        return (
            f"Composed concept='{m['concept']}' subject='{m['subject']}' "
            f"relation='{m['relation']}' field='{m['field']}' "
            f"framing='{m['framing']}'.\n"
            f"Elements: {m['element_count']}, occupancy: {m['occupancy']:.0%}, "
            f"within safe slot: {m['within_safe']}.\n"
            f"Already used in this post — subjects: {used_subjects}; "
            f"relations: {used_relations}.\n"
            "Record this concept (and the pinned subject/relation/field if you "
            "want it) in the plan entry for the current slide. Pick a different "
            "subject AND relation for the next slide."
        )

    async def loader() -> str:
        handlers = {
            FIND_PHOTO_TOOL["function"]["name"]: _handler_photo,
            CHOOSE_PHOTO_TOOL["function"]["name"]: _handler_photo_pick,
            ILLUSTRATE_TOOL["function"]["name"]: _handler_illustrate,
        }
        tools = [FIND_PHOTO_TOOL, CHOOSE_PHOTO_TOOL, ILLUSTRATE_TOOL]
        system_prompt = _plan_system_prompt(state)
        if _pre_constraint:
            # The pre-gate verdict leads the prompt so it binds the whole
            # session, not just one turn.
            system_prompt = f"{_pre_constraint}\n\n{system_prompt}"
        return await call_llm_tool_loop(
            agent_role="designer",
            system_prompt=system_prompt,
            user_prompt=_build_user_prompt(state, llm_targets),
            tools=tools,
            handlers=handlers,
            max_turns=MAX_TURNS,
            temperature=0.8,
            max_tokens=2048,
        )

    raw = await post_cached(task_id, _PLAN_CACHE_KEY, loader)
    parsed = _parse_plan(raw or "")
    await _finalize_illustrations(parsed, state)
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
    valid_kinds = {"photo", "illustration", "chart", "none"}
    out: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("target") or "")
        kind = str(entry.get("kind") or "none")
        if not tid or kind not in valid_kinds:
            continue
        chart = entry.get("chart") if isinstance(entry.get("chart"), dict) else {}
        out.append({
            "target": tid,
            "kind": kind,
            "query": str(entry.get("query") or "")[:80],
            "style": str(entry.get("style") or "procedural")[:40],
            "concept": str(entry.get("concept") or "")[:40],
            "subject": str(entry.get("subject") or "")[:40],
            "relation": str(entry.get("relation") or "")[:40],
            "field": str(entry.get("field") or "")[:40],
            "emphasis": str(entry.get("emphasis") or entry.get("theme") or "")[:80],
            "theme": str(entry.get("theme") or "")[:60],
            "rationale": str(entry.get("rationale") or "")[:500],
            "chart": {
                "values": (chart.get("values") or [])[:8],
                "labels": (chart.get("labels") or [])[:8],
                "title": str(chart.get("title") or "")[:60],
            },
        })
    return out


async def _finalize_illustrations(parsed: list[dict], state: GenerationState) -> None:
    """Resolve every illustration to a concrete composition, without repeats.

    The director chooses a concept per slide; this pass fills the concrete
    subject/relation/field and enforces the sequence rule: no subject and no
    relation may appear twice in one post. Recent design-system compositions
    (Redis) are soft-avoided so consecutive posts also differ.
    """
    from app.services.art import resolve_concept, select_combination
    from app.services.art.ledger import recent_fingerprints

    title = state.get("title", "") or ""
    recent = await recent_fingerprints(state.get("design_system_id") or "default")

    used_subjects: list[str] = []
    used_relations: list[str] = []
    used_pairs: list[str] = []
    used_fingerprints: list[str] = []
    for entry in parsed:
        if entry.get("kind") != "illustration" or entry.get("style") not in ("", "procedural"):
            continue
        concept = resolve_concept(
            f"{entry['target']}|{title}", entry.get("concept", ""),
            entry.get("emphasis") or entry.get("theme") or "", title,
        )
        subject, relation, field = select_combination(
            f"{entry['target']}|{title}",
            concept,
            entry.get("subject", ""),
            entry.get("relation", ""),
            entry.get("field", ""),
            tuple(used_subjects),
            tuple(used_relations),
            tuple(used_fingerprints) + tuple(recent),
            tuple(used_pairs),
        )
        entry.update(concept=concept, subject=subject, relation=relation, field=field)
        used_subjects.append(subject)
        used_relations.append(relation)
        used_pairs.append(f"{subject}|{relation}")
        used_fingerprints.append(f"{subject}|{relation}|{field}")

    if used_fingerprints:
        from app.services.art.ledger import remember_fingerprints

        await remember_fingerprints(
            state.get("design_system_id") or "default", used_fingerprints
        )


# ---------------------------------------------------------------------------
# Per-slide execution — the branches call these to materialize media.
# ---------------------------------------------------------------------------


async def execute_slide_photo(
    plan_entry: dict, orientation: str, seed: str, grayscale: bool = True
) -> dict | None:
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
    shortlist = await search_photo_candidates(query, orientation, grayscale=grayscale)
    if not shortlist:
        return None
    user = f"Choose the single best photo from the shortlist for query: {query!r}"
    try:
        args = await call_llm_for_tool(
            agent_role="designer",
            system_prompt=(
                "You are the photo director for this design system. Pick the "
                "single best photo from the shortlist."
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


def aspect_for(width: int, height: int) -> str:
    if not width or not height:
        return "square"
    ratio = width / height
    if ratio > 1.45:
        return "wide"
    if ratio > 1.1:
        return "landscape"
    if ratio < 0.62:
        return "story"
    if ratio < 0.92:
        return "portrait"
    return "square"


def execute_slide_illustration(
    plan_entry: dict,
    seed: str,
    ground: str,
    category: str,
    api_style: str = "",
    aspect: str = "square",
) -> str:
    """Execute an illustration plan entry → figure HTML fragment (offline)."""
    from app.services.tools.illustrator import run_illustrate

    style = plan_entry.get("style") or api_style or "procedural"
    return run_illustrate(
        {
            "style": style,
            "concept": plan_entry.get("concept") or "",
            "subject": plan_entry.get("subject") or "",
            "relation": plan_entry.get("relation") or "",
            "field": plan_entry.get("field") or "",
            "emphasis": plan_entry.get("emphasis") or plan_entry.get("theme") or "",
            "theme": plan_entry.get("theme") or "",
            "ground": ground,
            "aspect": aspect,
        },
        seed=seed,
    )


def execute_slide_chart(plan_entry: dict, ground: str) -> str:
    """Execute a chart plan entry → token-only bar-chart SVG fragment."""
    from app.services.charts import generate_chart_svg

    chart = plan_entry.get("chart") or {}
    values = chart.get("values") or []
    labels = chart.get("labels") or []
    title = chart.get("title") or ""
    svg = generate_chart_svg(values, labels, ground, title)
    return (
        '<div class="figure" style="--ill-ink:var(--color-text);'
        '--ill-paper:var(--color-bg);width:100%;height:100%">'
        f"<style>.figure svg{{width:100%;height:100%;display:block}}</style>{svg}</div>"
    )


__all__ = [
    "build_media_plan",
    "execute_slide_chart",
    "execute_slide_illustration",
    "execute_slide_photo",
]
