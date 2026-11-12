import json
from unittest.mock import AsyncMock, patch

from app.agents.orchestrator.graph import _run_format_chain, _run_publish_gate, _run_sequence_check
from app.agents.orchestrator.nodes.copywriter import _write_copy_for_platform
from app.agents.orchestrator.nodes.planner import planner_node
from app.agents.orchestrator.state import initial_state
from app.services.agents import get_agent_config


async def test_pinned_structure_survives_conflicting_model_plan():
    state = initial_state(
        "Practice",
        "Daily practice improves retention.",
        ["instagram-carousel"],
        slides=4,
        ratio="auto",
    )
    llm = AsyncMock(
        return_value=json.dumps({"post_type": "single", "slides": 0, "platforms": ["twitter-card"]})
    )
    with patch("app.agents.orchestrator.nodes.planner.call_llm", llm):
        out = await planner_node(state)
    assert out["platforms"] == ["instagram-carousel"]
    assert out["slides"] == 4
    assert len(out["post_plan"]["slides_outline"]) == 4


async def test_copy_candidates_change_actual_carousel_cover_and_keep_pins():
    source = "Daily practice improves retention. Short sessions support a daily routine."
    response = {
        "headline": "Original",
        "subhead": "",
        "body": "",
        "slides": [
            {"headline": "Cover", "subhead": "", "body": "Daily practice helps."},
            {"headline": "A daily routine", "subhead": "", "body": "Keep sessions short."},
        ],
        "hook_candidates": [
            {
                "headline": "Daily practice improves retention",
                "angle": "finding",
                "source_support": "Daily practice improves retention.",
                "specificity": 5,
                "relevance": 5,
                "faithfulness": 5,
            }
        ],
    }
    cfg = await get_agent_config("copywriter")
    mock = AsyncMock(return_value=json.dumps(response))
    with patch("app.agents.orchestrator.nodes.copywriter.call_llm", mock):
        _, copy = await _write_copy_for_platform(
            "instagram-carousel", {}, source, "Practice", cfg, slides_count=2
        )
        _, pinned = await _write_copy_for_platform(
            "instagram-carousel",
            {},
            source,
            "Practice",
            cfg,
            slides_count=2,
            overrides={"headline": "Pinned title"},
        )
    assert copy.slides[0].headline == "Daily practice improves retention"
    assert copy.hook_selection["selected"]
    assert len(copy.narrative) == 2
    assert pinned.headline == pinned.slides[0].headline == "Pinned title"
    assert "NARRATIVE PLAN" in mock.call_args.kwargs["user_prompt"]


async def test_retry_actually_redesigns_and_routes_copy_correction():
    fmt = "instagram-square"
    state = initial_state(
        "Practice", "Practice improves retention.", [fmt], template_mode="designer"
    )
    state["format_tasks"][fmt]["copy"] = json.dumps(
        {"headline": "Practice", "subhead": "", "body": "Short"}
    )
    calls = []

    async def design(local):
        calls.append("design")
        return {"format_tasks": {fmt: {**local["format_tasks"][fmt], "html": "<html>new</html>"}}}

    async def verify(local):
        passed = len(calls) == 2
        return {
            "format_tasks": {
                fmt: {
                    **local["format_tasks"][fmt],
                    "status": "verified" if passed else "needs_retry",
                }
            },
            "verification": {
                fmt: {
                    "pass": passed,
                    "issues": [] if passed else ["Wordy copy"],
                    "critique": "Tighten body",
                }
            },
        }

    with (
        patch("app.agents.orchestrator.graph.designer_node_single", design),
        patch("app.agents.orchestrator.graph.renderer_node_single", AsyncMock(return_value={})),
        patch("app.agents.orchestrator.graph.quality_check_node_single", verify),
        patch(
            "app.services.generation_refinement.revise_format_copy", AsyncMock(return_value=False)
        ) as revise,
    ):
        out = await _run_format_chain(state, fmt)
    assert calls == ["design", "design"]
    assert out["format_tasks"][fmt]["status"] == "verified"
    assert revise.call_args.args[2][0]["target"] == "copy"


