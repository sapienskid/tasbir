"""Procedural cover motifs adapted from the operator's stdlib SVG program.

No built-in palettes: bg/ink/acc/hi are CSS variable references supplied by
Tasbir. Geometry, noise, grain and variations are deterministic per seed.
Field motifs intentionally meet the canvas edge; the nested SVG clips them.
"""

from __future__ import annotations

import hashlib
import math
import random


class Noise:
    """Two-octave value noise, roughly in [0, 1]."""

    def __init__(self, rng, n=64):
        if n < 2 or n & (n - 1):
            raise ValueError("Noise grid size must be a power of two")
        self.n = n
        self.g = [[rng.random() for _ in range(n)] for _ in range(n)]

    def _oct(self, x, y):
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
        g, m = self.g, self.n - 1
        a, b = g[yi & m][xi & m], g[yi & m][(xi + 1) & m]
        c, d = g[(yi + 1) & m][xi & m], g[(yi + 1) & m][(xi + 1) & m]
        return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v

    def __call__(self, x, y):
        return 0.65 * self._oct(x, y) + 0.35 * self._oct(x * 2.1 + 17, y * 2.1 + 5)


def smooth(pts, closed=True):
    n = len(pts)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n if closed else n - 1):
        p0 = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed else pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return "".join(d) + ("Z" if closed else "")


def blob_pts(rng, cx, cy, r, wob=0.28, n=None):
    n = n or rng.randint(6, 10)
    off = rng.uniform(0, math.tau)
    pts = []
    for i in range(n):
        a = off + math.tau * i / n + rng.uniform(-0.12, 0.12)
        rr = r * (1 + wob * rng.uniform(-1, 1))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def circ(cx, cy, r, fill="none", stroke=None, sw=0):
    st = f' stroke="{stroke}" stroke-width="{sw:.1f}"' if stroke else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{st}/>'


def pth(d, fill="none", stroke=None, sw=0, extra=""):
    st = (
        (
            f' stroke="{stroke}" stroke-width="{sw:.1f}" stroke-linecap="round" '
            'stroke-linejoin="round"'
        )
        if stroke
        else ""
    )
    return f'<path d="{d}" fill="{fill}"{st}{extra}/>'


def ln(x1, y1, x2, y2, col, sw):
    return pth(f"M{x1:.1f},{y1:.1f}L{x2:.1f},{y2:.1f}", stroke=col, sw=sw)


def poly(pts, fill="none", stroke=None, sw=0):
    return pth("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z", fill, stroke, sw)


class Svg:
    def __init__(self, w, h, bg, prefix="art"):
        self.w, self.h, self.prefix, self.n = w, h, prefix, 0
        self.el = [f'<rect width="{w}" height="{h}" fill="{bg}"/>']

    def uid(self):
        self.n += 1
        return f"{self.prefix}-{self.n}"

    def add(self, element):
        self.el.append(element)

    def grain(self, seed, ink, opacity=0.09):
        # Noise affects opacity only; the ink color always comes from the DS.
        gid = self.uid()
        self.add(
            f'<filter id="{gid}" x="0" y="0" width="100%" height="100%" '
            'color-interpolation-filters="sRGB">'
            f'<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" '
            f'seed="{seed % 1000}"/>'
            '<feColorMatrix type="matrix" '
            'values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  1 0 0 0 0" result="noise"/>'
            f'<feFlood flood-color="{ink}"/>'
            '<feComposite in2="noise" operator="in"/></filter>'
            f'<rect width="{self.w}" height="{self.h}" opacity="{opacity}" '
            f'filter="url(#{gid})"/>'
        )

    def __str__(self):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" overflow="hidden">' + "".join(self.el) + "</svg>"
        )


