"""LangGraph state machine for the generation pipeline with sequential agent execution.

Defines the agent workflow as a directed graph:
  strategist → copywriter → visual_director → designer → quality_check → renderer → END
                                                                ↓ (refinement loop)
                                                            designer

Each agent reads from shared state, enabling proper hand-off:
- copywriter receives strategic_brief from strategist
- visual_director receives copy_by_format from copywriter
- designer receives copy + backgrounds from both upstream agents
Quality check passes/fails; renderer converts HTML to PNG.
"""

from collections.abc import Awaitable, Callable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.nodes.designer import designer_node
from app.agents.orchestrator.nodes.quality_check import quality_check_node
from app.agents.orchestrator.nodes.renderer import renderer_node
from app.agents.orchestrator.nodes.strategist import strategist_node
from app.agents.orchestrator.nodes.visual_director import visual_director_node
from app.agents.orchestrator.state import GenerationState, initial_state

NODE_PROGRESS: dict[str, int] = {
    "strategist": 15,
    "copywriter": 35,
    "visual_director": 55,
    "designer": 70,
    "quality_check": 85,
    "renderer": 95,
}


def after_quality(state: GenerationState) -> str:
    if state["quality_score"] >= 50:
        return "renderer"
    if state["refinement_count"] < state["max_refinements"]:
        return "designer"
    return END


def build_pipeline() -> StateGraph:
    workflow = StateGraph(GenerationState)

    workflow.add_node("strategist", strategist_node)
    workflow.add_node("copywriter", copywriter_node)
    workflow.add_node("visual_director", visual_director_node)
    workflow.add_node("designer", designer_node)
    workflow.add_node("quality_check", quality_check_node)
    workflow.add_node("renderer", renderer_node)

    workflow.set_entry_point("strategist")

    workflow.add_edge("strategist", "copywriter")
    workflow.add_edge("copywriter", "visual_director")
    workflow.add_edge("visual_director", "designer")
    workflow.add_edge("designer", "quality_check")
    workflow.add_conditional_edges("quality_check", after_quality)
    workflow.add_edge("renderer", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


pipeline = build_pipeline()


async def run_pipeline(
    input_data: dict,
    progress_callback: Callable[[int], Awaitable[None]] | None = None,
) -> dict:
    state = initial_state(**input_data)
    config = {"configurable": {"thread_id": input_data.get("_task_id", "default")}}
    seen_progress = 0

    async for event in pipeline.astream_events(state, config, version="v2"):
        if event["event"] == "on_chain_start":
            node = event["name"]
            pct = NODE_PROGRESS.get(node)
            if pct and pct > seen_progress:
                seen_progress = pct
                if progress_callback:
                    await progress_callback(pct)

    result = pipeline.get_state(config).values
    return result
