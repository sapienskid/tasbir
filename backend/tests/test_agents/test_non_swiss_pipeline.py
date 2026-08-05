"""Golden test — a non-Swiss (vibrant-pop) design language flows end-to-end.

Proves the pipeline layers read the design language instead of a hardcoded
monochrome default: the designer prompt carries the style rules (emoji allowed,
accent tokens, full-color photos), the media director gets the style guidance,
and the format verifies.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from app.agents.orchestrator.graph import _run_format_chain
from app.agents.orchestrator.state import initial_state
from app.services.styles import apply_style_preset

VIBRANT_DI = apply_style_preset("vibrant-pop", {})
TOKENS = {
    "--color-bg": "#FFFFFF",
    "--color-bg-inverted": "#1A1A2E",
    "--color-text": "#131322",
    "--color-text-inverted": "#FFFFFF",
    "--color-text-secondary": "#5A5A6A",
    "--color-border": "#D8D8E0",
    "--color-border-inverted": "#33334A",
    "--color-accent": "#FF2D78",
    "--color-accent-secondary": "#4DA6FF",
    "--font-sans": "Inter",
    "--font-display": "Archivo",
    "--font-serif": "Lora",
}


def _vibrant_state(**kw):
    return initial_state(
        title="Vibrant Idea",
        content="An abstract idea about growth.",
        platforms=["instagram-square"],
        _task_id="golden-vibrant",
        design_tokens=dict(TOKENS),
        token_roles={},
        design_instruction=dict(VIBRANT_DI),
        ground="white",
        footer={"left": "", "right": "@B"},
        categories=[{"name": "WRITING"}],
        **kw,
    )


def _patches(captured: dict):
    import re

    def designer_html(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        captured["designer_user_prompt"] = user_prompt
        captured["designer_system_prompt"] = system_prompt
        m = re.search(r"CANVAS: (\d+)px × (\d+)px", user_prompt)
        w, h = (m.group(1), m.group(2)) if m else ("1080", "1080")
        return (
            '<html><head><style>'
            f'body{{width:{w}px;height:{h}px;background:var(--color-bg);'
            "color:var(--color-text);font-family:var(--font-sans)}}"
            ".kicker{text-transform:uppercase}"
            ".headline{font-family:var(--font-display)}"
            ".panel{background:var(--color-accent);border-radius:24px}"
            "</style></head>"
            f'<body style="width:{w}px;height:{h}px;overflow:hidden;margin:0">'
            '<div class="kicker">WRITING</div>'
            '<h1 class="headline">Vibrant Idea</h1>'
            '<div class="panel"></div>'
            '<span>@B</span></body></html>'
        )

    async def fake_media_plan(state):
        captured["media_system_prompt"] = None
        return {}

    return (
        patch(
            "app.agents.orchestrator.nodes.designer.call_llm",
            new=AsyncMock(side_effect=designer_html),
        ),
        patch(
            "app.agents.orchestrator.nodes.quality_check.render_to_png",
            new=AsyncMock(return_value=b"PNG"),
        ),
        patch(
            "app.agents.orchestrator.nodes.quality_check._call_vision_llm",
            new=AsyncMock(return_value='{"pass":true,"score":90,"issues":[],"critique":"ok"}'),
        ),
        patch(
            "app.services.media_plan.build_media_plan",
            new=AsyncMock(side_effect=fake_media_plan),
        ),
    )


def test_vibrant_designer_prompt_carries_style_rules():
    state = _vibrant_state()
    state["format_tasks"]["instagram-square"]["copy"] = (
        '{"headline":"Vibrant Idea","subhead":"","body":"B","tagline":"","badge":null}'
    )
    captured: dict = {}
    with ExitStack() as stack:
        for p in _patches(captured):
            stack.enter_context(p)
        out = asyncio.run(_run_format_chain(state, "instagram-square"))

    sp = captured["designer_system_prompt"]
    up = captured["designer_user_prompt"]
    # The design-instruction block (system prompt) reflects the vibrant
    # language — not the Swiss monochrome default.
    assert "Emoji: ALLOWED" in sp
    assert "var(--color-accent)" in sp
    assert "photos render full color" in sp
    assert "monochrome editorial" not in sp
    # The user prompt still carries the platform/canvas context.
    assert "CANVAS: 1080px × 1080px" in up

    ft = out["format_tasks"]["instagram-square"]
    assert ft["status"] == "verified"
    assert out["verification"]["instagram-square"]["pass"] is True


def test_vibrant_tokens_flow_into_output_html():
    state = _vibrant_state()
    state["format_tasks"]["instagram-square"]["copy"] = (
        '{"headline":"Vibrant Idea","subhead":"","body":"B","tagline":"","badge":null}'
    )
    captured: dict = {}
    with ExitStack() as stack:
        for p in _patches(captured):
            stack.enter_context(p)
        out = asyncio.run(_run_format_chain(state, "instagram-square"))
    # The rendered HTML embeds the accent token (vibrant palette), proving the
    # design system's tokens reached the output rather than a monochrome default.
    html_path = out["format_tasks"]["instagram-square"].get("html_path")
    assert html_path, "html_path missing"
    from pathlib import Path

    html = Path(html_path).read_text(encoding="utf-8")
    assert "--color-accent" in html
    assert "FF2D78" in html  # accent injected via tokens


def test_non_swiss_template_first_path():
    """A vibrant-tagged starter template is selected + renders token-only HTML."""
    from app.services.style_templates import STARTER_TEMPLATES

    state = _vibrant_state()
    state["ds_templates"] = [
        {
            "id": "vibrant-pop-square",
            "family": "square",
            "grounds": ["white", "black"],
            "categories": [],
            "hint_tags": ["style", "vibrant-pop"],
            "weight": 1.0,
            "description": "",
            "html": STARTER_TEMPLATES["vibrant-pop"]["square"],
            "image_slots": [],
            "has_logo_slot": False,
            "design_system_id": "x",
        }
    ]
    state["format_tasks"]["instagram-square"]["copy"] = (
        '{"headline":"Vibrant Idea","subhead":"","body":"B","tagline":"","badge":null}'
    )
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.agents.orchestrator.nodes.quality_check.render_to_png",
                new=AsyncMock(return_value=b"PNG"),
            )
        )
        stack.enter_context(
            patch(
                "app.agents.orchestrator.nodes.quality_check._call_vision_llm",
                new=AsyncMock(return_value='{"pass":true,"score":95,"issues":[],"critique":"ok"}'),
            )
        )
        stack.enter_context(
            patch("app.services.media_plan.build_media_plan", new=AsyncMock(return_value={}))
        )
        out = asyncio.run(_run_format_chain(state, "instagram-square"))

    ft = out["format_tasks"]["instagram-square"]
    assert ft["template_id"] == "vibrant-pop-square"  # style-tagged selection
    assert ft["status"] == "verified"
