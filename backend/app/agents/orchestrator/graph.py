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
from collections.abc import Awaitable, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.nodes.designer import designer_node_single
from app.agents.orchestrator.nodes.quality_check import MAX_RETRIES, quality_check_node_single
from app.agents.orchestrator.nodes.renderer import renderer_node_single
from app.agents.orchestrator.nodes.strategist import strategist_node
from app.agents.orchestrator.nodes.template_renderer import template_node_single
from app.agents.orchestrator.state import GenerationState, initial_state

log = logging.getLogger(__name__)

NODE_PROGRESS: dict[str, int] = {
    "strategist": 10,
    "copywriter": 25,
    "process_all_formats": 50,
}

NODE_LABELS: dict[str, str] = {
    "strategist": "Analyzing content...",
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

    use_template = True
    for _attempt in range(MAX_RETRIES + 1):
        if use_template:
            _apply_updates(local, await template_node_single(local))

        fmt_task = local.get("format_tasks", {}).get(fmt_id, {})
        if not fmt_task.get("html"):
            # No template matched (or copy missing) → LLM designer.
            _apply_updates(local, await designer_node_single(local))

        _apply_updates(local, await renderer_node_single(local))
        _apply_updates(local, await quality_check_node_single(local))

        fmt_task = local.get("format_tasks", {}).get(fmt_id, {})
        status = fmt_task.get("status", "")
        if status in ("verified", "error", "failed"):
            break
        if status == "needs_retry":
            if use_template:
                # Chosen template failed QC (e.g. overflow) → LLM designer.
                use_template = False
                fmt_task["html"] = None
                fmt_task.pop("template_id", None)
                continue
            if _attempt >= MAX_RETRIES:
                break

    return {
        "format_tasks": {fmt_id: local["format_tasks"].get(fmt_id, {})},
        "verification": {fmt_id: local["verification"].get(fmt_id, {})},
        "retry_count": {fmt_id: local["retry_count"].get(fmt_id, 0)},
    }


async def process_all_formats_node(state: GenerationState) -> dict:
    """Run the full per-format chain for every platform in parallel.

    Each branch is isolated and merges its slice back deterministically,
    so the final state always reflects every format's real status.
    """
    import asyncio

    platforms = state.get("platforms", [])
    log.info("[graph] Processing %d format(s) in parallel", len(platforms))

    results = await asyncio.gather(
        *(_run_format_chain(state, fmt_id) for fmt_id in platforms)
    )

    format_tasks = {}
    verification = {}
    retry_count = {}
    for r in results:
        format_tasks.update(r.get("format_tasks", {}))
        verification.update(r.get("verification", {}))
        retry_count.update(r.get("retry_count", {}))

    return {
        "format_tasks": format_tasks,
        "verification": verification,
        "retry_count": retry_count,
    }


def build_pipeline() -> StateGraph:
    workflow = StateGraph(GenerationState)

    workflow.add_node("strategist", strategist_node)
    workflow.add_node("copywriter", copywriter_node)
    workflow.add_node("process_all_formats", process_all_formats_node)

    workflow.set_entry_point("strategist")
    workflow.add_edge("strategist", "copywriter")
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
