"""Authored editorial compositions for the shared procedural SVG engine.

Each recipe describes one visual relationship. The existing element model
handles seeded line variation, palette resolution, and safe-frame fitting.
"""

from dataclasses import dataclass

from app.services.illustration import Arc, Blob, Box, Circle, Line, Ring, _El


@dataclass
class Drawing(_El):
    """An authored Bézier silhouette with a conservative control-point box."""

    path: str
    bounds: tuple[float, float, float, float]
    fill: str = "none"
    width: float = 2.4
    noise: str = ""

    def box(self) -> Box:
        x0, y0, x1, y1 = self.bounds
        pad = self.width / 2 + 1
        return Box(x0 - pad, y0 - pad, x1 + pad, y1 + pad)

    def to_svg(self, p: dict) -> str:
        fill = p.get(self.fill, "none")
        return (
            f'<path d="{self.path}" style="fill:{fill};stroke:{p["ink"]};'
            f'stroke-width:{self.width};stroke-linecap:round;stroke-linejoin:round"/>'
        )


def _hand():
    # Open palm, thumb, and gently curled fingers; the object rests above it.
    return Drawing(
        "M 94 212 L 130 176 C 142 166 147 153 154 143 "
        "C 159 136 166 140 163 148 L 156 164 "
        "C 176 153 197 147 221 147 L 272 147 "
        "C 285 147 284 157 273 158 L 228 162 "
        "L 280 161 C 292 162 290 172 279 173 L 231 177 "
        "L 269 178 C 280 180 276 189 265 189 L 224 191 "
        "L 247 194 C 257 198 250 205 239 204 L 193 200 "
        "C 173 200 159 204 147 217 Z",
        (94, 136, 292, 217),
        fill="paper",
    )


def hand_balance(p, rng):
    return [
        Blob(212, 94, 66, 47, fill="accent"),
        Drawing("M 178 131 L 203 73 L 230 131 Z", (178, 73, 230, 131), "paper"),
        Ring(253, 110, 17),
        _hand(),
        Arc(163, 176, 189, 164, 211, 171, width=1.5),
    ]


def hand_seed(p, rng):
    return [
        Blob(199, 96, 56, 60, fill="accent"),
        Arc(205, 139, 191 + rng.uniform(-8, 8), 96, 210, 55),
        Drawing(
            "M 202 104 C 168 102 165 75 178 77 C 194 78 205 89 202 104 Z",
            (165, 75, 205, 104),
            "paper",
        ),
        Drawing(
            "M 204 86 C 207 62 234 55 238 61 C 238 79 222 89 204 86 Z", (204, 55, 238, 89), "paper"
        ),
        _hand(),
    ]


def botanical_grid(p, rng):
    els = []
    for x in range(120, 301, 30):
        els.append(Line(x, 54, x, 192, stroke="carrier", width=1, amp=0))
    for y in range(54, 193, 23):
        els.append(Line(120, y, 300, y, stroke="carrier", width=1, amp=0))
    els.append(Drawing("M 196 205 C 177 156 219 114 200 35", (177, 35, 219, 205)))
    for x, y, flip in [(201, 78, 1), (201, 116, -1), (194, 155, 1)]:
        extent = rng.uniform(36, 49) * flip
        els.append(
            Drawing(
                f"M {x} {y} Q {x + extent} {y - 4} {x + extent} {y - 31} "
                f"Q {x + 5} {y - 35} {x} {y} Z",
                (min(x, x + extent), y - 35, max(x + 5, x + extent), y),
                "ink",
            )
        )
    return els


def asymptote_grid(p, rng):
    els = [Line(96, 190, 310, 190, width=1.6), Line(96, 190, 96, 39, width=1.6)]
    for x in range(126, 300, 25):
        els.append(Line(x, 50, x, 190, width=1, amp=0, stroke="carrier"))
    for y in range(50, 191, 28):
        els.append(Line(96, y, 306, y, width=1, amp=0, stroke="carrier"))
    els.append(
        Drawing(
            "M 108 175 C 158 175 185 160 204 128 C 223 96 224 52 226 34",
            (108, 34, 226, 175),
            width=3.6,
        )
    )
    for y in range(35, 190, 15):
        els.append(Line(238, y, 238, y + 5, width=1.5, amp=0))
    els.append(Circle(280, 79 + rng.uniform(-12, 12), 14, fill="accent"))
    return els


