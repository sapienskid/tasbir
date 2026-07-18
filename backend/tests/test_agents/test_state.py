"""Tests for the agent state machine."""

from app.agents.orchestrator.state import GenerationState, initial_state


def test_initial_state_defaults():
    state = initial_state(
        title="Test Title",
        content="Test content here.",
        requested_formats=["instagram-square", "linkedin-post"],
    )

    assert state["title"] == "Test Title"
    assert state["content"] == "Test content here."
    assert "instagram-square" in state["requested_formats"]
    assert state["next_node"] == "strategist"
    assert state["quality_score"] == 0
    assert state["refinement_count"] == 0
    assert state["max_refinements"] == 2
    assert state["messages"] == []
    assert state["_task_id"] == ""


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
    assert "copy_by_format" in state
    assert "html_by_format" in state
    assert "assets_by_format" in state