def flow(s, rng, pal, nz):
    """Noise-driven streamlines inside an organic island."""
    w, h = s.w, s.h
    cols = pal["acc"] + [pal["ink"]]
    scale, twist = rng.uniform(0.0012, 0.0022), rng.choice([1.5, 2, 3]) * math.pi
    sw = rng.uniform(5, 9)
    gap, step = sw * rng.uniform(2.4, 3.2), 6
    cx, cy = w * rng.uniform(0.4, 0.6), h * rng.uniform(0.42, 0.58)
    threshold = rng.uniform(0.05, 0.2)
    y = gap / 2
    while y < h:
        x = gap / 2
        while x < w:
            px, py = x + rng.uniform(-0.3, 0.3) * gap, y + rng.uniform(-0.3, 0.3) * gap
            distance = math.hypot((px - cx) / w, (py - cy) / h)
            if nz(px * scale * 0.6 + 9, py * scale * 0.6 + 9) - distance * 0.9 > threshold:
                col = cols[
                    int(nz(px * scale * 0.5 + 50, py * scale * 0.5) * 2.2 * len(cols)) % len(cols)
                ]
                pts, qx, qy = [(px, py)], px, py
                for _ in range(rng.randint(10, 26)):
                    a = nz(qx * scale, qy * scale) * twist
                    qx, qy = qx + step * math.cos(a), qy + step * math.sin(a)
                    pts.append((qx, qy))
                s.add(pth(smooth(pts, False), stroke=col, sw=sw))
            x += gap
        y += gap


def burst(s, rng, pal, nz):
    w, h = s.w, s.h
    cx, cy = w * rng.uniform(0.4, 0.6), h * rng.uniform(0.42, 0.58)
    radius = min(w, h) * rng.uniform(0.26, 0.36)
    cols = pal["acc"] + [pal["ink"]]
    s.add(circ(cx, cy, radius * rng.uniform(0.55, 0.8), pal["hi"]))
    n = rng.choice([12, 16, 20, 24, 32])
    for i in range(n):
        a = math.tau * i / n + rng.uniform(-0.03, 0.03)
        r0, r1 = radius * rng.uniform(0.12, 0.5), radius * rng.uniform(0.8, 1.5)
        col = pal["ink"] if rng.random() < 0.6 else rng.choice(cols)
        s.add(
            ln(
                cx + r0 * math.cos(a),
                cy + r0 * math.sin(a),
                cx + r1 * math.cos(a),
                cy + r1 * math.sin(a),
                col,
                radius * rng.uniform(0.06, 0.13),
            )
        )
    for _ in range(rng.randint(10, 22)):
        a, r = rng.uniform(0, math.tau), radius * rng.uniform(1.35, 2.2)
        x, y = cx + r * math.cos(a) * 1.4, cy + r * math.sin(a)
        if 0 < x < w and 0 < y < h:
            s.add(circ(x, y, radius * rng.uniform(0.015, 0.05), rng.choice(cols)))


def tiles(s, rng, pal, nz):
    n = rng.choice([4, 5, 6, 8])
    c = s.w / n
    rows = math.ceil(s.h / c)
    oy, cols = (s.h - rows * c) / 2, pal["acc"] + [pal["ink"]]
    for j in range(rows):
        for i in range(n):
            x, y = i * c, oy + j * c
            cx, cy = x + c / 2, y + c / 2
            bgc = rng.choice(cols) if rng.random() < 0.3 else None
            # A monochrome DS can collapse several roles to the same value.
            col = rng.choice([k for k in cols if k != bgc] or [pal["bg"]])
            kind = rng.choice(
                [
                    "quarter",
                    "quarter",
                    "half",
                    "circle",
                    "diamond",
                    "stripes",
                    "dot",
                    "none",
                    "none",
                ]
            )
            element = ""
            if kind == "quarter":
                element = pth(
                    f"M{x:.1f},{y:.1f}h{c:.1f}A{c:.1f},{c:.1f} 0 0 1 {x:.1f},{y + c:.1f}Z",
                    col,
                )
            elif kind == "half":
                element = pth(
                    f"M{x:.1f},{y + c:.1f}A{c / 2:.1f},{c / 2:.1f} 0 0 1 {x + c:.1f},{y + c:.1f}Z",
                    col,
                )
            elif kind in ("circle", "dot"):
                element = circ(cx, cy, c * (0.38 if kind == "circle" else 0.17), col)
            elif kind == "diamond":
                element = poly(
                    [(cx, y + c * 0.1), (x + c * 0.9, cy), (cx, y + c * 0.9), (x + c * 0.1, cy)],
                    col,
                )
            elif kind == "stripes":
                element = "".join(
                    ln(x + c * 0.12, y + c * t, x + c * 0.88, y + c * t, col, c * 0.11)
                    for t in (0.22, 0.5, 0.78)
                )
            if bgc:
                s.add(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{c:.1f}" height="{c:.1f}" fill="{bgc}"/>'
                )
            if element:
                s.add(
                    f'<g transform="rotate({rng.choice([0, 90, 180, 270])} {cx} {cy})">'
                    f"{element}</g>"
                )


