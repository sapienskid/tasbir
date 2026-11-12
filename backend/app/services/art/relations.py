"""Relations — how a subject is composed against its field.

The relation is the difference between two genuinely different compositions.
"Seed cradled by a contour set" and "seed emerging from a hatch field" are not
the same drawing with a swapped background: the subject's scale, anchor and
paint order change, and the field is built around the subject.
"""

from __future__ import annotations

import math

from .geom import (
    CARRIER,
    INK,
    PAPER,
    Box,
    Circle,
    El,
    Path,
    polyline,
)

__all__ = ["RELATION_NAMES", "fit_into", "relation_extras", "subject_target"]


def subject_target(framing: str, safe: Box, aspect: str) -> Box:
    """The region the subject is fitted into, before its own bounds are known."""
    if framing == "left-third":
        w, h = safe.w * 0.52, safe.h * 0.66
        cx = safe.x0 + safe.w * 0.30
        cy = safe.y0 + safe.h * 0.46
    elif framing == "right-third":
        w, h = safe.w * 0.52, safe.h * 0.66
        cx = safe.x0 + safe.w * 0.70
        cy = safe.y0 + safe.h * 0.46
    elif framing == "bottom-anchored":
        w, h = safe.w * 0.60, safe.h * 0.66
        cx = safe.cx
        cy = safe.y1 - h / 2
    elif framing == "bleed":
        w, h = safe.w * 0.82, safe.h * 0.86
        cx = safe.cx
        cy = safe.y1 - h / 2
    else:  # centered
        w, h = safe.w * 0.58, safe.h * 0.64
        cx = safe.cx
        cy = safe.y0 + safe.h * (0.44 if aspect != "portrait" else 0.46)
    return Box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def fit_into(bounds: Box, region: Box) -> tuple[float, float, float]:
    """Uniform scale + translate that fits ``bounds`` centred in ``region``."""
    if bounds.w <= 0 or bounds.h <= 0:
        return 1.0, region.x0, region.y0
    s = min(region.w / bounds.w, region.h / bounds.h)
    nw, nh = bounds.w * s, bounds.h * s
    tx = region.x0 + (region.w - nw) / 2 - bounds.x0 * s
    ty = region.y0 + (region.h - nh) / 2 - bounds.y0 * s
    return s, tx, ty


def _rule(x0, y0, x1, y1, width=1.4, role=INK) -> Path:
    pts = [(x0, y0), (x1, y1)]
    from .geom import box_of

    return Path(polyline(pts), box_of(pts), stroke=role, width=width)


def relation_extras(
    relation: str,
    subject_box: Box,
    safe: Box,
    focus: tuple[float, float],
    base: tuple[float, float],
    divider_x: float | None = None,
) -> list[El]:
    """Rules, dividers, horizons and knock-outs the relation adds."""
    els: list[El] = []
    if relation == "occlude":
        # A paper-coloured knock-out behind the subject clears the field.
        rx = max(subject_box.w * 0.58, 18)
        ry = max(subject_box.h * 0.58, 18)
        els.append(
            Path(
                _ellipse_path(subject_box.cx, subject_box.cy, rx, ry),
                Box(subject_box.cx - rx, subject_box.cy - ry,
                    subject_box.cx + rx, subject_box.cy + ry),
                fill=PAPER,
            )
        )
    elif relation == "cradle":
        rx = max(subject_box.w * 0.56, 26)
        y = base[1] + max(safe.h * 0.035, 6)
        pts = []
        for i in range(25):
            t = i / 24
            pts.append((subject_box.cx - rx + 2 * rx * t,
                        y - math.sin(t * math.pi) * safe.h * 0.055))
        els.append(Path(polyline(pts), _box(pts), stroke=INK, width=2.4))
        els.append(_rule(subject_box.cx - rx * 0.62, y + 8,
                         subject_box.cx + rx * 0.62, y + 8, 1.0, CARRIER))
    elif relation == "emerge-from":
        y = base[1]
        els.append(_rule(safe.x0, y, safe.x1, y, 2.2, INK))
        els.append(_rule(safe.x0, y + max(6, safe.h * 0.03),
                         safe.x1, y + max(6, safe.h * 0.03), 1.0, CARRIER))
    elif relation == "frame":
        pad = max(safe.h * 0.05, 8)
        top = max(subject_box.y0 - pad, safe.y0)
        bottom = min(subject_box.y1 + pad, safe.y1)
        x0 = max(subject_box.x0 - safe.w * 0.06, safe.x0)
        x1 = min(subject_box.x1 + safe.w * 0.06, safe.x1)
        els.append(_rule(x0, top, x1, top, 1.6, INK))
        els.append(_rule(x0, bottom, x1, bottom, 1.6, INK))
        els.append(_rule(x0, top, x0, bottom, 1.0, CARRIER))
        els.append(_rule(x1, top, x1, bottom, 1.0, CARRIER))
    elif relation == "converge-to":
        els.append(Circle(focus[0], focus[1], 7.5, fill=PAPER, stroke=INK, width=1.4))
    elif relation == "split":
        x = divider_x if divider_x is not None else safe.cx
        els.append(_rule(x, safe.y0, x, safe.y1, 1.6, INK))
    elif relation == "intersect-at-node":
        els.append(Circle(focus[0], focus[1], 5.0, fill=PAPER, stroke=INK, width=1.6))
        els.append(Circle(focus[0], focus[1], 1.8, fill=INK))
    return els


def _box(pts: list[tuple[float, float]]) -> Box:
    from .geom import box_of

    return box_of(pts)


def _ellipse_path(cx, cy, rx, ry) -> str:
    n = 30
    pts = []
    for i in range(n):
        a = i / n * math.tau
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    from .geom import catmull_closed

    return catmull_closed(pts)


RELATION_NAMES = (
    "occlude",
    "intersect-at-node",
    "cradle",
    "emerge-from",
    "converge-to",
    "frame",
    "split",
    "sequence",
    "scale-asymmetry",
)
