"""Procedural editorial illustration generator.

A small, dependency-free SVG generator that recreates the Anthropic-style
abstract illustration system as a clean, provably-safe composition engine:

  1. a single organic carrier blob (never a perfect circle),
  2. one bold gestural mark (rays / spiral / waves / rings / stem …),
  3. optional quiet accents (dots, hairlines) — never a scattered collage.

Every composition is a pure, deterministic function of its seed and theme
(no ambient randomness anywhere — each element is rendered from a hash of its
own parameters), and every element is placed inside a **safe inner frame** so
a figure can never clip out of its slot box or paint on top of the copy.

The catalog of archetypes is deliberately large (~29) and each silhouette is
genuinely distinct, so two posts rarely land on the same composition; the
seed-hashed pick spreads variety across post+format while staying pure.

Strict monochrome: only ``var(--color-*)`` token names (no raw hex), so the
verifier's hex check passes and the art adapts to both grounds.

The generator is also exposed as an LLM **tool**: an "illustration director"
prompt asks the model to pick an abstract theme for the post and the tool
renders it. ``illustration_via_tool`` orchestrates LLM → tool → fallback.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

log = logging.getLogger(__name__)

__all__ = [
    "generate_illustration_svg",
    "generate_figure_metrics",
    "ILLUSTRATION_TOOL",
    "illustration_via_tool",
    "ARCHETYPES",
]

DEFAULT_VIEW_BOX = "0 0 400 240"

VIEW_W, VIEW_H = 400, 240
# Safe inner frame — no element may cross it, so the figure never clips out of
# its slot box or collides with surrounding copy.
SAFE_MARGIN = 16
SAFE = (SAFE_MARGIN, SAFE_MARGIN, VIEW_W - SAFE_MARGIN, VIEW_H - SAFE_MARGIN)

# Catmull-Rom spline through the sampled blob points can bulge slightly past
# those points (plus round stroke caps). Every organic element's box is padded
# by this so the *conservative* box (what we check) always contains the real
# rendered curve.
_OVERSHOOT = 6.0

# Token-mapped palette — the only colors the art is allowed to use.
_INK_WHITE = "var(--color-text)"
_INK_BLACK = "var(--color-text-inverted)"
_CARRIER_WHITE = "var(--color-border)"
_CARRIER_BLACK = "var(--color-border-inverted)"
_MID = "var(--color-text-secondary)"


def _palette(ground: str) -> dict:
    if ground == "black":
        return {"ink": _INK_BLACK, "carrier": _CARRIER_BLACK, "mid": _MID}
    return {"ink": _INK_WHITE, "carrier": _CARRIER_WHITE, "mid": _MID}


def _fmt(n: float) -> str:
    return f"{n:.1f}"


def _rng(*keys: object) -> random.Random:
    """Stable RNG derived from element parameters — guarantees determinism."""
    return random.Random(";".join(str(k) for k in keys))


@dataclass(frozen=True)
class Box:
    """Axis-aligned bounding box (x0,y0 top-left, x1,y1 bottom-right)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def within(self, safe: tuple[float, float, float, float]) -> bool:
        return self.x0 >= safe[0] and self.y0 >= safe[1] and self.x1 <= safe[2] and self.y1 <= safe[3]


def _pad(x0: float, y0: float, x1: float, y1: float, extra: float = _OVERSHOOT) -> Box:
    """Conservative box: real stroke/spline geometry always fits inside."""
    return Box(x0 - extra, y0 - extra, x1 + extra, y1 + extra)


def _catmull_closed(points: list[tuple[float, float]]) -> str:
    n = len(points)
    d = ["M " + _fmt(points[0][0]) + " " + _fmt(points[0][1])]
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d.append(f"C {_fmt(c1[0])} {_fmt(c1[1])} {_fmt(c2[0])} {_fmt(c2[1])} {_fmt(p2[0])} {_fmt(p2[1])}")
    return " ".join(d) + " Z"


def _blob_points(cx, cy, rx, ry, rng: random.Random, n: int = 18) -> list[tuple[float, float]]:
    harmonics = 3
    amps = [rng.uniform(0.04, 0.12) for _ in range(harmonics)]
    freqs = [rng.randint(2, 5) for _ in range(harmonics)]
    phases = [rng.uniform(0, math.tau) for _ in range(harmonics)]
    pts = []
    for i in range(n):
        a = i / n * math.tau
        rad = 1.0 + sum(amps[j] * math.sin(freqs[j] * a + phases[j]) for j in range(harmonics))
        pts.append((cx + rx * rad * math.cos(a), cy + ry * rad * math.sin(a)))
    return pts


def _wobble_points(x0, y0, x1, y1, rng: random.Random, steps: int = 6, amp: float = 4.0) -> list[tuple[float, float]]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    pts = []
    for i in range(steps + 1):
        t = i / steps
        off = (rng.random() - 0.5) * 2 * amp
        pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    return pts


