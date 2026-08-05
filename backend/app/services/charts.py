"""Deterministic data-viz for stat-driven posts (Phase 3 foundation).

A small, token-only chart generator: bar charts rendered as clean SVG using
``var(--color-*)`` references only, so the output passes the verifier and
adapts to both grounds. Deterministic per input — no LLM, no hex, no emoji.

The media-plan director can choose ``kind: "chart"`` for comparison/tutorial
posts; the rendered SVG is injected into a template's illustration slot (or the
designer's ``data-illustration`` marker) exactly like a procedural figure.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

VIEW_W, VIEW_H = 800, 480
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 48, 24, 40, 48
_LABEL_W = 700  # track width for bars
_MAX_BARS = 6


def _ink(ground: str) -> str:
    return "var(--color-text-inverted)" if ground == "black" else "var(--color-text)"


def _muted(ground: str) -> str:
    return "var(--color-text-secondary)"


def _baseline(ground: str) -> str:
    return "var(--color-border-inverted)" if ground == "black" else "var(--color-border)"


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def generate_chart_svg(
    values: list,
    labels: list | None = None,
    ground: str = "white",
    title: str = "",
) -> str:
    """A clean token-only bar chart. ``values`` are numbers, ``labels`` optional."""
    ground = ground if ground in ("white", "black") else "white"
    vals = [_num(v) for v in (values or [])][: _MAX_BARS]
    if not vals:
        vals = [1.0]
    labs = list(labels or [])[: _MAX_BARS]
    while len(labs) < len(vals):
        labs.append("")

    hi = max(vals) if vals else 1.0
    if hi <= 0:
        hi = 1.0
    track_w = VIEW_W - PAD_LEFT - PAD_RIGHT
    bar_h = VIEW_H - PAD_TOP - PAD_BOTTOM
    slot = track_w / len(vals)
    bar_w = min(slot * 0.5, 64.0)

    el: list[str] = []
    for i, v in enumerate(vals):
        h = max(bar_h * (v / hi), 2.0)
        x = PAD_LEFT + i * slot + (slot - bar_w) / 2
        y = PAD_TOP + (bar_h - h)
        el.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="{_ink(ground)}"/>'
        )
        el.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 10:.1f}" text-anchor="middle" '
            f'font-family="var(--font-sans)" font-size="22" font-weight="500" '
            f'fill="{_muted(ground)}">{v:g}</text>'
        )
        if labs[i]:
            el.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{PAD_TOP + bar_h + 34:.1f}" '
                f'text-anchor="middle" font-family="var(--font-sans)" font-size="20" '
                f'fill="{_muted(ground)}">{labs[i]}</text>'
            )

    baseline_y = PAD_TOP + bar_h
    el.insert(
        0,
        f'<line x1="{PAD_LEFT:.0f}" y1="{baseline_y:.0f}" '
        f'x2="{VIEW_W - PAD_RIGHT:.0f}" y2="{baseline_y:.0f}" '
        f'stroke="{_baseline(ground)}" stroke-width="2"/>',
    )
    head = ""
    if title:
        head = (
            f'<text x="{PAD_LEFT:.0f}" y="{32:.0f}" font-family="var(--font-display)" '
            f'font-size="26" font-weight="700" fill="{_ink(ground)}">{title}</text>'
        )

    body = "\n  ".join(el)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{VIEW_W}" height="{VIEW_H}" '
        f'viewBox="0 0 {VIEW_W} {VIEW_H}" preserveAspectRatio="xMidYMid meet" '
        'role="img" aria-hidden="true">\n'
        f"  {head}\n  {body}\n"
        "</svg>"
    )


def chart_plan_ok(entry: dict) -> bool:
    """Whether a media-plan entry is a renderable chart."""
    values = (entry or {}).get("chart") or {}
    return bool(entry.get("kind") == "chart" and (values.get("values") or []))


__all__ = ["generate_chart_svg", "chart_plan_ok"]
