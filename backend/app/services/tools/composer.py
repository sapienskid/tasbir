"""Unified Scene Composer — deterministic, content-mapped editorial figures.

The composer assembles a full editorial figure for the designated illustration
slot from up to five element sources:

  - **custom hero**   — hand-authored category SVGs (fountain-pen for WRITING,
                       wrench+gear for PROJECT, frame for PORTFOLIO, spark for
                       NOTE, robot for AI/dev) in ``illustrations/heroes/``
  - **DiceBear figure** — a curated avatar (humans: open-peeps / lorelei /
                       notionists; robots: bottts) recolored to the brand
  - **Lucide motifs** — content-mapped line icons rendered via ``<svg>`` with
                       ``stroke: currentColor`` + ``color: var(--ill-ink)``
  - **Highlights**    — CC0 hand-drawn marks (arrows, underlines, sprinkles,
                       loops, spirals, doodles…) recolored through the design
                       system tokens
  - **geometry**      — procedural hairline fields, scrims, dot grids

Everything resolves through the ground-adaptive ``--ill-*`` tokens (which the
``.figure`` wrapper derives from ``--color-*``), so **the composed figure
follows the active design system** — edit a token in the Studio and every
figure recolors. No raw hex, no emoji, verifier-safe.

Composition is a pure deterministic function of ``(seed, ground, archetype,
hero, motifs, style, theme)`` — the same inputs always produce the same SVG.
"""

from __future__ import annotations

import logging
import math
import random
import re
from pathlib import Path

from app.config import get_settings
from app.services.tools.illustrator import (
    _clean_svg,
    _figure_wrapper,
    _recolor_svg,
    _render_avatar_raw,
    _safe_ids,
)

log = logging.getLogger(__name__)

_VIEW_BOX = "0 0 400 240"

# --- Lucide motif rendering ----------------------------------------------
# Lucide SVGs are fill="none" stroke="currentColor" line art. We render them
# inside a wrapper <g> whose color is var(--ill-ink), so they follow the DS.

_ICON_DIR = "icons/lucide"

_icon_cache: dict[str, str] = {}


def _load_icon(name: str) -> str | None:
    """Return the raw Lucide SVG body for ``name`` (or None)."""
    if name in _icon_cache:
        return _icon_cache[name]
    path = Path(get_settings().design_system_dir).parent / _ICON_DIR / f"{name}.svg"
    if not path.exists():
        return None
    try:
        body = path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("[composer] icon read failed %s: %s", name, e)
        return None
    _icon_cache[name] = body
    return body


def _render_icon(name: str, x: float, y: float, size: float) -> str:
    """Wrap a Lucide icon into a positioned, ink-colored <g> element."""
    body = _load_icon(name)
    if not body:
        return ""
    # Keep only the inner path/shape elements (drop the <svg> wrapper attrs).
    inner = re.sub(r"^<svg[^>]*>", "", body, flags=re.IGNORECASE)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.IGNORECASE).strip()
    scale = size / 24.0
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) scale({scale:.3f})" '
        f'color="var(--ill-ink)" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{inner}</g>"
    )


# --- Highlights (hand-drawn marks) ---------------------------------------
# CC0 kit (see data/design_system/illustrations/highlights/LICENSE.md). Marks
# are recolored through _recolor_svg so they follow the design system.

_HL_ROOT = Path(get_settings().design_system_dir) / "illustrations" / "highlights"

_hl_cache: dict[str, str] = {}


def _load_highlight(slug: str) -> str | None:
    """Return the raw SVG for a Highlights mark (searched by slug across cats)."""
    if slug in _hl_cache:
        return _hl_cache[slug]
    if not _HL_ROOT.exists():
        return None
    for match in _HL_ROOT.rglob(f"{slug}.svg"):
        try:
            body = match.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        _hl_cache[slug] = body
        return body
    return None


def _render_highlight(slug: str, x: float, y: float, w: float, h: float, ground: str) -> str:
    """Recolor + position a Highlights mark; empty string if unknown."""
    raw = _load_highlight(slug)
    if not raw:
        return ""
    svg = _clean_svg(raw)
    svg = _recolor_svg(svg, palette="mono")
    m = re.search(r'viewBox="([^"]+)"', svg)
    vb = m.group(1) if m else "0 0 100 100"
    parts = [float(p) for p in vb.replace(",", " ").split()]
    vbw = parts[2] if len(parts) >= 3 else 100.0
    vbh = parts[3] if len(parts) >= 4 else 100.0
    scale_x = w / vbw
    scale_y = h / vbh
    inner = re.sub(r"^<svg[^>]*>", "", svg, flags=re.IGNORECASE)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.IGNORECASE).strip()
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) scale({scale_x:.3f},{scale_y:.3f})">'
        f"{inner}</g>"
    )


