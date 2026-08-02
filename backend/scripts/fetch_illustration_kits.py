"""Fetch the CC0 hand-drawn illustration kits into the repo.

Downloads Open Peeps (Pablo Stanley) and Open Doodles SVGs from their public
CDNs into ``backend/data/illustrations/{open-peeps,open-doodles}/``. Both are
CC0 (public domain) — free for commercial use, no attribution required.

Run once from the repo root:
    python backend/scripts/fetch_illustration_kits.py

The SVGs are committed so the pipeline composes illustrations offline and
deterministically (no runtime network dependency).
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

KIT_URLS = {
    "open-peeps": [
        "https://www.openpeeps.com/",
        re.compile(r"(https://cdn\.prod\.website-files\.com/[^\"']+_peep-([\w-]+\.svg))"),
    ],
    "open-doodles": [
        "https://www.opendoodles.com/",
        re.compile(r"(https://cdn\.prod\.website-files\.com/[^\"']+_[a-z0-9-]+\.svg)"),
    ],
}

OUT = Path(__file__).resolve().parent.parent / "data" / "illustrations"

_UA = "Tasbir/1.0 (illustration-kit vendoring; local build)"


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    total = 0
    for kit, (page, pat) in KIT_URLS.items():
        dest = OUT / kit
        dest.mkdir(parents=True, exist_ok=True)
        html = _fetch(page).decode("utf-8", errors="replace")
        urls = []
        for m in pat.finditer(html):
            url = m.group(1)
            name = m.group(2) if len(m.groups()) > 1 else Path(url).name
            if not name.endswith(".svg"):
                name += ".svg"
            urls.append((url, name))
        # de-dup by filename
        seen: dict[str, str] = {}
        for url, name in urls:
            seen.setdefault(name, url)
        count = 0
        for name, url in sorted(seen.items()):
            target = dest / name
            if target.exists() and target.stat().st_size > 200:
                continue
            try:
                body = _fetch(url)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {name}: {e}")
                continue
            target.write_bytes(body)
            count += 1
        print(f"{kit}: {count} downloaded -> {dest} (total {len(seen)})")
        total += count
    print(f"Done. {total} new files under {OUT}")


if __name__ == "__main__":
    sys.exit(main())