def blobs(s, rng, pal, nz):
    shapes = []
    count = rng.randint(4, 7)
    for k in range(count):
        r = min(s.w, s.h) * rng.uniform(0.13, 0.27)
        fill = pal["hi"] if k == count - 1 else rng.choice(pal["acc"] + [pal["bg"], pal["ink"]])
        shapes.append(
            (
                smooth(
                    blob_pts(rng, rng.uniform(0.2, 0.8) * s.w, rng.uniform(0.28, 0.72) * s.h, r)
                ),
                fill,
            )
        )
    for d, col in shapes:
        s.add(pth(d, col))
    for d, _ in shapes:
        s.add(
            pth(
                d,
                stroke=pal["ink"],
                sw=rng.uniform(3, 5),
                extra=f' transform="translate({rng.uniform(-14, 14):.1f} '
                f'{rng.uniform(-14, 14):.1f})"',
            )
        )
    for _ in range(rng.randint(8, 16)):
        x, y, r = rng.uniform(0, s.w), rng.uniform(0, s.h), rng.uniform(5, 16)
        s.add(
            circ(x, y, r, pal["ink"])
            if rng.random() < 0.6
            else ln(x - r, y, x + r, y, pal["ink"], 4) + ln(x, y - r, x, y + r, pal["ink"], 4)
        )


def orbits(s, rng, pal, nz):
    cx, cy = s.w * rng.uniform(0.35, 0.65), s.h * rng.uniform(0.4, 0.6)
    rings, base = rng.randint(4, 8), min(s.w, s.h) * rng.uniform(0.06, 0.1)
    gap = min(s.w, s.h) * rng.uniform(0.06, 0.085)
    s.add(circ(cx, cy, base * 0.8, pal["hi"]))
    seed = rng.random() * 100
    for i in range(rings):
        r = base + (i + 1) * gap
        pts = []
        for k in range(48):
            a = math.tau * k / 48
            radius = r * (1 + 0.05 * (nz(math.cos(a) + seed + i, math.sin(a) + i) - 0.5))
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        s.add(
            pth(
                smooth(pts),
                stroke=pal["ink"],
                sw=rng.choice([3, 4, 6]),
                extra=' stroke-dasharray="2 14"' if rng.random() < 0.25 else "",
            )
        )
        a = rng.uniform(0, math.tau)
        s.add(
            circ(
                cx + r * math.cos(a),
                cy + r * math.sin(a),
                gap * rng.uniform(0.18, 0.4),
                rng.choice(pal["acc"]),
                pal["ink"],
                4,
            )
        )


def waves(s, rng, pal, nz):
    w, h = s.w, s.h
    s.add(
        circ(
            w * rng.uniform(0.25, 0.75),
            h * rng.uniform(0.25, 0.4),
            h * rng.uniform(0.12, 0.2),
            pal["hi"],
        )
    )
    layers = rng.randint(4, 7)
    fills = [pal["bg"], *pal["acc"], pal["ink"]]
    for k in range(layers):
        base = h * (0.38 + 0.6 * k / layers)
        amp, freq = h * rng.uniform(0.04, 0.1), rng.uniform(0.0015, 0.004)
        pts = [
            (x, base + (nz(x * freq + k * 7, k * 3.1) - 0.5) * 2 * amp)
            for x in range(-40, w + 80, 40)
        ]
        s.add(
            pth(
                smooth(pts, False) + f"L{w + 80},{h}L-40,{h}Z", fills[k % len(fills)], pal["ink"], 3
            )
        )


