"""Format dimensions — loaded from platforms.yaml."""

from dataclasses import dataclass

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