async def test_sequence_critique_blocks_entire_carousel_but_not_single_post():
    base = "instagram-carousel"
    state = initial_state("Practice", "Source", [base])
    state["slide_context"] = {f"{base}-{i}": {"index": i, "total": 2} for i in (1, 2)}
    state["format_tasks"] = {
        f"{base}-{i}": {
            "copy": json.dumps({"headline": f"Frame {i}", "body": "Distinct point"}),
            "html": f"<html>{i}/2</html>",
            "html_path": f"{i}.html",
            "status": "verified",
        }
        for i in (1, 2)
    }
    review = {
        "passed": False,
        "flow": 1,
        "distinctness": 4,
        "terminology": 4,
        "promise_delivered": 1,
        "issues": ["Ending does not deliver the hook"],
    }
    with patch("app.services.llm.call_llm", AsyncMock(return_value=json.dumps(review))):
        result = await _run_sequence_check(state)
    assert not result["ok"]
    assert result["failed_bases"] == [base]
    state["sequence_check"] = result
    state["format_tasks"]["twitter-card"] = {"html_path": "card.html", "status": "verified"}
    with patch("app.services.decisions.providers_configured", return_value=False):
        publish = await _run_publish_gate(state)
    assert publish[f"{base}-1"]["decision"] == "hold"
    assert publish[f"{base}-2"]["decision"] == "hold"
    assert publish["twitter-card"]["decision"] == "publish"


async def test_irrelevant_generated_media_is_removed_on_retry():
    fmt = "instagram-square"
    state = initial_state(
        "Practice", "Practice improves retention.", [fmt], template_mode="designer"
    )
    state["format_tasks"][fmt]["copy"] = json.dumps(
        {"headline": "Practice", "subhead": "", "body": "Short"}
    )
    state["media_plan"] = {fmt: {"kind": "photo", "query": "coffee"}}
    calls = []

    async def design(local):
        calls.append(local["media_plan"][fmt]["kind"])
        if len(calls) == 1:
            local["images"] = [{"data": "generated photo"}]
        else:
            assert local["images"] == []
        return {"format_tasks": {fmt: {**local["format_tasks"][fmt], "html": "new design"}}}

    async def verify(local):
        passed = len(calls) == 2
        return {
            "format_tasks": {
                fmt: {
                    **local["format_tasks"][fmt],
                    "status": "verified" if passed else "needs_retry",
                }
            },
            "verification": {
                fmt: {"pass": passed, "issues": [] if passed else ["Unrelated photo"]}
            },
        }

    with (
        patch("app.agents.orchestrator.graph.designer_node_single", design),
        patch("app.agents.orchestrator.graph.renderer_node_single", AsyncMock(return_value={})),
        patch("app.agents.orchestrator.graph.quality_check_node_single", verify),
    ):
        result = await _run_format_chain(state, fmt)
    assert calls == ["photo", "none"]
    assert result["media_plan"][fmt]["kind"] == "none"


async def test_no_worthwhile_retry_keeps_copy_and_render_in_sync():
    fmt = "instagram-square"
    state = initial_state("Practice", "Source", [fmt], template_mode="designer")
    original = json.dumps({"headline": "Practice", "subhead": "", "body": "Short"})
    state["format_tasks"][fmt]["copy"] = original
    designed = {"format_tasks": {fmt: {**state["format_tasks"][fmt], "html": "last usable HTML"}}}
    review = {
        "format_tasks": {fmt: {"status": "needs_retry"}},
        "verification": {
            fmt: {"pass": False, "issues": ["Wordy copy"], "decision_refine": {"brief": ""}}
        },
    }
    with (
        patch(
            "app.agents.orchestrator.graph.designer_node_single", AsyncMock(return_value=designed)
        ),
        patch("app.agents.orchestrator.graph.renderer_node_single", AsyncMock(return_value={})),
        patch(
            "app.agents.orchestrator.graph.quality_check_node_single",
            AsyncMock(return_value=review),
        ),
        patch("app.services.generation_refinement.revise_format_copy", AsyncMock()) as revise,
    ):
        result = await _run_format_chain(state, fmt)
    revise.assert_not_called()
    assert result["format_tasks"][fmt]["copy"] == original
    assert result["format_tasks"][fmt]["html"] == "last usable HTML"


async def test_empty_model_output_does_not_count_as_successful_sequence_review():
    from app.agents.orchestrator.graph import _review_sequence_copy

    with patch("app.services.llm.call_llm", AsyncMock(return_value="{}")):
        result = await _review_sequence_copy({}, "instagram-carousel", [("slide-1", 1)], [{}])
    assert result == {}