def hatch(s, rng, pal, nz):
    count = rng.randint(3, 5)
    highlight = rng.randrange(count)
    angle = rng.choice([-60, -45, -30, 30, 45, 60])
    for k in range(count):
        r = min(s.w, s.h) * rng.uniform(0.14, 0.26)
        cx, cy = rng.uniform(0.18, 0.82) * s.w, rng.uniform(0.25, 0.75) * s.h
        d = smooth(blob_pts(rng, cx, cy, r))
        if k == highlight:
            s.add(pth(d, pal["hi"], pal["ink"], 4))
            continue
        cid, spacing, sw = s.uid(), rng.uniform(9, 18), rng.uniform(1.8, 3.2)
        count_lines = int(r * 1.6 / spacing)
        lines = "".join(
            ln(cx - r * 1.6, cy + i * spacing, cx + r * 1.6, cy + i * spacing, pal["ink"], sw)
            for i in range(-count_lines, count_lines + 1)
        )
        s.add(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        s.add(pth(d, pal["bg"]))
        s.add(
            f'<g clip-path="url(#{cid})"><g transform="rotate('
            f'{angle + rng.choice([0, 0, 90])} {cx} {cy})">{lines}</g></g>'
        )
        s.add(pth(d, stroke=pal["ink"], sw=4))


def stipple(s, rng, pal, nz):
    radius = min(s.w, s.h) * rng.uniform(0.27, 0.35)
    cx, cy = s.w * rng.uniform(0.42, 0.58), s.h * rng.uniform(0.45, 0.55)
    a = rng.uniform(0, math.tau)
    s.add(
        circ(
            cx - radius * 0.5 * math.cos(a),
            cy - radius * 0.5 * math.sin(a),
            radius * rng.uniform(0.55, 0.7),
            pal["hi"],
        )
    )
    lx, ly, lz = 0.75 * math.cos(a), 0.75 * math.sin(a), 0.66
    base, dots = max(1.0, radius / 200), []
    for _ in range(min(40000, int(radius * radius / 1.2))):
        x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
        q = x * x + y * y
        if q > 1:
            continue
        shade = 1 - max(0, x * lx + y * ly + math.sqrt(1 - q) * lz)
        if rng.random() < shade**1.5 * 0.85 + 0.02:
            dots.append(
                circ(cx + x * radius, cy + y * radius, base * rng.uniform(0.7, 1.3), pal["ink"])
            )
    s.add("".join(dots))


def mesh(s, rng, pal, nz):
    w, h, ink = s.w, s.h, pal["ink"]
    nx = rng.randint(14, 24)
    ny = max(6, round(nx * h / w))
    cx, cy = w * rng.uniform(0.3, 0.7), h * rng.uniform(0.3, 0.7)
    sigma, strength = (
        min(w, h) * rng.uniform(0.2, 0.35),
        rng.uniform(0.35, 0.7) * rng.choice([-1, 1]),
    )
    scale, amp, seed = (
        rng.uniform(0.001, 0.002),
        min(w, h) * rng.uniform(0.03, 0.08),
        rng.random() * 50,
    )

    def point(i, j):
        x, y = -0.05 * w + i * 1.1 * w / nx, -0.05 * h + j * 1.1 * h / ny
        dx = (nz(x * scale + seed, y * scale) - 0.5) * 2 * amp
        dy = (nz(x * scale + seed + 31, y * scale + 11) - 0.5) * 2 * amp
        f = strength * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / sigma**2)
        return x + dx + (x - cx) * f, y + dy + (y - cy) * f

    grid = [[point(i, j) for i in range(nx + 1)] for j in range(ny + 1)]
    for _ in range(rng.randint(1, 2)):
        i0, j0 = rng.randrange(nx - 2), rng.randrange(ny - 2)
        bw, bh = rng.randint(1, 3), rng.randint(1, 2)
        for j in range(j0, min(ny, j0 + bh)):
            for i in range(i0, min(nx, i0 + bw)):
                if rng.random() < 0.85:
                    s.add(
                        poly(
                            [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]],
                            pal["hi"],
                        )
                    )
    sw = max(1.5, w / 640)
    for row in grid:
        s.add(pth(smooth(row, False), stroke=ink, sw=sw))
    for i in range(nx + 1):
        s.add(pth(smooth([grid[j][i] for j in range(ny + 1)], False), stroke=ink, sw=sw))