# --- Custom hero SVGs -----------------------------------------------------
# Category heroes authored as monochrome var(--ill-*) fragments in
# data/design_system/illustrations/heroes/. Loaded raw (already token-based).

_HERO_ROOT = Path(get_settings().design_system_dir) / "illustrations" / "heroes"

_hero_cache: dict[str, str] = {}


def _load_hero(slug: str) -> str | None:
    if slug in _hero_cache:
        return _hero_cache[slug]
    if not _HERO_ROOT.exists():
        return None
    for match in _HERO_ROOT.rglob(f"{slug}.svg"):
        try:
            body = match.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        _hero_cache[slug] = body
        return body
    return None


def _render_hero(slug: str, x: float, y: float, w: float, h: float) -> str:
    raw = _load_hero(slug)
    if not raw:
        return ""
    svg = _safe_ids(raw)
    m = re.search(r'viewBox="([^"]+)"', svg)
    vb = m.group(1) if m else "0 0 100 100"
    parts = [float(p) for p in vb.replace(",", " ").split()]
    vbw = parts[2] if len(parts) >= 3 else 100.0
    vbh = parts[3] if len(parts) >= 4 else 100.0
    scale_x = w / vbw
    scale_y = h / vbh
    inner = re.sub(r"^<svg[^>]*>", "", svg, flags=re.IGNORECASE)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.IGNORECASE).strip()
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) scale({scale_x:.3f},{scale_y:.3f})">'
        f"{inner}</g>"
    )


# --- Deterministic geometry primitives -----------------------------------


def _hairline(x1, y1, x2, y2, color="var(--ill-ink)") -> str:
    return (
        f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" '
        f'style="fill:none;stroke:{color};stroke-width:1.5;stroke-linecap:round"/>'
    )


def _wobble_line(rng: random.Random, x0, y0, x1, y1, amp=5.0, steps=6) -> str:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    pts = []
    for i in range(steps + 1):
        t = i / steps
        off = (rng.random() - 0.5) * 2 * amp
        pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    d = "M " + f"{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for p in pts[1:]:
        d += f" L {p[0]:.1f} {p[1]:.1f}"
    return (
        f'<path d="{d}" style="fill:none;stroke:var(--ill-ink);stroke-width:2;'
        'stroke-linecap:round;stroke-linejoin:round"/>'
    )


def _blob(rng: random.Random, cx, cy, rx, ry, fill="var(--ill-paper)") -> str:
    """Organic closed blob — an ellipse whose radius breathes with sines."""
    n = 18
    pts = []
    for i in range(n):
        a = i / n * math.tau
        rad = 1.0 + sum(
            rng.uniform(0.04, 0.12) * math.sin(rng.randint(2, 5) * a + rng.uniform(0, math.tau))
            for _ in range(3)
        )
        pts.append((cx + rx * rad * math.cos(a), cy + ry * rad * math.sin(a)))
    d = "M " + f"{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d += f" C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return f'<path d="{d}" style="fill:{fill};stroke:none"/>'


# --- Composition archetypes ----------------------------------------------
# Each archetype is a function (rng, ctx) -> list[str] of SVG elements.
# ctx carries: hero (list[str]), motifs (list[str]), hl (list[str]),
# palette dict with ink/mid/light/paper tokens.

_ARCHETYPES: dict[str, str] = {}


def _register(name: str, fn):
    _ARCHETYPES[name] = fn


def _rng(seed: str, salt: str = "") -> random.Random:
    return random.Random(f"{seed}|{salt}")


def _ctx_palette(ground: str) -> dict:
    # ink/paper follow ground; mid is ground-stable. Values are --ill-* names.
    return {
        "ink": "var(--ill-ink)",
        "paper": "var(--ill-paper)",
        "mid": "var(--ill-mid)",
        "light": "var(--ill-light)",
    }


# --- Archetype definitions (deterministic fillable layouts) --------------