# ---------------------------------------------------------------------------
# Element model — data + a pure (deterministic) renderer. The bounding box is
# authoritative, so the no-clip guarantee is tracked exactly, never re-parsed
# from SVG text.
# ---------------------------------------------------------------------------


class _El:
    def box(self) -> Box:
        raise NotImplementedError

    def to_svg(self, p: dict) -> str:
        raise NotImplementedError


@dataclass
class Blob(_El):
    cx: float
    cy: float
    rx: float
    ry: float
    fill: str = "carrier"
    noise: str = ""

    def _pts(self) -> list[tuple[float, float]]:
        rng = _rng("blob", self.noise, round(self.cx, 1), round(self.cy, 1), round(self.rx, 1), round(self.ry, 1))
        return _blob_points(self.cx, self.cy, self.rx, self.ry, rng, 18)

    def box(self) -> Box:
        pts = self._pts()
        return _pad(min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))

    def to_svg(self, p: dict) -> str:
        d = _catmull_closed(self._pts())
        return f'<path d="{d}" style="fill:{p.get(self.fill)};stroke:none"/>'


@dataclass
class Circle(_El):
    cx: float
    cy: float
    r: float
    fill: str = "ink"
    wobble: bool = True
    noise: str = ""

    def box(self) -> Box:
        if self.wobble:
            pts = self._pts()
            return _pad(min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        return Box(self.cx - self.r, self.cy - self.r, self.cx + self.r, self.cy + self.r)

    def _pts(self) -> list[tuple[float, float]]:
        rng = _rng("circle-w", self.noise, round(self.cx, 1), round(self.cy, 1), round(self.r, 1))
        return _blob_points(self.cx, self.cy, self.r, self.r, rng, 22)

    def to_svg(self, p: dict) -> str:
        color = p.get(self.fill)
        if self.wobble:
            return f'<path d="{_catmull_closed(self._pts())}" style="fill:{color};stroke:none"/>'
        return f'<circle cx="{_fmt(self.cx)}" cy="{_fmt(self.cy)}" r="{_fmt(self.r)}" style="fill:{color}"/>'


@dataclass
class Ring(_El):
    cx: float
    cy: float
    r: float
    stroke: str = "ink"
    width: float = 3.0
    noise: str = ""

    def _pts(self) -> list[tuple[float, float]]:
        rng = _rng("ring", self.noise, round(self.cx, 1), round(self.cy, 1), round(self.r, 1))
        return _blob_points(self.cx, self.cy, self.r, self.r, rng, 22)

    def box(self) -> Box:
        w = self.width / 2 + 1
        pts = self._pts()
        return _pad(min(p[0] for p in pts) - w, min(p[1] for p in pts) - w, max(p[0] for p in pts) + w, max(p[1] for p in pts) + w)

    def to_svg(self, p: dict) -> str:
        d = _catmull_closed(self._pts())
        return (
            f'<path d="{d}" style="fill:none;stroke:{p.get(self.stroke)};'
            f'stroke-width:{self.width:.1f};stroke-linecap:round;stroke-linejoin:round"/>'
        )


@dataclass
class Line(_El):
    x0: float
    y0: float
    x1: float
    y1: float
    stroke: str = "ink"
    width: float = 3.0
    amp: float = 4.0
    steps: int = 6
    noise: str = ""

    def _pts(self) -> list[tuple[float, float]]:
        rng = _rng("line", self.noise, round(self.x0, 1), round(self.y0, 1), round(self.x1, 1), round(self.y1, 1))
        return _wobble_points(self.x0, self.y0, self.x1, self.y1, rng, self.steps, self.amp)

    def box(self) -> Box:
        w = self.width / 2 + 1
        pts = self._pts()
        return _pad(min(p[0] for p in pts) - w, min(p[1] for p in pts) - w, max(p[0] for p in pts) + w, max(p[1] for p in pts) + w)

    def to_svg(self, p: dict) -> str:
        pts = self._pts()
        d = " ".join(
            ("M " if i == 0 else "L ") + _fmt(pt[0]) + " " + _fmt(pt[1]) for i, pt in enumerate(pts)
        )
        return (
            f'<path d="{d}" style="fill:none;stroke:{p.get(self.stroke)};'
            f'stroke-width:{self.width:.1f};stroke-linecap:round;stroke-linejoin:round"/>'
        )


@dataclass
class Arc(_El):
    x0: float
    y0: float
    xa: float
    ya: float
    x1: float
    y1: float
    stroke: str = "ink"
    width: float = 3.0

    def box(self) -> Box:
        # A quadratic Bézier stays within the convex hull of its three points.
        w = self.width / 2 + 1
        xs = [self.x0, self.xa, self.x1]
        ys = [self.y0, self.ya, self.y1]
        return _pad(min(xs) - w, min(ys) - w, max(xs) + w, max(ys) + w)

    def to_svg(self, p: dict) -> str:
        d = (
            f"M {_fmt(self.x0)} {_fmt(self.y0)} "
            f"Q {_fmt(self.xa)} {_fmt(self.ya)} {_fmt(self.x1)} {_fmt(self.y1)}"
        )
        return (
            f'<path d="{d}" style="fill:none;stroke:{p.get(self.stroke)};'
            f'stroke-width:{self.width:.1f};stroke-linecap:round;stroke-linejoin:round"/>'
        )


@dataclass
class Wave(_El):
    """A deterministic sine polyline across the frame."""

    x0: float
    x1: float
    base: float
    peak: float
    cycles: int = 1
    stroke: str = "ink"
    width: float = 2.6
    noise: str = ""

    def box(self) -> Box:
        w = self.width / 2 + 1
        return _pad(min(self.x0, self.x1) - w, self.base - self.peak - w, max(self.x0, self.x1) + w, self.base + self.peak + w)

    def _phase(self) -> float:
        rng = _rng("wave", self.noise, round(self.base, 1))
        return rng.uniform(0, math.pi)

    def to_svg(self, p: dict) -> str:
        steps = 12
        phase = self._phase()
        d = []
        for i in range(steps + 1):
            t = i / steps
            x = self.x0 + (self.x1 - self.x0) * t
            y = self.base + self.peak * math.sin(t * math.pi * self.cycles * 2 + phase)
            d.append(("M " if i == 0 else "L ") + _fmt(x) + " " + _fmt(y))
        return (
            f'<path d="{" ".join(d)}" style="fill:none;stroke:{p.get(self.stroke)};'
            f'stroke-width:{self.width:.1f};stroke-linecap:round;stroke-linejoin:round"/>'
        )


@dataclass
class Spiral(_El):
    cx: float
    cy: float
    r0: float
    r1: float
    turns: float = 2.6
    stroke: str = "ink"
    width: float = 3.0
    noise: str = ""

    def _pts(self) -> list[tuple[float, float]]:
        rng = _rng("spiral", self.noise, round(self.cx, 1), round(self.cy, 1), round(self.r0, 1), round(self.r1, 1))
        steps = 80
        pts = []
        for i in range(steps + 1):
            t = i / steps
            a = t * self.turns * math.tau
            rad = self.r0 + (self.r1 - self.r0) * t
            j = (rng.random() - 0.5) * 2.5
            pts.append((self.cx + (rad + j) * math.cos(a), self.cy + (rad + j) * math.sin(a)))
        return pts

    def box(self) -> Box:
        w = self.width / 2 + 1
        pts = self._pts()
        return _pad(min(p[0] for p in pts) - w, min(p[1] for p in pts) - w, max(p[0] for p in pts) + w, max(p[1] for p in pts) + w)

    def to_svg(self, p: dict) -> str:
        pts = self._pts()
        d = " ".join(
            ("M " if i == 0 else "L ") + _fmt(pt[0]) + " " + _fmt(pt[1]) for i, pt in enumerate(pts)
        )
        return (
            f'<path d="{d}" style="fill:none;stroke:{p.get(self.stroke)};'
            f'stroke-width:{self.width:.1f};stroke-linecap:round;stroke-linejoin:round"/>'
        )


def _unioned_box(els: list[_El]) -> Box:
    boxes = [e.box() for e in els]
    if not boxes:
        return Box(0, 0, 0, 0)
    return Box(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def _fit_transform(els: list[_El]) -> tuple[float, float, float]:
    """Return (scale, tx, ty) that uniformly fits the union box inside SAFE.

    Deterministic and always safe: shrink proportionally only if needed, then
    center. This is the hard no-clip guarantee — no matter how an archetype is
    authored, the rendered figure can never overflow its slot box.
    """
    u = _unioned_box(els)
    if u.x1 <= u.x0 or u.y1 <= u.y0:
        return 1.0, 0.0, 0.0
    bw = u.x1 - u.x0
    bh = u.y1 - u.y0
    sw = SAFE[2] - SAFE[0]
    sh = SAFE[3] - SAFE[1]
    s = min(1.0, sw / bw if bw > 0 else 1.0, sh / bh if bh > 0 else 1.0)
    if s >= 1.0:
        # center within the safe box
        tx = SAFE[0] + (sw - bw) / 2 - u.x0
        ty = SAFE[1] + (sh - bh) / 2 - u.y0
        return 1.0, tx, ty
    nw = bw * s
    nh = bh * s
    tx = SAFE[0] + (sw - nw) / 2 - u.x0 * s
    ty = SAFE[1] + (sh - nh) / 2 - u.y0 * s
    return s, tx, ty


# ---------------------------------------------------------------------------
# Archetypes — each composes a full 400×240 frame inside the safe region.
# ---------------------------------------------------------------------------


def _sun(cx, cy, r, rng: random.Random) -> list[_El]:
    els: list[_El] = [Circle(cx, cy, r, fill="ink")]
    rays = rng.randint(6, 8)
    for i in range(rays):
        a = i / rays * math.tau + rng.uniform(-0.08, 0.08)
        x0 = cx + r * 1.3 * math.cos(a)
        y0 = cy + r * 1.3 * math.sin(a)
        x1 = cx + r * (1.85 + rng.uniform(-0.1, 0.1)) * math.cos(a)
        y1 = cy + r * (1.85 + rng.uniform(-0.1, 0.1)) * math.sin(a)
        els.append(Line(x0, y0, x1, y1, width=rng.uniform(2.4, 3.2), amp=2.0, steps=2))
    return els


def _arch_carrier_sun(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 122, 150, 92)]
    els += _sun(200, 116, 30, rng)
    els.append(Line(140, 206, 264, 206, amp=3, steps=4))
    return els


def _arch_sun_left(p, rng: random.Random) -> list[_El]:
    els = _sun(120, 118, 42, rng)
    els.append(Line(206, 196, 336, 196, amp=3, steps=4))
    els.append(Line(206, 210, 308, 210, width=2.4, amp=2, steps=3))
    return els


def _arch_carrier_spiral(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 120, 156, 94)]
    els.append(Spiral(200, 118, 10, 56, turns=rng.uniform(2.2, 2.8)))
    for _ in range(rng.randint(2, 3)):
        ang = rng.uniform(0, math.tau)
        rad = rng.uniform(70, 92)
        cx = 200 + rad * math.cos(ang)
        cy = 118 + rad * math.sin(ang)
        cx = min(max(cx, SAFE[0] + 6), SAFE[2] - 6)
        cy = min(max(cy, SAFE[1] + 6), SAFE[3] - 6)
        els.append(Circle(cx, cy, rng.uniform(2.6, 4.6), fill="mid", wobble=False))
    return els


