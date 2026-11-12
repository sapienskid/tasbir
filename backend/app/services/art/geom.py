"""Geometry primitives with authoritative bounds.

Every element knows its own bounding box, so the no-clip guarantee is tracked
exactly instead of being re-parsed from SVG text. Builder functions compute
conservative boxes (control-point hulls plus stroke padding), and groups
transform their children's boxes with the same matrix used for rendering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Palette roles. A role resolves through the render palette to a CSS variable.
PAPER = "paper"
INK = "ink"
MID = "mid"
CARRIER = "carrier"
ACCENT = "accent"


def fmt(n: float) -> str:
    return f"{n:.1f}"


@dataclass(frozen=True)
class Box:
    """Axis-aligned bounding box (x0,y0 top-left, x1,y1 bottom-right)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    def within(self, safe: tuple[float, float, float, float]) -> bool:
        return (
            self.x0 >= safe[0]
            and self.y0 >= safe[1]
            and self.x1 <= safe[2]
            and self.y1 <= safe[3]
        )

    def expand(self, d: float) -> "Box":
        return Box(self.x0 - d, self.y0 - d, self.x1 + d, self.y1 + d)

    def union(self, other: "Box") -> "Box":
        return Box(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )

    def translated(self, dx: float, dy: float) -> "Box":
        return Box(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def scaled(self, s: float, tx: float = 0.0, ty: float = 0.0) -> "Box":
        return Box(
            self.x0 * s + tx,
            self.y0 * s + ty,
            self.x1 * s + tx,
            self.y1 * s + ty,
        )

    def as_dict(self) -> dict:
        return {k: round(v, 1) for k, v in
                (("x0", self.x0), ("y0", self.y0), ("x1", self.x1), ("y1", self.y1))}


def box_of(points: list[tuple[float, float]]) -> Box:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Box(min(xs), min(ys), max(xs), max(ys))


def bounds_of(*items) -> Box:
    """Union of Box objects and point tuples."""
    boxes: list[Box] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, Box):
            boxes.append(item)
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            boxes.append(Box(item[0], item[1], item[0], item[1]))
        elif isinstance(item, (tuple, list)) and len(item) == 4:
            boxes.append(Box(*item))
        else:
            boxes.extend(i for i in (item,) if isinstance(i, Box))
    if not boxes:
        return Box(0, 0, 0, 0)
    out = boxes[0]
    for b in boxes[1:]:
        out = out.union(b)
    return out


@dataclass(frozen=True)
class Frame:
    """A canvas and its safe drawing area."""

    width: float = 400
    height: float = 400
    margin: float = 0.07

    @property
    def safe(self) -> tuple[float, float, float, float]:
        mx = self.width * self.margin
        my = self.height * self.margin
        return (mx, my, self.width - mx, self.height - my)

    @property
    def safe_box(self) -> Box:
        return Box(*self.safe)

    def fit(self, box: Box, into: Box | None = None) -> tuple[float, float, float]:
        """Uniform scale + translate that fits ``box`` inside ``into`` (SAFE)."""
        target = into or self.safe_box
        if box.w <= 0 or box.h <= 0:
            return 1.0, 0.0, 0.0
        s = min(1.0, target.w / box.w, target.h / box.h)
        nw, nh = box.w * s, box.h * s
        tx = target.x0 + (target.w - nw) / 2 - box.x0 * s
        ty = target.y0 + (target.h - nh) / 2 - box.y0 * s
        return s, tx, ty


@dataclass(frozen=True)
class Placed:
    """A bounding box plus the transform that produced it (diagnostics only)."""

    box: Box
    scale: float = 1.0
    tx: float = 0.0
    ty: float = 0.0


class El:
    """One drawable element."""

    def box(self) -> Box:
        raise NotImplementedError

    def svg(self, pal: dict) -> str:
        raise NotImplementedError


@dataclass
class Path(El):
    d: str
    bounds: Box
    fill: str | None = None
    stroke: str | None = None
    width: float = 0.0

    def box(self) -> Box:
        pad = self.width / 2 + 0.6
        return self.bounds.expand(pad)

    def svg(self, pal: dict) -> str:
        parts = [f'd="{self.d}"']
        style = []
        if self.fill:
            style.append(f"fill:{pal.get(self.fill, 'none')}")
        else:
            style.append("fill:none")
        if self.stroke:
            style.append(f"stroke:{pal.get(self.stroke, 'none')}")
            style.append(f"stroke-width:{self.width:.1f}")
            style.append("stroke-linecap:round")
            style.append("stroke-linejoin:round")
        return f'<path {" ".join(parts)} style="{";".join(style)}"/>'


