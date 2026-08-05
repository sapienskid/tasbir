"""Deterministic chart generator + media-plan chart kind (Phase 3)."""

from __future__ import annotations

from app.services.charts import chart_plan_ok, generate_chart_svg
from app.services.media_plan import _parse_plan


def test_chart_svg_is_token_only_and_has_bars():
    svg = generate_chart_svg([10, 25, 40], ["A", "B", "C"], ground="white", title="Growth")
    assert "<svg" in svg
    assert svg.count("<rect") == 3
    assert "var(--color-text)" in svg
    assert "var(--color-border)" in svg
    assert "#" not in svg  # no raw hex — verifier-safe
    assert "Growth" in svg


def test_chart_svg_adapts_to_black_ground():
    svg = generate_chart_svg([5], ground="black")
    assert "var(--color-text-inverted)" in svg
    assert "var(--color-border-inverted)" in svg


def test_chart_svg_handles_empty():
    svg = generate_chart_svg([], [], "white", "")
    assert "<svg" in svg  # degrades to a single bar instead of crashing


def test_chart_plan_ok():
    assert chart_plan_ok({"kind": "chart", "chart": {"values": [1, 2]}})
    assert not chart_plan_ok({"kind": "chart", "chart": {}})
    assert not chart_plan_ok({"kind": "photo"})


def test_parse_plan_accepts_chart_kind():
    raw = (
        '[{"target": "instagram-square", "kind": "chart", '
        '"chart": {"values": [12, 30, 45], "labels": ["A", "B", "C"], "title": "Stats"}}]'
    )
    plan = _parse_plan(raw)
    assert plan[0]["kind"] == "chart"
    assert plan[0]["chart"]["values"] == [12, 30, 45]
    assert plan[0]["chart"]["title"] == "Stats"
