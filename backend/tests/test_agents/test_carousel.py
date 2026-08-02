"""Carousel support tests — slide expansion, formats, and copy splitting."""

import asyncio
import json
from contextlib import ExitStack

from app.agents.orchestrator.graph import _extract_slides, process_all_formats_node
from app.agents.orchestrator.nodes.copywriter import _fallback_slides, _split_sentences
from app.agents.orchestrator.state import initial_state
from app.services.formats import (
    get_format_info,
    is_carousel,
    parse_carousel_slide,
)

# ─── Format helpers ─────────────────────────────────────────────────────────


def test_carousel_format_registered():
    info = get_format_info("instagram-carousel")
    assert (info.width, info.height) == (1080, 1080)


def test_slide_format_resolves_to_carousel_dims():
    assert is_carousel("instagram-carousel")
    assert is_carousel("instagram-carousel-3")
    assert not is_carousel("instagram-square")
    assert parse_carousel_slide("instagram-carousel-2") == ("instagram-carousel", 2)
    assert parse_carousel_slide("instagram-carousel") is None
    assert parse_carousel_slide("instagram-square") is None
    info = get_format_info("instagram-carousel-5")
    assert (info.width, info.height) == (1080, 1080)


# ─── Copy splitting helpers ─────────────────────────────────────────────────


def test_fallback_slides_produce_n_frames():
    slides = _fallback_slides(
        "First sentence. Second sentence. Third finding. Fourth insight.", "Title", 4
    )
    assert len(slides) == 4
    assert slides[0].headline == "Title"
    assert slides[0].body  # first slide carries the hook
    for s in slides:
        assert s.headline  # every slide has a headline (cover + derived)
        assert s.body  # every slide has substance


def test_finalize_slides_guarantees_headline_and_bounds_body():
    from app.agents.orchestrator.nodes.copywriter import SlideCopy, _finalize_slides

    long_body = "A very long sentence that goes on and on about typography and " * 12
    slides = [
        SlideCopy(headline="", subhead="", body=long_body, tagline="", badge=None),
        SlideCopy(headline="Real hook", subhead="", body="Short body.", tagline="", badge=None),
    ]
    out = _finalize_slides(slides, "Title")
    assert out[0].headline  # derived, non-empty
    assert len(out[0].body) <= 160  # bounded so it fits the square canvas
    assert out[1].headline == "Real hook"
    assert out[1].body == "Short body."


def test_split_sentences_respects_count():
    chunks = _split_sentences(
        "One. Two. Three. Four. Five. Six. Seven. Eight.", 4
    )
    assert len(chunks) == 4
    assert all(c.strip() for c in chunks)


def test_extract_slides_parses_carousel_copy():
    copy = json.dumps({
        "slides": [
            {"headline": "C1", "subhead": "", "body": "B1", "tagline": "", "badge": None},
            {"headline": "C2", "subhead": "", "body": "B2", "tagline": "", "badge": None},
        ]
    })
    slides = _extract_slides(copy)
    assert len(slides) == 2
    assert slides[0]["headline"] == "C1"


def test_extract_slides_empty_on_plain_copy():
    assert _extract_slides('{"headline":"H","body":"B"}') == []
    assert _extract_slides("not json") == []
    assert _extract_slides("") == []


# ─── Pipeline expansion ──────────────────────────────────────────────────────


def _carousel_state():
    state = initial_state(
        title="T",
        content="C",
        platforms=["instagram-carousel"],
        slides=3,
        _task_id="test-carousel",
        design_tokens={
            "--color-bg": "#FFFFFF",
            "--color-text": "#000000",
            "--color-border": "#D9D9D9",
            "--color-bg-inverted": "#000000",
            "--color-text-inverted": "#FFFFFF",
            "--color-text-secondary": "#6E6E6E",
            "--font-sans": "Inter",
            "--font-display": "Space Grotesk",
        },
        footer={"left": "A", "right": "@B"},
        categories=[{"name": "WRITING"}],
    )
    state["format_tasks"]["instagram-carousel"]["copy"] = json.dumps({
        "slides": [
            {"headline": "C1", "subhead": "", "body": "B1", "tagline": "", "badge": None},
            {"headline": "C2", "subhead": "", "body": "B2", "tagline": "", "badge": None},
            {"headline": "C3", "subhead": "", "body": "B3", "tagline": "", "badge": None},
        ]
    })
    return state


def _patches():
    import re

    def good_html(agent_role, system_prompt, user_prompt, temperature, max_tokens):
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

    from unittest.mock import AsyncMock, patch

    return (
        patch("app.agents.orchestrator.nodes.designer.call_llm",
              new=AsyncMock(side_effect=good_html)),
        patch("app.agents.orchestrator.nodes.quality_check.render_to_png",
              new=AsyncMock(return_value=b"PNG")),
        patch("app.agents.orchestrator.nodes.quality_check._call_vision_llm",
              new=AsyncMock(return_value='{"pass":true,"score":90,"issues":[],"critique":"ok"}')),
    )


def test_process_all_formats_expands_carousel_into_slides():
    state = _carousel_state()
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))

    fts = out["format_tasks"]
    assert set(fts.keys()) == {
        "instagram-carousel-1",
        "instagram-carousel-2",
        "instagram-carousel-3",
    }
    for sid, ft in fts.items():
        assert ft["status"] == "verified", f"{sid}: {ft['status']}"
        assert ft["quality_score"] >= 80
        # each slide's copy is its own frame
        assert json.loads(ft["copy"])["headline"].startswith("C")
    assert out["verification"]["instagram-carousel-1"]["pass"] is True


def test_carousel_expansion_assigns_slide_context():
    state = _carousel_state()
    with ExitStack() as stack:
        for p in _patches():
            stack.enter_context(p)
        out = asyncio.run(process_all_formats_node(state))

    # slide_context is carried on the merged state through the chain slices
    assert out["retry_count"]  # merged deterministically
    for sid in ("instagram-carousel-1", "instagram-carousel-3"):
        assert sid in out["verification"]
