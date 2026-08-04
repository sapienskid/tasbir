"""LangGraph state machine for the v3 generation pipeline.

Topology:
  strategist → copywriter → process_all_formats → END

`process_all_formats` runs the per-format chain
(designer → renderer → verifier, with retry loop) for every platform in
PARALLEL via asyncio.gather, but each branch works on an isolated state copy
and merges its results back deterministically in Python. This avoids the
reducer race conditions that occur when many parallel Send branches write to
nested dict state through a shared checkpointer.
"""

import copy
import logging
import re
from collections.abc import Awaitable, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.nodes.designer import designer_node_single
from app.agents.orchestrator.nodes.planner import planner_node
from app.agents.orchestrator.nodes.quality_check import MAX_RETRIES, quality_check_node_single
from app.agents.orchestrator.nodes.renderer import renderer_node_single
from app.agents.orchestrator.nodes.strategist import strategist_node
from app.agents.orchestrator.nodes.template_renderer import template_node_single
from app.agents.orchestrator.state import GenerationState, initial_state
from app.services.settings import get_runtime_setting

log = logging.getLogger(__name__)

NODE_PROGRESS: dict[str, int] = {
    "strategist": 10,
    "planner": 18,
    "copywriter": 25,
    "process_all_formats": 50,
}

NODE_LABELS: dict[str, str] = {
    "strategist": "Analyzing content...",
    "planner": "Planning post structure...",
    "copywriter": "Writing copy...",
    "process_all_formats": "Designing & verifying...",
}


def _apply_updates(state: dict, updates: dict) -> None:
    """Merge node output dicts into a mutable state (deep merge on nested dicts)."""
    for key, value in updates.items():
        if key == "_processing_format_id":
            continue
        current = state.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            merged = dict(current)
            for k, v in value.items():
                if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
            state[key] = merged
        elif isinstance(value, list) and isinstance(current, list):
            state[key] = current + value
        else:
            state[key] = value


async def _run_format_chain(base_state: dict, fmt_id: str) -> dict:
    """Run template → renderer → verifier, falling back to the LLM designer.

    Templates are the first choice. If none matches, or the chosen template
    fails QC (e.g. overflow), the chain falls back to the designer on the
    next attempt. Works on an isolated deep copy so parallel branches never
    share mutable state. Returns the per-format updates to merge.
    """
    local = copy.deepcopy(base_state)
    local["_processing_format_id"] = fmt_id
    task_id = local.get("_task_id", "")

    async def _audit(agent_name: str, decision: dict, critique: str = "") -> None:
        if not task_id:
            return
        from app.services.audit import record_audit

        await record_audit(task_id, agent_name, decision=decision, critique=critique)

    use_template = True
    max_retries = int(
        await get_runtime_setting("verifier.max_retries", MAX_RETRIES)
    )
    for _attempt in range(max_retries + 1):
        if use_template:
            _apply_updates(local, await template_node_single(local))
            used_template = bool(local.get("format_tasks", {}).get(fmt_id, {}).get("html"))
            await _audit(
                "template",
                {"format": fmt_id, "used": used_template,
                 "template_id": local.get("format_tasks", {}).get(fmt_id, {}).get("template_id")},
            )

        fmt_task = local.get("format_tasks", {}).get(fmt_id, {})
        if not fmt_task.get("html"):
            # No template matched (or copy missing) → LLM designer.
            _apply_updates(local, await designer_node_single(local))
            await _audit(
                "designer",
                {"format": fmt_id, "attempt": _attempt, "status": "designed"},
            )

        _apply_updates(local, await renderer_node_single(local))
        _apply_updates(local, await quality_check_node_single(local))

        fmt_task = local.get("format_tasks", {}).get(fmt_id, {})
        status = fmt_task.get("status", "")
        verification = local.get("verification", {}).get(fmt_id, {})
        await _audit(
            "verifier",
            {
                "format": fmt_id,
                "status": status,
                "pass": verification.get("pass"),
                "score": verification.get("score"),
            },
            critique=str(verification.get("critique") or ""),
        )
        if status in ("verified", "error", "failed"):
            break
        if status == "needs_retry":
            if use_template:
                # Chosen template failed QC (e.g. overflow) → LLM designer.
                use_template = False
                fmt_task["html"] = None
                fmt_task.pop("template_id", None)
                continue
            if _attempt >= max_retries:
                break

    return {
        "format_tasks": {fmt_id: local["format_tasks"].get(fmt_id, {})},
        "verification": {fmt_id: local["verification"].get(fmt_id, {})},
        "retry_count": {fmt_id: local["retry_count"].get(fmt_id, 0)},
        "media_credits": local.get("media_credits") or [],
    }


