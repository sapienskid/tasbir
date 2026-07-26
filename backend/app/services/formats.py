"""Format service — resolves dynamic format specifications and AI instructions from database."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from sqlalchemy import select

from app.models.format import Format

log = logging.getLogger(__name__)


@dataclass
class FormatInfo:
    id: str
    name: str
    width: int
    height: int
    ai_instruction: str


DEFAULT_FORMAT_DIMS = {
    "instagram-square": (1080, 1080),
    "instagram-portrait": (1080, 1350),
    "instagram-story": (1080, 1920),
    "linkedin-post": (1200, 627),
    "twitter-card": (1200, 675),
    "facebook-post": (1200, 630),
    "pinterest-pin": (1000, 1500),
    "carousel-post": (1080, 1350),
}

_format_cache: dict[str, FormatInfo] = {}


async def get_format_info(format_id: str) -> FormatInfo:
    """Fetch format details from database with fallback to default dimensions.

    Results are cached in-process after first lookup so parallel format
    processing doesn't each open a separate DB connection.
    """
    if format_id in _format_cache:
        return _format_cache[format_id]

    try:
        from app.db.session import get_shared_session_factory
        pool = await get_shared_session_factory()
        async with pool() as session:
            result = await session.execute(select(Format).where(Format.id == format_id))
            fmt = result.scalar_one_or_none()
            if fmt:
                info = FormatInfo(
                    id=fmt.id,
                    name=fmt.name,
                    width=fmt.width,
                    height=fmt.height,
                    ai_instruction=fmt.ai_instruction or "",
                )
                _format_cache[format_id] = info
                return info
    except Exception as exc:
        log.warning("[formats] DB lookup failed for format '%s': %s", format_id, exc)

    w, h = DEFAULT_FORMAT_DIMS.get(format_id, (1080, 1080))
    info = FormatInfo(
        id=format_id,
        name=format_id.replace("-", " ").title(),
        width=w,
        height=h,
        ai_instruction="",
    )
    return info

