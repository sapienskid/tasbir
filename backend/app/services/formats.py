"""Format dimensions — hardcoded defaults for known platforms.

Each format defines a canvas size for the generated design.
"""

from dataclasses import dataclass


@dataclass
class FormatInfo:
    id: str
    name: str
    width: int
    height: int
    ai_instruction: str


DEFAULT_FORMAT_DIMS: dict[str, tuple[int, int]] = {
    "instagram-square": (1080, 1080),
    "instagram-portrait": (1080, 1350),
    "instagram-story": (1080, 1920),
    "linkedin-post": (1200, 627),
    "twitter-card": (1200, 675),
    "facebook-post": (1200, 630),
    "pinterest-pin": (1000, 1500),
}


def get_format_info(format_id: str) -> FormatInfo:
    """Return format dimensions. No DB lookups needed."""
    w, h = DEFAULT_FORMAT_DIMS.get(format_id, (1080, 1080))
    return FormatInfo(
        id=format_id,
        name=format_id.replace("-", " ").title(),
        width=w,
        height=h,
        ai_instruction="",
    )
