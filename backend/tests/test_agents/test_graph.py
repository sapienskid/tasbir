"""Tests for LangGraph pipeline configuration and per-format streaming routing."""

import pytest
from app.agents.orchestrator.graph import after_quality_single, build_pipeline, fan_out_to_formats, pipeline
from app.agents.orchestrator.nodes.quality_check import (
    _check_agent_name_leak,
    _check_canvas_dimensions,
    _check_overflow_hidden,
    _check_background_present,
    _check_visible_text,
    _check_placeholders,
)
from app.agents.orchestrator.state import FormatTask, GenerationState, initial_state
from langgraph.graph import END
from langgraph.types import Send


def test_graph_nodes_and_edges():
    graph = build_pipeline()
    nodes = graph.nodes
    assert "strategist" in nodes
    assert "copywriter" in nodes
    assert "visual_director" in nodes
    assert "process_format" in nodes


def test_after_quality_single_decisions():
    state_pass = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square"]
    )
    state_pass["_processing_format_id"] = "instagram-square"
    state_pass["format_tasks"]["instagram-square"]["quality_score"] = 85
    assert after_quality_single(state_pass) == "renderer"

    state_fail_refine = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square"]
    )
    state_fail_refine["_processing_format_id"] = "instagram-square"
    state_fail_refine["format_tasks"]["instagram-square"]["quality_score"] = 30
    state_fail_refine["format_tasks"]["instagram-square"]["refinement_count"] = 1
    state_fail_refine["max_refinements"] = 2
    assert after_quality_single(state_fail_refine) == "designer"

    state_fail_max = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square"]
    )
    state_fail_max["_processing_format_id"] = "instagram-square"
    state_fail_max["format_tasks"]["instagram-square"]["quality_score"] = 30
    state_fail_max["format_tasks"]["instagram-square"]["refinement_count"] = 2
    state_fail_max["max_refinements"] = 2
    assert after_quality_single(state_fail_max) == END


def test_fan_out_to_formats_returns_send_list():
    state = initial_state(
        title="Test", content="Content", requested_formats=["instagram-square", "linkedin-post"]
    )
    sends = fan_out_to_formats(state)
    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)
    assert sends[0].node == "process_format"
    assert sends[1].node == "process_format"
    assert sends[0].arg["_processing_format_id"] == "instagram-square"
    assert sends[1].arg["_processing_format_id"] == "linkedin-post"


# ── Quality Check deterministic checks ─────────────────────────────────────

def test_quality_check_visible_text_fails_on_empty():
    assert _check_visible_text("<html><body></body></html>") is True


def test_quality_check_visible_text_passes_with_content():
    assert _check_visible_text("<html><body><h1>Hello world this is content</h1></body></html>") is False


def test_quality_check_agent_name_leak_detected():
    assert _check_agent_name_leak("<p>Designed by Marcus Chen</p>") is True


def test_quality_check_agent_name_leak_clean():
    assert _check_agent_name_leak("<p>Designed by our studio</p>") is False


def test_quality_check_canvas_dimensions_found():
    html = '<body style="width: 1080px; height: 1080px;">content</body>'
    # check returns True on FAILURE (dims missing), False on pass (dims present)
    assert _check_canvas_dimensions(html, 1080, 1080) is False


def test_quality_check_canvas_dimensions_missing():
    html = '<body style="width: 100%;">content</body>'
    assert _check_canvas_dimensions(html, 1080, 1080) is True


def test_quality_check_overflow_hidden_passes():
    html = '<body style="overflow: hidden;">content</body>'
    assert _check_overflow_hidden(html) is False


def test_quality_check_overflow_hidden_fails():
    html = '<body style="overflow: visible;">content</body>'
    assert _check_overflow_hidden(html) is True


def test_quality_check_background_present_passes():
    html = '<body style="background: linear-gradient(...);">content</body>'
    assert _check_background_present(html) is False


def test_quality_check_background_missing_fails():
    html = '<body style="color: red;">content</body>'
    assert _check_background_present(html) is True


def test_quality_check_placeholders_detected():
    html = "<div>Hello {{ name }}</div>"
    assert _check_placeholders(html) is True


def test_quality_check_placeholders_clean():
    html = "<div>Hello World</div>"
    assert _check_placeholders(html) is False