async def test_missing_hook_candidates_get_one_bounded_repair():
    from app.agents.orchestrator.nodes.copywriter import (
        PlatformCopy,
        SlideCopy,
        _ensure_grounded_hook,
    )

    copy = PlatformCopy(
        headline="Cut your editing time in half",
        subhead="",
        body="",
        slides=[SlideCopy(headline="Old", subhead="", body="Practice improves retention.")],
    )
    result = {
        "hook_candidates": [
            {
                "headline": "Practice improves retention",
                "angle": "finding",
                "source_support": "Practice improves retention.",
                "specificity": 5,
                "relevance": 5,
                "faithfulness": 5,
            }
        ]
    }
    model = AsyncMock(return_value=json.dumps(result))
    with patch("app.agents.orchestrator.nodes.copywriter.call_llm", model):
        await _ensure_grounded_hook(
            copy, "Practice improves retention.", "Practice", await get_agent_config("copywriter")
        )
    assert model.await_count == 1
    assert copy.hook_selection["selected"]
    assert copy.headline == copy.slides[0].headline == "Practice improves retention"


async def test_qa_rewrite_cannot_replace_grounded_hook_with_a_new_promise():
    from app.agents.orchestrator.nodes.copywriter import PlatformCopy, _rewrite_copy_for_platform

    prior = PlatformCopy(
        headline="A clear editorial workflow", subhead="", body="Review the draft."
    )
    response = {"headline": "Cut your time in half", "subhead": "", "body": "Review the draft."}
    with patch(
        "app.agents.orchestrator.nodes.copywriter.call_llm",
        AsyncMock(return_value=json.dumps(response)),
    ):
        result = await _rewrite_copy_for_platform(
            "instagram-square",
            "Review the draft.",
            "An editorial workflow",
            await get_agent_config("copywriter"),
            prior,
            {"verdict": "rewrite", "dims": {"clarity": 0.2}, "score": 0.2},
        )
    assert result is not None
    assert result[1].headline == prior.headline


async def test_collective_revision_changes_only_the_failed_carousel():
    from app.agents.orchestrator.graph import _revise_failed_sequences
    from app.agents.orchestrator.nodes.copywriter import PlatformCopy, SlideCopy
    from app.services.generation_quality import NarrativeBeat

    base = "instagram-carousel"
    state = initial_state("Practice", "Practice improves retention.", [base, "twitter-card"])
    ids = [base + "-1", base + "-2"]
    state["format_tasks"] = {
        sid: {"copy": "{}", "html": "old", "status": "verified"} for sid in ids
    }
    state["format_tasks"]["twitter-card"] = {"html": "keep single", "copy": "{}"}
    state["slide_context"] = {sid: {"index": i, "total": 2} for i, sid in enumerate(ids, 1)}
    state["images"] = [{"data": "pinned-user-image"}]
    revised = PlatformCopy(
        headline="Practice",
        subhead="",
        body="",
        slides=[
            SlideCopy(headline="Practice", subhead="", body="Practice improves retention."),
            SlideCopy(headline="Review", subhead="", body="Review your draft."),
        ],
        narrative=[NarrativeBeat(role="hook"), NarrativeBeat(role="takeaway")],
    )

    async def render(local, sid):
        assert local["images"] == [{"data": "pinned-user-image"}]
        return {
            "format_tasks": {
                sid: {**local["format_tasks"][sid], "html": "new", "status": "verified"}
            }
        }

    with (
        patch(
            "app.services.generation_refinement.revise_carousel_copy",
            AsyncMock(return_value=revised),
        ),
        patch(
            "app.agents.orchestrator.nodes.copywriter._copy_qa_for_platform",
            AsyncMock(return_value={}),
        ),
        patch("app.services.media_plan.build_media_plan", AsyncMock(return_value={})),
        patch("app.agents.orchestrator.graph._run_format_chain", render),
    ):
        assert await _revise_failed_sequences(
            state,
            {
                "failed_bases": [base],
                "editorial": {base: {"passed": False, "issues": ["Weak flow"]}},
            },
        )
    assert state["format_tasks"]["twitter-card"]["html"] == "keep single"
    assert state["format_tasks"][ids[0]]["html"] == "new"
    assert len(json.loads(state["revised_carousel_copies"][base])["slides"]) == 2
