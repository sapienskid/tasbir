"""Tests for the media tools (find_photo + unified illustrate)."""

import re

import pytest

from app.services.tools.illustrator import (
    ILLUSTRATE_TOOL,
    compose_handdrawn,
    run_illustrate,
)
from app.services.tools.photo import (
    FIND_PHOTO_TOOL,
    embed_photo_into_html,
    pick_best_candidate,
    run_find_photo,
)

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")


# ---------------------------------------------------------------------------
# Hand-drawn kits
# ---------------------------------------------------------------------------


def test_kit_files_vendored():
    from app.services.tools.illustrator import _kit_files

    assert len(_kit_files("open-peeps")) >= 10
    assert len(_kit_files("open-doodles")) >= 10
    assert _kit_files("nonexistent") == []


def test_compose_handdrawn_monochrome_and_deterministic():
    a = compose_handdrawn("open-peeps", "post|fig", "white", "focus")
    b = compose_handdrawn("open-peeps", "post|fig", "white", "focus")
    assert a == b  # deterministic
    assert 'class="figure"' in a
    assert "<svg" in a
    assert not HEX_RE.search(a)  # verifier-safe: no raw hex
    assert "var(" in a  # recolored to brand tokens
    assert "data-ground=\"black\"" in a  # ground-adaptive role vars
    # kit files carry emoji in <title>/<desc> — stripped at compose time
    assert not EMOJI_RE.search(a)
    assert "<title" not in a.lower() and "<desc" not in a.lower()


def test_compose_handdrawn_varies_by_seed():
    a = compose_handdrawn("open-peeps", "seed-a", "white")
    b = compose_handdrawn("open-peeps", "seed-b", "white")
    assert a != b


def test_run_illustrate_styles():
    anthropic = run_illustrate({"style": "anthropic", "theme": "flow"}, "s")
    assert anthropic.startswith("<svg")
    peep = run_illustrate({"style": "open-peeps", "theme": "growth"}, "s")
    assert 'class="figure"' in peep
    doodle = run_illustrate({"style": "open-doodles", "theme": "play"}, "s")
    assert 'class="figure"' in doodle


def test_run_illustrate_unknown_style_falls_back():
    svg = run_illustrate({"style": "bogus", "theme": "x"}, "s")
    assert svg.startswith("<svg")


# ---------------------------------------------------------------------------
# find_photo
# ---------------------------------------------------------------------------


def test_pick_best_candidate_prefers_wider():
    cands = [
        {"url": "a", "width": 800, "provider": "pexels"},
        {"url": "b", "width": 1600, "provider": "pexels"},
    ]
    best = pick_best_candidate(cands)
    assert best["url"] == "b"
    assert best["attribution"]  # attribution built


def test_pick_best_candidate_none():
    assert pick_best_candidate([]) is None


@pytest.mark.asyncio
async def test_run_find_photo_uses_provider_results(monkeypatch):
    async def _fake(query, orientation="landscape", min_width=None, limit=8):
        return [{"url": "https://x.example/p.jpg", "width": 1200, "height": 627,
                 "provider": "pexels", "photographer": "Jo", "license": "Pexels License"}]

    monkeypatch.setattr("app.services.tools.photo.search_photo_candidates", _fake)
    out = await run_find_photo({"query": "minimal", "orientation": "landscape"})
    assert out["ok"] is True
    assert out["url"].startswith("https://")
    assert "Pexels" in out["attribution"]


@pytest.mark.asyncio
async def test_run_find_photo_empty_query():
    out = await run_find_photo({"query": "  "})
    assert out["ok"] is False


@pytest.mark.asyncio
async def test_run_find_photo_no_results(monkeypatch):
    async def _none(*args, **kwargs):
        return []

    monkeypatch.setattr("app.services.tools.photo.search_photo_candidates", _none)
    out = await run_find_photo({"query": "nothing", "orientation": "landscape"})
    assert out["ok"] is False


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
