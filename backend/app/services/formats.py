"""Format dimensions — loaded from platforms.yaml."""

import re
from dataclasses import dataclass

from fastapi import HTTPException

from app.config import get_settings

CAROUSEL_FORMAT = "instagram-carousel"

_SLIDE_RE = re.compile(r"^(.+)-(\d+)$")


@dataclass
class FormatInfo:
    id: str
    name: str
    width: int
    height: int


def is_carousel(format_id: str) -> bool:
    """True for the base carousel format or any of its slides."""
    return format_id == CAROUSEL_FORMAT or format_id.startswith(f"{CAROUSEL_FORMAT}-")


def carousel_slide_id(format_id: str, index: int) -> str:
    """Return the slide format id for a carousel frame, e.g. instagram-carousel-2."""
    return f"{format_id}-{index}"


def parse_carousel_slide(format_id: str) -> tuple[str, int] | None:
    """If format_id is a carousel slide (instagram-carousel-N), return (base, N)."""
    if not format_id.startswith(f"{CAROUSEL_FORMAT}-"):
        return None
    m = _SLIDE_RE.match(format_id)
    if m and m.group(2).isdigit():
        return m.group(1), int(m.group(2))
    return None


def get_format_info(format_id: str) -> FormatInfo:
    """Return format dimensions from platforms.yaml, fallback to 1080x1080.

    Carousel slide ids (instagram-carousel-N) resolve to the carousel dims.
    """
    from app.services.tokens import load_platforms

    dims = {}
    settings = get_settings()
    if hasattr(settings, "platforms_path"):
        dims = load_platforms(settings.platforms_path)
    parsed = parse_carousel_slide(format_id)
    base_id = parsed[0] if parsed else format_id
    w, h = dims.get(base_id, (1080, 1080))
    return FormatInfo(
        id=format_id,
        name=format_id.replace("-", " ").title(),
        width=w,
        height=h,
    )


def validate_platforms(platforms: list[str]) -> list[str]:
    """Validate platform ids against platforms.yaml; reject unknown/unsafe ids.

    Unknown or path-traversal format ids would otherwise end up in output file
    names (e.g. `data/output/{task_id}/{fmt_id}.html`).
    """
    from app.services.tokens import load_platforms

    settings = get_settings()
    known = set(load_platforms(settings.platforms_path).keys())
    cleaned: list[str] = []
    for p in platforms:
        if not p or p != p.strip() or ".." in p or "/" in p or "\\" in p:
            raise HTTPException(status_code=422, detail=f"Unsafe format id: {p!r}")
        if p not in known:
            raise HTTPException(status_code=422, detail=f"Unknown format: {p!r}")
        cleaned.append(p)
    return cleaned
