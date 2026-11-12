#!/usr/bin/env python3
"""Generate seeded covers using a Tasbir design system (no LLM calls).

Run from backend with its virtual environment:
  .venv/bin/python procgen.py -m system -s 7 --png --grain
  .venv/bin/python procgen.py -m limit -t 'The limits' --size 1200x630
  .venv/bin/python procgen.py -n 12 -d default --ground black

The geometry engine uses only the stdlib. This adapter uses Tasbir's DB for
its palette and the configured Playwright service for optional PNG exports.
"""

import argparse
import asyncio
import hashlib
import random
import re
from pathlib import Path

from app.db.session import close_shared_engine
from app.services.artifacts import atomic_write
from app.services.covers import (
    COVER_MOTIFS,
    CoverRequest,
    build_cover_svg,
    cover_html,
    cover_theme,
)
from app.services.dom_extractor import render_to_png
from app.services.ds_context import resolve_ds_context_strict


async def run(args) -> None:
    width, height = map(int, args.size.lower().split("x"))
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(10**9)
    if args.title:
        seed = int(hashlib.sha256(args.title.strip().lower().encode()).hexdigest()[:8], 16)
    output = args.out
    if args.title and output == "cover":
        output = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:60] or "cover"
    motif = args.motif
    try:
        ctx = await resolve_ds_context_strict(None, args.design_system)
        for index in range(args.count):
            request = CoverRequest(
                design_system_id=args.design_system,
                title=args.title or "",
                seed=str(seed + index),
                motif=motif,
                ground=args.ground,
                texture="print" if args.grain else "clean",
                width=width,
                height=height,
            )
            svg = build_cover_svg(request, ctx, 0)
            stem = output if args.count == 1 else f"{output}_{seed + index}"
            path = Path(f"{stem}.svg")
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, svg)
            if args.png:
                png = await render_to_png(cover_html(svg, width, height), width, height)
                if not png:
                    raise RuntimeError("PNG render failed; SVG saved. Check the Playwright service")
                atomic_write(f"{stem}.png", png)
            print(
                f"{path}  motif={cover_theme(request, 0)} "
                f"design_system={ctx.ds_id} seed={seed + index}"
            )
    finally:
        await close_shared_engine()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-m", "--motif", default="auto", choices=list(COVER_MOTIFS))
    parser.add_argument("-d", "--design-system", default="default")
    parser.add_argument("--ground", default="white", choices=["white", "black"])
    parser.add_argument("-s", "--seed", type=int)
    parser.add_argument("-t", "--title")
    parser.add_argument("--size", default="1600x900", help="WxH, each between 256 and 2400")
    parser.add_argument("-o", "--out", default="cover")
    parser.add_argument("-n", "--count", type=int, default=1)
    parser.add_argument("--png", action="store_true")
    parser.add_argument("--grain", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        parser.error("count must be between 1 and 100")
    try:
        asyncio.run(run(args))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
