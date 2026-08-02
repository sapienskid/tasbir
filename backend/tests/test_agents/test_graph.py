"""Tests for v3 LangGraph pipeline — graph topology and format processing."""

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from app.agents.orchestrator.graph import (
    build_pipeline,
    process_all_formats_node,
    _run_format_chain,
)
from app.agents.orchestrator.state import initial_state


def test_graph_has_required_nodes():
    """Pipeline must have strategist, planner, copywriter, and process_all_formats nodes."""
    graph = build_pipeline()
    nodes = graph.nodes
    assert "strategist" in nodes
    assert "planner" in nodes
    assert "copywriter" in nodes
    assert "process_all_formats" in nodes


def test_graph_edges():
    """strategist → planner → copywriter → process_all_formats → END."""
    edges = build_pipeline().builder.edges
    assert ("__start__", "strategist") in edges
    assert ("strategist", "planner") in edges
    assert ("planner", "copywriter") in edges
    assert ("copywriter", "process_all_formats") in edges
    assert ("process_all_formats", "__end__") in edges


def _base_state(**kw):
    return initial_state(
        title="T",
        content="C",
        platforms=["instagram-square", "linkedin-post"],
        _task_id="test-graph",
        design_tokens={
            "--color-bg": "#FFFFFF",
            "--color-text": "#000000",
            "--color-border": "#D9D9D9",
            "--color-bg-inverted": "#000000",
            "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#6E6E6E",
            "--font-sans": "Inter",
        },
        footer={"left": "A", "right": "@B"},
        categories=[{"name": "WRITING"}],
        **kw,
    )


GOOD_HTML = (
    '<html><head><style>body{background:var(--color-bg);color:var(--color-text);'
    'font-family:var(--font-sans)}.kicker{text-transform:uppercase}'
    '.headline{font-family:var(--font-display)}</style></head>'
    '<body style="width:1080px;height:1080px;overflow:hidden;margin:0">'
    '<div class="kicker">WRITING</div><h1 class="headline">Hello World Headline</h1>'
    '<div class="footer"><span>SABIN POKHAREL</span><span>@B</span></div></body></html>'
)

BAD_HTML = (
    '<html><head><style>body{background:#FFFFFF;color:#000000}</style></head>'
    '<body style="width:1080px;height:1080px;overflow:hidden;margin:0"><p>Some content here</p>'
    '</body></html>'
)


def _set_copy(state, copy='{"headline":"H","subhead":"","body":"B","tagline":"","badge":null}'):
    for p in state["platforms"]:
        state["format_tasks"][p]["copy"] = copy
    return state


def _patches():
    import re

    def good_html_for_prompt(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        m = re.search(r"CANVAS: (\d+)px × (\d+)px", user_prompt)
        w, h = (m.group(1), m.group(2)) if m else ("1080", "1080")
        return (
            '<html><head><style>'
            f'body{{width:{w}px;height:{h}px;background:var(--color-bg);'
            'color:var(--color-text);font-family:var(--font-sans)}}'
            '.kicker{text-transform:uppercase}'
            '.headline{font-family:var(--font-display)}'
            '.wordmark{font-family:var(--font-display)}'
            '</style></head>'
            f'<body style="width:{w}px;height:{h}px;overflow:hidden;margin:0">'
            '<div class="kicker">WRITING</div><h1 class="headline">Hello World Headline</h1>'
            '<div class="footer"><span class="wordmark">A</span><span>@B</span></div></body></html>'
        )

    return (
        patch("app.agents.orchestrator.nodes.designer.call_llm",
              new=AsyncMock(side_effect=good_html_for_prompt)),
        patch("app.agents.orchestrator.nodes.quality_check.render_to_png",
              new=AsyncMock(return_value=b"PNG")),
        patch("app.agents.orchestrator.nodes.quality_check._call_vision_llm",
              new=AsyncMock(return_value='{"pass":true,"score":90,"issues":[],"critique":"ok"}')),
    )


def test_run_format_chain_processes_and_passes():
    """A format should end 'verified' when designer + vision succeed."""
    state = _set_copy(_base_state())
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(_run_format_chain(state, "instagram-square"))
    ft = out["format_tasks"]["instagram-square"]
    assert ft["status"] == "verified"
    assert ft["quality_score"] >= 80
    assert out["verification"]["instagram-square"]["pass"] is True


def test_run_format_chain_retries_on_deterministic_violation():
    """A bad first attempt (hex colors) must be retried and fixed."""
    state = _set_copy(_base_state())
    calls = {"n": 0}

    async def fake_llm(*a, **k):
        calls["n"] += 1
        return BAD_HTML if calls["n"] == 1 else GOOD_HTML

    with patch("app.agents.orchestrator.nodes.designer.call_llm",
               new=AsyncMock(side_effect=fake_llm)), \
         patch("app.agents.orchestrator.nodes.quality_check.render_to_png",
               new=AsyncMock(return_value=b"PNG")), \
         patch("app.agents.orchestrator.nodes.quality_check._call_vision_llm",
               new=AsyncMock(return_value='{"pass":true,"score":85,"issues":[],"critique":"ok"}')):

        out = asyncio.run(_run_format_chain(state, "instagram-square"))

    assert calls["n"] >= 2
    assert out["format_tasks"]["instagram-square"]["status"] == "verified"


def test_process_all_formats_merges_every_platform():
    """All platforms must reach a processed state — no lost updates."""
    state = _set_copy(_base_state())
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))
    fts = out["format_tasks"]
    assert set(fts.keys()) == {"instagram-square", "linkedin-post"}
    for p, ft in fts.items():
        assert ft["status"] == "verified", f"{p} not verified: {ft['status']}"