_SEG = {
    1: "LB",
    2: "BR",
    3: "LR",
    4: "TR",
    5: "TL BR",
    6: "TB",
    7: "TL",
    8: "TL",
    9: "TB",
    10: "TR LB",
    11: "TR",
    12: "LR",
    13: "RB",
    14: "LB",
}


def _edge(edge, x, y, a, b, c, d, level, step):
    if edge == "T":
        return x + step * (level - a) / (b - a), y
    if edge == "R":
        return x + step, y + step * (level - b) / (c - b)
    if edge == "B":
        return x + step * (level - d) / (c - d), y + step
    return x, y + step * (level - a) / (d - a)


def contour(s, rng, pal, nz):
    """Marching squares over a noise field with a Gaussian hill."""
    w, h, ink = s.w, s.h, pal["ink"]
    step = max(6, w // 170)
    scale, seed = rng.uniform(0.0014, 0.0026), rng.random() * 80
    cx, cy = w * rng.uniform(0.3, 0.7), h * rng.uniform(0.3, 0.7)
    nx, ny = w // step + 2, h // step + 2
    field = [
        [
            nz(x * step * scale + seed, y * step * scale + seed * 0.7)
            + 0.45 * math.exp(-(((x * step - cx) / w) ** 2 + ((y * step - cy) / h) ** 2) * 6)
            for x in range(nx)
        ]
        for y in range(ny)
    ]
    lo, hi = min(map(min, field)), max(map(max, field))
    levels = rng.randint(10, 16)
    highlight, sw = rng.randrange(2, levels - 1), max(1.6, w / 700)
    for li in range(levels):
        level = lo + (hi - lo) * (li + 0.5) / levels
        paths = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                a, b, c, d = field[j][i], field[j][i + 1], field[j + 1][i + 1], field[j + 1][i]
                mask = (a >= level) * 8 + (b >= level) * 4 + (c >= level) * 2 + (d >= level)
                if mask in (0, 15):
                    continue
                for pair in _SEG[mask].split():
                    p = _edge(pair[0], i * step, j * step, a, b, c, d, level, step)
                    q = _edge(pair[1], i * step, j * step, a, b, c, d, level, step)
                    paths.append(f"M{p[0]:.1f},{p[1]:.1f}L{q[0]:.1f},{q[1]:.1f}")
        if li == highlight:
            s.add(pth("".join(paths), stroke=ink, sw=sw * 5))
            s.add(pth("".join(paths), stroke=pal["hi"], sw=sw * 2.6))
        else:
            s.add(pth("".join(paths), stroke=ink, sw=sw * (1.8 if li % 4 == 0 else 1)))


def nodes(s, rng, pal, nz):
    w, h, ink = s.w, s.h, pal["ink"]
    count, mind = rng.randint(30, 55), min(w, h) * 0.07
    centers = [
        (rng.uniform(0.2, 0.8) * w, rng.uniform(0.25, 0.75) * h) for _ in range(rng.randint(2, 4))
    ]
    pts, tries = [], 0
    while len(pts) < count and tries < 6000:
        tries += 1
        center, spread = rng.choice(centers), min(w, h) * 0.28
        x, y = rng.gauss(center[0], spread * 1.3), rng.gauss(center[1], spread)
        if (
            20 < x < w - 20
            and 20 < y < h - 20
            and all(math.hypot(x - p[0], y - p[1]) > mind for p in pts)
        ):
            pts.append((x, y))
    if not pts:
        return
    edges, nbr = set(), {i: [] for i in range(len(pts))}
    for i, p in enumerate(pts):
        near = sorted(
            range(len(pts)), key=lambda j: (pts[j][0] - p[0]) ** 2 + (pts[j][1] - p[1]) ** 2
        )
        for j in near[1 : rng.randint(3, 4)]:
            edge = min(i, j), max(i, j)
            if edge not in edges:
                edges.add(edge)
                nbr[i].append(j)
                nbr[j].append(i)
    for i, j in sorted(edges):
        s.add(ln(*pts[i], *pts[j], ink, 2.5))
    current = rng.randrange(len(pts))
    path = [current]
    for _ in range(rng.randint(5, 9)):
        nxt = [j for j in nbr[current] if j not in path]
        if not nxt:
            break
        current = rng.choice(nxt)
        path.append(current)
    if len(path) > 1:
        d = "M" + "L".join(f"{pts[i][0]:.1f},{pts[i][1]:.1f}" for i in path)
        s.add(pth(d, stroke=ink, sw=13))
        s.add(pth(d, stroke=pal["hi"], sw=7))
    base = min(w, h) * 0.012
    for i, p in enumerate(pts):
        r, on = base * rng.choice([1, 1, 1.5, 2.2]), i in path
        fill = pal["hi"] if on else (pal["bg"] if rng.random() < 0.35 else ink)
        s.add(circ(*p, r * (1.4 if on else 1), fill, ink, 3))


def cubes(s, rng, pal, nz):
    w, h, ink = s.w, s.h, pal["ink"]
    count, size = rng.randint(6, 9), min(w, h) * rng.uniform(0.07, 0.09)
    cw, ch, cz = size * 0.866, size * 0.5, size * rng.uniform(0.8, 1)
    seed, scale = rng.random() * 50, rng.uniform(0.25, 0.45)
    heights = [
        [int(nz(i * scale + seed, j * scale) ** 1.3 * 6) for i in range(count)]
        for j in range(count)
    ]
    cells = [(i, j) for j in range(count) for i in range(count) if heights[j][i]]
    highlights = set(rng.sample(cells, min(2, len(cells))))
    ox, oy = w / 2, h / 2 - count * ch + cz * 1.5
    for t in range(2 * count - 1):
        for i in range(count):
            j = t - i
            if not 0 <= j < count or not heights[j][i]:
                continue
            sx, sy, up = ox + (i - j) * cw, oy + (i + j) * ch, heights[j][i] * cz
            top = [
                (sx, sy - up),
                (sx + cw, sy + ch - up),
                (sx, sy + 2 * ch - up),
                (sx - cw, sy + ch - up),
            ]
            bottom = [(sx, sy), (sx + cw, sy + ch), (sx, sy + 2 * ch), (sx - cw, sy + ch)]
            s.add(poly([top[3], top[2], bottom[2], bottom[3]], ink, ink, 3))
            s.add(poly([top[2], top[1], bottom[1], bottom[2]], pal["bg"], ink, 3))
            s.add(poly(top, pal["hi"] if (i, j) in highlights else pal["bg"], ink, 3))


def scribble(s, rng, pal, nz):
    w, h = s.w, s.h
    s.add(
        pth(
            smooth(
                blob_pts(
                    rng,
                    rng.uniform(0.3, 0.7) * w,
                    rng.uniform(0.35, 0.65) * h,
                    min(w, h) * rng.uniform(0.18, 0.3),
                )
            ),
            pal["hi"],
        )
    )
    x, y, a = w * rng.uniform(0.3, 0.7), h * rng.uniform(0.3, 0.7), rng.uniform(0, math.tau)
    step, k, seed = min(w, h) * 0.02, rng.uniform(0.35, 0.7), rng.random() * 60
    pts = [(x, y)]
    for t in range(rng.randint(450, 800)):
        a += (nz(t * 0.012 + seed, seed * 0.3) - 0.5) * k * 2.2
        if not (w * 0.1 < x < w * 0.9 and h * 0.1 < y < h * 0.9):
            a += ((math.atan2(h / 2 - y, w / 2 - x) - a + math.pi) % math.tau - math.pi) * 0.12
        x, y = x + step * math.cos(a), y + step * math.sin(a)
        pts.append((x, y))
    s.add(pth(smooth(pts[::3], False), stroke=pal["ink"], sw=max(3, w / 320)))


def halftone(s, rng, pal, nz):
    w, h, ink = s.w, s.h, pal["ink"]
    gap = rng.uniform(0.022, 0.032) * min(w, h)
    scale, seed, angle = rng.uniform(0.0012, 0.0022), rng.random() * 50, rng.uniform(0, math.tau)
    gx, gy = math.cos(angle), math.sin(angle)

    def field(x, y):
        return min(
            1,
            max(
                0,
                nz(x * scale + seed, y * scale) * 0.7 + ((x * gx + y * gy) / w * 0.5 + 0.25) * 0.6,
            ),
        )

    fc = field(rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h)
    dark, highlight, row, y = [], [], 0, 0.0
    while y < h + gap:
        x = gap / 2 if row % 2 else 0.0
        while x < w + gap:
            f = field(x, y)
            radius = gap * 0.55 * f
            if radius > 0.8:
                (highlight if abs(f - fc) < 0.04 else dark).append(circ(x, y, radius, "inherit"))
            x += gap
        row, y = row + 1, y + gap * 0.866
    s.add(
        f'<g fill="{ink}">{"".join(dark)}</g><g fill="{pal["hi"]}" '
        f'stroke="{ink}" stroke-width="2">{"".join(highlight)}</g>'
    )


def phyllo(s, rng, pal, nz):
    w, h, ink = s.w, s.h, pal["ink"]
    cx, cy = w * rng.uniform(0.42, 0.58), h * rng.uniform(0.45, 0.55)
    count, c, mod = (
        rng.randint(900, 1800),
        min(w, h) * rng.uniform(0.0105, 0.0145),
        rng.choice([21, 34]),
    )
    angle = math.pi * (3 - math.sqrt(5))
    dark, highlight = [], []
    for i in range(1, count):
        rr, a = c * math.sqrt(i), i * angle
        radius, on = c * (0.25 + 0.45 * (i / count) ** 0.8), i % mod == 0
        (highlight if on else dark).append(
            circ(
                cx + rr * math.cos(a), cy + rr * math.sin(a), radius * (1.9 if on else 1), "inherit"
            )
        )
    s.add(
        f'<g fill="{ink}">{"".join(dark)}</g><g fill="{pal["hi"]}" '
        f'stroke="{ink}" stroke-width="2">{"".join(highlight)}</g>'
    )


MOTIFS = {
    fn.__name__: fn
    for fn in (
        flow,
        burst,
        tiles,
        blobs,
        orbits,
        waves,
        hatch,
        stipple,
        mesh,
        contour,
        nodes,
        cubes,
        scribble,
        halftone,
        phyllo,
    )
}


def generate_art_svg(
    motif: str,
    seed: str,
    palette: dict,
    width: int = 1600,
    height: int = 900,
    grain: bool = False,
    placement: str = "center",
) -> str:
    """Render at native dimensions; callers scale the resulting SVG for preview."""
    digest = hashlib.sha256(str(seed).encode()).hexdigest()
    numeric_seed = int(digest[:16], 16)
    rng = random.Random(numeric_seed)
    svg = Svg(width, height, palette["bg"], prefix=f"art-{motif}-{digest[:10]}")
    noise = Noise(rng)
    shift = {"center": 0, "left": -width * 0.1, "right": width * 0.1}[placement]
    if shift:
        svg.add(f'<g transform="translate({shift} 0)">')
    MOTIFS[motif](svg, rng, palette, noise)
    if shift:
        svg.add("</g>")
    if grain:
        svg.grain(numeric_seed, palette["ink"])
    return str(svg)