async def process_all_formats_node(state: GenerationState) -> dict:
    """Run the full per-format chain for every platform in parallel.

    Carousels (instagram-carousel) are expanded into one chain per slide
    (instagram-carousel-1..N), each carrying that slide's copy. Each branch is
    isolated and merges its slice back deterministically, so the final state
    always reflects every format's real status.
    """
    import asyncio
    import json

    from app.services.formats import carousel_slide_id, is_carousel

    platforms = state.get("platforms", [])
    format_tasks = dict(state.get("format_tasks", {}))
    slide_context: dict[str, dict] = {}
    runnable: list[str] = []

    for fmt_id in platforms:
        if is_carousel(fmt_id):
            copy = format_tasks.get(fmt_id, {}).get("copy", "")
            slides = _extract_slides(copy)
            if not slides:
                # No slide copy produced — fall back to a single-frame design.
                runnable.append(fmt_id)
                continue
            base_meta = {
                k: v for k, v in format_tasks[fmt_id].items() if k not in ("copy", "status")
            }
            for i, slide_copy in enumerate(slides, start=1):
                sid = carousel_slide_id(fmt_id, i)
                format_tasks[sid] = {
                    **base_meta,
                    "status": "waiting",
                    "copy": json.dumps(slide_copy),
                }
                slide_context[sid] = {"index": i, "total": len(slides)}
                runnable.append(sid)
            format_tasks.pop(fmt_id, None)  # base carousel entry is not an output
        else:
            runnable.append(fmt_id)

    log.info("[graph] Processing %d format(s)/slide(s) in parallel", len(runnable))

    # Auto-distribute user images across carousel slides (image i → slide i,
    # wrapping). Single formats keep the full image list.
    all_images = list(state.get("images") or [])
    slide_images: dict[str, list[dict]] = {}
    for i, sid in enumerate(runnable):
        if is_carousel(sid):
            if all_images:
                slide_images[sid] = [all_images[i % len(all_images)]]
        else:
            if all_images:
                slide_images[sid] = all_images

    base_state = dict(state)
    base_state["format_tasks"] = format_tasks
    base_state["slide_context"] = slide_context
    base_state["_slide_images"] = slide_images

    # One structured media plan decides media for every slide (cached once per
    # post). Slides already filled by a user image are skipped inside the plan.
    from app.services.media_plan import build_media_plan

    base_state["media_plan"] = await build_media_plan(base_state)

    results = await asyncio.gather(
        *(_run_format_chain(base_state, fmt_id) for fmt_id in runnable)
    )

    merged_tasks = {}
    verification = {}
    retry_count = {}
    media_credits: list[dict] = []
    for r in results:
        merged_tasks.update(r.get("format_tasks", {}))
        verification.update(r.get("verification", {}))
        retry_count.update(r.get("retry_count", {}))
        media_credits.extend(r.get("media_credits") or [])

    merged_state = dict(base_state)
    merged_state["format_tasks"] = merged_tasks
    merged_state["verification"] = verification

    sequence = await _run_sequence_check(merged_state)

    # Bounded duplicate-media retry: if two+ slides share the same image/SVG,
    # force the non-first slides to 'none' (drop the dup), clear their media
    # caches, and re-run just those branches. One pass, deterministic — no
    # extra LLM planning call.
    dup_slides = _duplicate_media_slides(merged_state)
    if dup_slides:
        log.warning("[graph] duplicate media on %s — forcing distinct media", dup_slides)
        from app.agents.orchestrator.post_cache import post_cache_drop

        # Drop this task's cached media so the retried branches recompute
        # (a plan entry of 'none' then yields no media instead of the dup).
        post_cache_drop(base_state.get("_task_id", ""))
        plan = dict(base_state.get("media_plan") or {})
        for sid in dup_slides:
            plan[sid] = {"kind": "none"}
        retry_base = dict(base_state)
        retry_base["media_plan"] = plan
        retry_results = await asyncio.gather(
            *(_run_format_chain(retry_base, sid) for sid in dup_slides)
        )
        for r in retry_results:
            merged_tasks.update(r.get("format_tasks", {}))
            verification.update(r.get("verification", {}))
            retry_count.update(r.get("retry_count", {}))
            media_credits.extend(r.get("media_credits") or [])
        merged_state["format_tasks"] = merged_tasks
        merged_state["verification"] = verification
        sequence = await _run_sequence_check(merged_state)

    return {
        "format_tasks": merged_tasks,
        "verification": verification,
        "retry_count": retry_count,
        "sequence_check": sequence,
        "media_credits": media_credits,
    }


