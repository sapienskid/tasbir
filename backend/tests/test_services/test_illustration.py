"""Tests for the unified composition engine (art package + public facade)."""

import collections
import re

import pytest

from app.services.art import (
    ASPECTS,
    CONCEPTS,
    CONCEPT_NAMES,
    FIELDS,
    RELATIONS,
    SUBJECTS,
    compose_scene,
    select_combination,
)
from app.services.illustration import (
    ILLUSTRATION_TOOL,
    generate_figure_metrics,
    generate_illustration_svg,
    illustration_via_tool,
)

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def test_deterministic_per_seed():
    a = generate_illustration_svg("My Post|illustration", "white")
    b = generate_illustration_svg("My Post|illustration", "white")
    assert a == b


def test_seed_changes_structure():
    fingerprints = {
        compose_scene(f"seed-{i}", concept="system").fingerprint for i in range(12)
    }
    assert len(fingerprints) > 1


def test_catalog_is_a_composition_grammar():
    # Every concept must offer enough combinations for a full carousel.
    for name, spec in CONCEPTS.items():
        assert len(spec["subjects"]) >= 5, name
        assert len(spec["relations"]) >= 4, name
        assert len(spec["fields"]) >= 3, name
    assert len(SUBJECTS) >= 18
    assert len(RELATIONS) >= 9
    assert len(FIELDS) >= 12


def test_structural_diversity_across_seeds():
    fingerprints: list[str] = []
    subjects: collections.Counter = collections.Counter()
    relations: collections.Counter = collections.Counter()
    fields: collections.Counter = collections.Counter()
    for i in range(200):
        scene = compose_scene(f"diversity-{i}")
        fingerprints.append(scene.fingerprint)
        subjects[scene.subject] += 1
        relations[scene.relation] += 1
        fields[scene.field] += 1

    assert len(set(fingerprints)) >= 120
    assert len(subjects) >= 14
    assert len(relations) >= 8
    assert len(fields) >= 10
    assert max(subjects.values()) / len(fingerprints) < 0.25


def test_carousel_never_repeats_a_subject_in_the_same_relation():
    for concept in CONCEPT_NAMES:
        for run in range(40):
            used_pairs: list[str] = []
            for slide in range(10):
                subject, relation, _field = select_combination(
                    f"carousel-{run}-{slide}",
                    concept,
                    avoid_pairs=tuple(used_pairs),
                )
                pair = f"{subject}|{relation}"
                assert pair not in used_pairs, (concept, run, slide, pair)
                used_pairs.append(pair)


def test_avoid_fingerprint_forces_a_different_composition():
    first = compose_scene("diversity-1", concept="system")
    second = compose_scene(
        "diversity-1", concept="system", avoid_fingerprints=(first.fingerprint,)
    )
    assert second.fingerprint != first.fingerprint


def test_every_concept_renders_clean_on_both_grounds():
    for concept in CONCEPT_NAMES:
        for ground in ("white", "black"):
            for aspect in ("square", "portrait"):
                scene = compose_scene(f"{concept}|{ground}", concept=concept, aspect=aspect)
                svg = generate_illustration_svg(
                    f"{concept}|{ground}", ground, theme=concept, aspect=aspect
                )
                assert svg.lstrip().startswith("<svg")
                assert svg.rstrip().endswith("</svg>")
                assert not HEX_RE.search(svg)
                assert "{{" not in svg
                assert "<text" not in svg
                assert "None" not in svg
                assert scene.metrics()["element_count"] >= 2


def test_every_subject_stays_inside_the_safe_frame():
    for name in SUBJECTS:
        if name == "portrait":
            continue
        for ground in ("white", "black"):
            for aspect in ASPECTS:
                scene = compose_scene(
                    f"{name}|{aspect}", ground, subject=name, aspect=aspect
                )
                m = scene.metrics()
                assert m["within_safe"], f"{name}/{aspect}: {m['box']}"
                assert 0.0 < m["occupancy"] <= 1.0
                assert m["element_count"] <= 500


def test_ground_palette_mapping():
    white = generate_illustration_svg("g|white", "white")
    black = generate_illustration_svg("g|black", "black")
    assert "var(--color-text)" in white
    assert "var(--color-text-inverted)" in black


def test_accent_is_opt_in():
    plain = generate_illustration_svg("accent|white", "white")
    accented = generate_illustration_svg("accent|white", "white", use_accent=True)
    assert "var(--color-accent)" not in plain
    assert "var(--color-accent)" in accented


def test_legacy_theme_ids_still_resolve():
    from app.services.art import LEGACY_COMBOS

    for legacy, (subject, relation, _field) in LEGACY_COMBOS.items():
        m = generate_figure_metrics(f"legacy|{legacy}", "white", legacy)
        assert m["subject"] == subject
        assert m["relation"] == relation


def test_metrics_are_structured():
    m = generate_figure_metrics("post|slide", "white", None)
    assert {
        "concept", "subject", "relation", "field", "fingerprint",
        "element_count", "box", "occupancy", "within_safe",
    } <= set(m)
    assert m["within_safe"] is True
    assert m["element_count"] >= 1
    assert m["box"]["x0"] <= m["box"]["x1"]
    assert m["box"]["y0"] <= m["box"]["y1"]


def test_tool_schema_shape():
    assert ILLUSTRATION_TOOL["type"] == "function"
    fn = ILLUSTRATION_TOOL["function"]
    assert fn["name"] == "illustrate"
    params = fn["parameters"]
    props = params["properties"]
    # The director chooses a concept; subject/relation/field are optional pins.
    assert props["concept"]["enum"] == list(CONCEPT_NAMES)
    assert params["required"] == ["concept"]
    assert "subject" in props and "relation" in props and "field" in props
    # Style enum still carries procedural + curated portrait styles.
    style_enum = props["style"]["enum"]
    assert "procedural" in style_enum
    assert "open-peeps" in style_enum
    assert "compose" not in style_enum
    assert "anthropic" not in style_enum
    for part in ("facial_hair", "hair", "expression", "accessory"):
        assert part in props


@pytest.mark.asyncio
async def test_illustration_via_tool_failure_means_no_media(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("no tools today")

    monkeypatch.setattr("app.services.llm.call_llm_for_tool", _boom)
    svg = await illustration_via_tool(
        title="T", headline="H", ground="white", seed="s|illustration"
    )
    assert svg == ""  # no deterministic fallback — media only when the LLM chose it


@pytest.mark.asyncio
async def test_illustration_via_tool_uses_args(monkeypatch):
    async def _fake(agent_role=None, system_prompt="", user_prompt="", tool=None,
                    temperature=0.7, max_tokens=1024):
        return {"concept": "limit", "ground": "black"}

    monkeypatch.setattr("app.services.llm.call_llm_for_tool", _fake)
    svg = await illustration_via_tool(
        title="T", headline="H", ground="white", seed="s|illustration"
    )
    assert svg.startswith("<svg")
    assert "var(--color-text-inverted)" in svg  # black ground ink
