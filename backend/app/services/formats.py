"""Format dimensions — loaded from platforms.yaml."""

import re
from dataclasses import dataclass

from fastapi import HTTPException

CAROUSEL_FORMAT = "instagram-carousel"
PORTRAIT_CAROUSEL_FORMAT = "instagram-carousel-portrait"

# Base ids whose slides (instagram-carousel-N / instagram-carousel-portrait-N)
# are real outputs; the base entry itself only holds the slide copy.
CAROUSEL_BASES = {CAROUSEL_FORMAT, PORTRAIT_CAROUSEL_FORMAT}

_SLIDE_RE = re.compile(r"^(.+)-(\d+)$")


@dataclass
class FormatInfo:
    id: str
    name: str
    width: int
    height: int


def is_carousel(format_id: str) -> bool:
    """True for any carousel base or its slides (square + portrait)."""
    return format_id in CAROUSEL_BASES or any(
        format_id.startswith(f"{base}-") for base in CAROUSEL_BASES
    )


def is_carousel_base(format_id: str) -> bool:
    """True only for the base carousel ids (not slides)."""
    return format_id in CAROUSEL_BASES


def carousel_slide_id(format_id: str, index: int) -> str:
    """Return the slide format id for a carousel frame, e.g. instagram-carousel-2."""
    return f"{format_id}-{index}"


def parse_carousel_slide(format_id: str) -> tuple[str, int] | None:
    """If format_id is a carousel slide (instagram-carousel-N / instagram-carousel-portrait-N), return (base, N)."""
    if not any(format_id.startswith(f"{base}-") for base in CAROUSEL_BASES):
        return None
    m = _SLIDE_RE.match(format_id)
    if m and m.group(2).isdigit() and m.group(1) in CAROUSEL_BASES:
        return m.group(1), int(m.group(2))
    return None


def get_format_info(format_id: str) -> FormatInfo:
    """Return format dimensions from the DB platforms table (YAML seed fallback).

    Carousel slide ids (instagram-carousel-N / instagram-carousel-portrait-N)
    resolve to their base platform's dims.
    """
    from app.services.platforms import get_platform_dims

    parsed = parse_carousel_slide(format_id)
    base_id = parsed[0] if parsed else format_id
    dims = get_platform_dims(base_id) or (1080, 1080)
    return FormatInfo(
        id=format_id,
        name=format_id.replace("-", " ").title(),
        width=dims[0],
        height=dims[1],
    )


def validate_platforms(platforms: list[str]) -> list[str]:
    """Validate platform ids against the DB platforms table; reject unknown/unsafe ids.

    Unknown or path-traversal format ids would otherwise end up in output file
    names (e.g. `data/output/{task_id}/{fmt_id}.html`). Also accepts valid
    carousel slide ids (e.g. `instagram-carousel-portrait-5`).
    """
    from app.services.platforms import list_platforms

    known = {r["id"] for r in list_platforms(include_inactive=True)}
    cleaned: list[str] = []
    for p in platforms:
        if not p or p != p.strip() or ".." in p or "/" in p or "\\" in p:
            raise HTTPException(status_code=422, detail=f"Unsafe format id: {p!r}")
        if p in known:
            cleaned.append(p)
            continue
        parsed = parse_carousel_slide(p)
        if parsed and (parsed[0] in known or parsed[0] in CAROUSEL_BASES) and parsed[1] > 0:
            cleaned.append(p)
            continue
        raise HTTPException(status_code=422, detail=f"Unknown format: {p!r}")
    return cleaned