def _arch_ascend(rng, ctx):
    """Hero bottom-left rising; arrow + supporting motifs swept up-right."""
    els = []
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    els.append(_wobble_line(rng, 60, 210, 320, 40, amp=7, steps=8))
    n = min(len(ctx["motifs"]), 3)
    for i in range(n):
        x = 140 + i * 90 + rng.uniform(-8, 8)
        y = 200 - i * 55 + rng.uniform(-8, 8)
        els.append(_render_icon(ctx["motifs"][i], x, y, 34))
    if ctx["hl"]:
        els.append(_render_highlight(ctx["hl"][0], 300, 170, 60, 40, ctx["ground"]))
    return els


def _arch_cluster(rng, ctx):
    """Hero centered; supporting motifs radiate around it."""
    els = []
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    n = min(len(ctx["motifs"]), 5)
    for i in range(n):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(90, 150)
        cx = 200 + r * math.cos(a)
        cy = 120 + r * math.sin(a) * 0.7
        els.append(_render_icon(ctx["motifs"][i], cx, cy, 30))
    for h in ctx["hl"][:2]:
        els.append(_render_highlight(
            h, rng.uniform(60, 300), rng.uniform(30, 180), 50, 34, ctx["ground"]
        ))
    return els


def _arch_horizon(rng, ctx):
    """Motif row on a ground line; hero on a field above."""
    els = [_hairline(40, 195, 360, 195, ctx["p"]["ink"])]
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    n = min(len(ctx["motifs"]), 4)
    for i in range(n):
        x = 70 + i * 80
        els.append(_render_icon(ctx["motifs"][i], x, 130, 30))
    if ctx["hl"]:
        els.append(_render_highlight(ctx["hl"][0], 320, 150, 60, 36, ctx["ground"]))
    return els


def _arch_field(rng, ctx):
    """Repeated motif grid across the canvas (structural, Swiss)."""
    els = []
    n = min(len(ctx["motifs"]), 8)
    rows = 2
    cols = math.ceil(n / rows)
    for i in range(n):
        col = i % cols
        row = i // cols
        x = 70 + col * 110
        y = 80 + row * 90
        els.append(_render_icon(ctx["motifs"][i], x, y, 34))
    if ctx["hl"]:
        els.append(_render_highlight(ctx["hl"][0], 320, 40, 55, 34, ctx["ground"]))
    return els


def _arch_orbit(rng, ctx):
    """Hero at center with a ring of supporting motifs."""
    els = []
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    els.append(
        '<circle cx="200" cy="120" r="60" fill="none" stroke="var(--ill-mid)" stroke-width="1.5"/>'
    )
    n = min(len(ctx["motifs"]), 6)
    for i in range(n):
        a = i / n * math.tau
        cx = 200 + 60 * math.cos(a)
        cy = 120 + 60 * math.sin(a)
        els.append(_render_icon(ctx["motifs"][i], cx - 14, cy - 14, 28))
    return els


def _arch_stack(rng, ctx):
    """Vertical stack of motifs ascending like bars."""
    els = []
    n = min(len(ctx["motifs"]), 4)
    base = 200
    for i in range(n):
        h = 40 + i * 30 + rng.uniform(0, 10)
        w = 60 + i * 12
        x = 60 + i * 78
        els.append(
            f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{ctx["p"]["paper"]}" stroke="{ctx["p"]["ink"]}" stroke-width="1.5"/>'
        )
        els.append(_render_icon(ctx["motifs"][i], x + (w - 28) / 2, base - h - 34, 28))
    if ctx["hl"]:
        els.append(_render_highlight(ctx["hl"][0], 300, 170, 60, 36, ctx["ground"]))
    return els


def _arch_cascade(rng, ctx):
    """Diagonal cascade of motifs like steps."""
    els = []
    n = min(len(ctx["motifs"]), 5)
    for i in range(n):
        x = 60 + i * 62
        y = 190 - i * 34
        els.append(_render_icon(ctx["motifs"][i], x, y, 36))
    els.append(_wobble_line(rng, 40, 215, 360, 120, amp=6, steps=7))
    return els


def _arch_counterpoint(rng, ctx):
    """Two dominant elements in tension: hero top-left, big motif bottom-right."""
    els = []
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    if ctx["motifs"]:
        els.append(_render_icon(ctx["motifs"][0], 250, 120, 80))
    if len(ctx["motifs"]) > 1:
        els.append(_render_icon(ctx["motifs"][1], 80, 40, 40))
    els.append(_hairline(40, 70, 360, 70, ctx["p"]["ink"]))
    return els