def _arch_orbit(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 120, 120, 74)]
    els.append(Ring(200, 120, 46, stroke="ink", width=3.0))
    els.append(Ring(200, 120, 62, stroke="mid", width=2.6))
    els.append(Circle(200 - 62, 120, 8, fill="ink"))
    els.append(Circle(200 + 46, 120, 5, fill="ink", wobble=False))
    return els


def _arch_diptych(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(128, 120, 74, 84)]
    els.append(Blob(302, 120, 50, 66))
    els.append(Line(240, 82, 240, 168, width=2.6, amp=2, steps=3))
    return els


def _arch_column(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    for i in range(3):
        y = 56 + i * 46
        els.append(Blob(200, y, 58, 18))
    els.append(Line(128, 208, 272, 208, amp=3, steps=4))
    return els


def _arch_cross(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 120, 30, 64)]
    els.append(Blob(200, 120, 64, 28))
    els.append(Line(200, 36, 200, 204, amp=2.5, steps=5))
    els.append(Line(96, 120, 304, 120, amp=2.5, steps=5))
    return els


def _arch_horizon(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Line(96, 96, 304, 96, width=3.0, amp=3, steps=5)]
    els.append(Blob(150, 172, 88, 30, fill="carrier"))
    els.append(Circle(300, 72, 16, fill="ink"))
    els.append(Line(96, 210, 304, 210, width=2.4, amp=2, steps=3))
    return els


