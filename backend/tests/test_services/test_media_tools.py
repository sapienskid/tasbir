"""Tests for the media tools (find_photo + unified illustrate)."""

import re

import pytest

from app.services.tools.illustrator import (
    compose_peep,
    run_illustrate,
)
from app.services.tools.photo import (
    FIND_PHOTO_TOOL,
    embed_photo_into_html,
    format_shortlist,
    pick_candidate,
    search_photo_candidates,
)

# ---------------------------------------------------------------------------
# Multi-turn tool loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_llm_tool_loop_roundtrip(monkeypatch):
    """find_photo → (tool result fed back) → final text, in one loop."""
    from types import SimpleNamespace

    from langchain_core.messages import AIMessage

    from app.services.llm import call_llm_tool_loop

    script = [
        AIMessage(content="", tool_calls=[
            {"name": "find_photo", "args": {"query": "minimal"}, "id": "c1"}
        ]),
        AIMessage(content="reviewed, declining", tool_calls=[]),
    ]
    state = {"i": 0, "messages": None}

    async def fake_retry(bound, messages):
        r = script[state["i"]]
        state["i"] += 1
        if state["i"] == 2:
            state["messages"] = list(messages)
        return r

    monkeypatch.setattr("app.services.llm.call_llm_with_retry", fake_retry)
    async def _cfg(name):
        return SimpleNamespace(model="test-model", fallback_models=[])

    monkeypatch.setattr("app.services.agents.get_agent_config", _cfg)

    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key"),
    )

    handled = []

    async def find_handler(args):
        handled.append(args)
        return "[0] pexels · 1200x627"

    out = await call_llm_tool_loop(
        agent_role="designer",
        system_prompt="sys",
        user_prompt="user",
        tools=[FIND_PHOTO_TOOL],
        handlers={"find_photo": find_handler},
    )
    assert out == "reviewed, declining"
    assert handled == [{"query": "minimal"}]
    # the tool result was fed back as a ToolMessage before the final turn
    types = [type(m).__name__ for m in state["messages"]]
    assert types[-1] == "ToolMessage"
    assert "pexels" in state["messages"][-1].content


@pytest.mark.asyncio
async def test_call_llm_tool_loop_hits_turn_cap(monkeypatch):
    from types import SimpleNamespace

    from langchain_core.messages import AIMessage

    from app.services.llm import call_llm_tool_loop

    async def always_tool(bound, messages):
        return AIMessage(content="", tool_calls=[
            {"name": "find_photo", "args": {"query": "x"}, "id": "c"}
        ])

    monkeypatch.setattr("app.services.llm.call_llm_with_retry", always_tool)
    async def _cfg(name):
        return SimpleNamespace(model="test-model", fallback_models=[])

    monkeypatch.setattr("app.services.agents.get_agent_config", _cfg)

    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key"),
    )

    async def find_handler(args):
        return "[0] pexels · 1200x627"

    out = await call_llm_tool_loop(
        agent_role="designer",
        system_prompt="sys",
        user_prompt="user",
        tools=[FIND_PHOTO_TOOL],
        handlers={"find_photo": find_handler},
        max_turns=2,
    )
    assert out == ""  # exhausted turns → no final answer

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}")
NAMED_RE = re.compile(r'(?:fill|stroke)="(?:black|white)"')
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")


# ---------------------------------------------------------------------------
# DiceBear curated styles
# ---------------------------------------------------------------------------


def test_curated_styles_register():
    from app.services.tools.peep_styles import CURATED_STYLE_IDS, CURATED_STYLES

    # The keep-list: 3 humans + 1 robot + 4 abstract + landscape (see ADR-0018).
    assert len(CURATED_STYLES) == 9
    for sid in CURATED_STYLE_IDS:
        info = CURATED_STYLES[sid]
        assert info.id == sid
        assert info.license  # every curated style has a license label
        assert info.description


def test_keep_list_styles():
    from app.services.tools.peep_styles import CURATED_STYLES

    expected = {"open-peeps", "lorelei", "notionists", "bottts",
                "blobs", "initials", "shapes", "waves", "landscape"}
    assert set(CURATED_STYLES) == expected