def _arch_measure(rng, ctx):
    """A ruled measure column: hairline guides + motif along a baseline."""
    els = [
        _hairline(40, 60, 360, 60, ctx["p"]["mid"]),
        _hairline(40, 200, 360, 200, ctx["p"]["mid"]),
    ]
    n = min(len(ctx["motifs"]), 4)
    for i in range(n):
        x = 70 + i * 78
        els.append(_render_icon(ctx["motifs"][i], x, 120, 32))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


def _arch_frame(rng, ctx):
    """Hero framed by a rect border; motifs outside it."""
    els = [
        '<rect x="70" y="40" width="260" height="160" fill="none" \
          stroke="var(--ill-mid)" stroke-width="1.5"/>'
    ]
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    for i, m in enumerate(ctx["motifs"][:2]):
        els.append(_render_icon(m, 40 + i * 160, 210, 26))
    return els


def _arch_burst(rng, ctx):
    """Radial burst of hairline rays + hero/motif at center."""
    els = []
    rays = rng.randint(8, 12)
    for i in range(rays):
        a = i / rays * math.tau
        x0 = 200 + 40 * math.cos(a)
        y0 = 120 + 40 * math.sin(a)
        x1 = 200 + 150 * math.cos(a)
        y1 = 120 + 150 * math.sin(a)
        els.append(_hairline(x0, y0, x1, y1, ctx["p"]["mid"]))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    for i, m in enumerate(ctx["motifs"][:2]):
        els.append(_render_icon(m, 140 + i * 90, 160, 30))
    return els


def _arch_scatter(rng, ctx):
    """Scattered motifs + highlights across the canvas (airy)."""
    els = []
    for i, m in enumerate(ctx["motifs"][:6]):
        x = rng.uniform(50, 320)
        y = rng.uniform(40, 180)
        els.append(_render_icon(m, x, y, 28))
    for h in ctx["hl"][:3]:
        els.append(_render_highlight(
            h, rng.uniform(60, 300), rng.uniform(30, 170), 50, 32, ctx["ground"]
        ))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


def _arch_gate(rng, ctx):
    """Hero between two vertical rules (a 'gate')."""
    els = [
        _hairline(50, 30, 50, 210, ctx["p"]["ink"]),
        _hairline(350, 30, 350, 210, ctx["p"]["ink"]),
    ]
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    for i, m in enumerate(ctx["motifs"][:2]):
        els.append(_render_icon(m, 130 + i * 120, 40, 30))
    return els


def _arch_column(rng, ctx):
    """Vertical column of motifs; hero at the foot."""
    els = []
    n = min(len(ctx["motifs"]), 3)
    for i in range(n):
        x = 175
        y = 50 + i * 60
        els.append(_render_icon(ctx["motifs"][i], x, y, 40))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


def _arch_cross(rng, ctx):
    """Cross composition: horizontal + vertical rule meeting at center."""
    els = [
        _hairline(40, 120, 360, 120, ctx["p"]["mid"]),
        _hairline(200, 30, 200, 210, ctx["p"]["mid"]),
    ]
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    for i, m in enumerate(ctx["motifs"][:4]):
        x = 120 if i % 2 == 0 else 250
        y = 80 if i < 2 else 150
        els.append(_render_icon(m, x, y, 28))
    return els


def _arch_wave_field(rng, ctx):
    """Layered wave lines + a motif row riding them."""
    els = []
    for row in range(3):
        y = 140 + row * 26
        els.append(_wobble_line(rng, 40, y, 360, y + rng.uniform(-8, 8), amp=10, steps=10))
    for i, m in enumerate(ctx["motifs"][:3]):
        els.append(_render_icon(m, 90 + i * 90, 60, 32))
    if ctx["hl"]:
        els.append(_render_highlight(ctx["hl"][0], 300, 170, 55, 32, ctx["ground"]))
    return els


def _arch_ring(rng, ctx):
    """Concentric rings with a single motif emphasis."""
    els = []
    for r in (50, 80, 110):
        els.append(
            f'<circle cx="200" cy="120" r="{r}" fill="none" stroke="var(--ill-mid)" \
              stroke-width="1.5"/>'
        )
    if ctx["motifs"]:
        els.append(_render_icon(ctx["motifs"][0], 180, 100, 40))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


