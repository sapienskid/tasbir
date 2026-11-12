"""Subjects — figurative but abstract, parameterized, never frozen paths.

Every subject is a small relational drawing (seed → stem → leaves, vessel →
sprig, curve → boundary) built from continuous seeded parameters, so two posts
with the same subject are still different drawings. Each returns local
geometry plus the anchors the composer needs: ``base`` (where it stands),
``focus`` (its visual mass) and ``knockout`` (the shape used when the relation
occludes the field behind it).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .geom import (
    ACCENT,
    CARRIER,
    INK,
    MID,
    PAPER,
    Box,
    Circle,
    El,
    Path,
    box_of,
    catmull_closed,
    polyline,
    quadratic,
)

__all__ = ["SUBJECT_NAMES", "Subject", "build_subject"]


@dataclass
class Subject:
    name: str
    els: list[El]
    bounds: Box
    base: tuple[float, float]
    focus: tuple[float, float]
    knockout: Box = field(default_factory=lambda: Box(0, 0, 0, 0))


def _line(x0, y0, x1, y1, width=2.6, role=INK, wobble=0.0, rng=None, steps=3) -> Path:
    pts = [(x0, y0), (x1, y1)]
    if wobble and rng is not None and steps > 1:
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        pts = []
        for i in range(steps + 1):
            t = i / steps
            off = (rng.uniform(-1, 1) * wobble) if 0 < i < steps else 0.0
            pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    return Path(polyline(pts), box_of(pts), stroke=role, width=width)


def _quad(p0, c, p1, width=2.8, role=INK) -> Path:
    return Path(quadratic(p0, c, p1), box_of([p0, c, p1]), stroke=role, width=width)


def _ellipse(cx, cy, rx, ry, rot=0.0, fill=None, stroke=INK, width=2.4,
             rng=None, wobble=1.0) -> Path:
    n = 26
    pts = []
    for i in range(n):
        a = i / n * math.tau
        r = 1.0
        if wobble and rng is not None:
            r += 0.035 * wobble * math.sin(3 * a + rng.uniform(0, 0.3))
        x, y = rx * r * math.cos(a), ry * r * math.sin(a)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return Path(catmull_closed(pts), box_of(pts), fill=fill, stroke=stroke, width=width)


def _leaf(x, y, length, angle, width, rng, fill=INK) -> Path:
    """A tapered leaf attached at (x,y), growing along ``angle``."""
    ux, uy = math.cos(angle), math.sin(angle)
    nx, ny = -uy, ux
    tip = (x + ux * length, y + uy * length)
    c1 = (x + ux * length * 0.45 + nx * width, y + uy * length * 0.45 + ny * width)
    c2 = (x + ux * length * 0.45 - nx * width, y + uy * length * 0.45 - ny * width)
    d = (
        f"M {x:.1f} {y:.1f} Q {c1[0]:.1f} {c1[1]:.1f} {tip[0]:.1f} {tip[1]:.1f} "
        f"Q {c2[0]:.1f} {c2[1]:.1f} {x:.1f} {y:.1f} Z"
    )
    return Path(d, box_of([(x, y), tip, c1, c2]), fill=fill, stroke=INK, width=1.4)


def _seed(rng) -> Subject:
    root = (50 + rng.uniform(-3, 3), 84)
    tip = (50 + rng.uniform(-10, 10), 14 + rng.uniform(-3, 3))
    ctrl = (34 + rng.uniform(-6, 6), 48)
    stem = _quad(root, ctrl, tip, 3.0)
    els: list[El] = [stem]
    leaves = rng.randint(2, 4)
    for i in range(leaves):
        t = 0.30 + 0.42 * i / max(leaves - 1, 1)
        x = root[0] + (tip[0] - root[0]) * t + (ctrl[0] - root[0]) * 0.6 * t * (1 - t)
        y = root[1] + (tip[1] - root[1]) * t
        side = 1 if i % 2 == 0 else -1
        els.append(_leaf(x, y, 20 + rng.uniform(-4, 5), side * (0.5 + rng.uniform(-0.2, 0.3)),
                         7 + rng.uniform(-2, 2), rng, fill=CARRIER))
    # The seed itself, split open at the root.
    els.append(_ellipse(root[0], root[1] + 9, 13, 8, rng.uniform(-0.2, 0.2),
                        fill=ACCENT, rng=rng, width=2.2))
    els.append(_line(root[0], root[1] + 4, root[0], root[1], 2.0))
    els.append(_line(root[0] - 12, root[1] + 18, root[0] + 12, root[1] + 18, 1.2, CARRIER))
    b = box_of([(root[0] - 16, root[1] + 18), (tip[0], tip[1]), (root[0] + 26, root[1] + 2)])
    return Subject("seed", els, b, base=(root[0], root[1] + 18),
                   focus=(root[0], 46), knockout=Box(root[0] - 22, 30, root[0] + 22, 96))


def _vessel(rng) -> Subject:
    cx = 50 + rng.uniform(-3, 3)
    top, bottom = 52, 88
    half_top, half_bottom = 26, 15
    bowl = (
        f"M {cx - half_top:.1f} {top:.1f} "
        f"C {cx - half_top:.1f} {top + 22:.1f} {cx - half_bottom:.1f} {bottom - 4:.1f} "
        f"{cx:.1f} {bottom:.1f} "
        f"C {cx + half_bottom:.1f} {bottom - 4:.1f} {cx + half_top:.1f} {top + 22:.1f} "
        f"{cx + half_top:.1f} {top:.1f}"
    )
    els: list[El] = [
        Path(bowl, Box(cx - half_top, top, cx + half_top, bottom),
             stroke=INK, width=3.0),
    ]
    # Rim, drawn slightly open so the vessel reads as a container.
    els.append(_ellipse(cx, top, half_top, 5.5, fill=PAPER, width=2.6))
    # Sprig growing out of the vessel.
    top_y = 20 + rng.uniform(-3, 4)
    els.append(_quad((cx, top - 2), (cx - 9, 38), (cx + rng.uniform(-5, 5), top_y), 2.6))
    side = 1 if rng.random() < 0.5 else -1
    els.append(_leaf(cx - 4, 42, 21, -0.42 + side * 0.18, 7, rng, fill=CARRIER))
    els.append(_leaf(cx + 2, 33, 17, -1.95 - side * 0.18, 6, rng, fill=PAPER))
    # Fluid level.
    level = top + 18 + rng.uniform(0, 10)
    half = half_top - (level - top) * (half_top - half_bottom) / (bottom - top) - 3
    els.append(_line(cx - half, level, cx + half, level, 1.6, MID))
    return Subject("vessel", els, Box(cx - half_top, top_y - 4, cx + half_top, bottom),
                   base=(cx, bottom), focus=(cx, 44),
                   knockout=Box(cx - half_top, top, cx + half_top, bottom))


# Authored palm — still parameterized by the object it carries.
_PALM = (
    "M 94 212 L 130 176 C 142 166 147 153 154 143 "
    "C 159 136 166 140 163 148 L 156 164 "
    "C 176 153 197 147 221 147 L 272 147 "
    "C 285 147 284 157 273 158 L 228 162 "
    "L 280 161 C 292 162 290 172 279 173 L 231 177 "
    "L 269 178 C 280 180 276 189 265 189 L 224 191 "
    "L 247 194 C 257 198 250 205 239 204 L 193 200 "
    "C 173 200 159 204 147 217 Z"
)


def _hand(rng) -> Subject:
    elbow = rng.uniform(-6, 6)
    els: list[El] = [Path(_PALM, Box(94, 136, 292, 217), fill=PAPER, stroke=INK, width=2.6)]
    # The carried object: disc, seed or leaf — the only filled accent.
    kind = rng.choice(("disc", "seed", "leaf"))
    ox, oy = 202 + elbow, 108
    if kind == "disc":
        els.append(_ellipse(ox, oy, 22, 22, 0, fill=ACCENT, width=2.2))
        els.append(_ellipse(ox, oy, 10, 10, 0, fill=PAPER, stroke=None))
    elif kind == "seed":
        els.append(_ellipse(ox, oy, 14, 21, rng.uniform(-0.3, 0.3),
                            fill=ACCENT, width=2.2))
        els.append(_line(ox, oy - 12, ox, oy + 12, 1.3))
    else:
        els.append(_leaf(ox - 10, oy + 16, 34, -1.15, 10, rng, fill=ACCENT))
    els.append(_quad((150, 178), (172, 168), (196, 172), 1.2, MID))
    return Subject("hand", els, Box(94, 73, 292, 217), base=(200, 217),
                   focus=(ox, oy), knockout=Box(70, 60, 310, 230))


def _book(rng) -> Subject:
    els: list[El] = [
        Path(
            "M 200 184 C 174 162 145 161 109 164 L 109 72 "
            "C 146 69 178 81 200 99 C 224 79 256 69 291 72 L 291 164 "
            "C 254 162 225 162 200 184 Z M 200 99 L 200 184",
            Box(109, 69, 291, 184),
            fill=PAPER,
            stroke=INK,
            width=2.6,
        )
    ]
    pages = rng.randint(2, 4)
    for i in range(pages):
        y = 104 + i * rng.uniform(11, 15)
        els.append(_quad((124, y), (158, y - 2), (183, y + 14), 1.2, MID))
        els.append(_quad((217, y + 14), (249, y - 2), (277, y), 1.2, MID))
    if rng.random() < 0.6:
        x = rng.uniform(150, 250)
        els.append(_line(x, 78, x, 58, 3.0, ACCENT))
    return Subject("book", els, Box(109, 54, 291, 184), base=(200, 184),
                   focus=(200, 118), knockout=Box(96, 52, 304, 196))


def _arch(rng) -> Subject:
    els: list[El] = []
    outer = 34 + rng.uniform(-2, 4)
    for i in range(3):
        w = outer * (1 - i * 0.26)
        top = 12 + i * 9 + rng.uniform(-2, 2)
        pts = [
            (50 - w, 90),
            (50 - w, top + 18),
            (50 - w * 0.55, top),
            (50 + w * 0.55, top),
            (50 + w, top + 18),
            (50 + w, 90),
        ]
        d = (
            f"M {pts[0][0]:.1f} 90 L {pts[1][0]:.1f} {pts[1][1]:.1f} "
            f"Q {pts[2][0]:.1f} {pts[2][1]:.1f} {pts[3][0]:.1f} {pts[3][1]:.1f} "
            f"Q {pts[4][0]:.1f} {pts[4][1]:.1f} {pts[5][0]:.1f} {pts[5][1]:.1f} "
            f"L {pts[5][0]:.1f} 90"
        )
        els.append(Path(d, box_of(pts), stroke=INK, width=2.8 if i == 0 else 1.6))
    els.append(_line(10, 90, 90, 90, 2.4, INK))
    els.append(Circle(50, 56, 8, fill=ACCENT))
    return Subject("arch", els, Box(10, 10, 90, 92), base=(50, 90),
                   focus=(50, 54), knockout=Box(18, 14, 82, 90))


def _ladder(rng) -> Subject:
    lean = rng.uniform(-6, 2)
    els: list[El] = [
        _line(38 + lean, 90, 34, 12, 2.8),
        _line(64 + lean, 90, 58, 12, 2.8),
    ]
    rungs = rng.randint(5, 7)
    gap = rng.randrange(1, rungs - 1)
    for i in range(rungs):
        t = (i + 0.6) / (rungs + 0.2)
        x0 = 38 + lean + (34 - 38 - lean) * t
        x1 = 64 + lean + (58 - 64 - lean) * t
        y = 90 + (12 - 90) * t
        if i == gap:
            els.append(_line(x0 + 5, y, x1 - 5, y, 2.2, MID))
        else:
            els.append(_line(x0, y, x1, y, 2.4))
    els.append(Circle(62 + lean, 8, 5, fill=ACCENT))
    return Subject("ladder", els, Box(28, 3, 72, 92), base=(52 + lean, 90),
                   focus=(50, 46), knockout=Box(24, 4, 74, 92))


def _bridge(rng) -> Subject:
    els: list[El] = [
        _line(22, 90, 22, 42, 3.0),
        _line(78, 90, 78, 42, 3.0),
        _quad((10, 54), (50, 22 + rng.uniform(-3, 4)), (90, 54), 3.2),
        _line(10, 90, 90, 90, 1.6, MID),
    ]
    for i in range(5):
        t = (i + 0.8) / 5.6
        x = 10 + 80 * t
        y = 54 - (34 * 4 * t * (1 - t))
        els.append(_line(x, y + 2, x, 88, 1.0, CARRIER))
    els.append(Circle(30 + rng.uniform(0, 40), 44, 4.2, fill=ACCENT))
    return Subject("bridge", els, Box(10, 20, 90, 92), base=(50, 90),
                   focus=(50, 50), knockout=Box(8, 24, 92, 92))


def _orbit(rng) -> Subject:
    cx, cy = 50, 50
    els: list[El] = [Circle(cx, cy, 9.5, fill=ACCENT)]
    for i, (rx, ry, rot) in enumerate(((36, 12, -0.35), (28, 9, 0.6))):
        els.append(_ellipse(cx, cy, rx, ry, rot, stroke=INK if i == 0 else MID,
                            width=2.2 if i == 0 else 1.2))
        a = rng.uniform(0, math.tau)
        x = rx * math.cos(a)
        y = ry * math.sin(a)
        els.append(Circle(cx + x * math.cos(rot) - y * math.sin(rot),
                          cy + x * math.sin(rot) + y * math.cos(rot),
                          rng.uniform(2.4, 4.4), fill=INK))
    return Subject("orbit", els, Box(12, 34, 88, 66), base=(50, 66),
                   focus=(cx, cy), knockout=Box(26, 30, 74, 70))


def _curve_boundary(rng) -> Subject:
    limit = 26 + rng.uniform(-4, 6)
    els: list[El] = [
        _line(78, 12, 78, 90, 3.2),
    ]
    pts = []
    k = rng.uniform(2.6, 3.6)
    for i in range(31):
        t = i / 30
        x = 12 + 64 * t
        y = 90 - (90 - limit) * (1 - math.exp(-k * t))
        pts.append((x, y))
    els.append(Path(polyline(pts), box_of(pts), stroke=INK, width=3.0))
    for i in range(6):
        y = 20 + i * 12
        els.append(_line(78, y, 83, y, 1.4, MID))
    els.append(Circle(78, limit, 4.6, fill=ACCENT))
    els.append(_line(12, 90, 86, 90, 1.4, CARRIER))
    return Subject("curve-boundary", els, Box(10, 14, 86, 92), base=(50, 90),
                   focus=(70, limit), knockout=Box(8, 14, 88, 92))


def _network(rng) -> Subject:
    pts = [(50, 44)]
    for _ in range(7):
        pts.append((rng.uniform(14, 86), rng.uniform(14, 86)))
    els: list[El] = []
    for i, p in enumerate(pts):
        near = sorted(((math.hypot(p[0] - q[0], p[1] - q[1]), j)
                       for j, q in enumerate(pts) if j != i))[:2]
        for _, j in near:
            els.append(_line(p[0], p[1], pts[j][0], pts[j][1], 1.2,
                             ACCENT if i == 0 and j == 1 else CARRIER))
    for i, p in enumerate(pts):
        els.append(Circle(p[0], p[1], 6.2 if i == 0 else rng.uniform(2.6, 4.2),
                          fill=INK if i == 0 else MID))
    return Subject("network", els, Box(8, 8, 92, 92), base=(50, 92),
                   focus=pts[0], knockout=Box(10, 10, 90, 90))


def _wave_train(rng) -> Subject:
    els: list[El] = []
    count = 4
    break_at = rng.randrange(0, count)
    for i in range(count):
        base = 30 + i * 13
        amp = 4 + rng.uniform(0, 3)
        pts = []
        for step in range(49):
            t = step / 48
            if i == break_at and 0.46 < t < 0.56:
                continue
            pts.append((10 + 80 * t, base + amp * math.sin(t * math.tau * 1.6 + i * 0.8)))
        els.append(Path(polyline(pts), box_of(pts),
                        stroke=INK if i == break_at else MID,
                        width=2.8 if i == break_at else 1.4))
    els.append(Circle(82, rng.uniform(24, 30), 3.6, fill=ACCENT))
    return Subject("wave-train", els, Box(10, 22, 84, 74), base=(50, 74),
                   focus=(50, 48), knockout=Box(8, 22, 86, 76))


def _prism(rng) -> Subject:
    tri = [(46, 34), (24, 82), (68, 82)]
    d = (
        f"M {tri[0][0]} {tri[0][1]} L {tri[1][0]} {tri[1][1]} "
        f"L {tri[2][0]} {tri[2][1]} Z"
    )
    els: list[El] = [
        Path(d, box_of(tri), fill=PAPER, stroke=INK, width=2.8),
        _line(8, 58, 42, 58, 3.0),
    ]
    spread = rng.uniform(0.34, 0.5)
    for i in range(4):
        a = -spread + 2 * spread * i / 3
        els.append(_line(52, 58, 52 + 34 * math.cos(a), 58 + 34 * math.sin(a),
                         2.0 if i == 2 else 1.2, INK if i == 2 else MID))
    return Subject("prism", els, Box(8, 32, 90, 84), base=(46, 82),
                   focus=(46, 58), knockout=Box(6, 32, 92, 86))


def _loom(rng) -> Subject:
    els: list[El] = []
    for i in range(6):
        x = 20 + i * 12
        els.append(_line(x, 14, x, 88, 1.6, CARRIER))
    for j in range(5):
        y = 22 + j * 14
        els.append(_line(16, y, 84, y, 1.4, CARRIER))
    y = 22 + rng.randrange(1, 4) * 14
    for i in range(3):
        x = 20 + (i + 1) * 12
        els.append(_line(x, y - 3, x + 12, y - 3, 6.0, ACCENT))
        els.append(_line(x, y + 3, x + 12, y + 3, 1.6, INK))
    return Subject("loom", els, Box(16, 12, 84, 90), base=(50, 90),
                   focus=(50, y), knockout=Box(16, y - 12, 84, y + 12))


def _compass(rng) -> Subject:
    cx, cy = 50, 48
    els: list[El] = [
        _ellipse(cx, cy, 32, 32, 0, stroke=INK, width=2.8),
        _ellipse(cx, cy, 25, 25, 0, stroke=MID, width=1.2),
    ]
    for i in range(12):
        a = i / 12 * math.tau
        r0, r1 = (25, 30) if i % 3 == 0 else (27, 30)
        els.append(_line(cx + r0 * math.cos(a), cy + r0 * math.sin(a),
                         cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                         1.4, INK))
    a = rng.uniform(-2.6, -0.5)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    up = [(cx + ux * 22, cy + uy * 22), (cx + nx * 4, cy + ny * 4),
          (cx - nx * 4, cy - ny * 4)]
    dn = [(cx - ux * 14, cy - uy * 14), (cx + nx * 3, cy + ny * 3),
          (cx - nx * 3, cy - ny * 3)]
    els.append(Path(polyline(up + [up[0]]), box_of(up), fill=INK,
                    stroke=INK, width=1.0))
    els.append(Path(polyline(dn + [dn[0]]), box_of(dn), fill=CARRIER,
                    stroke=MID, width=1.0))
    els.append(Circle(cx, cy, 2.6, fill=PAPER, stroke=INK, width=1.2))
    return Subject("compass", els, Box(16, 14, 84, 82), base=(50, 82),
                   focus=(cx, cy), knockout=Box(16, 14, 84, 82))


def _magnifier(rng) -> Subject:
    lx, ly, lr = 42, 40, 23
    els: list[El] = [
        _ellipse(lx, ly, lr, lr, 0, fill=PAPER, stroke=INK, width=3.0),
        _line(lx + lr * 0.66, ly + lr * 0.66, 78, 80, 5.0, INK),
    ]
    for i in range(4):
        y = ly - 12 + i * 8
        half = math.sqrt(max(lr * lr - (y - ly) ** 2, 1)) * 0.72
        els.append(_line(lx - half, y, lx + half, y, 2.0, ACCENT if i == 1 else MID))
    els.append(_line(12, 84, 90, 84, 1.4, CARRIER))
    return Subject("magnifier", els, Box(12, 16, 82, 86), base=(42, 84),
                   focus=(lx, ly), knockout=Box(14, 14, 80, 72))


def _tunnel(rng) -> Subject:
    vx, vy = 56 + rng.uniform(-5, 5), 46 + rng.uniform(-4, 4)
    els: list[El] = []
    for i in range(5):
        t = i / 4
        x0 = 16 + (vx - 16) * t * 0.8
        x1 = 86 + (vx - 86) * t * 0.8
        y0 = 18 + (vy - 18) * t * 0.8
        y1 = 84 + (vy - 84) * t * 0.8
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        els.append(Path(polyline(pts), box_of(pts),
                        stroke=INK if i % 2 == 0 else MID,
                        width=2.2 if i % 2 == 0 else 1.2))
    els.append(Circle(vx, vy, 3.4, fill=ACCENT))
    return Subject("tunnel", els, Box(16, 18, 86, 86), base=(50, 86),
                   focus=(vx, vy), knockout=Box(26, 30, 80, 74))


def _stack(rng) -> Subject:
    els: list[El] = []
    count = 5
    for i in range(count):
        y = 82 - i * 14
        w = 30 - i * 2.4 + rng.uniform(-2, 2)
        dx = (i % 2) * 7 + rng.uniform(-2, 2)
        if i == rng.randrange(1, count - 1):
            dx += 12
        pts = [(50 - w + dx, y), (50 + w + dx, y),
               (50 + w + dx, y - 7), (50 - w + dx, y - 7), (50 - w + dx, y)]
        els.append(Path(polyline(pts), box_of(pts),
                        fill=CARRIER if i % 2 else None,
                        stroke=INK, width=2.2))
    els.append(Circle(78, 14, 4.2, fill=ACCENT))
    return Subject("stack", els, Box(14, 10, 84, 84), base=(50, 84),
                   focus=(58, 44), knockout=Box(16, 10, 82, 84))


BUILDERS = {
    "seed": _seed,
    "vessel": _vessel,
    "hand": _hand,
    "book": _book,
    "arch": _arch,
    "ladder": _ladder,
    "bridge": _bridge,
    "orbit": _orbit,
    "curve-boundary": _curve_boundary,
    "network": _network,
    "wave-train": _wave_train,
    "prism": _prism,
    "loom": _loom,
    "compass": _compass,
    "magnifier": _magnifier,
    "tunnel": _tunnel,
    "stack": _stack,
}

SUBJECT_NAMES = tuple(BUILDERS) + ("portrait",)


def build_subject(name: str, rng: random.Random) -> Subject:
    builder = BUILDERS.get(name) or _seed
    return builder(rng)
