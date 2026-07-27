"""Edge case tests for the LangGraph pipeline routing.

These tests verify edge cases in state transitions, quality scoring,
the refinement loop, and per-format streaming fan-out.
"""

import pytest
from app.agents.orchestrator.graph import after_quality_single, build_pipeline, fan_out_to_formats
from app.agents.orchestrator.state import GenerationState, initial_state
from langgraph.graph import END
from langgraph.types import Send


class TestAfterQualitySingleEdgeCases:
    _fmt = "instagram-square"

    def _state(self) -> GenerationState:
        s = initial_state(title="Test", content="Content", requested_formats=[self._fmt])
        s["_processing_format_id"] = self._fmt
        return s

    def test_perfect_score(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 100
        assert after_quality_single(state) == "renderer"

    def test_barely_passing_score(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 50
        assert after_quality_single(state) == "renderer"

    def test_barely_failing_score(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 49
        state["format_tasks"][self._fmt]["refinement_count"] = 0
        state["max_refinements"] = 2
        assert after_quality_single(state) == "designer"

    def test_zero_score_with_refinements_left(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 0
        state["format_tasks"][self._fmt]["refinement_count"] = 1
        state["max_refinements"] = 2
        assert after_quality_single(state) == "designer"

    def test_zero_score_no_refinements_left(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 0
        state["format_tasks"][self._fmt]["refinement_count"] = 2
        assert after_quality_single(state) == END

    def test_first_refinement_loop(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 30
        state["format_tasks"][self._fmt]["refinement_count"] = 0
        state["max_refinements"] = 2
        assert after_quality_single(state) == "designer"

    def test_exhausted_refinements_fails_to_end(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 30
        state["format_tasks"][self._fmt]["refinement_count"] = 2
        state["max_refinements"] = 2
        assert after_quality_single(state) == END

    def test_negative_score(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = -10
        state["format_tasks"][self._fmt]["refinement_count"] = 0
        state["max_refinements"] = 2
        assert after_quality_single(state) == "designer"

    def test_max_int_score(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 999999
        assert after_quality_single(state) == "renderer"

    def test_zero_refinements_maxed(self):
        state = self._state()
        state["format_tasks"][self._fmt]["quality_score"] = 50
        state["format_tasks"][self._fmt]["refinement_count"] = 0
        state["max_refinements"] = 0
        assert after_quality_single(state) == "renderer"


class TestFanOutEdgeCases:
    def test_fan_out_single_format(self):
        state = initial_state(title="T", content="C", requested_formats=["fmt1"])
        sends = fan_out_to_formats(state)
        assert len(sends) == 1
        assert sends[0].arg["_processing_format_id"] == "fmt1"

    def test_fan_out_many_formats(self):
        state = initial_state(title="T", content="C", requested_formats=["a", "b", "c", "d", "e"])
        sends = fan_out_to_formats(state)
        assert len(sends) == 5
        assert all(s.node == "process_format" for s in sends)

    def test_fan_out_empty(self):
        state = initial_state(title="T", content="C", requested_formats=[])
        sends = fan_out_to_formats(state)
        assert len(sends) == 0


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

    def test_default_format_tasks(self):
        state = initial_state(title="Title", content="Content", requested_formats=["instagram-square"])
        assert "format_tasks" in state
        assert "instagram-square" in state["format_tasks"]
        assert state["format_tasks"]["instagram-square"]["status"] == "waiting"
        assert state["format_tasks"]["instagram-square"]["copy"] == ""

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
        expected = {"strategist", "copywriter", "visual_director", "process_format"}
        for name in expected:
            assert name in node_names

    def test_pipeline_entry_point(self):
        graph = build_pipeline()
        assert "strategist" in graph.nodes

    def test_pipeline_is_compiled(self):
        """The pipeline should compile without errors."""
        graph = build_pipeline()
        assert graph is not None
        assert hasattr(graph, "invoke") or hasattr(graph, "astream_events")

    def test_pipeline_with_checkpointer(self):
        graph = build_pipeline()
        assert graph.checkpointer is not None
