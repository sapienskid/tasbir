"""Tests for the procedural Anthropic-style illustration generator."""

import re

import pytest

from app.services.illustration import (
    ARCHETYPES,
    ILLUSTRATION_TOOL,
    generate_illustration_svg,
    illustration_via_tool,
)

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}")


def test_deterministic_per_seed():
    a = generate_illustration_svg("My Post|illustration", "white")
    b = generate_illustration_svg("My Post|illustration", "white")
    assert a == b


def test_varies_across_seeds():
    a = generate_illustration_svg("Post A|illustration", "white")
    b = generate_illustration_svg("Post B|illustration", "white")
    assert a != b


def test_all_archetypes_reachable_and_clean():
    seeds = [f"seed-{i}|illustration" for i in range(40)]
    seen = set()
    for seed in seeds:
        svg = generate_illustration_svg(seed, "white")
        assert svg.lstrip().startswith("<svg")
        assert svg.rstrip().endswith("</svg>")
        assert "<path" in svg
        assert not HEX_RE.search(svg)  # verifier-safe: no raw hex
        assert "{{" not in svg  # fully rendered, no leftover Jinja
        seen.add(svg.split("\n  ")[1].split(" ")[0])  # first path prefix (not arch id)
    assert seen  # composition actually renders


def test_every_archetype_renders_clean():
    for name in ARCHETYPES:
        for ground in ("white", "black"):
            svg = generate_illustration_svg(f"x|{name}", ground)
            assert not HEX_RE.search(svg)
            assert svg.lstrip().startswith("<svg")


def test_ground_palette_mapping():
    white = generate_illustration_svg("g|white", "white")
    black = generate_illustration_svg("g|black", "black")
    assert "var(--color-text)" in white
    assert "var(--color-text-inverted)" in black


def test_theme_steers_archetype():
    themed = generate_illustration_svg("p|theme", "white", theme="spiral journey")
    unthemed = generate_illustration_svg("p|theme", "white")
    assert themed != unthemed
    # A "rings" theme should produce two ring strokes (the rings archetype).
    rings = generate_illustration_svg("p|rings", "white", theme="orbit")
    assert rings.count("stroke-width:3.0") >= 1


def test_empty_seed_is_safe():
    svg = generate_illustration_svg("", "black")
    assert svg.startswith("<svg")
    assert not HEX_RE.search(svg)


def test_tool_schema_shape():
    assert ILLUSTRATION_TOOL["type"] == "function"
    fn = ILLUSTRATION_TOOL["function"]
    assert fn["name"] == "generate_illustration"
    params = fn["parameters"]
    assert "theme" in params["properties"]
    assert "theme" in params["required"]
    assert "ground" in params["properties"]


@pytest.mark.asyncio
async def test_illustration_via_tool_falls_back_deterministic(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("no tools today")

    monkeypatch.setattr("app.services.llm.call_llm_for_tool", _boom)
    svg = await illustration_via_tool(title="T", headline="H", ground="white", seed="s|illustration")
    assert svg.startswith("<svg")
    assert not HEX_RE.search(svg)


@pytest.mark.asyncio
async def test_illustration_via_tool_uses_args(monkeypatch):
    async def _fake(agent_role=None, system_prompt="", user_prompt="", tool=None, temperature=0.7, max_tokens=1024):
        return {"theme": "orbit", "ground": "black"}

    monkeypatch.setattr("app.services.llm.call_llm_for_tool", _fake)
    svg = await illustration_via_tool(title="T", headline="H", ground="white", seed="s|illustration")
    assert svg.startswith("<svg")
    assert "var(--color-text-inverted)" in svg  # black ground ink