def _duplicate_media_slides(state: GenerationState) -> list[str]:
    """Return carousel slide ids that share the same embedded media signature.

    The FIRST slide of each duplicate group is kept; the rest are returned for
    a forced 'none' retry. A media signature is the base64 data URI embedded in
    the slide's HTML (images + composed SVG figures).
    """
    from collections import defaultdict

    slide_context = state.get("slide_context") or {}
    sig_to_slides: dict[str, list[str]] = defaultdict(list)
    for sid in slide_context:
        html = (state.get("format_tasks", {}).get(sid) or {}).get("html", "") or ""
        for match in re.finditer(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", html):
            sig = match.group(1)[:64]
            sig_to_slides[sig].append(sid)
    dup: list[str] = []
    for sids in sig_to_slides.values():
        unique = sorted(set(sids))
        if len(unique) > 1:
            dup.extend(unique[1:])
    return dup


async def _run_sequence_check(state: GenerationState) -> dict:
    """Carousel sequence check — deterministic always, vision set-pass opt-in.

    Deterministic (no LLM): every slide of a carousel must share the same
    canvas dims and carry its ``i/N`` counter (soft warning if missing).
    ``sequence_audit`` also renders the whole slide set as one grid and sends
    it to the vision verifier once (cohesion / repetition / flow).
    """
    from collections import defaultdict

    from app.services.formats import get_format_info, parse_carousel_slide

    slide_context = state.get("slide_context") or {}
    if not slide_context:
        return {}

    by_base: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for sid, ctx in slide_context.items():
        parsed = parse_carousel_slide(sid)
        if parsed:
            by_base[parsed[0]].append((sid, int(ctx.get("index", 1))))

    issues: list[str] = []
    warnings: list[str] = []
    for base, slides in by_base.items():
        slides.sort(key=lambda s: s[1])
        dims = {get_format_info(sid).width for sid, _ in slides}
        if len(dims) > 1:
            issues.append(f"{base}: slides have inconsistent canvas widths")
        total = len(slides)
        for sid, idx in slides:
            html = (state.get("format_tasks", {}).get(sid) or {}).get("html", "") or ""
            if f"{idx}/{total}" not in html:
                warnings.append(f"{sid}: no '{idx}/{total}' slide counter found")

    # Duplicate-media guard: the SAME image/SVG figure on 2+ slides is a hard
    # QC failure (the old one-photo-per-post bug). Signatures are the base64
    # data URIs embedded in each slide's HTML.
    media_by_sig: dict[str, list[str]] = defaultdict(list)
    for base, slides in by_base.items():
        for sid, _ in slides:
            html = (state.get("format_tasks", {}).get(sid) or {}).get("html", "") or ""
            for match in re.finditer(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', html):
                sig = match.group(1)[:64]
                media_by_sig[sig].append(sid)
    for sig, sids in media_by_sig.items():
        if len(sids) > 1:
            issues.append(
                f"Duplicate media detected across slides: {', '.join(sorted(sids))} "
                "share the same image — each slide must have distinct media"
            )

    result: dict = {
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
    }

    if state.get("sequence_audit") and by_base:
        vision = await _sequence_vision_audit(state, by_base)
        if vision:
            result["vision"] = vision
            result["ok"] = result["ok"] and bool(vision.get("pass", True))

    task_id = state.get("_task_id", "")
    if task_id:
        from app.services.audit import record_audit

        await record_audit(
            task_id,
            "sequence_check",
            decision={"ok": result["ok"], "issues": issues, "warnings": warnings},
            critique=result.get("vision", {}).get("critique", ""),
        )
    return result


async def _sequence_vision_audit(
    state: GenerationState, by_base: dict
) -> dict | None:
    """Render all carousel slide PNGs as one grid and audit once via vision."""
    import base64
    from pathlib import Path

    from app.config import get_settings
    from app.services.dom_extractor import render_to_png

    settings = get_settings()
    out_dir = Path(settings.output_dir) / (state.get("_task_id") or "")
    imgs: list[str] = []
    for base, slides in sorted(by_base.items()):
        for sid, _ in sorted(slides, key=lambda s: s[1]):
            png_path = out_dir / f"{sid}.png"
            if not png_path.is_file():
                continue
            b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
            imgs.append(
                f'<img src="data:image/png;base64,{b64}" '
                'style="height:280px;width:auto;border:1px solid #ddd">'
            )
    if not imgs:
        return None

    grid_html = (
        "<!DOCTYPE html><html><head><style>body{display:flex;flex-wrap:wrap;"
        "gap:12px;background:#fff;margin:0;padding:12px}</style></head>"
        f"<body>{''.join(imgs)}</body></html>"
    )
    rows = max(1, (len(imgs) + 2) // 3)
    composite = await render_to_png(grid_html, width=960, height=min(rows * 292 + 24, 6000))
    if not composite:
        return None

    from app.agents.orchestrator.nodes.quality_check import _call_vision_llm, _extract_json
    from app.services.agents import get_agent_config

    cfg = await get_agent_config("verifier")
    try:
        raw = await _call_vision_llm(
            cfg.system_prompt,
            "These are all the slides of ONE Instagram carousel post, shown as a "
            "set. Audit the SEQUENCE as a whole: is it cohesive, non-repetitive, "
            "and does it tell one story in order? "
            'Return ONLY valid JSON: {"pass": bool, "score": int, '
            '"issues": [...], "critique": "..."}',
            composite,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            model=cfg.model,
        )
        return _extract_json(raw)
    except Exception as e:
        log.warning("[sequence] vision audit failed: %s", e)
        return None


def _extract_slides(copy_json: str) -> list[dict]:
    """Parse a carousel copy JSON string into its slides list."""
    import json

    if not copy_json:
        return []
    try:
        data = json.loads(copy_json)
    except Exception:
        return []
    slides = data.get("slides") if isinstance(data, dict) else None
    if isinstance(slides, list):
        return [s for s in slides if isinstance(s, dict)]
    return []


def build_pipeline() -> StateGraph:
    workflow = StateGraph(GenerationState)

    workflow.add_node("strategist", strategist_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("copywriter", copywriter_node)
    workflow.add_node("process_all_formats", process_all_formats_node)

    workflow.set_entry_point("strategist")
    workflow.add_edge("strategist", "planner")
    workflow.add_edge("planner", "copywriter")
    workflow.add_edge("copywriter", "process_all_formats")
    workflow.add_edge("process_all_formats", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


pipeline = build_pipeline()


async def run_pipeline(
    input_data: dict,
    progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
) -> dict:
    state = initial_state(**input_data)
    config = {"configurable": {"thread_id": input_data.get("_task_id", "default")}}
    seen_progress = 0

    async for event in pipeline.astream_events(state, config, version="v2"):
        if event["event"] == "on_chain_start":
            event_name = event["name"]
            pct = NODE_PROGRESS.get(event_name)
            if pct and pct > seen_progress:
                seen_progress = pct
                if progress_callback:
                    label = NODE_LABELS.get(event_name, "Processing...")
                    await progress_callback(pct, label)

    try:
        state_result = pipeline.get_state(config)
        return state_result.values if state_result else state
    except Exception:
        return state
