"""Procedural Anthropic-style editorial illustration generator.

Recreates the three-layer Anthropic blog illustration system as a small,
dependency-free SVG generator:

  1. the card's ground plays the "accent field" (edge to edge),
  2. an irregular organic carrier blob (never a perfect circle),
  3. bold near-foreground gestural linework — naive, wobbled, asymmetrical,
     drawn like ink in a single breath.

The brand stays strictly monochrome: only ``var(--color-*)`` token names are
used (never raw hex), so the verifier's raw-hex check passes and the art
adapts to both grounds. Every composition is a pure function of its seed —
deterministic per post, visually random across seeds.

The generator is also exposed as an LLM **tool** (function calling): an
"illustration director" prompt asks the model to pick an abstract theme for
the post and the tool renders it. ``illustration_via_tool`` orchestrates
LLM → tool → deterministic fallback.

The returned fragment is a self-contained ``<svg viewBox="0 0 400 240">``
that templates render inside a slot (e.g. the right column of
``landscape-ad-card``) and the CSS/``:root`` variables of the host document
resolve.
"""

from __future__ import annotations

import logging
import math
import random

log = logging.getLogger(__name__)

__all__ = [
    "generate_illustration_svg",
    "ILLUSTRATION_TOOL",
    "illustration_via_tool",
    "ARCHETYPES",
]

DEFAULT_VIEW_BOX = "0 0 400 240"

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


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _fmt(n: float) -> str:
    return f"{n:.1f}"


def _catmull_closed(points: list[tuple[float, float]]) -> str:
    """Closed Catmull-Rom spline through points → smooth organic path."""
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


def _blob_path(cx, cy, rx, ry, rng: random.Random, n: int = 18) -> str:
    """Organic closed blob: an ellipse whose radius breathes with a few sines."""
    harmonics = 3
    amps = [rng.uniform(0.04, 0.14) for _ in range(harmonics)]
    freqs = [rng.randint(2, 5) for _ in range(harmonics)]
    phases = [rng.uniform(0, math.tau) for _ in range(harmonics)]
    pts = []
    for i in range(n):
        a = i / n * math.tau
        rad = 1.0 + sum(amps[j] * math.sin(freqs[j] * a + phases[j]) for j in range(harmonics))
        pts.append((cx + rx * rad * math.cos(a), cy + ry * rad * math.sin(a)))
    return _catmull_closed(pts)


