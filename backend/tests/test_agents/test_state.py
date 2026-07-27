"""Tests for the agent state machine."""

from app.agents.orchestrator.state import FormatTask, GenerationState, initial_state, merge_format_tasks


def test_initial_state_defaults():
    state = initial_state(
        title="Test Title",
        content="Test content here.",
        requested_formats=["instagram-square", "linkedin-post"],
    )

    assert state["title"] == "Test Title"
    assert state["content"] == "Test content here."
    assert "instagram-square" in state["requested_formats"]
    assert state["quality_score"] == 0
    assert state["refinement_count"] == 0
    assert state["max_refinements"] == 2
    assert state["_task_id"] == ""
    assert "instagram-square" in state["format_tasks"]
    assert "linkedin-post" in state["format_tasks"]
    assert state["format_tasks"]["instagram-square"]["status"] == "waiting"
    assert state["format_tasks"]["linkedin-post"]["copy"] == ""


def test_initial_state_with_optional_params():
    state = initial_state(
        title="Test",
        content="Content",
        requested_formats=["twitter-card"],
        brand={"name": "TestBrand", "tone": "energetic"},
        campaign={"id": "camp-1"},
        excerpt="Short excerpt",
        tags=["tech", "ai"],
        _task_id="abc-123",
    )

    assert state["brand"]["name"] == "TestBrand"
    assert state["campaign"]["id"] == "camp-1"
    assert state["excerpt"] == "Short excerpt"
    assert "tech" in state["tags"]
    assert state["_task_id"] == "abc-123"


def test_initial_state_type():
    state = initial_state(title="T", content="C", requested_formats=["f"])
    assert isinstance(state, dict)
    assert "strategic_brief" in state
    assert "format_tasks" in state
    assert "_processing_format_id" in state


def test_format_task_structure():
    task = FormatTask(
        status="done",
        copy="HEADLINE: Test\n",
        background={"css": "background: red;", "name": "solid"},
        html="<html></html>",
        png_url="https://example.com/img.png",
        quality_score=85,
        quality_issues=[],
        refinement_count=1,
        error=None,
    )
    assert task["status"] == "done"
    assert task["png_url"] == "https://example.com/img.png"
    assert task["quality_score"] == 85


def test_merge_format_tasks():
    a = {"fmt1": FormatTask(status="waiting", copy="", background={}, html=None, png_url=None, quality_score=0, quality_issues=[], refinement_count=0, error=None)}
    b = {"fmt1": FormatTask(status="done", copy="HEADLINE", background={}, html="<html>", png_url="https://img", quality_score=95, quality_issues=[], refinement_count=1, error=None)}
    merged = merge_format_tasks(a, b)
    assert merged["fmt1"]["status"] == "done"
    assert merged["fmt1"]["copy"] == "HEADLINE"


def test_merge_format_tasks_disjoint():
    a = {"fmt1": FormatTask(status="designed", copy="C1", background={}, html="<h1>", png_url=None, quality_score=50, quality_issues=[], refinement_count=0, error=None)}
    b = {"fmt2": FormatTask(status="done", copy="C2", background={}, html="<h2>", png_url="https://img2", quality_score=95, quality_issues=[], refinement_count=0, error=None)}
    merged = merge_format_tasks(a, b)
    assert "fmt1" in merged
    assert "fmt2" in merged
    assert merged["fmt1"]["copy"] == "C1"
    assert merged["fmt2"]["copy"] == "C2"
