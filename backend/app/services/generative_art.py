"""Seeded, connected vector illustrations: sparse editorial still lifes.

This module replaces the earlier "collage" engine. Instead of cropping complete
motif renderers into each other, it *draws* one coherent subject from a small
relational grammar: a shared anchor, a shared curve family and a shared stroke
weight. Every constituent shape is derived from continuous seeded parameters, so
two seeds change the geometry itself, not just which template is selected.

Subject grammars
----------------

``botanical``
    One arching stem carrying three to seven tapered leaves, attached at real
    points on the stem and angled from its tangent. Optionally one branch and
    either a lime sun disc behind the plant or one lime leaf.
``aperture``
    Two to four nested, deliberately asymmetrical arches standing on a
    baseline. The innermost opening is the lime aperture; small stair/tension
    bars attach to one foot.
``vessel``
    A filled vessel silhouette with a curved rim opening, optionally handled,
    supporting a forked sprout. One lime leaf sits on the sprout.

Every scene is built inside one box that keeps at least 12% breathing room on
all sides and occupies roughly half to two thirds of the canvas. A single
sub-minimal support (a ground line) is derived from the subject's own base
anchor; there is never scattered decoration.

The frozen recipe (:func:`build_composition`) contains the actual painted
elements as local SVG path data plus descriptive labels. Rendering is a pure
mapping from recipe to caller palette: ``ink``, ``paper`` and one accent. No
colour is invented here and no seed text is interpolated into markup.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from dataclasses import dataclass
from functools import lru_cache

__all__ = [
    "AccentPlan",
    "Box",
    "Composition",
    "Element",
    "Layer",
    "build_composition",
    "render_composition",
    "synthesis",
]

DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 900
MIN_CANVAS = 128
MAX_CANVAS = 4096
ENGINE = "connected-vector-v2"
SUBJECTS = ("botanical", "aperture", "vessel")
PLACEMENTS = ("center", "left", "right")

_MARGIN = 0.12


# --------------------------------------------------------------------------- #
# Recipe model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Box:
    """Axis-aligned bounds in canvas pixels."""

    x: float
    y: float
    width: float
    height: float

    @property
    def x1(self) -> float:
        return self.x + self.width

    @property
    def y1(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    def expanded(self, factor: float) -> "Box":
        if factor <= 0:
            raise ValueError("Expansion factor must be positive")
        dw = self.width * (factor - 1) / 2
        dh = self.height * (factor - 1) / 2
        return Box(self.x - dw, self.y - dh, self.width + 2 * dw, self.height + 2 * dh)

    def union(self, other: "Box") -> "Box":
        x = min(self.x, other.x)
        y = min(self.y, other.y)
        return Box(x, y, max(self.x1, other.x1) - x, max(self.y1, other.y1) - y)

    def to_dict(self) -> dict:
        return {
            "x": _round(self.x),
            "y": _round(self.y),
            "width": _round(self.width),
            "height": _round(self.height),
        }


@dataclass(frozen=True)
class Element:
    """One painted path: a leaf, stem, arch, vessel wall or support rule.

    ``fill``/``stroke`` use palette *roles*, never colour literals. The stored
    ``path`` is final canvas-space SVG path data, so the recipe describes the
    drawing exactly.
    """

    part: str
    path: str
    fill: str = "none"
    stroke: str = "none"
    stroke_width: float = 0.0
    closed: bool = False
    bbox: Box | None = None

    def to_dict(self) -> dict:
        return {
            "part": self.part,
            "path": self.path,
            "fill": self.fill,
            "stroke": self.stroke,
            "stroke_width": _round(self.stroke_width),
            "closed": self.closed,
            "bbox": self.bbox.to_dict() if self.bbox else None,
        }


@dataclass(frozen=True)
class Layer:
    """A coherent paint pass with one descriptive label."""

    index: int
    motif: str
    role: str
    accent: bool
    elements: tuple[Element, ...]

    @property
    def bounds(self) -> Box | None:
        result: Box | None = None
        for element in self.elements:
            if element.bbox is None:
                continue
            result = element.bbox if result is None else result.union(element.bbox)
        return result

    def to_dict(self) -> dict:
        bounds = self.bounds
        return {
            "index": self.index,
            "motif": self.motif,
            "role": self.role,
            "accent": self.accent,
            "element_count": len(self.elements),
            "bounds": bounds.to_dict() if bounds else None,
            "elements": [element.to_dict() for element in self.elements],
        }


@dataclass(frozen=True)
class AccentPlan:
    """Where the single lime element lives, and what it is."""

    layer: int
    part: str
    form: str
    area_ratio: float
    color_role: str = "hi"

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "part": self.part,
            "form": self.form,
            "area_ratio": round(self.area_ratio, 5),
            "color_role": self.color_role,
        }


@dataclass(frozen=True)
class Composition:
    """A palette-free, fully described illustration."""

    seed: str
    width: int
    height: int
    key: str
    subject: str
    topology: str
    caption: str
    layers: tuple[Layer, ...]
    accent: AccentPlan

    @property
    def bounds(self) -> Box:
        result: Box | None = None
        for layer in self.layers:
            bounds = layer.bounds
            if bounds is None:
                continue
            result = bounds if result is None else result.union(bounds)
        if result is None:  # pragma: no cover - every subject paints something
            return Box(self.width / 2, self.height / 2, 1, 1)
        return result

    def to_dict(self) -> dict:
        bounds = self.bounds
        return {
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "key": self.key,
            "engine": ENGINE,
            "subject": self.subject,
            "topology": self.topology,
            "caption": self.caption,
            "layer_count": len(self.layers),
            "occupancy": {
                "width_ratio": round(bounds.width / self.width, 4),
                "height_ratio": round(bounds.height / self.height, 4),
            },
            "bounds": bounds.to_dict(),
            "accent": self.accent.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
        }


# --------------------------------------------------------------------------- #
# Numeric helpers
# --------------------------------------------------------------------------- #


def _round(value: float) -> float:
    return round(float(value) + 0.0, 2)


def _f(value: float) -> str:
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _clamp(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _catmull_path(points, closed: bool = False, tension: float = 1.0) -> str:
    """Cubic path through ``points`` with Catmull-Rom tangents."""

    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 2:
        return f"M{_f(pts[0][0])},{_f(pts[0][1])}"
    n = len(pts)
    d = [f"M{_f(pts[0][0])},{_f(pts[0][1])}"]
    last = n if closed else n - 1
    for i in range(last):
        p0 = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed else pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        d.append(f"C{_f(c1[0])},{_f(c1[1])} {_f(c2[0])},{_f(c2[1])} {_f(p2[0])},{_f(p2[1])}")
    return "".join(d) + ("Z" if closed else "")


def _curve_points(points, samples: int = 27):
    """Sample a Catmull-Rom spline through ``points``."""

    pts = [(float(x), float(y)) for x, y in points]
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(i + 2, n - 1)]
        for step in range(samples):
            t = step / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                2 * p1[0]
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                2 * p1[1]
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1])
    return out


def _point_box(box: Box) -> tuple[float, float]:
    return box.cx, box.cy


def _ray_box_distance(origin, direction, box: Box, pad: float) -> float:
    """Distance from ``origin`` along ``direction`` until leaving ``box``."""

    x, y = origin
    dx, dy = direction
    lo_x, hi_x = box.x + pad, box.x1 - pad
    lo_y, hi_y = box.y + pad, box.y1 - pad
    limit = math.inf
    for p, d, lo, hi in ((x, dx, lo_x, hi_x), (y, dy, lo_y, hi_y)):
        if abs(d) < 1e-9:
            continue
        t1 = (lo - p) / d
        t2 = (hi - p) / d
        limit = min(limit, max(t1, t2))
    return max(0.0, limit)


def _bbox_of(points) -> Box | None:
    pts = list(points)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return Box(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _path_bounds(d: str) -> Box | None:
    # Every path this module emits contains only M/C/L/Z coordinate pairs, so
    # pairing the numbers is exact (control points included).
    nums = [float(value) for value in _NUMBER.findall(d)]
    points = list(zip(nums[0::2], nums[1::2]))
    return _bbox_of(points)


def _with_stroke(bounds: Box | None, stroke: str, stroke_width: float) -> Box | None:
    if bounds is None or stroke == "none" or stroke_width <= 0:
        return bounds
    return Box(
        bounds.x - stroke_width / 2,
        bounds.y - stroke_width / 2,
        bounds.width + stroke_width,
        bounds.height + stroke_width,
    )


def _element(
    part: str,
    points,
    *,
    fill: str = "none",
    stroke: str = "none",
    stroke_width: float = 0.0,
    closed: bool = False,
    tension: float = 1.0,
    extra_points=(),
) -> Element:
    pts = [(float(x), float(y)) for x, y in points]
    path = _catmull_path(pts, closed=closed, tension=tension)
    bounds = _path_bounds(path)
    return Element(
        part=part,
        path=path,
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        closed=closed,
        bbox=_with_stroke(bounds, stroke, stroke_width),
    )


def _raw_element(
    part: str,
    path: str,
    points,
    *,
    fill: str = "none",
    stroke: str = "none",
    stroke_width: float = 0.0,
    closed: bool = False,
) -> Element:
    return Element(
        part=part,
        path=path,
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        closed=closed,
        bbox=_with_stroke(_path_bounds(path), stroke, stroke_width),
    )


# --------------------------------------------------------------------------- #
# Primitive geometry
# --------------------------------------------------------------------------- #


def _circle_path(cx: float, cy: float, r: float) -> tuple[str, list[tuple[float, float]]]:
    k = 0.5522847498307936 * r
    pts = [
        (cx + r, cy),
        (cx + r, cy - k),
        (cx + k, cy - r),
        (cx, cy - r),
        (cx - k, cy - r),
        (cx - r, cy - k),
        (cx - r, cy),
        (cx - r, cy + k),
        (cx - k, cy + r),
        (cx, cy + r),
        (cx + k, cy + r),
        (cx + r, cy + k),
    ]
    path = (
        f"M{_f(cx + r)},{_f(cy)}"
        f"C{_f(cx + r)},{_f(cy - k)} {_f(cx + k)},{_f(cy - r)} {_f(cx)},{_f(cy - r)}"
        f"C{_f(cx - k)},{_f(cy - r)} {_f(cx - r)},{_f(cy - k)} {_f(cx - r)},{_f(cy)}"
        f"C{_f(cx - r)},{_f(cy + k)} {_f(cx - k)},{_f(cy + r)} {_f(cx)},{_f(cy + r)}"
        f"C{_f(cx + k)},{_f(cy + r)} {_f(cx + r)},{_f(cy + k)} {_f(cx + r)},{_f(cy)}Z"
    )
    return path, pts


def _arch_path(
    cx: float,
    base: float,
    left: float,
    right: float,
    height: float,
    apex_shift: float,
    close: bool = False,
    base_dip: float = 0.0,
) -> tuple[str, list[tuple[float, float]]]:
    """One asymmetrical arch: two cubic shoulders meeting at the apex."""

    ax = cx + apex_shift
    ay = base - height
    x0, x1 = cx - left, cx + right
    c1 = (x0, base - height * 0.5523)
    c2 = (ax - left * 0.5523, ay)
    c3 = (ax + right * 0.5523, ay)
    c4 = (x1, base - height * 0.5523)
    path = (
        f"M{_f(x0)},{_f(base)}"
        f"C{_f(c1[0])},{_f(c1[1])} {_f(c2[0])},{_f(c2[1])} {_f(ax)},{_f(ay)}"
        f"C{_f(c3[0])},{_f(c3[1])} {_f(c4[0])},{_f(c4[1])} {_f(x1)},{_f(base)}"
    )
    pts = [(x0, base), (ax, ay), (x1, base), c1, c2, c3, c4]
    if close:
        dip = base + base_dip
        mid = (x0 + x1) / 2
        path += (
            f"C{_f(x1 - right * 0.25)},{_f(dip)} {_f(mid + right * 0.2)},{_f(dip)} "
            f"{_f(mid)},{_f(dip)}"
            f"C{_f(mid - left * 0.2)},{_f(dip)} {_f(x0 + left * 0.25)},{_f(dip)} "
            f"{_f(x0)},{_f(base)}Z"
        )
        pts += [(x1 - right * 0.25, dip), (mid, dip), (x0 + left * 0.25, dip)]
    return path, pts


def _leaf_path(
    base: tuple[float, float],
    tip: tuple[float, float],
    width: float,
    bow: float,
    upper: float = 0.54,
    lower: float = 0.34,
) -> tuple[str, list[tuple[float, float]]]:
    """Broad leaf with a rounded petiolar base and a drawn, pointed tip."""

    bx, by = base
    tx, ty = tip
    vx, vy = tx - bx, ty - by
    length = math.hypot(vx, vy)
    if length < 1e-6:
        return f"M{_f(bx)},{_f(by)}Z", [(bx, by)]
    ux, uy = vx / length, vy / length
    nx, ny = -uy, ux
    half_base = width * 0.075
    base_l = (bx + nx * half_base, by + ny * half_base)
    base_r = (bx - nx * half_base, by - ny * half_base)
    c1 = (
        bx + vx * 0.22 + nx * (width * upper + bow * 0.50),
        by + vy * 0.22 + ny * (width * upper + bow * 0.50),
    )
    c2 = (
        bx + vx * 0.66 + nx * (width * upper * 0.74 + bow * 0.95),
        by + vy * 0.66 + ny * (width * upper * 0.74 + bow * 0.95),
    )
    c3 = (
        bx + vx * 0.68 - nx * (width * lower * 0.72 - bow * 0.85),
        by + vy * 0.68 - ny * (width * lower * 0.72 - bow * 0.85),
    )
    c4 = (
        bx + vx * 0.20 - nx * (width * lower - bow * 0.45),
        by + vy * 0.20 - ny * (width * lower - bow * 0.45),
    )
    # short rounded cap back to the petiole side of the blade
    b1 = (base_r[0] - vx * 0.035 - nx * width * 0.06, base_r[1] - vy * 0.035 - ny * width * 0.06)
    b2 = (base_l[0] - vx * 0.035 + nx * width * 0.06, base_l[1] - vy * 0.035 + ny * width * 0.06)
    path = (
        f"M{_f(base_l[0])},{_f(base_l[1])}"
        f"C{_f(c1[0])},{_f(c1[1])} {_f(c2[0])},{_f(c2[1])} {_f(tx)},{_f(ty)}"
        f"C{_f(c3[0])},{_f(c3[1])} {_f(c4[0])},{_f(c4[1])} {_f(base_r[0])},{_f(base_r[1])}"
        f"C{_f(b1[0])},{_f(b1[1])} {_f(b2[0])},{_f(b2[1])} {_f(base_l[0])},{_f(base_l[1])}Z"
    )
    return path, [base, base_l, base_r, c1, c2, (tx, ty), c3, c4, b1, b2]


def _taper_width(box: Box, factor: float, lo: float = 1.4, hi: float = 7.5) -> float:
    return _clamp(min(box.width, box.height) * factor, lo, hi)


def _safe_leaf(
    base: tuple[float, float],
    angle: float,
    desired: float,
    width_ratio: float,
    bow_ratio: float,
    box: Box,
    pad: float,
):
    """Clamp a leaf so its outline cannot leave the subject box."""

    direction = (math.cos(angle), math.sin(angle))
    reach = _ray_box_distance(base, direction, box, pad)
    length = max(12.0, min(desired, reach * 0.86))
    width = max(6.0, length * width_ratio)
    tip = (base[0] + direction[0] * length, base[1] + direction[1] * length)
    nx, ny = -direction[1], direction[0]
    bow = length * bow_ratio
    points = [
        base,
        (
            base[0] + (tip[0] - base[0]) * 0.24 + nx * (width * 0.56 + bow * 0.55),
            base[1] + (tip[1] - base[1]) * 0.24 + ny * (width * 0.56 + bow * 0.55),
        ),
        (
            base[0] + (tip[0] - base[0]) * 0.72 + nx * (width * 0.40 + bow * 0.95),
            base[1] + (tip[1] - base[1]) * 0.72 + ny * (width * 0.40 + bow * 0.95),
        ),
        tip,
        (
            base[0] + (tip[0] - base[0]) * 0.74 - nx * (width * 0.22),
            base[1] + (tip[1] - base[1]) * 0.74 - ny * (width * 0.22),
        ),
        (
            base[0] + (tip[0] - base[0]) * 0.26 - nx * (width * 0.30),
            base[1] + (tip[1] - base[1]) * 0.26 - ny * (width * 0.30),
        ),
    ]
    return base, tip, width, bow, points


# --------------------------------------------------------------------------- #
# Botanical grammar
# --------------------------------------------------------------------------- #


def _stem_sample(points, t: float) -> tuple[tuple[float, float], float]:
    samples = _curve_points(points, samples=36)
    index = _clamp(t, 0.0, 1.0) * (len(samples) - 1)
    i = int(index)
    frac = index - i
    if i >= len(samples) - 1:
        x, y = samples[-1]
        px, py = samples[-2]
    else:
        x = _lerp(samples[i][0], samples[i + 1][0], frac)
        y = _lerp(samples[i][1], samples[i + 1][1], frac)
        px, py = samples[i]
    return (x, y), math.atan2(y - py, x - px)


def _tapered_stem_path(
    samples, base_width: float, tip_width: float
) -> tuple[str, list[tuple[float, float]]]:
    """A filled, tapered stem outline around a sampled centerline."""

    pts = list(samples)
    if len(pts) < 3:
        return _catmull_path(pts), pts
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / (n - 1)
        prev = pts[max(i - 1, 0)]
        nxt = pts[min(i + 1, n - 1)]
        tx, ty = nxt[0] - prev[0], nxt[1] - prev[1]
        norm = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / norm, tx / norm
        width = tip_width + (base_width - tip_width) * (1.0 - t) ** 0.72
        left.append((x + nx * width / 2, y + ny * width / 2))
        right.append((x - nx * width / 2, y - ny * width / 2))
    outline = left + right[::-1]
    path = _catmull_path(outline, closed=True, tension=0.82)
    return path, outline


def _petiole_path(attach, blade, side: float):
    """A short curved petiole connecting the stem to the blade base."""

    mx = _lerp(attach[0], blade[0], 0.52)
    my = _lerp(attach[1], blade[1], 0.52)
    dx, dy = blade[0] - attach[0], blade[1] - attach[1]
    length = math.hypot(dx, dy) or 1.0
    bow = min(length * 0.22, 8.0) * side
    mid = (mx - dy / length * bow, my + dx / length * bow)
    return mid


def _botanical(box: Box, rng: random.Random, canvas_area: float):
    wide = box.width / box.height > 1.15
    pad = min(box.width, box.height) * 0.03

    base = (
        box.x + box.width * rng.uniform(0.44, 0.56),
        box.y + box.height * rng.uniform(0.90, 0.95),
    )
    stem_count = (
        rng.choices((1, 2, 3), weights=(10, 50, 40))[0]
        if wide
        else rng.choices((1, 2), weights=(35, 65))[0]
    )

    tips: list[tuple[float, float]] = []
    if wide:
        if stem_count == 1:
            side = rng.choice((-1.0, 1.0))
            tips.append(
                (
                    box.x
                    + box.width * (0.78 if side > 0 else 0.20)
                    + rng.uniform(-0.05, 0.05) * box.width,
                    box.y + box.height * rng.uniform(0.12, 0.26),
                )
            )
        elif stem_count == 2:
            tall_left = rng.random() < 0.5
            tips.append(
                (
                    box.x + box.width * rng.uniform(0.12, 0.26),
                    box.y
                    + box.height
                    * (rng.uniform(0.10, 0.20) if tall_left else rng.uniform(0.28, 0.42)),
                )
            )
            tips.append(
                (
                    box.x + box.width * rng.uniform(0.74, 0.88),
                    box.y
                    + box.height
                    * (rng.uniform(0.28, 0.42) if tall_left else rng.uniform(0.10, 0.20)),
                )
            )
        else:
            tips = [
                (
                    box.x + box.width * rng.uniform(0.46, 0.56),
                    box.y + box.height * rng.uniform(0.05, 0.13),
                ),
                (
                    box.x + box.width * rng.uniform(0.11, 0.23),
                    box.y + box.height * rng.uniform(0.28, 0.42),
                ),
                (
                    box.x + box.width * rng.uniform(0.77, 0.89),
                    box.y + box.height * rng.uniform(0.26, 0.40),
                ),
            ]
    else:
        if stem_count == 1:
            tips.append(
                (
                    box.x + box.width * rng.uniform(0.56, 0.70),
                    box.y + box.height * rng.uniform(0.06, 0.15),
                )
            )
        else:
            tips = [
                (
                    box.x + box.width * rng.uniform(0.26, 0.38),
                    box.y + box.height * rng.uniform(0.12, 0.24),
                ),
                (
                    box.x + box.width * rng.uniform(0.62, 0.74),
                    box.y + box.height * rng.uniform(0.08, 0.20),
                ),
            ]

    # a short trunk lifts the stem crown off the floor, so the fan never
    # collapses into a hard wishbone point
    crown = (
        base[0] + box.width * rng.uniform(-0.025, 0.025),
        base[1] - box.height * rng.uniform(0.10, 0.15),
    )
    stems: list[list[tuple[float, float]]] = []
    for tip in tips:
        dx, dy = tip[0] - crown[0], tip[1] - crown[1]
        outward = 1.0 if dx > 0 else -1.0
        sway = box.width * rng.uniform(0.015, 0.045) * rng.choice((-1.0, 1.0))
        stems.append(
            [
                crown,
                (
                    crown[0] + dx * 0.14 + outward * box.width * rng.uniform(0.08, 0.14) + sway,
                    crown[1] + dy * 0.24,
                ),
                (
                    crown[0]
                    + dx * 0.66
                    + outward * box.width * rng.uniform(0.05, 0.10)
                    - sway * 0.4,
                    crown[1] + dy * 0.72,
                ),
                tip,
            ]
        )

    base_width = min(box.width, box.height) * rng.uniform(0.018, 0.026)
    tip_width = base_width * rng.uniform(0.10, 0.18)
    stem_elements: list[Element] = []
    trunk_samples = _curve_points(
        [base, ((base[0] + crown[0]) / 2 + box.width * 0.015, (base[1] + crown[1]) / 2), crown],
        samples=12,
    )
    trunk_path, trunk_pts = _tapered_stem_path(trunk_samples, base_width * 1.10, base_width * 0.86)
    stem_elements.append(_raw_element("stem", trunk_path, trunk_pts, fill="ink", closed=True))
    stem_samples: list[list[tuple[float, float]]] = []
    for stem in stems:
        samples = _curve_points(stem, samples=22)
        stem_samples.append(samples)
        path, pts = _tapered_stem_path(samples, base_width, tip_width)
        stem_elements.append(_raw_element("stem", path, pts, fill="ink", closed=True))

    def leaf_angle(side: float) -> float:
        if side > 0:
            return -math.radians(rng.uniform(16, 74))
        return -math.pi + math.radians(rng.uniform(16, 74))

    # Distribute four to seven leaves over the stems, keeping the outer stems
    # sparser so the fan reads as one plant rather than a hedge.
    total_leaves = rng.randint(4, 7)
    stem_order = list(range(len(stems)))
    rng.shuffle(stem_order)
    leaf_specs = []
    for i in range(total_leaves):
        if i < len(stems):
            stem_index = i
            t = rng.uniform(0.26, 0.48)
        else:
            stem_index = stem_order[i % len(stems)]
            t = rng.uniform(0.48, 0.82)
        if i >= len(stems) * 2:
            t = rng.uniform(0.66, 0.90)
        attach, tangent = _stem_sample(stems[stem_index], t)
        side = -1.0 if (i + stem_index) % 2 == 0 else 1.0
        if rng.random() < 0.14:
            side *= -1
        droop = rng.random() < 0.22 and t < 0.60
        angle = leaf_angle(side)
        if droop:
            angle = (
                math.radians(rng.uniform(8, 34))
                if side > 0
                else -math.pi - math.radians(rng.uniform(2, 24))
            )
        desired = min(box.width * 0.40, box.height * 0.46) * rng.uniform(0.68, 1.0)
        desired *= 1.0 - 0.16 * max(0.0, t - 0.70)
        petiole = desired * rng.uniform(0.05, 0.09)
        blade = (
            attach[0] + math.cos(angle) * petiole,
            attach[1] + math.sin(angle) * petiole,
        )
        leaf_specs.append(
            {
                "attach": attach,
                "angle": angle,
                "blade": blade,
                "length": desired,
                "width_ratio": rng.uniform(0.50, 0.62),
                "bow_ratio": rng.uniform(0.06, 0.14) * rng.choice((-1.0, 1.0)),
                "upper": rng.uniform(0.44, 0.62),
                "lower": rng.uniform(0.27, 0.41),
                "accent": False,
                "stem": stem_index,
                "t": t,
            }
        )

    sun = rng.random() < 0.36
    if not sun and leaf_specs:
        candidates = [
            i for i, leaf in enumerate(leaf_specs) if 0.30 < leaf["t"] < 0.85 and leaf["stem"] == 0
        ] or list(range(len(leaf_specs)))
        leaf_specs[rng.choice(candidates)]["accent"] = True

    orbit_elements: list[Element] = []
    sun_elements: list[Element] = []
    accent_area = 0.0
    if sun:
        radius = min(box.width, box.height) * rng.uniform(0.115, 0.16)
        cx = _clamp(
            box.x + box.width * rng.uniform(0.44, 0.56),
            box.x + radius + pad * 0.4,
            box.x1 - radius - pad * 0.4,
        )
        cy = _clamp(
            box.y + box.height * rng.uniform(0.22, 0.34),
            box.y + radius + pad * 0.4,
            box.y1 - radius - pad * 0.4,
        )
        path, pts = _circle_path(cx, cy, radius)
        sun_elements.append(_raw_element("sun", path, pts, fill="accent", closed=True))
        accent_area = math.pi * radius * radius / canvas_area
        if rng.random() < 0.58:
            orbit = radius * rng.uniform(1.16, 1.30)
            available = min(cx - box.x, box.x1 - cx, cy - box.y, box.y1 - cy) - pad * 0.4
            if available > orbit:
                orbit_path, orbit_pts = _circle_path(cx, cy, orbit)
                orbit_elements.append(
                    _raw_element(
                        "orbit",
                        orbit_path,
                        orbit_pts,
                        stroke="ink",
                        stroke_width=max(1.2, base_width * 0.22),
                    )
                )

    leaf_elements: list[Element] = []
    accent_elements: list[Element] = []
    for leaf in leaf_specs:
        angle = leaf["angle"]
        direction = (math.cos(angle), math.sin(angle))
        reach = _ray_box_distance(leaf["blade"], direction, box, pad)
        blade_length = max(16.0, min(leaf["length"], reach * 0.92))
        width = max(10.0, blade_length * leaf["width_ratio"])
        tip = (
            leaf["blade"][0] + direction[0] * blade_length,
            leaf["blade"][1] + direction[1] * blade_length,
        )
        path, pts = _leaf_path(
            leaf["blade"],
            tip,
            width,
            leaf["bow_ratio"] * blade_length,
            upper=leaf["upper"],
            lower=leaf["lower"],
        )
        element = _raw_element(
            "leaf",
            path,
            pts,
            fill="accent" if leaf["accent"] else "ink",
            closed=True,
        )
        mid = _petiole_path(
            leaf["attach"],
            leaf["blade"],
            1.0 if leaf["attach"][0] < leaf["blade"][0] else -1.0,
        )
        petiole_element = _element(
            "petiole",
            [leaf["attach"], mid, leaf["blade"]],
            stroke="ink",
            stroke_width=max(1.8, base_width * 0.34),
        )
        if leaf["accent"]:
            accent_elements.extend([petiole_element, element])
            accent_area = 0.52 * width * blade_length / canvas_area
        else:
            leaf_elements.extend([petiole_element, element])

    subject_elements = stem_elements + leaf_elements + accent_elements

    layers: list[Layer] = []
    if orbit_elements:
        layers.append(Layer(0, "orbit", "support", False, tuple(orbit_elements)))
    if sun_elements:
        layers.append(Layer(len(layers), "sun", "accent", True, tuple(sun_elements)))
    subject_index = len(layers)
    layers.append(Layer(subject_index, "botanical", "subject", False, tuple(subject_elements)))

    leaf_count = len(leaf_specs)
    topology = (
        ("spray" if stem_count == 3 else "fork" if stem_count == 2 else "single-stem")
        + f" / {stem_count} stems"
        + (" / sun" if sun else "")
    )
    caption = (
        f"Botanical study — {leaf_count} broad leaves on a "
        f"{stem_count}-stem {'fan' if stem_count > 1 else 'stem'}"
    )
    accent = AccentPlan(
        layer=(1 if orbit_elements else 0) if sun else subject_index,
        part="sun" if sun else "leaf",
        form="disc" if sun else "leaf",
        area_ratio=max(0.0012, accent_area),
    )
    return tuple(layers), accent, topology, caption


# --------------------------------------------------------------------------- #
# Aperture grammar
# --------------------------------------------------------------------------- #


def _arch_geometry(cx, base, left, right, height, apex_shift):
    ax = cx + apex_shift
    ay = base - height
    x0, x1 = cx - left, cx + right
    return {
        "ax": ax,
        "ay": ay,
        "x0": x0,
        "x1": x1,
        "c1": (x0, base - height * 0.5523),
        "c2": (ax - left * 0.5523, ay),
        "c3": (ax + right * 0.5523, ay),
        "c4": (x1, base - height * 0.5523),
    }


def _arch_pts(geom, base):
    return [
        (geom["x0"], base),
        (geom["ax"], geom["ay"]),
        (geom["x1"], base),
        geom["c1"],
        geom["c2"],
        geom["c3"],
        geom["c4"],
    ]


def _arch_path_from(geom, base):
    return (
        f"M{_f(geom['x0'])},{_f(base)}"
        f"C{_f(geom['c1'][0])},{_f(geom['c1'][1])} "
        f"{_f(geom['c2'][0])},{_f(geom['c2'][1])} {_f(geom['ax'])},{_f(geom['ay'])}"
        f"C{_f(geom['c3'][0])},{_f(geom['c3'][1])} "
        f"{_f(geom['c4'][0])},{_f(geom['c4'][1])} {_f(geom['x1'])},{_f(base)}"
    )


def _arch_band_path(outer, inner, base):
    o = _arch_geometry(**outer)
    i = _arch_geometry(**inner)
    return (
        f"M{_f(o['x0'])},{_f(base)}"
        f"C{_f(o['c1'][0])},{_f(o['c1'][1])} {_f(o['c2'][0])},{_f(o['c2'][1])} "
        f"{_f(o['ax'])},{_f(o['ay'])}"
        f"C{_f(o['c3'][0])},{_f(o['c3'][1])} {_f(o['c4'][0])},{_f(o['c4'][1])} "
        f"{_f(o['x1'])},{_f(base)}"
        f"L{_f(i['x1'])},{_f(base)}"
        f"C{_f(i['c4'][0])},{_f(i['c4'][1])} {_f(i['c3'][0])},{_f(i['c3'][1])} "
        f"{_f(i['ax'])},{_f(i['ay'])}"
        f"C{_f(i['c2'][0])},{_f(i['c2'][1])} {_f(i['c1'][0])},{_f(i['c1'][1])} "
        f"{_f(i['x0'])},{_f(base)}Z"
    )


def _aperture(box: Box, rng: random.Random, canvas_area: float):
    arch_weight = _taper_width(box, 0.0125, 3.2, 7.5)
    support_weight = _taper_width(box, 0.0038, 1.2, 2.3)
    pad = min(box.width, box.height) * 0.02

    base_y = box.y1 - box.height * rng.uniform(0.075, 0.105)
    max_half = box.width * rng.uniform(0.25, 0.31)
    max_height = box.height * rng.uniform(0.82, 0.90)
    cx = box.x + box.width * rng.uniform(0.46, 0.56)
    lean = -1.0 if rng.random() < 0.5 else 1.0

    outer = {
        "cx": cx,
        "base": base_y,
        "left": max_half * rng.uniform(0.96, 1.04),
        "right": max_half * rng.uniform(0.96, 1.04),
        "height": max_height,
        "apex_shift": lean * box.width * rng.uniform(0.008, 0.030),
    }
    inner = {
        "cx": cx + lean * box.width * rng.uniform(0.010, 0.045),
        "base": base_y,
        "left": outer["left"] - box.width * rng.uniform(0.030, 0.070),
        "right": outer["right"] - box.width * rng.uniform(0.025, 0.065),
        "height": outer["height"] - box.height * rng.uniform(0.060, 0.100),
        "apex_shift": outer["apex_shift"] * rng.uniform(0.10, 0.55),
    }
    inner["left"] = max(inner["left"], box.width * 0.10)
    inner["right"] = max(inner["right"], box.width * 0.10)

    band_path = _arch_band_path(outer, inner, base_y)
    o = _arch_geometry(**outer)
    i = _arch_geometry(**inner)
    band_pts = [
        (o["x0"], base_y),
        (o["ax"], o["ay"]),
        (o["x1"], base_y),
        (i["x1"], base_y),
        (i["ax"], i["ay"]),
        (i["x0"], base_y),
        o["c1"],
        o["c2"],
        o["c3"],
        o["c4"],
        i["c1"],
        i["c2"],
        i["c3"],
        i["c4"],
    ]
    accent_elements = [
        _raw_element("aperture-band", band_path, band_pts, fill="accent", closed=True)
    ]

    arch_elements: list[Element] = []
    # the two boundary arches are drawn as ink rules over the lime band
    arch_elements.append(
        _raw_element(
            "outer-arch",
            _arch_path_from(o, base_y),
            _arch_pts(o, base_y),
            stroke="ink",
            stroke_width=arch_weight,
        )
    )
    arch_elements.append(
        _raw_element(
            "inner-arch",
            _arch_path_from(i, base_y),
            _arch_pts(i, base_y),
            stroke="ink",
            stroke_width=arch_weight * 0.62,
        )
    )
    # one or two extra hairline arches frame the band inside/outside
    extra_inner = rng.random() < 0.72
    if extra_inner:
        extra = {
            "cx": inner["cx"] + lean * box.width * rng.uniform(0.005, 0.022),
            "base": base_y,
            "left": max(inner["left"] - box.width * rng.uniform(0.035, 0.060), box.width * 0.075),
            "right": max(inner["right"] - box.width * rng.uniform(0.030, 0.055), box.width * 0.075),
            "height": inner["height"] - box.height * rng.uniform(0.045, 0.075),
            "apex_shift": inner["apex_shift"] * 0.4,
        }
        g = _arch_geometry(**extra)
        arch_elements.append(
            _raw_element(
                "nested-arch",
                _arch_path_from(g, base_y),
                _arch_pts(g, base_y),
                stroke="ink",
                stroke_width=arch_weight * 0.42,
            )
        )
    if rng.random() < 0.50:
        extra = {
            "cx": outer["cx"] + lean * box.width * rng.uniform(0.008, 0.025),
            "base": base_y,
            "left": outer["left"] + box.width * rng.uniform(0.018, 0.038),
            "right": outer["right"] + box.width * rng.uniform(0.018, 0.038),
            "height": outer["height"] + box.height * rng.uniform(0.012, 0.035),
            "apex_shift": outer["apex_shift"] * 1.25,
        }
        g = _arch_geometry(**extra)
        arch_elements.append(
            _raw_element(
                "nested-arch",
                _arch_path_from(g, base_y),
                _arch_pts(g, base_y),
                stroke="ink",
                stroke_width=arch_weight * 0.40,
            )
        )

    baseline_left = box.x + box.width * rng.uniform(0.05, 0.11)
    baseline_right = box.x1 - box.width * rng.uniform(0.05, 0.11)
    support_elements = [
        _element(
            "baseline",
            [(baseline_left, base_y), (baseline_right, base_y)],
            stroke="ink",
            stroke_width=support_weight,
        )
    ]

    stair_side = rng.choice((-1.0, 1.0))
    foot_x = outer["cx"] + (outer["right"] if stair_side > 0 else -outer["left"])
    step_rise = box.height * rng.uniform(0.038, 0.052)
    step_run = box.width * rng.uniform(0.030, 0.042)
    steps = rng.randint(3, 4)
    x = foot_x + stair_side * box.width * 0.030
    y = base_y
    stair_pts = [(x, y)]
    for _ in range(steps):
        nx = x + stair_side * step_run
        ny = y - step_rise
        stair_pts += [(x, ny), (nx, ny)]
        x, y = nx, ny
    stair_pts = [
        (
            _clamp(px, box.x + pad, box.x1 - pad),
            _clamp(py, box.y + pad, box.y1 - pad),
        )
        for px, py in stair_pts
    ]
    support_elements.append(
        _element("tension-bars", stair_pts, stroke="ink", stroke_width=support_weight)
    )

    plumb = rng.random() < 0.48
    if plumb:
        apex_x = o["ax"]
        support_elements.append(
            _element(
                "plumb-line",
                [
                    (apex_x, o["ay"] + box.height * 0.015),
                    (apex_x, base_y - box.height * rng.uniform(0.06, 0.14)),
                ],
                stroke="ink",
                stroke_width=support_weight * 0.90,
            )
        )
        bob_r = min(box.width, box.height) * rng.uniform(0.010, 0.017)
        bob_y = base_y - box.height * rng.uniform(0.06, 0.14)
        path, pts = _circle_path(apex_x, bob_y, bob_r)
        support_elements.append(_raw_element("plumb-bob", path, pts, fill="ink", closed=True))

    layers = [
        Layer(0, "aperture-band", "accent", True, tuple(accent_elements)),
        Layer(1, "nested-arches", "subject", False, tuple(arch_elements)),
        Layer(2, "measurement", "support", False, tuple(support_elements)),
    ]
    topology = f"band / {len(arch_elements)} arches"
    if plumb:
        topology += " / plumb"
    caption = "Instrument study — nested arches carrying a lime aperture band"
    outer_half = (outer["left"] + outer["right"]) / 2
    inner_half = (inner["left"] + inner["right"]) / 2
    area = math.pi / 2 * (outer_half * outer["height"] - inner_half * inner["height"])
    accent = AccentPlan(
        layer=0,
        part="aperture-band",
        form="band",
        area_ratio=max(0.002, area / canvas_area),
    )
    return tuple(layers), accent, topology, caption


# --------------------------------------------------------------------------- #
# Vessel grammar
# --------------------------------------------------------------------------- #


def _vessel(box: Box, rng: random.Random, canvas_area: float):
    stem_weight = _taper_width(box, 0.010, 2.7, 6.8)
    support_weight = _taper_width(box, 0.0038, 1.2, 2.3)
    pad = min(box.width, box.height) * 0.02

    rim_half = box.width * rng.uniform(0.20, 0.26)
    rim_y = box.y + box.height * rng.uniform(0.68, 0.74)
    cx = box.x + box.width * rng.uniform(0.47, 0.55)
    base_y = box.y + box.height * rng.uniform(0.90, 0.94)
    body_base = base_y - box.height * rng.uniform(0.050, 0.075)
    foot_half = rim_half * rng.uniform(0.40, 0.52)
    belly = rim_half * rng.uniform(1.02, 1.10)
    pot_h = body_base - rim_y
    dip = box.height * rng.uniform(0.026, 0.042)

    left_rim = cx - rim_half
    right_rim = cx + rim_half
    left_foot = cx - foot_half
    right_foot = cx + foot_half

    foot_path = (
        f"M{_f(left_foot)},{_f(body_base + 1)}"
        f"L{_f(cx - foot_half * 0.80)},{_f(base_y)}"
        f"L{_f(cx + foot_half * 0.80)},{_f(base_y)}"
        f"L{_f(right_foot)},{_f(body_base + 1)}Z"
    )
    foot_pts = [
        (left_foot, body_base),
        (cx - foot_half * 0.8, base_y),
        (cx + foot_half * 0.8, base_y),
        (right_foot, body_base),
    ]

    body_path = (
        f"M{_f(left_rim)},{_f(rim_y)}"
        f"C{_f(left_rim - rim_half * 0.04)},{_f(rim_y + pot_h * 0.28)} "
        f"{_f(cx - belly)},{_f(rim_y + pot_h * 0.55)} {_f(cx - foot_half * 1.06)},{_f(body_base)}"
        f"C{_f(cx - foot_half * 0.72)},{_f(body_base + box.height * 0.008)} "
        f"{_f(cx + foot_half * 0.72)},{_f(body_base + box.height * 0.008)} "
        f"{_f(cx + foot_half * 1.06)},{_f(body_base)}"
        f"C{_f(cx + belly)},{_f(rim_y + pot_h * 0.55)} "
        f"{_f(right_rim + rim_half * 0.04)},{_f(rim_y + pot_h * 0.28)} {_f(right_rim)},{_f(rim_y)}"
        f"C{_f(right_rim - rim_half * 0.20)},{_f(rim_y + dip)} "
        f"{_f(left_rim + rim_half * 0.20)},{_f(rim_y + dip)} {_f(left_rim)},{_f(rim_y)}Z"
    )
    body_pts = [
        (left_rim, rim_y),
        (cx - belly, rim_y + pot_h * 0.55),
        (cx - foot_half * 1.06, body_base),
        (cx, body_base + box.height * 0.008),
        (cx + foot_half * 1.06, body_base),
        (cx + belly, rim_y + pot_h * 0.55),
        (right_rim, rim_y),
        (cx, rim_y + dip),
    ]

    body_elements = [
        _raw_element("vessel-foot", foot_path, foot_pts, fill="ink", closed=True),
        _raw_element("vessel-body", body_path, body_pts, fill="ink", closed=True),
    ]

    # two fine paper ribs make the silhouette read as a drawn vessel rather
    # than a solid blob; they follow the same wall curves as the body.
    rib_elements: list[Element] = []
    rib_specs = [(0.32, 0.010), (0.60, 0.007)]
    for t, bulge in rib_specs:
        if rng.random() < 0.70:
            y = rim_y + pot_h * t + box.height * rng.uniform(-0.006, 0.006)
            half = rim_half * (1.03 - 0.28 * t)
            rib_elements.append(
                _element(
                    "rim-rib",
                    [
                        (cx - half, y),
                        (cx, y + box.height * bulge),
                        (cx + half, y),
                    ],
                    stroke="paper",
                    stroke_width=max(1.4, support_weight * 0.95),
                )
            )

    handle = rng.random() < 0.34
    if handle:
        side = -1.0 if rng.random() < 0.5 else 1.0
        anchor = left_rim if side < 0 else right_rim
        attach_upper = (anchor + side * rim_half * 0.02, rim_y + box.height * 0.02)
        attach_lower = (
            cx + side * belly * 0.92,
            rim_y + pot_h * rng.uniform(0.30, 0.42),
        )
        out = (
            cx + side * (belly + rim_half * rng.uniform(0.05, 0.14)),
            _lerp(attach_upper[1], attach_lower[1], 0.48),
        )
        body_elements.append(
            _element(
                "handle",
                [attach_upper, out, attach_lower],
                stroke="ink",
                stroke_width=stem_weight * 0.66,
            )
        )

    # Lime sun behind the plant; the leaves cross it, so the accent is part of
    # the still life rather than a shape that satisfies a colour check.
    radius = min(box.width, box.height) * rng.uniform(0.130, 0.175)
    sun_cx = _clamp(
        cx + box.width * rng.uniform(-0.05, 0.05),
        box.x + radius + pad * 0.4,
        box.x1 - radius - pad * 0.4,
    )
    sun_cy = _clamp(
        box.y + box.height * rng.uniform(0.20, 0.34),
        box.y + radius + pad * 0.4,
        box.y1 - radius - pad * 0.4,
    )
    sun_path, sun_pts = _circle_path(sun_cx, sun_cy, radius)

    # A wide fan of stems lifts the plant well above the small vessel, so the
    # silhouette is foliage first and container second.
    sprout_base = (cx, rim_y + dip * 0.45)
    count = rng.choices((2, 3), weights=(30, 70))[0]
    tips: list[tuple[float, float]] = []
    if count == 2:
        tips = [
            (
                box.x + box.width * rng.uniform(0.20, 0.34),
                box.y + box.height * rng.uniform(0.14, 0.26),
            ),
            (
                box.x + box.width * rng.uniform(0.66, 0.80),
                box.y + box.height * rng.uniform(0.08, 0.20),
            ),
        ]
    else:
        tips = [
            (
                box.x + box.width * rng.uniform(0.44, 0.56),
                box.y + box.height * rng.uniform(0.05, 0.13),
            ),
            (
                box.x + box.width * rng.uniform(0.15, 0.28),
                box.y + box.height * rng.uniform(0.24, 0.38),
            ),
            (
                box.x + box.width * rng.uniform(0.72, 0.85),
                box.y + box.height * rng.uniform(0.20, 0.34),
            ),
        ]

    stems: list[list[tuple[float, float]]] = []
    for tip in tips:
        dx, dy = tip[0] - sprout_base[0], tip[1] - sprout_base[1]
        outward = 1.0 if dx > 0 else -1.0
        stems.append(
            [
                sprout_base,
                (
                    sprout_base[0] + dx * 0.16 + outward * box.width * rng.uniform(0.07, 0.12),
                    sprout_base[1] + dy * 0.26,
                ),
                (
                    sprout_base[0] + dx * 0.84 + outward * box.width * rng.uniform(0.01, 0.04),
                    sprout_base[1] + dy * 0.80,
                ),
                tip,
            ]
        )

    sprout_elements: list[Element] = []
    for path in stems:
        samples = _curve_points(path, samples=20)
        spath, spts = _tapered_stem_path(samples, stem_weight * 0.60, stem_weight * 0.12)
        sprout_elements.append(_raw_element("sprout-stem", spath, spts, fill="ink", closed=True))

    leaf_count = rng.randint(5, 7)
    per_stem = [leaf_count // len(stems)] * len(stems)
    for i in range(leaf_count % len(stems)):
        per_stem[i] += 1
    leaf_index = 0
    for stem_index, path in enumerate(stems):
        n_here = per_stem[stem_index]
        for j in range(n_here):
            t = _clamp(0.26 + 0.60 * (j + 0.5) / n_here + rng.uniform(-0.03, 0.03), 0.22, 0.88)
            attach, tangent = _stem_sample(path, t)
            side = -1.0 if (leaf_index + stem_index) % 2 == 0 else 1.0
            if rng.random() < 0.14:
                side *= -1
            if side > 0:
                angle = -math.radians(rng.uniform(16, 70))
            else:
                angle = -math.pi + math.radians(rng.uniform(16, 70))
            if rng.random() < 0.16 and t < 0.55:
                angle = (
                    math.radians(rng.uniform(8, 30))
                    if side > 0
                    else -math.pi - math.radians(rng.uniform(2, 22))
                )
            desired = min(box.width * 0.27, box.height * 0.35) * rng.uniform(0.66, 1.0)
            desired *= 1.0 - 0.16 * max(0.0, t - 0.70)
            petiole = desired * rng.uniform(0.05, 0.09)
            blade = (
                attach[0] + math.cos(angle) * petiole,
                attach[1] + math.sin(angle) * petiole,
            )
            reach = _ray_box_distance(blade, (math.cos(angle), math.sin(angle)), box, pad)
            blade_length = max(16.0, min(desired, reach * 0.90))
            width = max(10.0, blade_length * rng.uniform(0.50, 0.62))
            tip = (
                blade[0] + math.cos(angle) * blade_length,
                blade[1] + math.sin(angle) * blade_length,
            )
            leaf_path, pts = _leaf_path(
                blade,
                tip,
                width,
                rng.uniform(0.06, 0.13) * blade_length * (1.0 if leaf_index % 2 == 0 else -1.0),
                upper=rng.uniform(0.44, 0.62),
                lower=rng.uniform(0.27, 0.41),
            )
            mid = _petiole_path(attach, blade, 1.0 if leaf_index % 2 == 0 else -1.0)
            sprout_elements.append(
                _element(
                    "petiole",
                    [attach, mid, blade],
                    stroke="ink",
                    stroke_width=max(1.8, stem_weight * 0.34),
                )
            )
            sprout_elements.append(_raw_element("leaf", leaf_path, pts, fill="ink", closed=True))
            leaf_index += 1

    support_elements: list[Element] = []
    if rng.random() < 0.38:
        y = min(base_y + box.height * 0.025, box.y1 - pad * 0.3)
        half = rim_half * rng.uniform(1.02, 1.14)
        support_elements.append(
            _element(
                "ground-line",
                [(cx - half, y), (cx + half, y)],
                stroke="ink",
                stroke_width=support_weight,
            )
        )

    layers = [
        Layer(
            0,
            "sun",
            "accent",
            True,
            (_raw_element("sun", sun_path, sun_pts, fill="accent", closed=True),),
        ),
        Layer(1, "vessel", "subject", False, tuple(body_elements + rib_elements)),
        Layer(2, "sprout", "subject", False, tuple(sprout_elements)),
    ]
    if support_elements:
        layers.append(Layer(3, "ground-line", "support", False, tuple(support_elements)))

    topology = (
        ("handled" if handle else "plain")
        + " / footed-planter / "
        + ("forked-sprout" if count > 1 else "single-sprout")
    )
    caption = (
        f"Vessel study — {'handled ' if handle else ''}footed planter holding a "
        f"{'forked' if count > 1 else 'single'} sprout"
    )
    accent = AccentPlan(
        layer=0,
        part="sun",
        form="disc",
        area_ratio=math.pi * radius * radius / canvas_area,
    )
    return tuple(layers), accent, topology, caption


# --------------------------------------------------------------------------- #
# Scene planning
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=128)
def _compose(seed: str, width: int, height: int) -> Composition:
    if width < MIN_CANVAS or height < MIN_CANVAS:
        raise ValueError(f"Composition canvas must be at least {MIN_CANVAS}x{MIN_CANVAS}")
    if width > MAX_CANVAS or height > MAX_CANVAS:
        raise ValueError(f"Composition canvas must not exceed {MAX_CANVAS}x{MAX_CANVAS}")

    digest = hashlib.sha256(f"{ENGINE}:{seed}:{width}x{height}".encode()).hexdigest()
    key = digest[:12]
    rng = random.Random(int(digest[:16], 16))

    subject = rng.choices(SUBJECTS, weights=(40, 31, 29))[0]
    box_w = width * rng.uniform(0.53, 0.64)
    box_h = height * rng.uniform(0.57, 0.68)
    box = Box((width - box_w) / 2, (height - box_h) / 2, box_w, box_h)

    if subject == "botanical":
        layers, accent, topology, caption = _botanical(box, rng, float(width * height))
    elif subject == "aperture":
        layers, accent, topology, caption = _aperture(box, rng, float(width * height))
    else:
        layers, accent, topology, caption = _vessel(box, rng, float(width * height))

    return Composition(
        seed=seed,
        width=width,
        height=height,
        key=key,
        subject=subject,
        topology=topology,
        caption=caption,
        layers=layers,
        accent=accent,
    )


def build_composition(
    seed: str, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
) -> Composition:
    """Return the frozen, palette-free recipe for ``seed`` at ``width x height``."""

    return _compose(str(seed), int(width), int(height))


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _palette_roles(palette: dict) -> dict:
    """Normalise the caller palette. No colour is ever invented here."""

    accents = [str(value) for value in (palette.get("acc") or []) if value]
    ink = str(palette.get("ink") or "currentColor")
    accent = str(palette.get("hi") or (accents[0] if accents else ink))
    paper = str(palette.get("bg") or "none")
    return {"ink": ink, "accent": accent, "paper": paper}


def _paint(role: str, roles: dict) -> str:
    return roles.get(role) or "none"


def _element_markup(element: Element, roles: dict) -> str:
    attrs = [f'fill="{_paint(element.fill, roles)}"']
    if element.stroke != "none" and element.stroke_width > 0:
        attrs += [
            f'stroke="{_paint(element.stroke, roles)}"',
            f'stroke-width="{_f(element.stroke_width)}"',
            'stroke-linecap="round"',
            'stroke-linejoin="round"',
        ]
    return f'<path d="{element.path}" {" ".join(attrs)}/>'


def _placement_offset(recipe: Composition, placement: str) -> tuple[float, float]:
    """Move the *complete* drawing into the requested area without cropping."""

    if placement not in PLACEMENTS:
        raise ValueError("Placement must be center, left or right")
    width, height = recipe.width, recipe.height
    bounds = recipe.bounds
    margin_x, margin_y = width * _MARGIN, height * _MARGIN

    dx = width / 2 - bounds.cx
    if placement == "left":
        dx = width * 0.20 - bounds.x
    elif placement == "right":
        dx = width * 0.80 - bounds.x1
    dy = height / 2 - bounds.cy

    dx = _clamp(dx, margin_x - bounds.x, width - margin_x - bounds.x1)
    dy = _clamp(dy, margin_y - bounds.y, height - margin_y - bounds.y1)
    return dx, dy


def _render_into(s, recipe: Composition, palette: dict, placement: str = "center") -> None:
    width, height = recipe.width, recipe.height
    if (getattr(s, "w", width), getattr(s, "h", height)) != (width, height):
        raise ValueError("Collector size does not match the composition canvas")

    roles = _palette_roles(palette)
    safe = "".join(ch for ch in str(getattr(s, "prefix", "art"))[:32] if ch.isalnum() or ch in "-_")
    safe = safe or "art"
    clip_id = f"{safe}-{recipe.key}-{s.uid()}-frame"
    s.add(
        f'<defs><clipPath id="{clip_id}">'
        f'<rect x="0" y="0" width="{width}" height="{height}"/>'
        "</clipPath></defs>"
    )
    s.add(f'<g clip-path="url(#{clip_id})">')
    dx, dy = _placement_offset(recipe, placement)
    if abs(dx) > 0.001 or abs(dy) > 0.001:
        s.add(f'<g transform="translate({_f(dx)} {_f(dy)})">')
        moved = True
    else:
        moved = False
    for layer in recipe.layers:
        for element in layer.elements:
            s.add(_element_markup(element, roles))
    if moved:
        s.add("</g>")
    s.add("</g>")


def render_composition(
    seed: str,
    palette: dict,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    placement: str = "center",
) -> str:
    """Render ``seed`` as one connected illustration in the caller's palette."""

    from app.services.procedural_art import Svg

    recipe = build_composition(seed, width, height)
    svg = Svg(width, height, palette.get("bg") or "none", prefix=f"gen-{recipe.key}")
    _render_into(svg, recipe, palette, placement=placement)
    return str(svg)


def synthesis(s, rng, pal, nz) -> None:
    """Adapter for ``procedural_art.MOTIFS['synthesis']``.

    The scene seed comes from the caller's RNG so the illustration is
    deterministic for a given parent seed and never touches global randomness.
    """

    seed = f"scene:{rng.getrandbits(64):016x}"
    recipe = build_composition(
        seed,
        int(getattr(s, "w", DEFAULT_WIDTH)),
        int(getattr(s, "h", DEFAULT_HEIGHT)),
    )
    _render_into(s, recipe, pal)