def _wobble_path(x0, y0, x1, y1, rng: random.Random, steps: int = 6, amp: float = 6.0) -> str:
    """A hand-drawn line from A→B with perpendicular wobble and round caps."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    pts = []
    for i in range(steps + 1):
        t = i / steps
        off = (rng.random() - 0.5) * 2 * amp
        pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    d = ["M " + _fmt(pts[0][0]) + " " + _fmt(pts[0][1])]
    for p in pts[1:]:
        d.append(f"L {_fmt(p[0])} {_fmt(p[1])}")
    return " ".join(d)


def _stroke(d: str, color: str, width: float) -> str:
    return (
        f'<path d="{d}" style="fill:none;stroke:{color};stroke-width:{width:.1f};'
        'stroke-linecap:round;stroke-linejoin:round"/>'
    )


def _fill(d: str, color: str) -> str:
    return f'<path d="{d}" style="fill:{color};stroke:none"/>'


def _wobble_circle(cx, cy, r, rng: random.Random, n: int = 22) -> str:
    return _blob_path(cx, cy, r, r, rng, n=n)


# ---------------------------------------------------------------------------
# Naive linework vocab (abstract, monochrome-safe)
# ---------------------------------------------------------------------------


def _sun(cx, cy, r, ink, rng: random.Random) -> list[str]:
    els = [_fill(_wobble_circle(cx, cy, r, rng), ink)]
    rays = rng.randint(6, 9)
    for i in range(rays):
        a = i / rays * math.tau + rng.uniform(-0.1, 0.1)
        x0 = cx + r * 1.25 * math.cos(a)
        y0 = cy + r * 1.25 * math.sin(a)
        x1 = cx + r * (1.9 + rng.uniform(-0.15, 0.15)) * math.cos(a)
        y1 = cy + r * (1.9 + rng.uniform(-0.15, 0.15)) * math.sin(a)
        els.append(_stroke(_wobble_path(x0, y0, x1, y1, rng, steps=2, amp=2.5), ink, rng.uniform(2.6, 3.6)))
    return els


def _spiral(cx, cy, r0, r1, ink, rng: random.Random) -> list[str]:
    turns = rng.uniform(2.2, 3.2)
    steps = 90
    pts = []
    for i in range(steps + 1):
        t = i / steps
        a = t * turns * math.tau
        rad = r0 + (r1 - r0) * t
        j = (rng.random() - 0.5) * 3.0
        pts.append((cx + (rad + j) * math.cos(a), cy + (rad + j) * math.sin(a)))
    d = ["M " + _fmt(pts[0][0]) + " " + _fmt(pts[0][1])]
    for p in pts[1:]:
        d.append(f"L {_fmt(p[0])} {_fmt(p[1])}")
    return [_stroke(" ".join(d), ink, rng.uniform(2.4, 3.4))]


def _waves(x0, y0, x1, y1, ink, rng: random.Random) -> list[str]:
    els = []
    count = rng.randint(2, 4)
    for i in range(count):
        y = y0 + (y1 - y0) * i / (count - 1 if count > 1 else 1)
        peak = rng.uniform(6, 14)
        steps = 7
        pts = []
        for s in range(steps + 1):
            t = s / steps
            px = x0 + (x1 - x0) * t
            py = y + peak * math.sin(t * math.pi * rng.randint(1, 2))
            pts.append((px + (rng.random() - 0.5) * 4, py))
        d = ["M " + _fmt(pts[0][0]) + " " + _fmt(pts[0][1])]
        for p in pts[1:]:
            d.append(f"L {_fmt(p[0])} {_fmt(p[1])}")
        els.append(_stroke(" ".join(d), ink, rng.uniform(2.6, 3.6)))
    return els


def _stem(cx, base_y, tip_y, ink, rng: random.Random) -> list[str]:
    els = [_stroke(_wobble_path(cx, base_y, cx + rng.uniform(-4, 4), tip_y, rng, steps=4, amp=5), ink, rng.uniform(2.8, 3.8))]
    for _ in range(rng.randint(1, 2)):
        side = 1 if rng.random() < 0.5 else -1
        mx = cx + side * rng.uniform(20, 34)
        my = rng.uniform(tip_y + 10, base_y - 10)
        h = rng.uniform(14, 26)
        pts = [(cx, my), ((cx + mx) / 2, my - side * h), (mx, my)]
        d = ["M " + _fmt(pts[0][0]) + " " + _fmt(pts[0][1])]
        d.append(f"Q {_fmt((cx+mx)/2)} {_fmt(my - side*h)} {_fmt(mx)} {_fmt(my)}")
        els.append(_stroke(" ".join(d), ink, rng.uniform(2.4, 3.2)))
    return els


def _rings(cx, cy, r1, r2, ink, mid, rng: random.Random) -> list[str]:
    return [
        _stroke(_wobble_circle(cx, cy, r1, rng), ink, 3.0),
        _stroke(_wobble_circle(cx, cy, r2, rng), mid, 2.4),
    ]


# ---------------------------------------------------------------------------
# Archetypes — each composes a full 400×240 frame
# ---------------------------------------------------------------------------


def _arch_carrier_sun(p: dict, rng: random.Random) -> list[str]:
    els = [_fill(_blob_path(200, 120, 150, 92, rng), p["carrier"])]
    els += _sun(200, 112, 34, p["ink"], rng)
    els.append(_stroke(_wobble_path(150, 196, 260, 196, rng, steps=4, amp=4), p["ink"], 3.0))
    return els


def _arch_carrier_spiral(p: dict, rng: random.Random) -> list[str]:
    els = [_fill(_blob_path(200, 118, 155, 95, rng), p["carrier"])]
    els += _spiral(200, 116, 8, 58, p["ink"], rng)
    for _ in range(rng.randint(2, 3)):
        px = rng.uniform(130, 270)
        py = rng.uniform(40, 200)
        els.append(_fill(_wobble_circle(px, py, rng.uniform(4, 7), rng), p["mid"]))
    return els


def _arch_stacked(p: dict, rng: random.Random) -> list[str]:
    els = []
    for i in range(rng.randint(2, 3)):
        cx = rng.uniform(120, 280)
        cy = rng.uniform(50, 170)
        rx = rng.uniform(46, 74)
        ry = rng.uniform(34, 52)
        els.append(_fill(_blob_path(cx, cy, rx, ry, rng), p["carrier"]))
    els += _stem(rng.choice([150, 200, 250]), 210, 60, p["ink"], rng)
    els.append(_stroke(_wobble_path(120, 214, 280, 214, rng, steps=3, amp=2), p["ink"], 3.2))
    return els


def _arch_wave(p: dict, rng: random.Random) -> list[str]:
    els = [_fill(_blob_path(200, 118, 148, 88, rng), p["carrier"])]
    els += _waves(120, 96, 280, 150, p["ink"], rng)
    els.append(_fill(_wobble_circle(rng.uniform(150, 250), rng.uniform(40, 70), rng.uniform(5, 9), rng), p["ink"]))
    return els


def _arch_burst(p: dict, rng: random.Random) -> list[str]:
    els = [_fill(_blob_path(200, 122, 84, 64, rng), p["carrier"])]
    rays = rng.randint(8, 12)
    for i in range(rays):
        a = i / rays * math.tau + rng.uniform(-0.08, 0.08)
        r0 = rng.uniform(64, 84)
        r1 = rng.uniform(128, 160)
        x0 = 200 + r0 * math.cos(a)
        y0 = 122 + r0 * math.sin(a)
        x1 = 200 + r1 * math.cos(a)
        y1 = 122 + r1 * math.sin(a)
        els.append(_stroke(_wobble_path(x0, y0, x1, y1, rng, steps=2, amp=3), p["ink"], rng.uniform(2.2, 3.2)))
        els.append(_fill(_wobble_circle(x1, y1, rng.uniform(3, 5.5), rng), p["ink"]))
    return els


def _arch_rings(p: dict, rng: random.Random) -> list[str]:
    els = [_fill(_blob_path(200, 120, 152, 92, rng), p["carrier"])]
    els += _rings(200, 118, 40, 66, p["ink"], p["mid"], rng)
    els.append(_stroke(_wobble_path(150, 40, 250, 40, rng, steps=3, amp=3), p["ink"], 2.8))
    return els


ARCHETYPES: dict[str, callable] = {
    "carrier-sun": _arch_carrier_sun,
    "carrier-spiral": _arch_carrier_spiral,
    "stacked": _arch_stacked,
    "wave": _arch_wave,
    "burst": _arch_burst,
    "rings": _arch_rings,
}

# Loose theme → archetype steering. Substring-matched (case-insensitive) so the
# LLM can pick any natural-language theme and the composition still lands on a
# known archetype; unknown themes fall back to the seeded random choice.
THEME_ARCHETYPES: dict[str, str] = {
    "sun": "carrier-sun",
    "light": "carrier-sun",
    "rise": "carrier-sun",
    "spiral": "carrier-spiral",
    "growth": "carrier-spiral",
    "journey": "carrier-spiral",
    "stack": "stacked",
    "layer": "stacked",
    "block": "stacked",
    "build": "stacked",
    "wave": "wave",
    "flow": "wave",
    "stream": "wave",
    "current": "wave",
    "burst": "burst",
    "spark": "burst",
    "radial": "burst",
    "focus": "burst",
    "ring": "rings",
    "orbit": "rings",
    "cycle": "rings",
    "loop": "rings",
}


def _archetype_for(seed: str, theme: str | None) -> str:
    rng = random.Random(seed or "default-illustration")
    if theme:
        low = theme.lower()
        for key, arch in THEME_ARCHETYPES.items():
            if key in low:
                return arch
    name, _ = rng.choice(list(ARCHETYPES.items()))
    return name


def generate_illustration_svg(
    seed: str,
    ground: str = "white",
    theme: str | None = None,
    view_box: str = DEFAULT_VIEW_BOX,
) -> str:
    """Generate an Anthropic-style monochrome SVG fragment from a seed.

    Deterministic per ``seed``; visually random across seeds. An optional
    ``theme`` steers the composition archetype. Uses only ``var(--color-*)``
    token names (no raw hex), so it passes the verifier and adapts to
    white/black grounds. Returns the ``<svg>…</svg>`` fragment.
    """
    rng = random.Random(seed or "default-illustration")
    p = _palette(ground)
    fn = ARCHETYPES[_archetype_for(seed, theme)]
    body = "\n    ".join(fn(p, rng))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240" '
        f'viewBox="{view_box}" preserveAspectRatio="xMidYMid meet" '
        'role="img" aria-hidden="true">\n'
        f"  {body}\n"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# LLM tool integration — the generator as a callable tool
# ---------------------------------------------------------------------------

# The unified ``illustrate`` tool (Anthropic procedural OR hand-drawn CC0 kits)
# lives in services/tools/illustrator.py; alias it here so existing importers
# and the deterministic generator stay stable.
from app.services.tools.illustrator import ILLUSTRATE_TOOL as ILLUSTRATION_TOOL  # noqa: E402

_DIRECTOR_SYSTEM = (
    "You are the illustration director for a strict monochrome editorial "
    "design system. An illustration is OPTIONAL — add one only if it "
    "genuinely strengthens this post. If you decide one helps, call the "
    "illustrate tool once with a style: 'anthropic' for abstract procedural "
    "compositions, 'open-peeps' for a hand-drawn person, 'open-doodles' for a "
    "hand-drawn scene — plus an abstract theme only (growth, flow, burst, "
    "orbit, layers, spiral...) — no literal objects, no words/letters, no "
    "emoji, no color terms. Keep the theme under 60 characters. If no "
    "illustration helps, do NOT call any tool."
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
