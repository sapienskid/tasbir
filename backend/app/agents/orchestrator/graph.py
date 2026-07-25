"""LangGraph state machine for the generation pipeline.

Defines the agent workflow as a directed graph with 6 nodes:
    strategist → copywriter → visual_director → designer → quality_check
                                                              ↓
                                                         renderer (always runs if quality passes)
                                                              ↓
                                                             END

The quality_check node can loop back to designer for refinements.
The renderer node always runs after quality passes — deterministic,
not dependent on the LLM calling any tools.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.nodes.designer import designer_node
from app.agents.orchestrator.nodes.quality_check import quality_check_node
from app.agents.orchestrator.nodes.renderer import renderer_node
from app.agents.orchestrator.nodes.strategist import strategist_node
from app.agents.orchestrator.nodes.visual_director import visual_director_node
from app.agents.orchestrator.state import GenerationState, initial_state


def after_quality(state: GenerationState) -> str:
    """Decide next step after quality check.

    - If quality passes (>= 50): render assets, then finish
    - If quality fails but refinements remain: loop to designer
    - If quality fails and no refinements left: finish without rendering
    """
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


import asyncio


async def run_pipeline(input_data: dict) -> dict:
    state = initial_state(**input_data)
    config = {"configurable": {"thread_id": input_data.get("_task_id", "default")}}
    result = await asyncio.wait_for(
        pipeline.ainvoke(state, config),
        timeout=300,
    )
    return result