def _arch_orbit_burst(rng, ctx):
    """Orbit ring + radiating rays (focus/energy)."""
    els = [
        '<circle cx="200" cy="120" r="70" fill="none" stroke="var(--ill-mid)" stroke-width="1.5"/>'
    ]
    rays = rng.randint(10, 14)
    for i in range(rays):
        a = i / rays * math.tau
        x0 = 200 + 70 * math.cos(a)
        y0 = 120 + 70 * math.sin(a)
        x1 = 200 + 165 * math.cos(a)
        y1 = 120 + 165 * math.sin(a)
        els.append(_hairline(x0, y0, x1, y1, ctx["p"]["mid"]))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


def _arch_grid(rng, ctx):
    """Strict Swiss grid of cells, each holding a motif."""
    els = []
    n = min(len(ctx["motifs"]), 9)
    for i in range(n):
        col = i % 3
        row = i // 3
        x = 55 + col * 105
        y = 55 + row * 65
        els.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="70" height="48" fill="none" '
            f'stroke="var(--ill-mid)" stroke-width="1.2"/>'
        )
        els.append(_render_icon(ctx["motifs"][i], x + 20, y + 10, 30))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


def _arch_diptych(rng, ctx):
    """Two-panel split: hero in one, motif row in the other."""
    els = [
        '<rect x="30" y="30" width="170" height="180" fill="none" \
          stroke="var(--ill-mid)" stroke-width="1.5"/>',
        '<rect x="210" y="30" width="160" height="180" fill="none" \
          stroke="var(--ill-mid)" stroke-width="1.5"/>',
    ]
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    for i, m in enumerate(ctx["motifs"][:2]):
        els.append(_render_icon(m, 250 + i * 45, 90, 30))
    return els


def _arch_sun_marks(rng, ctx):
    """Radiating hand-drawn marks from a corner (Highlights-led)."""
    els = []
    for i, h in enumerate(ctx["hl"][:5]):
        a = rng.uniform(0, math.pi / 2)
        r = 40 + i * 45
        x = 60 + r * math.cos(a)
        y = 200 - r * math.sin(a)
        els.append(_render_highlight(h, x, y, 50, 32, ctx["ground"]))
    if ctx["motifs"]:
        els.append(_render_icon(ctx["motifs"][0], 260, 140, 40))
    return els


def _arch_underline(rng, ctx):
    """A strong hand-drawn underline under a motif row."""
    els = []
    for i, m in enumerate(ctx["motifs"][:3]):
        els.append(_render_icon(m, 90 + i * 95, 60, 34))
    if ctx["hl"]:
        els.append(_render_highlight(ctx["hl"][0], 40, 150, 320, 40, ctx["ground"]))
    if ctx["hero"]:
        els.append(ctx["hero"][0])
    return els


# Register all archetypes.
for _name, _fn in {
    "ascend": _arch_ascend,
    "cluster": _arch_cluster,
    "horizon": _arch_horizon,
    "field": _arch_field,
    "orbit": _arch_orbit,
    "stack": _arch_stack,
    "cascade": _arch_cascade,
    "counterpoint": _arch_counterpoint,
    "measure": _arch_measure,
    "frame": _arch_frame,
    "burst": _arch_burst,
    "scatter": _arch_scatter,
    "gate": _arch_gate,
    "column": _arch_column,
    "cross": _arch_cross,
    "wave-field": _arch_wave_field,
    "ring": _arch_ring,
    "orbit-burst": _arch_orbit_burst,
    "grid": _arch_grid,
    "diptych": _arch_diptych,
    "sun-marks": _arch_sun_marks,
    "underline": _arch_underline,
}.items():
    _register(_name, _fn)

ARCHETYPE_IDS: list[str] = sorted(_ARCHETYPES.keys())

# Loose theme → archetype steering (substring-matched).
THEME_ARCHETYPES: dict[str, str] = {
    "rise": "ascend", "launch": "ascend", "up": "ascend", "growth": "ascend",
    "focus": "cluster", "hub": "cluster", "network": "cluster",
    "journey": "horizon", "distance": "horizon", "path": "horizon",
    "system": "field", "grid": "grid", "data": "field", "repeat": "grid",
    "cycle": "orbit", "orbit": "orbit", "circular": "ring",
    "stack": "stack", "build": "stack", "layer": "stack", "structure": "stack",
    "flow": "cascade", "stream": "cascade", "sequence": "cascade",
    "tension": "counterpoint", "duality": "counterpoint", "contrast": "counterpoint",
    "measure": "measure", "rules": "measure", "systematic": "measure",
    "frame": "frame", "contain": "frame",
    "burst": "burst", "energy": "burst", "spark": "burst",
    "scatter": "scatter", "loose": "scatter",
    "gate": "gate", "threshold": "gate",
    "column": "column", "vertical": "column",
    "cross": "cross", "intersection": "cross",
    "wave": "wave-field", "rhythm": "wave-field", "motion": "wave-field",
    "burst-orbit": "orbit-burst", "radial": "orbit-burst",
    "diptych": "diptych", "pair": "diptych", "duo": "diptych",
    "sun": "sun-marks", "hand": "sun-marks", "marks": "sun-marks",
    "underline": "underline", "emphasis": "underline",
}


