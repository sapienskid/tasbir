"""Tests for LangGraph pipeline configuration and parallel execution routing."""

import pytest
from app.agents.orchestrator.graph import after_quality, build_pipeline, pipeline
from app.agents.orchestrator.state import initial_state
from langgraph.graph import END


def test_graph_nodes_and_edges():
    graph = build_pipeline()
    nodes = graph.nodes
    assert "strategist" in nodes
    assert "copywriter" in nodes
    assert "visual_director" in nodes
    assert "designer" in nodes
    assert "quality_check" in nodes
    assert "renderer" in nodes


def test_after_quality_decisions():
    state_pass = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square"]
    )
    state_pass["quality_score"] = 85
    assert after_quality(state_pass) == "renderer"

    state_fail_refine = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square"]
    )
    state_fail_refine["quality_score"] = 30
    state_fail_refine["refinement_count"] = 1
    state_fail_refine["max_refinements"] = 2
    assert after_quality(state_fail_refine) == "designer"

    state_fail_max = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square"]
    )
    state_fail_max["quality_score"] = 30
    state_fail_max["refinement_count"] = 2
    state_fail_max["max_refinements"] = 2
    assert after_quality(state_fail_max) == END
