"""Tests for the decision-driven quality gates.

Covers: claims grounding (invented figures), Clef hard/soft flag splitting,
the publish gate (deterministic hold, disabled, fail-open), the media-plan
pre-gate constraint, and the human feedback endpoint.
"""

import pytest


# ---------------------------------------------------------------------------
# Claims grounding
# ---------------------------------------------------------------------------


def _copy(**fields):
    from app.agents.orchestrator.nodes.copywriter import PlatformCopy

    base = {"headline": "", "subhead": "", "body": "", "tagline": "",
            "badge": "", "extra": {}}
    base.update(fields)
    return PlatformCopy(**base)


def test_figures_extracts_claims_not_counters():
    from app.agents.orchestrator.nodes.copywriter import _figures

    assert _figures("Cut deploys from 9 percent to under 1 percent") == []
    found = _figures("Cut failed deploys from 9% to under 1% in Q3")
    assert "9%" in found and "1%" in found
    assert _figures("Slide 1 of 3, 2026 edition") == ["2026"]  # years are claims too


def test_claims_grounding_flags_invented_figures():
    from app.agents.orchestrator.nodes.copywriter import _claims_grounding

    source = "Teams cut failed deploys from 9% to under 1% in a quarter."
    ok = _copy(headline="Deploys down from 9% to 1%")
    assert _claims_grounding(ok, source) == {"invented": []}
    bad = _copy(headline="Deploys down 47% this week")
    assert _claims_grounding(bad, source) == {"invented": ["47%"]}
    # No source → nothing to check against (never block blindly).
    assert _claims_grounding(bad, "") == {"invented": []}


# ---------------------------------------------------------------------------
# Clef hard/soft flags
# ---------------------------------------------------------------------------


def _visual(**nouls):
    return {"answers": {k: {"noul": v} for k, v in nouls.items()}}


def test_hard_flags_need_strength_and_decisiveness():
    from app.agents.orchestrator.nodes.quality_check import _clef_hard_flags

    hard, soft = _clef_hard_flags(
        _visual(has_overflow=0.9, ground_correct=0.9, emoji_present=0.1,
                hierarchy_ok=0.9, footer_present=0.9), {}, False)
    assert any("overflow" in h for h in hard) and not soft

    # Unsure model (near 0.5) must not burn retries.
    hard, soft = _clef_hard_flags(
        _visual(has_overflow=0.55, ground_correct=0.5, emoji_present=0.5,
                hierarchy_ok=0.5, footer_present=0.5), {}, False)
    assert hard == [] and soft == []

    # Weak hierarchy is soft scrutiny, not a forced retry.
    hard, soft = _clef_hard_flags(
        _visual(has_overflow=0.1, ground_correct=0.9, emoji_present=0.1,
                hierarchy_ok=0.2, footer_present=0.9), {}, False)
    assert hard == [] and any("hierarchy" in s for s in soft)

    # Emoji allowed by the design language → not even soft.
    hard, soft = _clef_hard_flags(
        _visual(has_overflow=0.1, ground_correct=0.9, emoji_present=0.95,
                hierarchy_ok=0.9, footer_present=0.9), {}, True)
    assert hard == [] and soft == []


def test_relevance_hard_drives_retry():
    from app.agents.orchestrator.nodes.quality_check import _clef_hard_flags

    rel = {"relevant": False, "clash": True, "hard": True,
           "issues": ["photo does not illustrate the headline"]}
    hard, _ = _clef_hard_flags(_visual(has_overflow=0.1), rel, False)
    assert any("headline" in h for h in hard)

    rel_soft = dict(rel, hard=False)
    hard, soft = _clef_hard_flags(_visual(has_overflow=0.1), rel_soft, False)
    assert hard == [] and soft != []


# ---------------------------------------------------------------------------
# Publish gate
# ---------------------------------------------------------------------------


def _pub_state(**kw):
    state = {
        "_task_id": "",
        "format_tasks": {
            "instagram-square": {
                "status": "verified", "html_path": "x.html",
                "quality_score": 90, "quality_issues": [],
            },
        },
        "verification": {
            "instagram-square": {"pass": True, "score": 90, "issues": []},
        },
        "copy_qa": {
            "instagram-square": {"verdict": "pass", "score": 0.8, "issues": []},
        },
    }
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(state.get(k), dict):
            state[k].update(v)
        else:
            state[k] = v
    return state


async def _noop_settings(name, default=None):
    return default


@pytest.mark.asyncio
async def test_publish_gate_disabled(monkeypatch):
    from app.agents.orchestrator import graph as g

    async def off(name, default=None):
        return False if name == "publish.enabled" else default

    monkeypatch.setattr("app.services.settings.get_runtime_setting", off)
    assert await g._run_publish_gate(_pub_state()) == {}


@pytest.mark.asyncio
async def test_publish_gate_deterministic_hold(monkeypatch):
    from app.agents.orchestrator import graph as g

    monkeypatch.setattr("app.services.settings.get_runtime_setting", _noop_settings)
    state = _pub_state(copy_qa={
        "instagram-square": {"verdict": "rewrite", "score": 0.4,
                             "issues": ["ungrounded figures: 47%"],
                             "claims_hold": True,
                             "claims_grounding": {"invented": ["47%"]}},
    })
    out = await g._run_publish_gate(state)
    gate = out["instagram-square"]
    assert gate["decision"] == "hold"
    assert gate["source"] == "deterministic"
    assert any("47%" in r for r in gate["reasons"])


@pytest.mark.asyncio
async def test_publish_gate_llm_hold_and_failopen(monkeypatch):
    from app.agents.orchestrator import graph as g
    from app.services import decisions as d

    monkeypatch.setattr("app.services.settings.get_runtime_setting", _noop_settings)
    monkeypatch.setattr(d, "providers_configured", lambda: True)

    async def fake_decide(pack_id, state, **kw):
        assert pack_id == "publish-gate"
        return {"provider": "clef-flash",
                "answers": {"decision": {"choice": "hold"},
                            "blocker": {"noul": 0.8}}}

    monkeypatch.setattr(d, "decide", fake_decide)
    out = await g._run_publish_gate(_pub_state())
    assert out["instagram-square"]["decision"] == "hold"

    async def boom(pack_id, state, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(d, "decide", boom)
    out = await g._run_publish_gate(_pub_state())
    gate = out["instagram-square"]
    assert gate["decision"] == "publish" and gate["source"] == "fail-open"


# ---------------------------------------------------------------------------
# Media pre-gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_media_pregate_none_blocks_tools(monkeypatch):
    from app.services import decisions as d
    from app.services import media_plan as mp

    monkeypatch.setattr(d, "providers_configured", lambda: True)

    async def fake_decide(pack_id, state, **kw):
        assert pack_id == "media-kind"
        return {"provider": "clef-flash",
                "answers": {"kind": {"choice": "none"},
                            "photo_worthy": {"noul": 0.1}}}

    monkeypatch.setattr(d, "decide", fake_decide)

    seen = {}

    async def fake_loop(**kw):
        seen["system"] = kw["system_prompt"]
        return "[]"

    monkeypatch.setattr("app.services.llm.call_llm_tool_loop", fake_loop)

    state = {"title": "t", "strategic_brief": {"content_summary": "abstract essay"},
             "format_tasks": {"instagram-square": {"copy": '{"headline": "h"}'}},
             "ground": "white", "design_instruction": {}, "_task_id": ""}
    out = await mp.build_media_plan(state)
    assert out == {}
    assert "PURE TYPOGRAPHY" in seen["system"]
    assert "Do NOT call find_photo" in seen["system"]