def test_excluded_styles_not_registered():
    from app.services.tools.peep_styles import CURATED_STYLES

    # Gradients forbidden (Swiss rule), text-based, micro-canvas, CC BY,
    # and the previously-curated styles pruned to the 9-style keep-list.
    for sid in ("identicon", "pixel-art", "fun-emoji", "avataaars", "planets",
                "constellation", "critters", "sprouts", "clay", "moods",
                "rings", "stripes", "triangles", "squircles", "shape-grid",
                "loops", "disco", "weave"):
        assert sid not in CURATED_STYLES


def test_people_styles_have_parts():
    from app.services.tools.peep_styles import style_parts

    parts = style_parts("open-peeps")
    assert "facial_hair" in parts
    assert "moustache3" in parts["facial_hair"]
    assert "hair" in parts
    assert len(parts["hair"]) >= 20
    # Abstract styles expose no pinnable parts.
    assert style_parts("blobs") == {}


def test_compose_peep_monochrome_and_deterministic():

    a = compose_peep("post|fig", ground="white", style="open-peeps")
    b = compose_peep("post|fig", ground="white", style="open-peeps")
    assert a == b  # deterministic
    assert 'class="figure"' in a
    assert "<svg" in a
    assert not HEX_RE.search(a)  # verifier-safe: no raw hex
    assert not NAMED_RE.search(a)  # no raw named colors either
    assert "var(--ill-" in a  # recolored to brand tokens
    assert 'data-ground="black"' in a  # ground-adaptive role vars
    assert "<metadata" not in a  # DiceBear RDF metadata stripped
    assert "<!--" not in a  # comment banner stripped
    assert not EMOJI_RE.search(a)
    assert "<title" not in a.lower() and "<desc" not in a.lower()


def test_compose_peep_all_curated_styles_clean():
    from app.services.tools.peep_styles import CURATED_STYLES

    for sid in CURATED_STYLES:
        for ground in ("white", "black"):
            fig = compose_peep(f"check|{sid}|{ground}", ground=ground, style=sid)
            assert fig.startswith('<div class="figure">'), sid
            assert not HEX_RE.search(fig), f"{sid}: raw hex"
            assert not NAMED_RE.search(fig), f"{sid}: named color"
            assert "var(--ill-" in fig, f"{sid}: not recolored"
            assert "<metadata" not in fig, f"{sid}: metadata"


def test_compose_peep_varies_by_seed():

    a = compose_peep("seed-a", style="open-peeps")
    b = compose_peep("seed-b", style="open-peeps")
    assert a != b


def test_compose_peep_pins_part():

    fig = compose_peep("p", style="open-peeps", parts={"facial_hair": "moustache3"})
    assert "facialHair-moustache3" in fig
    # Abstract styles ignore part pinning gracefully.
    fig2 = compose_peep("p", style="blobs", parts={"facial_hair": "moustache3"})
    assert fig2.startswith('<div class="figure">')


def test_compose_peep_invalid_part_ignored():

    fig = compose_peep("p", style="open-peeps", parts={"facial_hair": "bogus-style"})
    assert fig.startswith('<div class="figure">')  # graceful fallback to random


def test_compose_peep_line_palette_no_mid_grays():

    fig = compose_peep("p", style="open-peeps", palette="line")
    # 2-tone mapping must not reference the mid/light tokens.
    assert "--ill-mid" not in fig.split("</style>")[0] or "var(--ill-mid)" not in fig
    assert "var(--ill-ink)" in fig and "var(--ill-paper)" in fig
    assert not HEX_RE.search(fig)


def test_compose_peep_original_palette_keeps_colors():

    # "original" skips recolor → raw hex present (preview-only path).
    fig = compose_peep("p", style="open-peeps", palette="original")
    assert HEX_RE.search(fig)  # colors kept intentionally
    assert 'class="figure"' in fig


def test_compose_peep_unknown_palette_falls_back():

    fig = compose_peep("p", style="open-peeps", palette="bogus")
    assert not HEX_RE.search(fig)  # defaulted to mono (recolored)
    assert "var(--ill-" in fig


def test_run_illustrate_styles():
    anthropic = run_illustrate({"style": "anthropic", "theme": "flow"}, "s")
    assert anthropic.startswith("<svg")
    peep = run_illustrate({"style": "open-peeps", "theme": "growth"}, "s")
    assert 'class="figure"' in peep
    lorelei = run_illustrate({"style": "lorelei", "theme": "focus", "hair": "variant03"}, "s")
    assert 'class="figure"' in lorelei
    assert "variant03" in lorelei  # part passed through


