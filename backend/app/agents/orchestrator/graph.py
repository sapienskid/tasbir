"""LangGraph state machine for the v3 generation pipeline.

Topology (5 nodes):
  strategist → copywriter → designer → html_to_penpot → verifier
                                                     ↓
                                              [fail+retry<2] → designer

Copywriter and Designer use Send fan-out per platform.
HTML→Penpot and Verifier run per-platform (no LLM, fast).
"""

from collections.abc import Awaitable, Callable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.agents.orchestrator.nodes.strategist import strategist_node
from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.nodes.designer import designer_node_single
from app.agents.orchestrator.nodes.quality_check import quality_check_node_single
from app.agents.orchestrator.nodes.renderer import renderer_node_single
from app.agents.orchestrator.state import GenerationState, initial_state

NODE_PROGRESS: dict[str, int] = {
    "strategist": 10,
    "copywriter": 25,
    "process_format:designer": 50,
    "process_format:html_to_penpot": 75,
    "process_format:verifier": 90,
}

NODE_LABELS: dict[str, str] = {
    "strategist": "Analyzing content...",
    "copywriter": "Writing copy...",
    "process_format:designer": "Designing layouts...",
    "process_format:html_to_penpot": "Converting to Penpot...",
    "process_format:verifier": "Verifying quality...",
}


def after_verifier(state: GenerationState) -> str:
    fmt_id = state["_processing_format_id"]
    task = state["format_tasks"].get(fmt_id, {})
    verification = state.get("verification", {}).get(fmt_id, {})
    if verification.get("pass", True):
        return END
    retries = state.get("retry_count", {}).get(fmt_id, 0)
    if retries < 2:
        return "designer"
    return END


def fan_out_to_formats(state: GenerationState) -> list[Send]:
    return [
        Send("process_format", {**state, "_processing_format_id": fmt_id})
        for fmt_id in state["platforms"]
    ]


def build_format_subgraph() -> StateGraph:
    subgraph = StateGraph(GenerationState)
    subgraph.add_node("designer", designer_node_single)
    subgraph.add_node("html_to_penpot", renderer_node_single)
    subgraph.add_node("verifier", quality_check_node_single)

    subgraph.set_entry_point("designer")
    subgraph.add_edge("designer", "html_to_penpot")
    subgraph.add_edge("html_to_penpot", "verifier")
    subgraph.add_conditional_edges("verifier", after_verifier)

    return subgraph.compile()


def build_pipeline() -> StateGraph:
    workflow = StateGraph(GenerationState)

    workflow.add_node("strategist", strategist_node)
    workflow.add_node("copywriter", copywriter_node)
    workflow.add_node("process_format", build_format_subgraph())

    workflow.set_entry_point("strategist")
    workflow.add_edge("strategist", "copywriter")
    workflow.add_conditional_edges("copywriter", fan_out_to_formats)

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
            if not pct:
                for key in NODE_PROGRESS:
                    if event_name.startswith(key.split(":")[-1]):
                        pct = NODE_PROGRESS[key]
                        event_name = key
                        break
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