@dataclass
class Circle(El):
    cx: float
    cy: float
    r: float
    fill: str | None = None
    stroke: str | None = None
    width: float = 0.0

    def box(self) -> Box:
        pad = self.width / 2 + 0.6
        return Box(self.cx - self.r, self.cy - self.r,
                   self.cx + self.r, self.cy + self.r).expand(pad)

    def svg(self, pal: dict) -> str:
        style = [f"fill:{pal.get(self.fill) if self.fill else 'none'}"]
        if self.stroke:
            style.append(f"stroke:{pal.get(self.stroke, 'none')}")
            style.append(f"stroke-width:{self.width:.1f}")
        return (
            f'<circle cx="{fmt(self.cx)}" cy="{fmt(self.cy)}" r="{fmt(self.r)}" '
            f'style="{";".join(style)}"/>'
        )


@dataclass
class Group(El):
    els: list[El]
    scale: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def box(self) -> Box:
        out: Box | None = None
        for e in self.els:
            b = e.box().scaled(self.scale, self.tx, self.ty)
            out = b if out is None else out.union(b)
        return out or Box(0, 0, 0, 0)

    def svg(self, pal: dict) -> str:
        body = "".join(e.svg(pal) for e in self.els)
        if self.scale != 1.0 or self.tx != 0.0 or self.ty != 0.0:
            return (
                f'<g transform="translate({fmt(self.tx)},{fmt(self.ty)}) '
                f'scale({self.scale:.4f})">{body}</g>'
            )
        return f"<g>{body}</g>"


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #


def polyline(points: list[tuple[float, float]]) -> str:
    return " ".join(
        ("M " if i == 0 else "L ") + fmt(p[0]) + " " + fmt(p[1])
        for i, p in enumerate(points)
    )


def quadratic(p0, p1, p2) -> str:
    return (
        f"M {fmt(p0[0])} {fmt(p0[1])} Q {fmt(p1[0])} {fmt(p1[1])} "
        f"{fmt(p2[0])} {fmt(p2[1])}"
    )


def cubic(p0, c1, c2, p3) -> str:
    return (
        f"M {fmt(p0[0])} {fmt(p0[1])} C {fmt(c1[0])} {fmt(c1[1])} "
        f"{fmt(c2[0])} {fmt(c2[1])} {fmt(p3[0])} {fmt(p3[1])}"
    )


def catmull_closed(points: list[tuple[float, float]]) -> str:
    n = len(points)
    d = ["M " + fmt(points[0][0]) + " " + fmt(points[0][1])]
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d.append(
            f"C {fmt(c1[0])} {fmt(c1[1])} {fmt(c2[0])} {fmt(c2[1])} "
            f"{fmt(p2[0])} {fmt(p2[1])}"
        )
    return " ".join(d) + " Z"


def blob_points(cx, cy, rx, ry, rng, n: int = 24, strength: float = 1.0):
    """Organic closed outline — smooth harmonics, never a perfect circle."""
    harmonics = 3
    amps = [rng.uniform(0.03, 0.075) * strength for _ in range(harmonics)]
    freqs = [rng.randint(2, 4) for _ in range(harmonics)]
    phases = [rng.uniform(0, math.tau) for _ in range(harmonics)]
    pts = []
    for i in range(n):
        a = i / n * math.tau
        rad = 1.0 + sum(amps[j] * math.sin(freqs[j] * a + phases[j])
                        for j in range(harmonics))
        pts.append((cx + rx * rad * math.cos(a), cy + ry * rad * math.sin(a)))
    return pts


def arc_path(cx, cy, r, a0, a1) -> tuple[str, Box]:
    """Circular arc as a path + conservative box (endpoints, mid, centre)."""
    steps = 18
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return polyline(pts), box_of(pts)


def stroke_box(pts: list[tuple[float, float]], width: float = 0.0) -> Box:
    return box_of(pts).expand(width / 2 + 0.6)
