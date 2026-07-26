"""Format service — resolves dynamic format specifications and AI instructions from database."""

from dataclasses import dataclass
from sqlalchemy import select

from app.config import get_settings
from app.db.session import create_pool
from app.models.format import Format


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


async def get_format_info(format_id: str) -> FormatInfo:
    """Fetch format details from database with fallback to default dimensions."""
    try:
        s = get_settings()
        engine, pool = await create_pool(s.database_url)
        async with pool() as session:
            result = await session.execute(select(Format).where(Format.id == format_id))
            fmt = result.scalar_one_or_none()
            await engine.dispose()
            if fmt:
                return FormatInfo(
                    id=fmt.id,
                    name=fmt.name,
                    width=fmt.width,
                    height=fmt.height,
                    ai_instruction=fmt.ai_instruction or "",
                )
    except Exception:
        pass

    w, h = DEFAULT_FORMAT_DIMS.get(format_id, (1080, 1080))
    return FormatInfo(
        id=format_id,
        name=format_id.replace("-", " ").title(),
        width=w,
        height=h,
        ai_instruction="",
    )
