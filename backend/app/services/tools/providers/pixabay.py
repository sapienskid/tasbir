"""Pixabay photo search client.

GET https://pixabay.com/api/?key=... — free tier: 100 req/60s. Content License.
Pixabay requires:
  - downloaded (no permanent hotlinking)  -> matches our base64 pipeline
  - search responses cached for 24h       -> in-process TTL cache below
  - attribution shown when results are displayed

When the design language is monochrome we prefer ``colors=grayscale`` and fall
back to full colour on empty results (the pipeline grayscales it anyway). For
color languages the search is full colour only.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_BASE = "https://pixabay.com/api/"

# In-process 24h response cache (Pixabay ToS). Single-worker deployments share
# it; keyed by (query, orientation, grayscale).
_cache: dict[tuple[str, str, bool], tuple[float, list[dict]]] = {}
_TTL = 24 * 60 * 60


async def _search_once(
    key: str,
    query: str,
    orientation: str,
    grayscale: bool,
    per_page: int,
) -> list[dict]:
    params = {
        "key": key,
        "q": query,
        "image_type": "photo",
        "safesearch": "true",
        "per_page": str(per_page),
        "orientation": "horizontal" if orientation in ("landscape", "square") else "vertical",
    }
    if grayscale:
        params["colors"] = "grayscale"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("[pixabay] search failed: %s", e)
        return []
    hits = data.get("hits") or []
    out: list[dict] = []
    for h in hits:
        url = h.get("largeImageURL") or h.get("webformatURL")
        if not url:
            continue
        out.append({
            "url": url,
            "width": h.get("imageWidth") or h.get("webformatWidth") or 0,
            "height": h.get("imageHeight") or h.get("webformatHeight") or 0,
            "avg_color": "",
            "provider": "pixabay",
            "photographer": h.get("user") or "",
            "license": "Pixabay Content License",
        })
    return out


async def search_pixabay(
    query: str,
    orientation: str = "landscape",
    per_page: int = 10,
    grayscale: bool = True,
) -> list[dict]:
    """Return normalized Pixabay candidates, honoring the 24h cache rule.

    ``grayscale=True`` tries ``colors=grayscale`` first and widens to colour
    on empty results (monochrome brands). ``grayscale=False`` searches full
    colour only (color design languages).
    """
    key = get_settings().pixabay_api_key
    if not key:
        log.info("[pixabay] no API key configured")
        return []

    # Grayscale first (monochrome brands); widen to colour on empty results.
    for want_gray in ((True, False) if grayscale else (False,)):
        ck = (query, orientation, want_gray)
        now = time.time()
        if ck in _cache:
            expires, cached = _cache[ck]
            if now < expires:
                hits = cached
            else:
                del _cache[ck]
                hits = await _search_once(key, query, orientation, want_gray, per_page)
                _cache[ck] = (now + _TTL, hits)
        else:
            hits = await _search_once(key, query, orientation, want_gray, per_page)
            _cache[ck] = (now + _TTL, hits)
        if hits:
            return hits
    return []
