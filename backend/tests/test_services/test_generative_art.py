"""Connected artwork: reproducible geometry, safe output and complete framing."""

import dataclasses
import json
import random
import re
from xml.etree import ElementTree as ET

import pytest

from app.services.generative_art import build_composition, render_composition, synthesis
from app.services.procedural_art import Noise, Svg, generate_art_svg

PALETTE = {
    "bg": "var(--paper)",
    "ink": "var(--ink)",
    "acc": ["var(--accent)"],
    "hi": "var(--accent)",
}
SIZES = [(1600, 900), (1080, 1080), (256, 2400), (2400, 256)]
NS = {"s": "http://www.w3.org/2000/svg"}


@pytest.mark.parametrize("size", SIZES)
def test_repeatable_geometry_and_valid_xml(size):
    first = render_composition("repeatable", PALETTE, *size)
    assert first == render_composition("repeatable", PALETTE, *size)
    root = ET.fromstring(first)
    assert root.attrib["viewBox"] == f"0 0 {size[0]} {size[1]}"
    assert root.findall(".//s:path", NS)
    assert len(first) < 60_000


def test_recipe_describes_real_parts_without_colors():
    recipe = build_composition("recipe")
    payload = recipe.to_dict()
    json.dumps(payload)
    assert payload["seed"] == "recipe"
    assert payload["layer_count"] == len(payload["layers"])
    assert all(layer["elements"] for layer in payload["layers"])
    assert any(
        element["fill"] == "accent" for layer in payload["layers"] for element in layer["elements"]
    )
    assert "var(--" not in json.dumps(payload)
    with pytest.raises(dataclasses.FrozenInstanceError):
        recipe.seed = "changed"


def test_seed_changes_geometry_and_structure():
    recipes = [build_composition(f"variety-{i}") for i in range(60)]
    assert {r.subject for r in recipes} == {"botanical", "aperture", "vessel"}
    assert len({(r.subject, r.topology) for r in recipes}) >= 8
    geometry = {tuple(e.path for layer in r.layers for e in layer.elements) for r in recipes}
    assert len(geometry) == 60
    assert build_composition("same", 1600, 900).key != build_composition("same", 1080, 1080).key


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("placement", ["left", "center", "right"])
def test_svg_control_points_stay_inside_safe_frame(size, placement):
    width, height = size
    for index in range(20):
        root = ET.fromstring(
            render_composition(f"frame-{index}", PALETTE, width, height, placement)
        )
        moved = root.find(".//s:g[@transform]", NS)
        dx, dy = (0.0, 0.0)
        if moved is not None:
            dx, dy = map(float, re.findall(r"-?\d+(?:\.\d+)?", moved.attrib["transform"]))
        # All paths use M/L/C commands. Cubic curves stay inside their control
        # point hull, so this also checks that complete silhouettes fit.
        for path in root.findall(".//s:path", NS):
            values = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", path.attrib["d"])))
            assert len(values) % 2 == 0
            half_stroke = float(path.attrib.get("stroke-width", "0")) / 2
            for x, y in zip(values[::2], values[1::2]):
                assert width * 0.12 - 0.2 <= x + dx - half_stroke
                assert x + dx + half_stroke <= width * 0.88 + 0.2
                assert height * 0.12 - 0.2 <= y + dy - half_stroke
                assert y + dy + half_stroke <= height * 0.88 + 0.2


@pytest.mark.parametrize("seed", [f"palette-{i}" for i in range(12)])
def test_palette_mapping_preserves_geometry_and_visible_accent(seed):
    swapped = {
        "bg": "var(--other-paper)",
        "ink": "var(--other-ink)",
        "acc": ["var(--other-accent)"],
        "hi": "var(--other-accent)",
    }
    original = render_composition(seed, PALETTE)
    changed = render_composition(seed, swapped)
    for role in ("bg", "ink", "hi"):
        original = original.replace(PALETTE[role], swapped[role])
    assert original == changed
    assert 'fill="var(--other-accent)"' in changed
    root = ET.fromstring(changed)
    colors = {"none", swapped["bg"], swapped["ink"], swapped["hi"]}
    assert all(
        value in colors
        for element in root.iter()
        for key, value in element.attrib.items()
        if key in ("fill", "stroke")
    )


def test_hostile_seed_cannot_inject_markup_or_external_references():
    seed = '"><script>alert(1)</script><image href="https://evil.test/a"/>'
    svg = render_composition(seed, PALETTE)
    assert seed not in svg
    root = ET.fromstring(svg)
    assert not root.findall(".//s:script", NS)
    assert not root.findall(".//s:image", NS)
    assert not re.search(r"\b(?:href|onload)=", svg)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|hsl)\(", svg)


def test_registered_motif_and_shared_collector_are_deterministic():
    one = generate_art_svg("synthesis", "same", PALETTE)
    assert one == generate_art_svg("synthesis", "same", PALETTE)
    ET.fromstring(one)
    collector = Svg(1600, 900, PALETTE["bg"], prefix="shared")
    for _ in range(2):
        rng = random.Random(7)
        synthesis(collector, rng, PALETTE, Noise(rng))
    svg = str(collector)
    ids = re.findall(r'\bid="([^"]+)"', svg)
    assert len(ids) == len(set(ids))
    assert set(re.findall(r"url\(#([^)]+)\)", svg)) <= set(ids)


def test_generator_leaves_global_rng_untouched():
    random.seed(42)
    state = random.getstate()
    render_composition("local-rng", PALETTE)
    assert random.getstate() == state


@pytest.mark.parametrize("size", [(0, 900), (64, 64), (5000, 900)])
def test_invalid_canvas_is_rejected(size):
    with pytest.raises(ValueError):
        build_composition("invalid", *size)


def test_invalid_placement_is_rejected():
    with pytest.raises(ValueError):
        render_composition("invalid", PALETTE, placement="outside")
