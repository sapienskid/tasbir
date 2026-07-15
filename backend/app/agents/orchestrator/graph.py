"""LangGraph state machine for the generation pipeline.

Defines the agent workflow as a directed graph with 5 nodes:
    strategist → copywriter → visual_director → designer → quality_check

The quality_check node can loop back to designer for refinements.
"""

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.orchestrator.state import GenerationState, initial_state
from app.agents.orchestrator.nodes.strategist import strategist_node
from app.agents.orchestrator.nodes.copywriter import copywriter_node
from app.agents.orchestrator.nodes.visual_director import visual_director_node
from app.agents.orchestrator.nodes.designer import designer_node
from app.agents.orchestrator.nodes.quality_check import quality_check_node


def should_refine(state: GenerationState) -> str:
    """Decide whether to refine or finish.

    If quality check failed and refinements remain, loop to designer.
    Otherwise, proceed to END.
    """
    if (
        state["quality_score"] < 70
        and state["refinement_count"] < state["max_refinements"]
    ):
        return "designer"
    return END


def build_pipeline() -> StateGraph:
    """Build the generation pipeline state graph."""
    workflow = StateGraph(GenerationState)

    workflow.add_node("strategist", strategist_node)
    workflow.add_node("copywriter", copywriter_node)
    workflow.add_node("visual_director", visual_director_node)
    workflow.add_node("designer", designer_node)
    workflow.add_node("quality_check", quality_check_node)

    workflow.set_entry_point("strategist")

    workflow.add_edge("strategist", "copywriter")
    workflow.add_edge("copywriter", "visual_director")
    workflow.add_edge("visual_director", "designer")
    workflow.add_edge("designer", "quality_check")
    workflow.add_conditional_edges("quality_check", should_refine)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Compiled graph instance
pipeline = build_pipeline()


async def run_pipeline(input_data: dict) -> dict:
    """Run the generation pipeline with the given input.

    Args:
        input_data: Dictionary matching GenerationState fields
            (title, content, requested_formats, brand, etc.)

    Returns:
        The final state with all agent outputs populated.
    """
    state = initial_state(**input_data)
    config = {"configurable": {"thread_id": input_data.get("task_id", "default")}}
    result = await pipeline.ainvoke(state, config)
    return result
