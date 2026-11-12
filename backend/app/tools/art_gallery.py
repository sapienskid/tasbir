"""Render a contact sheet of the illustration catalog.

Usage (from ``backend/``):

    python -m app.tools.art_gallery --out /tmp/art --count 24
    python -m app.tools.art_gallery --out /tmp/art --concept limit --aspect landscape
    python -m app.tools.art_gallery --out /tmp/art --subjects

Writes one SVG per scene, an ``index.html`` gallery, and — when ``rsvg-convert``
and ImageMagick are installed — a ``sheet.png`` contact sheet. Token values are
resolved to concrete grayscale so the art can be rasterized outside a design
system.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from app.services.art import ASPECTS, CONCEPTS, compose_scene, render_scene

_TOKEN_VALUES = {
    "--color-text": "#111111",
    "--color-text-inverted": "#f2f2f2",
    "--color-border": "#d9d9d9",
    "--color-border-inverted": "#2a2a2a",
    "--color-text-secondary": "#6e6e6e",
    "--color-text-tertiary": "#b0b0b0",
    "--color-bg": "#ffffff",
    "--color-bg-inverted": "#000000",
    "--color-accent": "#111111",
    "--color-accent-secondary": "#6e6e6e",
}


def _resolve(svg: str) -> str:
    for var, value in _TOKEN_VALUES.items():
        svg = svg.replace(f"var({var})", value)
    return svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Illustration catalog contact sheet")
    parser.add_argument("--out", default="/tmp/tasbir-art", help="output directory")
    parser.add_argument("--count", type=int, default=12, help="scenes to render")
    parser.add_argument("--concept", default="all", help="concept id, or 'all'")
    parser.add_argument("--aspect", default="square", choices=sorted(ASPECTS))
    parser.add_argument("--ground", default="white", choices=("white", "black"))
    parser.add_argument("--subjects", action="store_true", help="one scene per subject")
    parser.add_argument("--show", action="store_true", help="open the gallery")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    concepts = sorted(CONCEPTS) if args.concept == "all" else [args.concept]

    tiles: list[tuple[str, str]] = []
    if args.subjects:
        from app.services.art import SUBJECTS

        combos = [
            (name, f"{name}-{i}")
            for i, name in enumerate(sorted(SUBJECTS))
            if name != "portrait"
        ]
        plans = [("all subjects", seed, name) for name, seed in combos]
    else:
        plans = [
            (concepts[i % len(concepts)], f"gallery-{i}", "")
            for i in range(args.count)
        ]

    files: list[Path] = []
    for i, (concept, seed, subject) in enumerate(plans):
        scene = compose_scene(
            seed,
            args.ground,
            concept="" if concept == "all subjects" else concept,
            subject=subject,
            aspect=args.aspect,
        )
        svg = _resolve(render_scene(scene, args.ground, True))
        svg_path = out / f"{i:02d}-{scene.subject}-{scene.relation}-{scene.field}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        files.append(svg_path)
        label = (
            f"{scene.concept} · {scene.subject} · {scene.relation} · "
            f"{scene.field} · {scene.framing}"
        )
        tiles.append((label, svg_path.name))

        png = svg_path.with_suffix(".png")
        if subprocess.run(["which", "rsvg-convert"], capture_output=True).returncode == 0:
            subprocess.run(
                ["rsvg-convert", "-w", "420", "-h", "420", str(svg_path), "-o", str(png)],
                check=False,
            )

    cards = "\n".join(
        f'<figure><img src="{name}" alt=""><figcaption>{label}</figcaption></figure>'
        for label, name in tiles
    )
    (out / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Artwork gallery</title>"
        "<style>body{font:13px system-ui;background:#888;color:#111;margin:16px}"
        "main{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}"
        "figure{margin:0;background:#fff}img{width:100%;display:block}"
        "figcaption{padding:6px 8px;font-size:11px;color:#444}</style>"
        f"<main>{cards}</main>",
        encoding="utf-8",
    )

    pngs = [f for f in files if f.with_suffix(".png").is_file()]
    if len(pngs) >= 2 and subprocess.run(["which", "magick"], capture_output=True).returncode == 0:
        subprocess.run(
            ["magick", "montage", *[str(p.with_suffix(".png")) for p in pngs],
             "-tile", "4x", "-geometry", "420x420+8+8", "-background", "white",
             "-alpha", "remove", "-alpha", "off", "-depth", "8",
             str(out / "sheet.png")],
            check=False,
        )

    print(f"{len(files)} scenes → {out} (index.html, sheet.png)")
    if args.show:
        subprocess.run(["xdg-open", str(out / "index.html")], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