def test_run_illustrate_unknown_style_falls_back():
    fig = run_illustrate({"style": "bogus", "theme": "x"}, "s")
    assert 'class="figure"' in fig  # defaults to open-peeps figure


# ---------------------------------------------------------------------------
# find_photo
# ---------------------------------------------------------------------------


def test_pick_candidate_by_index():
    cands = [
        {"url": "a", "width": 800, "provider": "pexels", "photographer": "Jo", "license": "Pexels License"},
        {"url": "b", "width": 1600, "provider": "pexels", "photographer": "Jo", "license": "Pexels License"},
    ]
    picked = pick_candidate(cands, 1)
    assert picked["url"] == "b"
    assert picked["attribution"]  # attribution attached on pick


def test_pick_candidate_invalid():
    cands = [{"url": "a", "provider": "pexels"}]
    assert pick_candidate(cands, None) is None
    assert pick_candidate(cands, 5) is None
    assert pick_candidate(cands, "x") is None
    assert pick_candidate([], 0) is None


def test_format_shortlist_empty():
    text = format_shortlist([])
    assert "No photos found" in text


def test_format_shortlist_lists_candidates():
    text = format_shortlist([
        {"url": "a", "width": 1200, "height": 627, "provider": "pexels", "license": "Pexels License",
         "photographer": "Jo"},
    ])
    assert "[0]" in text
    assert "pexels" in text
    assert "choose_photo" in text


@pytest.mark.asyncio
async def test_search_photo_candidates_is_direct_no_fallback(monkeypatch):
    """The exact query is passed through — no query rewriting or fallback pool."""
    seen = []

    async def _pexels(query, orientation="landscape", per_page=8):
        seen.append(("pexels", query))
        return []

    async def _pixabay(query, orientation="landscape", per_page=8):
        seen.append(("pixabay", query))
        return []

    async def _wiki(query, orientation="landscape", per_page=8):
        seen.append(("wikimedia", query))
        return [{"url": "https://w.example/x.jpg", "width": 1200, "height": 800,
                 "provider": "wikimedia", "photographer": "A", "license": "CC BY-SA 4.0"}]

    monkeypatch.setattr("app.services.tools.photo.search_pexels", _pexels)
    monkeypatch.setattr("app.services.tools.photo.search_pixabay", _pixabay)
    monkeypatch.setattr("app.services.tools.photo.search_wikimedia", _wiki)

    out = await search_photo_candidates("minimal brutalist concrete", "landscape")
    assert out and out[0]["provider"] == "wikimedia"
    # every provider got the SAME exact query (no variant/pool queries)
    assert all(q == "minimal brutalist concrete" for _, q in seen)
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_search_photo_candidates_empty_reports_no_results(monkeypatch):
    async def _none(*args, **kwargs):
        return []

    monkeypatch.setattr("app.services.tools.photo.search_pexels", _none)
    monkeypatch.setattr("app.services.tools.photo.search_pixabay", _none)
    monkeypatch.setattr("app.services.tools.photo.search_wikimedia", _none)
    assert await search_photo_candidates("nothing here", "landscape") == []


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


def test_embed_photo_into_html_img_marker():
    html = (
        "<!DOCTYPE html><html><head><style>:root{--color-text:#000}</style></head>"
        '<body><div class="slot"><img data-image-key="0" /></div></body></html>'
    )
    out = embed_photo_into_html(
        html, {"data": "QUJD", "mime": "image/jpeg", "alt": "A photo"}, "Photo by Jo on Pexels"
    )
    assert "class=\"auto-photo\"" in out
    assert "src=\"data:image/jpeg;base64,QUJD\"" in out
    assert "Photo by Jo on Pexels" in out
    assert "grayscale(1)" in out  # grayscale filter injected
    assert "data-image-key=\"0\"" not in out  # marker consumed


def test_embed_photo_into_html_element_marker():
    html = '<body><div data-image-key="0" class="img-box"></div></body>'
    out = embed_photo_into_html(html, {"data": "x", "mime": "image/png", "alt": ""}, "Credit")
    assert "auto-photo" in out
    assert "data-image-key" not in out


def test_embed_photo_into_html_no_marker_unchanged():
    html = "<html><body>plain</body></html>"
    out = embed_photo_into_html(html, {"data": "x", "mime": "image/png", "alt": ""}, "Credit")
    assert out == html
