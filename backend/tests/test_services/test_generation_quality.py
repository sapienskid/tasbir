import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.generation_quality import (
    HookCandidate,
    choose_hook,
    content_profile,
    corrections_from_review,
    narrative_outline,
    narrative_roles,
    repeated_slide_issues,
)
from app.services.templates import select_template


@pytest.mark.parametrize("count", range(2, 11))
def test_every_carousel_has_one_role_per_pinned_slide(count):
    beats = narrative_outline([], count, "Daily practice improves retention")
    assert len(beats) == count
    assert beats[0]["role"] == "hook"
    assert "takeaway" in [beat["role"] for beat in beats]
    assert len(narrative_roles(count)) == count
    assert all(beat["focus"] for beat in beats)


def test_hook_selection_rejects_hype_unsupported_numbers_and_fake_citations():
    source = "Daily practice improves retention. Study sessions lasted 20 minutes."
    hooks = [
        HookCandidate(
            headline="Unlock the power of daily practice",
            specificity=5,
            relevance=5,
            faithfulness=5,
            source_support="Daily practice improves retention.",
        ),
        HookCandidate(
            headline="Practice increases retention by 90%",
            specificity=5,
            relevance=5,
            faithfulness=5,
            source_support="Daily practice improves retention.",
        ),
        HookCandidate(
            headline="Practice doubles retention",
            specificity=5,
            relevance=5,
            faithfulness=5,
            source_support="Practice doubles retention",
        ),
        HookCandidate(
            headline="Daily practice improves retention",
            specificity=4,
            relevance=5,
            faithfulness=5,
            source_support="Daily practice improves retention.",
        ),
    ]
    selection = choose_hook(hooks, source, "Original hook")
    assert selection["headline"] == "Daily practice improves retention"
    assert [item["eligible"] for item in selection["candidates"]] == [False, False, False, True]


def test_hook_failure_preserves_usable_original():
    assert choose_hook([], "Source", "Original")["headline"] == "Original"


def test_written_quantitative_promises_require_source_support():
    from app.agents.orchestrator.nodes.copywriter import PlatformCopy, SlideCopy, _claims_grounding

    copy = PlatformCopy(headline="Cut your editing time in half", subhead="", body="Clear writing")
    assert "half" in _claims_grounding(copy, "An editorial workflow improves clarity")["invented"]
    copy.headline = "An editorial workflow"
    copy.slides = [SlideCopy(headline="Review", subhead="", body="Double your output")]
    assert "double" in _claims_grounding(copy, "An editorial workflow improves clarity")["invented"]
    assert not _claims_grounding(copy, "An editorial workflow can double your output")["invented"]


def test_density_and_composition_follow_actual_copy_and_canvas():
    copy = {"headline": "A comparison", "body": "a" * 300}
    assert content_profile(copy, 1200, 627).needs_rewrite
    assert not content_profile(copy, 1080, 1350).needs_rewrite
    assert content_profile(copy, post_type="comparison").composition == "comparison"
    assert content_profile({"body": "a" * 410}).density == "dense"


def test_layout_selection_preserves_copy_and_prefers_readable_text():
    templates = [
        {
            "id": "hero",
            "family": "square",
            "hint_tags": ["media"],
            "html": "{{ headline }}",
            "weight": 999,
        },
        {
            "id": "editorial",
            "family": "square",
            "hint_tags": ["text"],
            "html": "{{ headline }}{{ body }}",
        },
    ]
    selected = select_template(
        "square",
        "white",
        "",
        "",
        "seed",
        templates,
        copy_data={"headline": "Headline", "body": "a" * 400},
    )
    assert selected[0] == "editorial"
    assert (
        select_template(
            "square",
            "white",
            "",
            "",
            "seed",
            templates[:1],
            copy_data={"headline": "Headline", "body": "Do not lose this"},
        )
        is None
    )


def test_review_feedback_routes_copy_layout_and_media_separately():
    corrections = corrections_from_review(
        {
            "pass": False,
            "issues": [
                "Wordy body repeats the headline",
                "Footer exceeds the canvas",
                "Unrelated photo",
            ],
        }
    )
    assert [item["target"] for item in corrections] == ["copy", "layout", "media"]
    assert all(item["element"] and item["action"] for item in corrections)


def test_invalid_model_correction_cannot_break_deterministic_feedback():
    result = corrections_from_review(
        {"pass": False, "corrections": [{"target": "invented"}], "issues": ["Footer clips"]}
    )
    assert result[0]["target"] == "layout"


def test_repeated_points_detected_without_rejecting_shared_short_labels():
    body = "Make practice part of a daily routine, using short sessions and concrete feedback."
    assert repeated_slide_issues([{"body": body}, {"body": body}])
    assert not repeated_slide_issues([{"body": "Practice"}, {"body": "Practice"}])


async def test_typography_only_plan_never_creates_fallback_media():
    from app.agents.orchestrator.nodes.template_renderer import (
        _get_post_illustration,
        _get_post_photo,
    )

    state = {
        "_processing_format_id": "instagram-square",
        "media_plan": {"instagram-square": {"kind": "none"}},
        "_post_illustration_svg": "cached decorative art",
        "_auto_photo": {"image": "cached photo"},
    }
    with patch("app.services.illustration.generate_illustration_svg") as illustrate:
        assert await _get_post_illustration(state, "white", "seed") == ""
        assert await _get_post_photo(state, "square", required=True) is None
    illustrate.assert_not_called()


async def test_refinement_preserves_pins_and_rejects_invented_figures():
    from app.services.generation_refinement import revise_format_copy

    fmt = "instagram-square"
    state = {
        "title": "Practice",
        "content": "Daily practice improves retention.",
        "overrides": {"headline": "My exact headline"},
        "format_tasks": {
            fmt: {
                "copy": json.dumps(
                    {"headline": "My exact headline", "subhead": "", "body": "Old body"}
                )
            }
        },
    }
    corrections = [{"target": "copy", "element": "body", "problem": "Wordy", "action": "Tighten"}]
    response = {"headline": "New headline", "subhead": "", "body": "Practice improves retention."}
    with patch("app.services.llm.call_llm", AsyncMock(return_value=json.dumps(response))):
        assert await revise_format_copy(state, fmt, corrections)
    assert json.loads(state["format_tasks"][fmt]["copy"])["headline"] == "My exact headline"
    previous = state["format_tasks"][fmt]["copy"]
    response["body"] = "Practice improves retention by 99%."
    with patch("app.services.llm.call_llm", AsyncMock(return_value=json.dumps(response))):
        assert not await revise_format_copy(state, fmt, corrections)
    assert state["format_tasks"][fmt]["copy"] == previous
    state["verbatim"] = True
    with patch("app.services.llm.call_llm", AsyncMock()) as llm:
        assert not await revise_format_copy(state, fmt, corrections)
    llm.assert_not_called()