def _archetype_for(seed: str, theme: str | None) -> str:
    rng = _rng(seed, "archetype")
    if theme:
        low = theme.lower()
        for key, arch in THEME_ARCHETYPES.items():
            if key in low:
                return arch
    return rng.choice(ARCHETYPE_IDS)


_CAT_HEROES: dict[str, str] = {
    "WRITING": "fountain-pen",
    "PROJECT": "wrench-gear",
    "PORTFOLIO": "frame",
    "NOTE": "spark",
    "AI": "robot",
}


def _resolve_hero(category: str, style: str, seed: str, rng: random.Random) -> list[str] | None:
    """Choose the hero layer: DiceBear figure OR custom category SVG.

    When ``style`` names a curated DiceBear style, that figure is the hero.
    Otherwise the category's custom SVG hero is used (falling back to spark).
    """
    if style and style != "compose" and style != "procedural":
        from app.services.tools.peep_styles import CURATED_STYLES

        if style in CURATED_STYLES:
            try:
                raw = _render_avatar_raw(seed, style)
                m = re.search(r'viewBox="([^"]+)"', raw)
                vb = m.group(1) if m else "0 0 100 100"
                parts = [float(p) for p in vb.replace(",", " ").split()]
                vbw = parts[2] if len(parts) >= 3 else 100.0
                vbh = parts[3] if len(parts) >= 4 else 100.0
                scale = min(100 / vbw, 100 / vbh)
                inner = re.sub(r"^<svg[^>]*>", "", raw, flags=re.IGNORECASE)
                inner = re.sub(r"</svg>\s*$", "", inner, flags=re.IGNORECASE).strip()
                return [
                    f'<g transform="translate(150,80) scale({scale:.3f})">{inner}</g>'
                ]
            except Exception as e:  # noqa: BLE001
                log.warning("[composer] dicebear hero %s failed (%s)", style, e)

    slug = _CAT_HEROES.get(category.upper() or "", "spark")
    if _load_hero(slug) is None:
        return None
    return [_render_hero(slug, 150, 50, 100, 100)]


def compose_scene(
    seed: str,
    ground: str = "white",
    archetype: str | None = None,
    hero: str | None = None,
    motif_names: list[str] | None = None,
    highlights: list[str] | None = None,
    style: str = "compose",
    theme: str | None = None,
    category: str = "",
) -> str:
    """Compose a deterministic monochrome editorial figure.

    All element sources (custom hero / DiceBear figure / Lucide motifs /
    Highlights marks / procedural geometry) are laid out by a named archetype
    and resolve through the ``--ill-*`` design-system tokens, so the figure
    follows the active design system and stays verifier-safe (no hex, no
    emoji).
    """
    ground = ground if ground in ("white", "black") else "white"
    rng = _rng(seed, "compose")
    arch_key = archetype or _archetype_for(seed, theme)
    palette = _ctx_palette(ground)

    hero_layer = _resolve_hero(category or "", style, f"{seed}|hero", rng)

    from app.services.tools.icon_search import icon_exists

    motifs = [m for m in (motif_names or []) if icon_exists(m)][:8]
    hl = [h for h in (highlights or []) if _load_highlight(h) is not None][:5]

    ctx = {
        "hero": hero_layer,
        "motifs": motifs,
        "hl": hl,
        "p": palette,
        "ground": ground,
    }

    fn = _ARCHETYPES.get(arch_key)
    if fn is None:
        fn = _ARCHETYPES["cluster"]
    body = "\n    ".join(fn(rng, ctx))

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240" '
        f'viewBox="0 0 400 240" preserveAspectRatio="xMidYMid meet" '
        f'role="img" aria-hidden="true">\n'
        f"  {body}\n"
        f"</svg>"
    )
    return _figure_wrapper(svg)


__all__ = [
    "ARCHETYPE_IDS",
    "THEME_ARCHETYPES",
    "compose_scene",
]
