"""Format dimensions — loaded from platforms.yaml."""

from dataclasses import dataclass

from fastapi import HTTPException

from app.config import get_settings


@dataclass
class FormatInfo:
    id: str
    name: str
    width: int
    height: int


def get_format_info(format_id: str) -> FormatInfo:
    """Return format dimensions from platforms.yaml, fallback to 1080x1080."""
    from app.services.tokens import load_platforms

    settings = get_settings()
    dims = load_platforms(settings.platforms_path) if hasattr(settings, "platforms_path") else {}
    w, h = dims.get(format_id, (1080, 1080))
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
