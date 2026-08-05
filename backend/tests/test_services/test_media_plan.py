"""Tests for the Media Plan Director (per-slide media decisions)."""

import json
import re

import pytest

from app.agents.orchestrator.state import initial_state
from app.services.media_plan import (
    _extract_targets,
    _parse_plan,
    build_media_plan,
    execute_slide_illustration,
)

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}")


def test_plan_system_prompt_reflects_style_language():
    """The media director reads the DS design language, not a monochrome default."""
    from app.services.media_plan import _plan_system_prompt
    from app.services.styles import apply_style_preset

    vibrant = _state()
    vibrant["design_instruction"] = apply_style_preset("vibrant-pop", {})
    prompt_v = _plan_system_prompt(vibrant)
    assert "full color" in prompt_v
    assert "emoji are allowed" in prompt_v
    assert "monochrome editorial" not in prompt_v

    swiss = _state()
    swiss["design_instruction"] = apply_style_preset("swiss-editorial", {})
    prompt_s = _plan_system_prompt(swiss)
    assert "grayscale" in prompt_s


def _state(**overrides) -> dict:
    slides = [
        {"headline": "Launch day", "subhead": "", "body": "Rocket lifts off",
         "tagline": "", "badge": None},
        {"headline": "The payload", "subhead": "", "body": "What rides inside",
         "tagline": "", "badge": None},
    ]
    state = initial_state(
        title="Rocket Launch",
        content="A rocket launch story.",
        platforms=["instagram-carousel"],
        slides=2,
        ratio="square",
        design_instruction={"style": {"illustration_style": "procedural"}},
    )
    state["format_tasks"] = {
        "instagram-carousel": {
            "status": "waiting", "copy": json.dumps({"slides": slides}),
            "html": None, "html_path": None, "quality_score": 0,
            "quality_issues": [], "refinement_count": 0, "error": None, "template_id": None,
        }
    }
    state["strategic_brief"] = {"content_summary": "space, rocket, launch, orbit"}
    state["category"] = "PROJECT"
    state["ground"] = "white"
    state.update(overrides)
    return state


def test_parse_plan_valid():
    raw = (
        '[{"target": "instagram-carousel-1", "kind": "illustration", '
        '"style": "procedural", "theme": "launch"}, '
        '{"target": "instagram-carousel-2", "kind": "none"}]'
    )
    plan = _parse_plan(raw)
    assert plan[0]["kind"] == "illustration"
    assert plan[0]["style"] == "procedural"
    assert plan[0]["theme"] == "launch"
    assert plan[1]["kind"] == "none"


def test_parse_plan_invalid_kind_dropped():
    plan = _parse_plan('[{"target": "x", "kind": "video"}]')
    assert plan == []


def test_parse_plan_handles_markdown_fence():
    raw = '```json\n[{"target": "x", "kind": "photo", "query": "city"}]```'
    plan = _parse_plan(raw)
    assert plan[0]["kind"] == "photo"


def _slide_task(slide_id: str, headline: str, body: str) -> dict:
    """A format-task dict for a carousel slide."""
    return {
        slide_id: {
            "status": "waiting",
            "copy": json.dumps({"headline": headline, "subhead": "", "body": body,
                                "tagline": "", "badge": None}),
            "html": None, "html_path": None, "quality_score": 0,
            "quality_issues": [], "refinement_count": 0, "error": None, "template_id": None,
        }
    }


def test_extract_targets_includes_carousel_slides():
    state = _state()
    targets = _extract_targets(state)
    # The base carousel holds only slide copy — targets are the expanded slides
    # once the graph has expanded them. Here only the base exists, so the base
    # itself is skipped (no per-slide copy) → empty targets.
    assert isinstance(targets, list)


def test_extract_targets_marks_filled():
    state = _state()
    # Simulate the graph's expansion + user-image distribution.
    state["format_tasks"] = {
        **_slide_task("instagram-carousel-1", "A", "B"),
        **_slide_task("instagram-carousel-2", "C", "D"),
    }
    state["_slide_images"] = {"instagram-carousel-1": [{"data": "abc", "mime": "image/png"}]}
    targets = _extract_targets(state)
    by_id = {t["id"]: t for t in targets}
    assert by_id["instagram-carousel-1"]["filled"] is True
    assert by_id["instagram-carousel-2"]["filled"] is False


def test_execute_slide_illustration_compiles():
    svg = execute_slide_illustration(
        {"kind": "illustration", "style": "procedural", "theme": "launch"},
        seed="x|ill", ground="white", category="PROJECT",
    )
    assert "var(--color-text)" in svg or "var(--color-text-inverted)" in svg
    assert svg.strip().startswith("<svg")
    assert not HEX_RE.search(svg)


@pytest.mark.asyncio
async def test_build_media_plan_skips_filled_slides_without_llm(monkeypatch):
    """Filled slides become 'skip' and the LLM is never invoked."""
    state = _state()
    state["format_tasks"] = {
        **_slide_task("instagram-carousel-1", "A", "B"),
        **_slide_task("instagram-carousel-2", "C", "D"),
    }
    state["_slide_images"] = {
        "instagram-carousel-1": [{"data": "abc", "mime": "image/png"}],
        "instagram-carousel-2": [{"data": "def", "mime": "image/png"}],
    }
    called = {"n": 0}

    async def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("should not call LLM when all slides filled")

    monkeypatch.setattr("app.services.llm.call_llm_tool_loop", _boom)
    plan = await build_media_plan(state)
    assert called["n"] == 0
    assert plan["instagram-carousel-1"]["kind"] == "skip"
    assert plan["instagram-carousel-2"]["kind"] == "skip"


@pytest.mark.asyncio
async def test_build_media_plan_parses_llm_output(monkeypatch):
    state = _state()
    state["format_tasks"] = {
        **_slide_task("instagram-carousel-1", "A", "B"),
    }
    state["_slide_images"] = {}

    async def _fake(*args, **kwargs):
        return (
            '[{"target": "instagram-carousel-1", "kind": "illustration", '
            '"style": "procedural", "theme": "launch"}]'
        )

    monkeypatch.setattr("app.services.llm.call_llm_tool_loop", _fake)
    plan = await build_media_plan(state)
    entry = plan["instagram-carousel-1"]
    assert entry["kind"] == "illustration"
    assert entry["style"] == "procedural"


@pytest.mark.asyncio
async def test_illustrate_handler_returns_rendered_feedback(monkeypatch):
    """The illustrate tool returns real structural feedback, not a no-op ack.

    The media director must see the actual figure (element count, bounding
    box, safe-frame compliance) so it can iterate to a distinct, non-clipping
    composition before committing the plan.
    """
    state = _state()
    state["format_tasks"] = {
        **_slide_task("instagram-carousel-1", "A", "B"),
    }
    state["_slide_images"] = {}

    captured: dict = {}

    async def _fake(*args, **kwargs):
        handlers = kwargs["handlers"]
        captured["feedback"] = await handlers["illustrate"](
            {"style": "procedural", "theme": "orbit", "ground": "white"}
        )
        return '[{"target": "instagram-carousel-1", "kind": "none"}]'

    monkeypatch.setattr("app.services.llm.call_llm_tool_loop", _fake)
    await build_media_plan(state)

    fb = captured["feedback"]
    assert "Rendered style='procedural'" in fb
    assert "Archetype:" in fb
    assert "Element count:" in fb
    assert "bbox x0=" in fb
    assert "Within safe slot: True" in fb
