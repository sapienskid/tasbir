"""Tests for v3 GenerationState — state schema, initial_state factory, merge logic."""

from app.agents.orchestrator.state import FormatTask, GenerationState, initial_state, merge_format_tasks


def test_initial_state_defaults():
    state = initial_state(title="Test Title", content="Test content.", platforms=["instagram-square"])
    assert state["title"] == "Test Title"
    assert state["content"] == "Test content."
    assert "instagram-square" in state["platforms"]
    assert state["_task_id"] == ""
    assert "instagram-square" in state["format_tasks"]
    assert state["format_tasks"]["instagram-square"]["status"] == "waiting"
    assert state["strategic_brief"] == {}
    assert state["design_tokens"] == {}


def test_initial_state_multiple_platforms():
    state = initial_state(
        title="Test",
        content="Content",
        platforms=["instagram-square", "linkedin-post", "twitter-card"],
    )
    assert len(state["format_tasks"]) == 3
    for fmt_id in ["instagram-square", "linkedin-post", "twitter-card"]:
        assert fmt_id in state["format_tasks"]
        assert state["format_tasks"][fmt_id]["status"] == "waiting"
        assert state["format_tasks"][fmt_id]["copy"] == ""


def test_initial_state_with_task_id():
    state = initial_state(title="T", content="C", platforms=["instagram-square"], _task_id="abc-123")
    assert state["_task_id"] == "abc-123"


def test_initial_state_with_design_tokens():
    tokens = {"--color-bg": "#0f172a", "--color-text": "#ffffff"}
    state = initial_state(title="T", content="C", platforms=["instagram-square"], design_tokens=tokens)
    assert state["design_tokens"]["--color-bg"] == "#0f172a"


def test_initial_state_with_source_url():
    state = initial_state(title="T", content="C", platforms=["instagram-square"], source_url="https://example.com")
    assert state["source_url"] == "https://example.com"


def test_format_task_structure():
    task = FormatTask(
        status="html_ready",
        copy='{"headline": "Test"}',
        html="<html><body>test</body></html>",
        penpot_file_path=None,
        quality_score=0,
        quality_issues=[],
        refinement_count=0,
        error=None,
    )
    assert task["status"] == "html_ready"
    assert task["html"] is not None
    assert task["quality_score"] == 0


def test_merge_format_tasks_update():
    a = {
        "fmt1": FormatTask(
            status="waiting", copy="", html=None, penpot_file_path=None,
            quality_score=0, quality_issues=[], refinement_count=0, error=None,
        )
    }
    b = {
        "fmt1": FormatTask(
            status="html_ready", copy='{"headline": "H"}', html="<html>", penpot_file_path=None,
            quality_score=0, quality_issues=[], refinement_count=0, error=None,
        )
    }
    merged = merge_format_tasks(a, b)
    assert merged["fmt1"]["status"] == "html_ready"
    assert merged["fmt1"]["copy"] == '{"headline": "H"}'


def test_merge_format_tasks_disjoint():
    a = {
        "fmt1": FormatTask(
            status="html_ready", copy="C1", html="<h1>", penpot_file_path=None,
            quality_score=50, quality_issues=[], refinement_count=0, error=None,
        )
    }
    b = {
        "fmt2": FormatTask(
            status="penpot_ready", copy="C2", html="<h2>", penpot_file_path="/path/f2.penpot",
            quality_score=95, quality_issues=[], refinement_count=0, error=None,
        )
    }
    merged = merge_format_tasks(a, b)
    assert "fmt1" in merged
    assert "fmt2" in merged
    assert merged["fmt1"]["copy"] == "C1"
    assert merged["fmt2"]["penpot_file_path"] == "/path/f2.penpot"