def _arch_bounded_field(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    n = rng.randint(7, 11)
    for _ in range(n):
        r = rng.uniform(5, 13)
        cx = rng.uniform(SAFE[0] + r + 1, SAFE[2] - r - 1)
        cy = rng.uniform(SAFE[1] + r + 1, SAFE[3] - r - 1)
        els.append(Circle(cx, cy, r, fill="ink", wobble=bool(rng.random() < 0.4)))
    els.append(Line(96, 122, 304, 122, width=2.4, amp=2, steps=3))
    return els


def _arch_stack_blobs(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 88, 88, 40)]
    els.append(Blob(200, 150, 66, 34))
    els.append(Blob(200, 200, 44, 20))
    els.append(Line(120, 224, 280, 224, width=2.4, amp=2, steps=3))
    return els


def _arch_rings_field(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Ring(200, 120, 46, stroke="ink", width=3.0)]
    els.append(Ring(200, 120, 62, stroke="mid", width=2.6))
    for _ in range(rng.randint(3, 5)):
        ang = rng.uniform(0, math.tau)
        rad = rng.uniform(84, 110)
        r = rng.uniform(4, 7)
        cx = 200 + rad * math.cos(ang)
        cy = 120 + rad * math.sin(ang)
        cx = min(max(cx, SAFE[0] + r + 1), SAFE[2] - r - 1)
        cy = min(max(cy, SAFE[1] + r + 1), SAFE[3] - r - 1)
        els.append(Ring(cx, cy, r, stroke="ink", width=2.4))
    return els