def convergence(p, rng):
    els = [Blob(262, 120, 38, 51, fill="accent")]
    for i in range(9):
        y = 43 + i * 19
        bend = rng.uniform(-8, 8)
        els.append(
            Drawing(
                f"M 83 {y} C 158 {y + bend} 178 120 263 {115 + i * 1.3}",
                (83, min(y, 115, y + bend), 263, max(y, 126, y + bend)),
                width=1.6,
            )
        )
    els.extend([Line(266, 120, 321, 120, width=3, amp=0.5), Circle(321, 120, 5)])
    return els


def contour(p, rng):
    els = []
    for i in range(10):
        r = 14 + i * 6
        els.append(Ring(201 + i * 1.8, 119, r,
                        stroke="accent" if i == 5 else "ink",
                        width=5 if i == 5 else (1.2 if i % 3 else 2.5)))
    els.append(Circle(205 + rng.uniform(-8, 8), 117, 5))
    return els


def open_book(p, rng):
    els = [Blob(200, 118, 95, 63, fill="accent")]
    els.append(
        Drawing(
            "M 200 184 C 174 162 145 161 109 164 L 109 72 "
            "C 146 69 178 81 200 99 C 224 79 256 69 291 72 L 291 164 "
            "C 254 162 225 162 200 184 Z M 200 99 L 200 184",
            (109, 69, 291, 184),
            "paper",
        )
    )
    for y in (100, 117, 134):
        els.append(Arc(124, y, 158, y - 2, 183, y + 15, width=1.2))
        els.append(Arc(217, y + 15, 249, y - 2, 277, y, width=1.2))
    return els


def vessel_growth(p, rng):
    return [
        Blob(199, 96, 69, 59, fill="accent"),
        Drawing("M 161 143 L 171 204 Q 200 217 229 204 L 239 143 Z", (161, 143, 239, 217), "paper"),
        Arc(200, 153, 184, 96, 210, 42),
        Drawing("M 199 110 Q 150 110 158 73 Q 194 72 199 110 Z", (150, 72, 199, 110), "ink"),
        Drawing("M 200 88 Q 244 92 246 52 Q 211 49 200 88 Z", (200, 49, 246, 92), "paper"),
        Line(166, 154, 234, 154, width=1.2, amp=1),
    ]


EDITORIAL_ARCHETYPES = {
    "hand-balance": hand_balance,
    "hand-seed": hand_seed,
    "botanical-grid": botanical_grid,
    "asymptote-grid": asymptote_grid,
    "convergence": convergence,
    "contour": contour,
    "open-book": open_book,
    "vessel-growth": vessel_growth,
}


@dataclass
class FieldDrawing(_El):
    motif: str
    noise: str = ""

    def box(self) -> Box:
        # Field art is clipped by its nested SVG viewport, including strokes.
        return Box(0, 0, 400, 240)

    def to_svg(self, p: dict) -> str:
        from app.services.procedural_art import generate_art_svg

        art = generate_art_svg(
            self.motif,
            self.noise,
            {
                "bg": p["paper"],
                "ink": p["ink"],
                "acc": [p["accent"], p["mid"], p["carrier"]],
                "hi": p["accent"],
            },
        )
        return art.replace('width="1600" height="900"', 'width="400" height="240"', 1)


def _field_recipe(name):
    return lambda p, rng: [FieldDrawing(name)]


EDITORIAL_ARCHETYPES.update(
    {
        f"field-{name}": _field_recipe(name)
        for name in (
            "flow",
            "burst",
            "tiles",
            "blobs",
            "orbits",
            "waves",
            "hatch",
            "stipple",
            "mesh",
            "contour",
            "nodes",
            "cubes",
            "scribble",
            "halftone",
            "phyllo",
            "lissajous",
            "rose",
            "superformula",
            "attractor",
            "interference",
            "function_family",
            "synthesis",
        )
    }
)
