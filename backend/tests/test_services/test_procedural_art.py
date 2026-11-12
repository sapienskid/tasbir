"""All operator-supplied motifs remain deterministic and token-only."""

import random
import re
from xml.etree import ElementTree as ET

import pytest

from app.services.covers import COVER_MOTIFS, CoverRequest, build_cover_svg
from app.services.ds_context import DSContext
from app.services.illustration import generate_figure_metrics, generate_illustration_svg
from app.services.procedural_art import MOTIFS, Noise, generate_art_svg
from app.services.tokens import DEFAULT_TOKEN_VALUES

PALETTE = {
    "bg": "var(--color-bg)",
    "ink": "var(--color-text)",
    "acc": ["var(--color-text-secondary)", "var(--color-border)"],
    "hi": "var(--color-text-secondary)",
}


@pytest.mark.parametrize("motif", MOTIFS)
def test_all_fifteen_motifs_are_seeded_valid_and_exposed(motif):
    assert len(MOTIFS) == 22
    svg = generate_art_svg(motif, "7", PALETTE, grain=True)
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 1600 900"
    assert svg == generate_art_svg(motif, "7", PALETTE, grain=True)
    assert svg != generate_art_svg(motif, "8", PALETTE, grain=True)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg)
    assert "<text" not in svg
    assert "None" not in svg
    ids = re.findall(r'\bid="([^"]+)"', svg)
    assert len(ids) == len(set(ids))
    for reference in re.findall(r"url\(#([^)]+)\)", svg):
        assert reference in ids
    assert f"field-{motif}" in COVER_MOTIFS


@pytest.mark.parametrize("motif", MOTIFS)
def test_field_art_also_works_in_social_slots(motif):
    svg = generate_illustration_svg("article", "black", f"field-{motif}")
    ET.fromstring(svg)
    assert "var(--color-text-inverted)" in svg
    assert generate_figure_metrics("article", "black", f"field-{motif}")["within_safe"]


@pytest.mark.parametrize("size", [(1600, 900), (1200, 630), (1080, 1080)])
def test_native_size_and_brand_palette(size):
    width, height = size
    ctx = DSContext(ds_id="brand", tokens={**DEFAULT_TOKEN_VALUES, "--color-accent": "#D97757"})
    request = CoverRequest(motif="field-tiles", width=width, height=height)
    svg = build_cover_svg(request, ctx, 0)
    root = ET.fromstring(svg)
    assert root.attrib["width"] == str(width)
    assert root.attrib["height"] == str(height)
    assert root.attrib["viewBox"] == f"0 0 {width} {height}"
    assert "var(--color-accent)" in svg
    assert "#C6F432" not in svg  # No hardcoded highlight from the supplied example.


def test_noise_is_repeatable_and_validates_grid():
    first, second = Noise(random.Random(3)), Noise(random.Random(3))
    assert first(-1.2, 33.6) == second(-1.2, 33.6)
    assert 0 <= first(-1.2, 33.6) <= 1
    with pytest.raises(ValueError, match="power of two"):
        Noise(random.Random(3), 63)
