"""Spatial fields — the structure a subject is composed against.

A field is never decoration: it is a measurable structure (grid, contour set,
hatch, stipple cloud, node network, rays, waves …) generated **inside the safe
box**, so it can never clip. Every field exposes an optional ``node`` (a point
the subject can be anchored to) and ``horizon`` (a line the subject can stand
on), which is what makes the subject/field relation visible.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .geom import (
    CARRIER,
    INK,
    MID,
    Box,
    Circle,
    El,
    Path,
    blob_points,
    box_of,
    catmull_closed,
    polyline,
)

__all__ = ["FIELD_NAMES", "Field", "build_field"]


@dataclass
class Field:
    name: str
    els: list[El] = field(default_factory=list)
    node: tuple[float, float] | None = None
    horizon: float | None = None

    def box(self) -> Box:
        out: Box | None = None
        for e in self.els:
            b = e.box()
            out = b if out is None else out.union(b)
        return out or Box(0, 0, 0, 0)


def _line(x0, y0, x1, y1, width=1.2, role=INK) -> Path:
    pts = [(x0, y0), (x1, y1)]
    return Path(polyline(pts), box_of(pts), stroke=role, width=width)


def _safe_point(safe: Box, x: float, y: float, pad: float = 0.0) -> tuple[float, float]:
    return (
        min(max(x, safe.x0 + pad), safe.x1 - pad),
        min(max(y, safe.y0 + pad), safe.y1 - pad),
    )


def _ellipse_hits(cx, cy, rx, ry, angle, offset):
    """Endpoints of a line offset from an ellipse centre, or None."""
    ux, uy = math.cos(angle), math.sin(angle)
    nx, ny = -uy, ux
    px, py = cx + nx * offset, cy + ny * offset
    a = (ux / rx) ** 2 + (uy / ry) ** 2
    b = 2 * (px * ux / rx**2 + py * uy / ry**2)
    c = (px / rx) ** 2 + (py / ry) ** 2 - 1
    disc = b * b - 4 * a * c
    if disc <= 0:
        return None
    root = math.sqrt(disc)
    t0, t1 = (-b - root) / (2 * a), (-b + root) / (2 * a)
    return (px + ux * t0, py + uy * t0), (px + ux * t1, py + uy * t1)


def _grid(rng, safe: Box, focus, horizon) -> Field:
    cols = rng.randint(5, 7)
    rows = rng.randint(4, 6)
    els: list[El] = []
    for i in range(cols + 1):
        x = safe.x0 + safe.w * i / cols
        els.append(_line(x, safe.y0, x, safe.y1, 1.0, CARRIER))
    for j in range(rows + 1):
        y = safe.y0 + safe.h * j / rows
        els.append(_line(safe.x0, y, safe.x1, y, 1.0, CARRIER))
    node = focus or (safe.x0 + safe.w * 0.6, safe.y0 + safe.h * 0.45)
    els.append(Circle(node[0], node[1], 4.2, fill=INK))
    return Field("grid", els, node=node, horizon=safe.y1 - safe.h * 0.08)


def _bands(rng, safe: Box, focus, horizon) -> Field:
    count = rng.randint(5, 7)
    els: list[El] = []
    for i in range(count):
        t = (i + 0.6) / (count + 0.4)
        y = safe.y0 + safe.h * t
        width = 2.6 if i == count // 2 else rng.uniform(0.8, 1.6)
        if i == count // 2:
            els.append(_line(safe.x0, y, safe.x0 + safe.w * 0.72, y, width, INK))
            els.append(_line(safe.x0 + safe.w * 0.80, y, safe.x1, y, 1.0, MID))
        else:
            els.append(_line(safe.x0, y, safe.x1, y, width, CARRIER))
    node = focus or (safe.x0 + safe.w * 0.32, safe.y0 + safe.h * 0.5)
    els.append(Circle(node[0], node[1], 3.6, fill=INK))
    return Field("bands", els, node=node, horizon=safe.y0 + safe.h * 0.9)


def _contour(rng, safe: Box, focus, horizon) -> Field:
    els: list[El] = []
    cx, cy = focus or (safe.cx, safe.cy)
    max_r = min(safe.w, safe.h) * 0.46
    rings = rng.randint(6, 8)
    for i in range(rings):
        r = max_r * (i + 1) / rings
        pts = blob_points(cx, cy, r, r * rng.uniform(0.74, 0.9), rng, 22, 1.0)
        pts = [(min(max(x, safe.x0 + 1), safe.x1 - 1),
                min(max(y, safe.y0 + 1), safe.y1 - 1)) for x, y in pts]
        els.append(Path(catmull_closed(pts), box_of(pts), stroke=CARRIER if i % 2 else MID,
                        width=1.1 if i % 2 else 1.6))
    node = (cx, cy)
    els.append(Circle(cx, cy, 3.4, fill=INK))
    return Field("contour", els, node=node, horizon=safe.y0 + safe.h * 0.86)


def _hatch(rng, safe: Box, focus, horizon) -> Field:
    cx, cy = focus or (safe.cx, safe.cy)
    rx, ry = safe.w * 0.34, safe.h * 0.36
    angle = rng.choice([-0.9, -0.6, 0.6, 0.9])
    els: list[El] = []
    count = 13
    for i in range(count):
        off = -ry + 2 * ry * i / (count - 1)
        hit = _ellipse_hits(cx, cy, rx, ry, angle, off)
        if hit:
            els.append(_line(*hit[0], *hit[1], 1.0, MID if i % 3 else CARRIER))
    node = (cx - rx * 0.55, cy + ry * 0.42)
    els.append(Circle(node[0], node[1], 3.8, fill=INK))
    return Field("hatch", els, node=node, horizon=safe.y0 + safe.h * 0.9)


def _stipple(rng, safe: Box, focus, horizon) -> Field:
    cx, cy = focus or (safe.cx, safe.cy)
    rx, ry = safe.w * 0.4, safe.h * 0.42
    els: list[El] = []
    for _ in range(78):
        a = rng.uniform(0, math.tau)
        r = math.sqrt(rng.random())
        x, y = cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)
        els.append(Circle(x, y, rng.uniform(0.9, 2.2), fill=MID))
    els.append(Circle(cx, cy, 4.2, fill=INK))
    return Field("stipple", els, node=(cx, cy), horizon=safe.y0 + safe.h * 0.88)


def _halftone(rng, safe: Box, focus, horizon) -> Field:
    cx, cy = focus or (safe.cx, safe.cy)
    cols, rows = 14, 9
    els: list[El] = []
    span = max(safe.w, safe.h) * 0.62
    for j in range(rows):
        for i in range(cols):
            x = safe.x0 + safe.w * (i + 0.5) / cols
            y = safe.y0 + safe.h * (j + 0.5) / rows
            d = math.hypot((x - cx) / safe.w, (y - cy) / safe.h) * span
            r = max(0.7, 4.6 * (1 - min(d / span, 1.0)))
            els.append(Circle(x, y, r, fill=INK if i % 2 == j % 2 else MID))
    return Field("halftone", els, node=(cx, cy), horizon=safe.y0 + safe.h * 0.9)


def _flow(rng, safe: Box, focus, horizon) -> Field:
    els: list[El] = []
    lines = rng.randint(8, 10)
    for i in range(lines):
        base = safe.y0 + safe.h * (i + 0.5) / lines
        amp = safe.h * rng.uniform(0.04, 0.1)
        k = rng.uniform(1.2, 2.4)
        ph = rng.uniform(0, math.tau)
        pts = []
        for step in range(41):
            t = step / 40
            x = safe.x0 + safe.w * t
            drift = (t - 0.5) * safe.h * 0.10
            y = base + amp * math.sin(t * math.tau * k + ph) + drift
            pts.append(_safe_point(safe, x, y, 1.0))
        els.append(Path(polyline(pts), box_of(pts),
                        stroke=MID if i % 3 == 0 else CARRIER,
                        width=1.5 if i % 3 == 0 else 1.0))
    node = focus or (safe.x0 + safe.w * 0.5, safe.y0 + safe.h * 0.5)
    els.append(Circle(node[0], node[1], 3.8, fill=INK))
    return Field("flow", els, node=node, horizon=safe.y0 + safe.h * 0.84)


def _phyllotaxis(rng, safe: Box, focus, horizon) -> Field:
    cx, cy = focus or (safe.cx, safe.cy)
    count = 120
    max_r = min(safe.w, safe.h) * 0.46
    els: list[El] = []
    for i in range(count):
        a = i * math.pi * (3 - math.sqrt(5))
        r = max_r * math.sqrt(i / count)
        els.append(Circle(cx + r * math.cos(a), cy + r * math.sin(a),
                          max(0.7, 2.4 * (1 - i / count)), fill=MID))
    return Field("phyllotaxis", els, node=(cx, cy), horizon=safe.y0 + safe.h * 0.9)


def _nodes(rng, safe: Box, focus, horizon) -> Field:
    count = rng.randint(8, 10)
    pts = [focus or (safe.x0 + safe.w * 0.62, safe.y0 + safe.h * 0.44)]
    for _ in range(count):
        pts.append((rng.uniform(safe.x0 + safe.w * 0.06, safe.x1 - safe.w * 0.06),
                    rng.uniform(safe.y0 + safe.h * 0.08, safe.y1 - safe.h * 0.08)))
    els: list[El] = []
    for i, p in enumerate(pts):
        near = sorted(
            ((math.hypot(p[0] - q[0], p[1] - q[1]), j) for j, q in enumerate(pts) if j != i)
        )[:2]
        for d, j in near:
            if d < safe.w * 0.5:
                els.append(_line(p[0], p[1], pts[j][0], pts[j][1], 1.0, CARRIER))
    for i, p in enumerate(pts):
        els.append(Circle(p[0], p[1], 6.0 if i == 0 else rng.uniform(2.2, 4.2),
                          fill=INK if i == 0 else MID,
                          stroke=None))
    return Field("nodes", els, node=pts[0], horizon=safe.y0 + safe.h * 0.86)


def _rays(rng, safe: Box, focus, horizon) -> Field:
    cx, cy = focus or (safe.cx, safe.cy)
    els: list[El] = []
    count = rng.randint(14, 18)
    for i in range(count):
        a = i / count * math.tau + rng.uniform(-0.02, 0.02)
        # Ray from near the focus to the safe boundary.
        far = safe.w + safe.h
        ex, ey = cx + math.cos(a) * far, cy + math.sin(a) * far
        # Clip to the safe box along the segment.
        t_hi = 1.0
        dx, dy = ex - cx, ey - cy
        for lo, hi, d, base in ((safe.x0, safe.x1, dx, cx), (safe.y0, safe.y1, dy, cy)):
            if abs(d) > 1e-6:
                t = (hi - base) / d if d > 0 else (lo - base) / d
                t_hi = min(t_hi, t)
        ex, ey = cx + dx * t_hi, cy + dy * t_hi
        els.append(_line(cx + math.cos(a) * safe.w * 0.06,
                         cy + math.sin(a) * safe.h * 0.06, ex, ey,
                         1.0, MID if i % 4 == 0 else CARRIER))
    els.append(Circle(cx, cy, 4.6, fill=INK))
    return Field("rays", els, node=(cx, cy), horizon=safe.y0 + safe.h * 0.9)


def _waves(rng, safe: Box, focus, horizon) -> Field:
    els: list[El] = []
    count = rng.randint(4, 6)
    for i in range(count):
        base = safe.y0 + safe.h * (i + 0.5) / count
        amp = safe.h * rng.uniform(0.035, 0.075)
        k = rng.uniform(1.0, 2.2)
        pts = []
        for step in range(49):
            t = step / 48
            pts.append(_safe_point(
                safe,
                safe.x0 + safe.w * t,
                base + amp * math.sin(t * math.tau * k + i),
                1.0,
            ))
        els.append(Path(polyline(pts), box_of(pts),
                        stroke=MID if i == count // 2 else CARRIER,
                        width=2.0 if i == count // 2 else 1.1))
    node = focus or (safe.x0 + safe.w * 0.5, safe.y0 + safe.h * 0.5)
    els.append(Circle(node[0], node[1], 3.6, fill=INK))
    return Field("waves", els, node=node, horizon=safe.y0 + safe.h * 0.86)


def _dot_matrix(rng, safe: Box, focus, horizon) -> Field:
    cols, rows = 11, 7
    els: list[El] = []
    for j in range(rows):
        for i in range(cols):
            if (i + j) % 9 == 0:
                continue
            els.append(Circle(
                safe.x0 + safe.w * (i + 0.5) / cols,
                safe.y0 + safe.h * (j + 0.5) / rows,
                2.2, fill=MID if (i + j) % 2 else CARRIER,
            ))
    node = focus or (safe.cx, safe.cy)
    els.append(Circle(node[0], node[1], 5.0, fill=INK))
    return Field("dot-matrix", els, node=node, horizon=safe.y0 + safe.h * 0.9)


FIELD_BUILDERS = {
    "grid": _grid,
    "bands": _bands,
    "contour": _contour,
    "hatch": _hatch,
    "stipple": _stipple,
    "halftone": _halftone,
    "flow": _flow,
    "phyllotaxis": _phyllotaxis,
    "nodes": _nodes,
    "rays": _rays,
    "waves": _waves,
    "dot-matrix": _dot_matrix,
}

FIELD_NAMES = tuple(FIELD_BUILDERS)


def build_field(
    name: str,
    rng: random.Random,
    safe: Box,
    focus: tuple[float, float] | None = None,
    horizon: float | None = None,
) -> Field:
    builder = FIELD_BUILDERS.get(name) or _grid
    return builder(rng, safe, focus, horizon)