def _arch_burst(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 122, 58, 46)]
    for i in range(rng.randint(8, 10)):
        a = i / rng.randint(8, 10) * math.tau + rng.uniform(-0.06, 0.06)
        r0 = rng.uniform(46, 58)
        r1 = rng.uniform(70, 82)
        els.append(Line(200 + r0 * math.cos(a), 122 + r0 * math.sin(a), 200 + r1 * math.cos(a), 122 + r1 * math.sin(a), width=rng.uniform(2.4, 3.4), amp=2.5, steps=2))
    return els


def _arch_burst_left(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(120, 150, 44, 40)]
    for i in range(rng.randint(7, 9)):
        a = i / rng.randint(7, 9) * math.tau + math.pi / 2 + rng.uniform(-0.1, 0.1)
        r0 = rng.uniform(32, 44)
        r1 = rng.uniform(62, 76)
        els.append(Line(120 + r0 * math.cos(a), 150 + r0 * math.sin(a), 120 + r1 * math.cos(a), 150 + r1 * math.sin(a), width=rng.uniform(2.4, 3.4), amp=2.5, steps=2))
    els.append(Line(220, 210, 340, 210, width=2.6, amp=2, steps=3))
    return els


def _arch_stem(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    cx = rng.choice([150, 200, 250])
    els.append(Line(cx + rng.uniform(-4, 4), 212, cx, 60, width=3.2, amp=4, steps=5))
    for _ in range(rng.randint(2, 3)):
        side = 1 if rng.random() < 0.5 else -1
        mx = min(max(cx + side * rng.uniform(60, 100), SAFE[0] + 10), SAFE[2] - 10)
        my = rng.uniform(96, 160)
        h = rng.uniform(20, 30)
        els.append(Arc(cx, my, (cx + mx) / 2, my - side * h, mx, my, width=2.6))
    els.append(Blob(cx, 60, 20, 14))
    return els


def _arch_waves(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 120, 140, 82)]
    count = rng.randint(2, 3)
    for i in range(count):
        els.append(Wave(112, 288, 92 + i * 30, rng.uniform(9, 16), cycles=i + 1, width=2.6))
    els.append(Circle(rng.uniform(200, 230), rng.uniform(34, 52), 6, fill="ink", wobble=False))
    return els


