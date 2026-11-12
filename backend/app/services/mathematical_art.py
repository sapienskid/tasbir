"""Seeded equation-driven artwork, not charts of invented measurements."""

import math


def _curve(s, points, color, width=2.4):
    from app.services.procedural_art import pth

    s.add(pth("M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in points), stroke=color, sw=width))


def lissajous(s, rng, pal, nz):
    a, b = rng.choice([(2, 3), (3, 4), (3, 5), (5, 7), (4, 7)])
    phase = rng.uniform(0.2, math.pi)
    for k in range(rng.randint(3, 7)):
        radius = 0.22 + k * 0.018
        points = [
            (
                s.w / 2 + s.h * radius * math.sin(a * t + phase + k * 0.045),
                s.h / 2 + s.h * radius * math.sin(b * t),
            )
            for t in (i * math.tau / 1600 for i in range(1601))
        ]
        _curve(s, points, pal["hi"] if k == 1 else pal["ink"], 4.5 if k == 1 else 1.4)


def rose(s, rng, pal, nz):
    petals, phase = rng.choice([3, 4, 5, 7, 8]), rng.uniform(0, math.tau)
    for k in range(rng.randint(3, 6)):
        points = []
        for i in range(1801):
            t = i * math.tau / 1800
            r = s.h * (0.24 + k * 0.022) * math.cos(petals * t + phase)
            points.append((s.w / 2 + r * math.cos(t), s.h / 2 + r * math.sin(t)))
        _curve(s, points, pal["hi"] if k == 0 else pal["ink"], 5 if k == 0 else 1.6)


def superformula(s, rng, pal, nz):
    m = rng.choice([3, 4, 5, 6, 7, 8])
    n1, n2, n3 = rng.uniform(0.6, 3), rng.uniform(1, 5), rng.uniform(1, 5)
    points = []
    for i in range(1601):
        t = i * math.tau / 1600
        r = (abs(math.cos(m * t / 4)) ** n2 + abs(math.sin(m * t / 4)) ** n3) ** (-1 / n1)
        points.append((r * math.cos(t), r * math.sin(t)))
    extent = max(max(abs(x), abs(y)) for x, y in points)
    for k in range(9):
        factor = s.h * (0.12 + k * 0.027) / extent
        _curve(
            s,
            [(s.w / 2 + x * factor, s.h / 2 + y * factor) for x, y in points],
            pal["hi"] if k == 4 else pal["ink"],
            5 if k == 4 else 1.7,
        )


def attractor(s, rng, pal, nz):
    from app.services.procedural_art import circ

    a, b, c, d = rng.choice(
        [(1.4, -2.3, 2.4, -2.1), (-2, -2, -1.2, 2), (1.7, 1.7, 0.6, 1.2), (-2.7, -2.3, 2.8, 2.1)]
    )
    a += rng.uniform(-0.04, 0.04)
    x, y = 0.1, 0.1
    paths = [[], []]
    for i in range(14000):
        x, y = math.sin(a * y) - math.cos(b * x), math.sin(c * x) - math.cos(d * y)
        if i > 100:
            paths[int(i % 7 == 0)].append((s.w / 2 + x * s.h * 0.18, s.h / 2 + y * s.h * 0.18))
    for index, points in enumerate(paths):
        color = pal["hi"] if index else pal["ink"]
        s.add(
            f'<g fill="{color}">'
            + "".join(circ(x, y, 1.6 if index else 0.8, "inherit") for x, y in points)
            + "</g>"
        )


def interference(s, rng, pal, nz):
    separation, phase = rng.uniform(0.10, 0.25) * s.h, rng.uniform(0, math.tau)
    for k in range(26):
        points = []
        for i in range(401):
            x = s.w * (0.12 + 0.76 * i / 400)
            envelope = math.exp(-(((x - s.w / 2) / (s.w * 0.3)) ** 2))
            y = s.h * (0.2 + k * 0.024) + envelope * separation * 0.13 * (
                math.sin(x / s.w * math.tau * 3 + phase + k * 0.15)
                + math.sin(x / s.w * math.tau * 5 - phase + k * 0.08)
            )
            points.append((x, y))
        _curve(s, points, pal["hi"] if k in (11, 12) else pal["ink"], 4 if k in (11, 12) else 1.3)


def function_family(s, rng, pal, nz):
    power = rng.uniform(0.7, 2.5)
    for k in range(12):
        points = [
            (s.w * (0.15 + 0.7 * t), s.h * (0.78 - 0.56 * math.exp(-t * (1.2 + k * 0.65)) ** power))
            for t in (i / 500 for i in range(501))
        ]
        _curve(s, points, pal["hi"] if k == 4 else pal["ink"], 5 if k == 4 else 1.5)


MATHEMATICAL_MOTIFS = {
    fn.__name__: fn
    for fn in (
        lissajous,
        rose,
        superformula,
        attractor,
        interference,
        function_family,
    )
}
