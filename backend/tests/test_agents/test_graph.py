"""Tests for v3 LangGraph pipeline — graph topology and routing logic."""

import pytest
from langgraph.graph import END
from langgraph.types import Send

from app.agents.orchestrator.graph import after_verifier, build_pipeline, fan_out_to_formats
from app.agents.orchestrator.state import GenerationState, initial_state


def test_graph_has_required_nodes():
    """Pipeline must have strategist, copywriter, and process_format nodes."""
    graph = build_pipeline()
    nodes = graph.nodes
    assert "strategist" in nodes
    assert "copywriter" in nodes
    assert "process_format" in nodes


def test_after_verifier_pass():
    """after_verifier returns END when verification passes."""
    state = initial_state(title="Test", content="Content", platforms=["instagram-square"])
    state["_processing_format_id"] = "instagram-square"
    state["verification"] = {"instagram-square": {"pass": True, "score": 90}}
    assert after_verifier(state) == END


def test_after_verifier_fail_retry():
    """after_verifier returns 'designer' when verification fails and retries < 2."""
    state = initial_state(title="Test", content="Content", platforms=["instagram-square"])
    state["_processing_format_id"] = "instagram-square"
    state["verification"] = {"instagram-square": {"pass": False, "score": 40}}
    state["retry_count"] = {"instagram-square": 0}
    assert after_verifier(state) == "designer"


def test_after_verifier_fail_max_retries():
    """after_verifier returns END when retry limit (2) is reached."""
    state = initial_state(title="Test", content="Content", platforms=["instagram-square"])
    state["_processing_format_id"] = "instagram-square"
    state["verification"] = {"instagram-square": {"pass": False, "score": 30}}
    state["retry_count"] = {"instagram-square": 2}
    assert after_verifier(state) == END


def test_fan_out_to_formats_single_platform():
    """fan_out_to_formats creates one Send per platform."""
    state = initial_state(title="T", content="C", platforms=["instagram-square"])
    sends = fan_out_to_formats(state)
    assert len(sends) == 1
    assert isinstance(sends[0], Send)
    assert sends[0].node == "process_format"
    assert sends[0].arg["_processing_format_id"] == "instagram-square"


def test_fan_out_to_formats_multiple_platforms():
    """fan_out_to_formats creates one Send per platform for multiple platforms."""
    state = initial_state(title="T", content="C", platforms=["instagram-square", "linkedin-post", "twitter-card"])
    sends = fan_out_to_formats(state)
    assert len(sends) == 3
    platform_ids = {s.arg["_processing_format_id"] for s in sends}
    assert platform_ids == {"instagram-square", "linkedin-post", "twitter-card"}


def test_fan_out_preserves_state():
    """fan_out_to_formats passes full state to each Send."""
    state = initial_state(title="My Article", content="Content here", platforms=["instagram-square"])
    state["strategic_brief"] = {"angle": "Test angle"}
    sends = fan_out_to_formats(state)
    assert sends[0].arg["strategic_brief"]["angle"] == "Test angle"
    assert sends[0].arg["title"] == "My Article"
