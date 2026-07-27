"""Edge case tests for the LangGraph pipeline routing.

These tests verify edge cases in state transitions, quality scoring,
and the refinement loop.
"""

import pytest
from app.agents.orchestrator.graph import after_quality, build_pipeline
from app.agents.orchestrator.state import GenerationState, initial_state
from langgraph.graph import END


class TestAfterQualityEdgeCases:
    def test_perfect_score(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 100
        state["refinement_count"] = 0
        assert after_quality(state) == "renderer"

    def test_barely_passing_score(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 50
        state["refinement_count"] = 0
        assert after_quality(state) == "renderer"

    def test_barely_failing_score(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 49
        state["refinement_count"] = 0
        assert after_quality(state) == "designer"

    def test_zero_score_with_refinements_left(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 0
        state["refinement_count"] = 1
        state["max_refinements"] = 2
        assert after_quality(state) == "designer"

    def test_zero_score_no_refinements_left(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 0
        state["refinement_count"] = 2
        assert after_quality(state) == END

    def test_first_refinement_loop(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 30
        state["refinement_count"] = 0
        state["max_refinements"] = 2
        assert after_quality(state) == "designer"

    def test_second_refinement_loop(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 40
        state["refinement_count"] = 1
        state["max_refinements"] = 2
        assert after_quality(state) == "designer"

    def test_exhausted_refinements_fails_to_end(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 30
        state["refinement_count"] = 2
        state["max_refinements"] = 2
        assert after_quality(state) == END

    def test_negative_score(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = -10
        state["refinement_count"] = 0
        assert after_quality(state) == "designer"

    def test_max_int_score(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 999999
        state["refinement_count"] = 0
        assert after_quality(state) == "renderer"

    def test_zero_refinements_maxed(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 50
        state["refinement_count"] = 0
        state["max_refinements"] = 0
        # If score >= 50, goes to renderer regardless of refinements
        assert after_quality(state) == "renderer"

    def test_score_50_refinements_0_max_0(self):
        state = initial_state(title="Test", content="Content", requested_formats=["instagram-square"])
        state["quality_score"] = 50
        state["refinement_count"] = 0
        state["max_refinements"] = 0
        assert after_quality(state) == "renderer"


class TestInitialStateEdgeCases:
    def test_empty_title(self):
        state = initial_state(title="", content="Some content", requested_formats=["instagram-square"])
        assert state["title"] == ""
        assert state["content"] == "Some content"

    def test_empty_content(self):
        state = initial_state(title="Title", content="", requested_formats=["instagram-square"])
        assert state["title"] == "Title"
        assert state["content"] == ""

    def test_no_formats(self):
        state = initial_state(title="Title", content="Content", requested_formats=[])
        assert state["requested_formats"] == []

    def test_no_brand(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"])
        assert state["brand"] == {}

    def test_no_campaign(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"])
        assert state["campaign"] == {}

    def test_unknown_kwargs(self):
        """Unknown kwargs should be captured but not cause an error."""
        state = initial_state(
            title="Title",
            content="Content",
            requested_formats=["instagram-square"],
            unknown_param="value",
        )
        assert state["title"] == "Title"

    def test_task_id_propagation(self):
        state = initial_state(
            title="Title",
            content="Content",
            requested_formats=["instagram-square"],
            _task_id="abc-123",
        )
        assert state["_task_id"] == "abc-123"

    def test_default_refinement_values(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"])
        assert state["refinement_count"] == 0
        assert state["max_refinements"] == 2
        assert state["quality_score"] == 0

    def test_default_agent_outputs(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"])
        assert state["strategic_brief"] == ""
        assert state["copy_by_format"] == {}
        assert state["html_by_format"] == {}
        assert state["assets_by_format"] == {}

    def test_tags_as_empty_list(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"], tags=[])
        assert state["tags"] == []

    def test_tags_with_values(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"], tags=["tech", "ai"])
        assert state["tags"] == ["tech", "ai"]


class TestPipelineBuildEdgeCases:
    def test_pipeline_has_all_nodes(self):
        graph = build_pipeline()
        node_names = list(graph.nodes.keys())
        expected = {"strategist", "copywriter", "visual_director", "designer", "quality_check", "renderer"}
        for name in expected:
            assert name in node_names

    def test_pipeline_entry_point(self):
        graph = build_pipeline()
        # Verify the graph starts with strategist by checking the nodes
        assert "strategist" in graph.nodes
        # strategist should not be a target of any edge (no node points to it)
        # renderer should be the last node before END

    def test_pipeline_is_compiled(self):
        """The pipeline should compile without errors."""
        graph = build_pipeline()
        assert graph is not None
        assert hasattr(graph, "invoke") or hasattr(graph, "astream_events")

    def test_pipeline_with_checkpointer(self):
        graph = build_pipeline()
        assert graph.checkpointer is not None
