"""Pexels photo search client.

GET https://api.pexels.com/v1/search — Authorization: <key>. Free tier: 200
req/hr, 20,000/mo. The ``landscape``/``portrait`` CDN crops map 1:1 onto the
pipeline's format families, and ``avg_color`` is handy for ground choice.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_BASE = "https://api.pexels.com/v1/search"

# Pexels image CDN supports imgix-style resize/crop params.
_CROP = {
    "landscape": {"w": 1200, "h": 627, "fit": "crop"},
    "portrait": {"w": 800, "h": 1200, "fit": "crop"},
    "square": {"w": 1080, "h": 1080, "fit": "crop"},
}


async def search_pexels(
    query: str,
    orientation: str = "landscape",
    per_page: int = 10,
) -> list[dict]:
    """Return normalized photo candidates from Pexels ([] if no key/fail)."""
    key = get_settings().pexels_api_key
    if not key:
        log.info("[pexels] no API key configured")
        return []

    orient = "landscape" if orientation == "square" else orientation
    crop = _CROP.get(orientation, _CROP["landscape"])
    params = httpx.QueryParams(
        {"query": query, "orientation": orient, "per_page": str(per_page)}
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{_BASE}?{params}", headers={"Authorization": key})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("[pexels] search failed: %s", e)
        return []

    out: list[dict] = []
    for p in data.get("photos", []) or []:
        src = p.get("src") or {}
        orig = src.get("original") or src.get("large2x") or src.get("large")
        if not orig:
            continue
        resize = "&".join(f"{k}={v}" for k, v in crop.items())
        sep = "&" if "?" in orig else "?"
        url = f"{orig}{sep}auto=compress&cs=tinysrgb&{resize}"
        out.append({
            "url": url,
            "width": p.get("width") or 0,
            "height": p.get("height") or 0,
            "avg_color": p.get("avg_color") or "",
            "provider": "pexels",
            "photographer": p.get("photographer") or "",
            "license": "Pexels License",
        })
    return out
