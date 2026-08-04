"""Tests for the unified Scene Composer (deterministic, DS-following figures)."""

import re

import pytest

from app.services.tools.composer import (
    ARCHETYPE_IDS,
    compose_default_scene,
    compose_scene,
)
from app.services.tools.icon_search import search_icons

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}")
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]"
)


@pytest.mark.asyncio
async def test_composer_renders_all_archetypes():
    """Every archetype composes a non-trivial figure without exceptions."""
    for arch in ARCHETYPE_IDS:
        svg = compose_scene(
            seed="t|1", ground="white", archetype=arch,
            motif_names=["rocket", "chart-bar", "book"],
            highlights=["arrow-1", "sprinkle-3"],
            category="WRITING",
        )
        assert len(svg) > 300, f"{arch} produced no content"


@pytest.mark.asyncio
async def test_composer_is_deterministic():
    a = compose_scene(seed="same|2", ground="white", archetype="cluster",
                      motif_names=["rocket"], category="PROJECT")
    b = compose_scene(seed="same|2", ground="white", archetype="cluster",
                      motif_names=["rocket"], category="PROJECT")
    assert a == b


@pytest.mark.asyncio
async def test_composer_no_raw_hex_or_emoji():
    svg = compose_scene(seed="x|3", ground="white", archetype="cluster",
                        motif_names=["rocket", "book"], highlights=["arrow-1"])
    assert not _HEX.search(svg)
    assert not _EMOJI.search(svg)


@pytest.mark.asyncio
async def test_composer_uses_ds_tokens():
    svg = compose_scene(seed="x|4", ground="white", archetype="horizon",
                        motif_names=["rocket"])
    assert "var(--ill-ink)" in svg or "var(--color-text)" in svg


@pytest.mark.asyncio
async def test_composer_ground_adaptation():
    white = compose_scene(seed="g|1", ground="white", archetype="cluster", motif_names=["rocket"])
    black = compose_scene(seed="g|1", ground="black", archetype="cluster", motif_names=["rocket"])
    assert "var(--color-text-inverted)" in black  # black-ground ink token present
    assert "var(--ill-ink)" in white


@pytest.mark.asyncio
async def test_composer_motif_search_wiring():
    """Motifs resolved via icon_search find their way into the figure."""
    names = search_icons("rocket")
    assert names and "rocket" in names
    svg = compose_scene(seed="m|1", ground="white", archetype="cluster", motif_names=names[:2])
    assert len(svg) > 300


@pytest.mark.asyncio
async def test_composer_unknown_inputs_graceful():
    svg = compose_scene(seed="u|1", ground="white", archetype="cluster",
                        motif_names=["definitely-not-an-icon"],
                        highlights=["definitely-not-a-mark"])
    assert "definitely-not-an-icon" not in svg
    assert len(svg) > 200


@pytest.mark.asyncio
async def test_composer_dicebear_hero():
    svg = compose_scene(seed="h|1", ground="white", style="open-peeps",
                        archetype="ascend", motif_names=["rocket"])
    assert "open-peeps" in svg or len(svg) > 300


@pytest.mark.asyncio
async def test_composer_renders_at_2x_pixel_size():
    """The SVG declares 800x480 (2x) while keeping the 400x240 viewBox, so
    the vector renders crisply even when the figure is displayed small."""
    svg = compose_scene(seed="2x|1", ground="white", archetype="cluster",
                        motif_names=["rocket"])
    assert 'width="800" height="480"' in svg
    assert 'viewBox="0 0 400 240"' in svg


@pytest.mark.asyncio
async def test_compose_default_scene_is_deterministic_and_safe():
    a = compose_default_scene(seed="d|1", ground="white", category="PROJECT")
    b = compose_default_scene(seed="d|1", ground="white", category="PROJECT")
    assert a == b
    assert not _HEX.search(a)
    assert not _EMOJI.search(a)
    assert "var(--ill-ink)" in a or "var(--color-text)" in a
    assert len(a) > 300