def _arch_dot_grid(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    r = 3.5
    for gx in range(3):
        for gy in range(3):
            cx = SAFE[0] + 22 + gx * 38
            cy = SAFE[1] + 26 + gy * 36
            els.append(Circle(cx, cy, r, fill="mid", wobble=False))
    els.append(Blob(268, 122, 66, 46, fill="carrier"))
    els.append(Circle(268, 122, 12, fill="ink", wobble=False))
    return els


def _arch_radial_strokes(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Ring(200, 120, 30, stroke="ink", width=3.0)]
    for i in range(8):
        a = i / 8 * math.tau + rng.uniform(-0.08, 0.08)
        r0 = 40 + rng.uniform(-4, 4)
        r1 = 80 + rng.uniform(-6, 6)
        els.append(Line(200 + r0 * math.cos(a), 120 + r0 * math.sin(a), 200 + r1 * math.cos(a), 120 + r1 * math.sin(a), width=2.6, amp=2.5, steps=2))
    return els


def _arch_mountains(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(108, 176, 58, 34, fill="carrier")]
    els.append(Blob(200, 176, 84, 38, fill="carrier"))
    els.append(Blob(304, 176, 50, 30, fill="carrier"))
    els.append(Line(96, 214, 320, 214, width=2.6, amp=2, steps=3))
    els.append(Circle(92, 66, 13, fill="ink"))
    return els


def _arch_biohazard(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Ring(200, 120, 44, stroke="ink", width=3.0)]
    for i in range(3):
        a = i / 3 * math.tau + math.pi / 6
        xc = 200 + 26 * math.cos(a)
        yc = 120 + 26 * math.sin(a)
        els.append(Blob(xc, yc, 22, 12, fill="carrier"))
    els.append(Circle(200, 120, 9, fill="ink"))
    return els


def _arch_corner_mark(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(286, 120, 66, 86, fill="carrier")]
    els.append(Line(150, 70, 150, 174, width=3.0, amp=3, steps=4))
    els.append(Line(92, 120, 124, 120, width=3.0, amp=2, steps=2))
    els.append(Line(92, 120, 92, 172, width=3.0, amp=2, steps=2))
    return els


def _arch_slash(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    for i in range(2):
        x = 150 + i * 60
        els.append(Line(x, 40, x - 30, 200, width=3.2, amp=3, steps=6))
    els.append(Circle(120, 118, 20, fill="ink"))
    els.append(Circle(282, 64, 12, fill="ink", wobble=False))
    return els


def _arch_wedge(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(200, 120, 52, 62, fill="carrier")]
    els.append(Line(96, 52, 304, 52, width=3.0, amp=3, steps=5))
    els.append(Line(96, 188, 304, 188, width=3.0, amp=3, steps=5))
    els.append(Line(96, 52, 96, 188, width=2.6, amp=2, steps=3))
    els.append(Line(304, 52, 304, 188, width=2.6, amp=2, steps=3))
    return els


def _arch_circle_quad(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    centers = [(126, 84), (274, 84), (126, 156), (274, 156)]
    for (cx, cy) in centers:
        els.append(Circle(cx, cy, 22, fill="carrier", wobble=True))
    els.append(Circle(200, 120, 8, fill="ink", wobble=False))
    els.append(Line(200, 52, 200, 188, width=2.6, amp=2, steps=3))
    return els


def _arch_landscape_line(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Line(96, 120, 304, 120, width=2.8, amp=2, steps=4)]
    els.append(Line(96, 86, 304, 86, width=2.4, amp=2, steps=3))
    els.append(Line(96, 154, 304, 154, width=2.4, amp=2, steps=3))
    els.append(Circle(200, 44, 12, fill="ink"))
    return els


def _arch_double_wave(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Wave(96, 304, 96, rng.uniform(8, 13), cycles=rng.randint(1, 2))]
    els.append(Wave(96, 304, 148, rng.uniform(8, 13), cycles=rng.randint(1, 2)))
    els.append(Circle(96, 196, 8, fill="mid", wobble=False))
    els.append(Circle(304, 60, 8, fill="ink", wobble=False))
    return els


def _arch_ring_dash(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Ring(200, 120, 26, stroke="ink", width=3.0)]
    els.append(Ring(200, 120, 46, stroke="mid", width=2.6))
    els.append(Ring(200, 120, 66, stroke="ink", width=2.4))
    for i in range(6):
        a = i / 6 * math.tau
        els.append(Circle(200 + 66 * math.cos(a), 120 + 66 * math.sin(a), 3.4, fill="ink", wobble=False))
    return els


def _arch_two_dots(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Line(140, 120, 260, 120, width=3.0, amp=2, steps=3)]
    els.append(Circle(140, 112, 20, fill="carrier"))
    els.append(Circle(260, 132, 10, fill="ink", wobble=False))
    els.append(Line(100, 210, 300, 210, width=2.4, amp=2, steps=3))
    return els


def _arch_vertical_stripes(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    for i in range(4):
        x = 120 + i * 52
        els.append(Line(x, 40, x, 200, width=3.0, amp=2, steps=5))
    els.append(Blob(66, 120, 20, 72, fill="carrier"))
    return els


def _arch_diagonal(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    for i in range(3):
        x0 = 90 + i * 30
        y0 = 208
        x1 = 280 - i * 30
        y1 = 42
        els.append(Line(x0, y0, x1, y1, width=2.6, amp=2, steps=4))
    return els


def _arch_wave_field(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    for i in range(3):
        base = 70 + i * 42
        els.append(Wave(88, 312, base, rng.uniform(5, 9), cycles=1 + i, width=2.0 + i * 0.3))
    return els


def _arch_cloud(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Blob(170, 130, 88, 40, fill="carrier")]
    els.append(Blob(240, 116, 52, 30, fill="carrier"))
    els.append(Blob(120, 150, 48, 28, fill="carrier"))
    els.append(Line(90, 214, 310, 214, width=2.4, amp=2, steps=3))
    return els


def _arch_starburst(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Circle(200, 120, 10, fill="ink", wobble=False)]
    for i in range(rng.randint(10, 13)):
        a = i / rng.randint(10, 13) * math.tau + rng.uniform(-0.05, 0.05)
        r1 = rng.uniform(48, 70)
        els.append(Line(200 + 14 * math.cos(a), 120 + 14 * math.sin(a), 200 + r1 * math.cos(a), 120 + r1 * math.sin(a), width=rng.uniform(2.2, 3.0), amp=2.0, steps=2))
    return els


def _arch_pinwheel(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    for i in range(4):
        cx = 200 + 40 * math.cos(i / 4 * math.tau + math.pi / 4)
        cy = 120 + 40 * math.sin(i / 4 * math.tau + math.pi / 4)
        ang = i / 4 * math.tau + math.pi / 4
        els.append(Arc(cx - 26 * math.cos(ang), cy - 26 * math.sin(ang), cx, cy, cx - 12 * math.cos(ang + math.pi / 2), cy - 12 * math.sin(ang + math.pi / 2), width=3.0))
    els.append(Circle(200, 120, 6, fill="ink", wobble=False))
    return els


def _arch_rhythm_bars(p, rng: random.Random) -> list[_El]:
    els: list[_El] = []
    heights = [30, 52, 70, 44, 58, 34]
    x = 150
    for h in heights:
        y1 = 210
        y0 = 210 - h
        els.append(Line(x, y0, x, y1, width=rng.uniform(8, 12), amp=1, steps=1))
        x += 24
    return els


def _arch_spiral_free(p, rng: random.Random) -> list[_El]:
    els: list[_El] = [Spiral(200, 120, 6, 96, turns=rng.uniform(1.5, 2.2))]
    els.append(Circle(rng.uniform(140, 260), rng.uniform(34, 60), 5, fill="ink", wobble=False))
    return els


ARCHETYPES: dict[str, callable] = {
    "carrier-sun": _arch_carrier_sun,
    "sun-left": _arch_sun_left,
    "carrier-spiral": _arch_carrier_spiral,
    "spiral-free": _arch_spiral_free,
    "orbit": _arch_orbit,
    "diptych": _arch_diptych,
    "column": _arch_column,
    "cross": _arch_cross,
    "horizon": _arch_horizon,
    "bounded-field": _arch_bounded_field,
    "stack-blobs": _arch_stack_blobs,
    "rings-field": _arch_rings_field,
    "burst": _arch_burst,
    "burst-left": _arch_burst_left,
    "starburst": _arch_starburst,
    "stem": _arch_stem,
    "waves": _arch_waves,
    "dot-grid": _arch_dot_grid,
    "radial-strokes": _arch_radial_strokes,
    "mountains": _arch_mountains,
    "biohazard": _arch_biohazard,
    "corner-mark": _arch_corner_mark,
    "slash": _arch_slash,
    "wedge": _arch_wedge,
    "circle-quad": _arch_circle_quad,
    "landscape-line": _arch_landscape_line,
    "double-wave": _arch_double_wave,
    "ring-dash": _arch_ring_dash,
    "two-dots": _arch_two_dots,
    "vertical-stripes": _arch_vertical_stripes,
    "diagonal": _arch_diagonal,
    "wave-field": _arch_wave_field,
    "cloud": _arch_cloud,
    "pinwheel": _arch_pinwheel,
    "rhythm-bars": _arch_rhythm_bars,
}

# Loose theme → archetype steering. Substring-matched (case-insensitive).
THEME_ARCHETYPES: dict[str, str] = {
    "sun": "carrier-sun",
    "light": "carrier-sun",
    "rise": "carrier-sun",
    "dawn": "sun-left",
    "spiral": "carrier-spiral",
    "growth": "spiral-free",
    "journey": "horizon",
    "orbit": "orbit",
    "satellite": "orbit",
    "balance": "diptych",
    "split": "diptych",
    "stack": "stack-blobs",
    "layer": "stack-blobs",
    "column": "column",
    "pillar": "column",
    "cross": "cross",
    "intersect": "cross",
    "horizon": "horizon",
    "field": "bounded-field",
    "scatter": "bounded-field",
    "dots": "dot-grid",
    "grid": "dot-grid",
    "burst": "burst",
    "spark": "starburst",
    "radial": "radial-strokes",
    "focus": "radial-strokes",
    "ring": "rings-field",
    "rings": "rings-field",
    "cycle": "rings-field",
    "loop": "ring-dash",
    "wave": "double-wave",
    "flow": "wave-field",
    "stream": "waves",
    "current": "waves",
    "stem": "stem",
    "branch": "stem",
    "mountain": "mountains",
    "landscape": "landscape-line",
    "peak": "mountains",
    "signal": "biohazard",
    "barrier": "wedge",
    "frame": "corner-mark",
    "slash": "slash",
    "speed": "diagonal",
    "diagonal": "diagonal",
    "stripe": "vertical-stripes",
    "rhythm": "rhythm-bars",
    "beat": "rhythm-bars",
    "pulse": "two-dots",
    "pair": "two-dots",
    "cloud": "cloud",
    "pinwheel": "pinwheel",
}


def _archetype_for(seed: str, theme: str | None) -> str:
    if theme:
        low = theme.lower()
        for key, arch in THEME_ARCHETYPES.items():
            if key in low:
                return arch
    rng = random.Random(f"pick:{seed or 'figure'}")
    names = sorted(ARCHETYPES)
    return names[rng.randrange(len(names))]


def _elements_for(seed: str, ground: str, theme: str | None) -> tuple[str, list[_El]]:
    rng = _rng(seed or "figure")
    p = _palette(ground)
    arch = _archetype_for(seed, theme)
    els = ARCHETYPES[arch](p, rng)
    # Thread the post seed into every element so the wobble/phase of each shape
    # varies per post — not just the archetype. Same theme, different seed → a
    # genuinely different figure.
    for e in els:
        e.noise = seed or "figure"
    return arch, els


def _fitted(els: list[_El]) -> tuple[list[_El], float, float, float]:
    """Return (elements, scale, tx, ty) with the union box fit inside SAFE."""
    s, tx, ty = _fit_transform(els)
    return els, s, tx, ty


def generate_illustration_svg(
    seed: str,
    ground: str = "white",
    theme: str | None = None,
    view_box: str = DEFAULT_VIEW_BOX,
) -> str:
    """Generate an Anthropic-style monochrome SVG fragment from a seed.

    Deterministic per ``seed``; visually random across seeds. An optional
    ``theme`` steers the composition archetype. Uses only ``var(--color-*)``
    token names, so it passes the verifier and adapts to both grounds.

    Every element is guaranteed to sit inside the safe inner frame: the whole
    composition is auto-fit (uniform scale + center) into the safe box, so it
    can never clip out of its slot or collide with surrounding copy.
    """
    p = _palette(ground)
    _, els = _elements_for(seed, ground, theme)
    _, s, tx, ty = _fitted(els)
    body = "\n    ".join(e.to_svg(p) for e in els)
    if s != 1.0 or tx != 0.0 or ty != 0.0:
        body = f'  <g transform="translate({tx:.2f},{ty:.2f}) scale({s:.4f})">\n{body}\n  </g>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" '
        f'viewBox="{view_box}" preserveAspectRatio="xMidYMid meet" '
        'role="img" aria-hidden="true">\n'
        f"  {body}\n"
        "</svg>"
    )


def generate_figure_metrics(seed: str, ground: str, theme: str | None) -> dict:
    """Return structural metrics for a procedural figure (for tool feedback).

    ``{"archetype", "element_count", "box": {...}, "within_safe": bool}``.
    ``within_safe`` is true only when every element's bounding box lies inside
    the safe inner frame — i.e. the figure cannot clip or overlap copy when
    rendered in its slot. Box coordinates are the *post-fit* bounds (the
    composition is auto-fit into the safe frame before rendering).
    """
    arch, els = _elements_for(seed, ground, theme)
    _, s, tx, ty = _fitted(els)
    u = _unioned_box(els)
    box = {
        "x0": round(u.x0 * s + tx, 1),
        "y0": round(u.y0 * s + ty, 1),
        "x1": round(u.x1 * s + tx, 1),
        "y1": round(u.y1 * s + ty, 1),
    }
    within = box["x0"] >= SAFE[0] and box["y0"] >= SAFE[1] and box["x1"] <= SAFE[2] and box["y1"] <= SAFE[3]
    return {
        "archetype": arch,
        "element_count": len(els),
        "box": box,
        "within_safe": within,
        "scale": round(s, 4),
    }


# ---------------------------------------------------------------------------
# LLM tool integration — the generator as a callable tool
# ---------------------------------------------------------------------------

# The unified ``illustrate`` tool (procedural OR curated DiceBear styles) lives
# in services/tools/illustrator.py; alias it here so existing importers stay
# stable.
from app.services.tools.illustrator import ILLUSTRATE_TOOL as ILLUSTRATION_TOOL  # noqa: E402

_DIRECTOR_SYSTEM = (
    "You are the illustration director for a strict monochrome editorial "
    "design system. An illustration is OPTIONAL — add one only if it "
    "genuinely strengthens this post. If you decide one helps, call the "
    "illustrate tool once. Choose 'procedural' for abstract organic "
    "compositions (the default — most posts), or a curated DiceBear style: "
    "people styles (open-peeps, lorelei, notionists, bottts) for "
    "human/human-centred posts, abstract styles (blobs, shapes, waves, "
    "landscape) for data/ideas/editorial art, or 'landscape' for "
    "journey/horizon posts. Add an abstract theme only (growth, flow, burst, "
    "orbit, layers, spiral...) — no literal objects, no words/letters, no "
    "emoji, no color terms. Keep the theme under 60 characters. You may pin "
    "parts on people styles (facial_hair, hair, expression, accessory) — "
    "omit for a random match. If no illustration helps, do NOT call any tool."
)


async def illustration_via_tool(
    agent_role: str = "designer",
    title: str = "",
    headline: str = "",
    category: str = "",
    ground: str = "white",
    seed: str = "",
) -> str:
    """Ask the LLM (via the unified tool) for a post illustration.

    Returns the figure/svg fragment if the LLM decides to illustrate, or "" if
    it declines or the tool call fails — no deterministic fallback, so media
    only ever appears when the LLM chose it.
    """
    from app.services.llm import call_llm_for_tool
    from app.services.tools.illustrator import run_illustrate

    user = (
        f"Title: {title or '(untitled)'}\n"
        f"Headline: {headline or '(none)'}\n"
        f"Category: {category or '(none)'}\n"
        f"Ground: {ground}"
    )
    try:
        args = await call_llm_for_tool(
            agent_role=agent_role,
            system_prompt=_DIRECTOR_SYSTEM,
            user_prompt=user,
            tool=ILLUSTRATION_TOOL,
            temperature=0.8,
            max_tokens=1024,
        )
        return run_illustrate(args, seed)
    except Exception as e:  # noqa: BLE001
        log.warning("[illustration] LLM tool call failed (%s) — no illustration", e)
        return ""
