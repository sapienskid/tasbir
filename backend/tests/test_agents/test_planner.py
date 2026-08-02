"""Planner node tests — hybrid gating, deterministic synth, ratio mapping."""

from unittest.mock import patch

from app.agents.orchestrator.nodes.planner import (
    _structure_undecided,
    planner_node,
)
from app.agents.orchestrator.state import initial_state


def _state(**kw):
    base = dict(
        title="T",
        content="C",
        platforms=["instagram-square"],
        _task_id="",
        design_tokens={},
        brand_info={},
        campaign={},
        overrides={},
        images=[],
        footer={},
        categories=[],
        category="",
        ground="white",
    )
    base.update(kw)
    return initial_state(**base)


# ─── Gating ─────────────────────────────────────────────────────────────────


def test_structure_undecided():
    assert _structure_undecided(["instagram-carousel"], 0, "auto")
    assert _structure_undecided(["instagram-carousel"], 3, "auto")
    assert not _structure_undecided(["instagram-carousel"], 3, "square")
    assert not _structure_undecided(["instagram-square"], 3, "auto")
    assert _structure_undecided(["instagram-carousel-portrait"], 3, "auto")


# ─── Deterministic synth (no LLM) ──────────────────────────────────────────


async def test_deterministic_carousel_skips_llm():
    calls = []

    async def fake_call_llm(**kw):
        calls.append(kw)
        raise AssertionError("LLM must not be called for pinned structure")

    with patch("app.agents.orchestrator.nodes.planner.call_llm", fake_call_llm):
        state = _state(platforms=["instagram-carousel"], slides=4, ratio="square")
        out = await planner_node(state)

    assert calls == []
    plan = out["post_plan"]
    assert plan["post_type"] == "carousel"
    assert plan["slides"] == 4
    assert plan["ratio"] == "square"
    assert out["platforms"] == ["instagram-carousel"]


async def test_portrait_ratio_swaps_base():
    async def fake_call_llm(**kw):
        raise AssertionError("LLM must not be called")

    with patch("app.agents.orchestrator.nodes.planner.call_llm", fake_call_llm):
        state = _state(platforms=["instagram-carousel"], slides=4, ratio="portrait")
        out = await planner_node(state)

    assert out["post_plan"]["ratio"] == "portrait"
    assert out["platforms"] == ["instagram-carousel-portrait"]


async def test_single_platform_is_single():
    async def fake_call_llm(**kw):
        raise AssertionError("LLM must not be called")

    with patch("app.agents.orchestrator.nodes.planner.call_llm", fake_call_llm):
        out = await planner_node(_state(platforms=["instagram-square"]))

    assert out["post_plan"]["post_type"] == "single"
    assert out["platforms"] == ["instagram-square"]


# ─── Auto (LLM decides) ─────────────────────────────────────────────────────


async def test_auto_resolves_platforms_via_llm():
    async def fake_call_llm(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        assert agent_role == "planner"
        return (
            '{"post_type": "carousel", "ratio": "portrait", "slides": 5, '
            '"platforms": ["instagram-carousel"], "slides_outline": '
            '[{"focus": "hook", "headline_hint": "The premise"}]}'
        )

    with patch("app.agents.orchestrator.nodes.planner.call_llm", fake_call_llm):
        state = _state(platforms=["auto"])
        out = await planner_node(state)

    plan = out["post_plan"]
    assert plan["post_type"] == "carousel"
    assert plan["ratio"] == "portrait"
    assert plan["slides"] == 5
    assert len(plan["slides_outline"]) == 1
    # Portrait ratio → the resolved carousel base is the portrait one.
    assert out["platforms"] == ["instagram-carousel-portrait"]
    assert out["slides"] == 5


async def test_auto_falls_back_deterministically_on_llm_failure():
    async def fake_call_llm(**kw):
        raise RuntimeError("boom")

    with patch("app.agents.orchestrator.nodes.planner.call_llm", fake_call_llm):
        state = _state(platforms=["auto"])
        out = await planner_node(state)

    assert out["post_plan"]["post_type"] in ("single", "carousel", "story")
    assert out["platforms"]  # non-empty
