"""Google Fonts search API — used by the design-system font picker."""

from fastapi import APIRouter, HTTPException, Query

from app.services.google_fonts import default_fonts, search_fonts

router = APIRouter()


@router.get("/search")
async def search_fonts_route(
    q: str = Query(default="", max_length=64),
    limit: int = Query(default=25, ge=1, le=50),
):
    try:
        fonts = search_fonts(q, limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Google Fonts unavailable: {e}")
    return {"fonts": fonts}


@router.get("/default")
async def default_fonts_route():
    """Curated per-category families shown in the picker before any search."""
    return {"fonts": default_fonts()}
