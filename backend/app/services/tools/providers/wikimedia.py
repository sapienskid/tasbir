"""Wikimedia Commons photo search client.

Keyless MediaWiki API (``commons.wikimedia.org/w/api.php``). Content is CC /
public-domain licensed; many images require attribution, which the pipeline
renders as an on-image caption. A descriptive User-Agent is required.
"""

from __future__ import annotations

import html as html_lib
import logging
import re

import httpx

log = logging.getLogger(__name__)

_BASE = "https://commons.wikimedia.org/w/api.php"
_UA = "Tasbir/1.0 (https://github.com/sapienskid/tasbir; media pipeline)"

_STRIP_TAGS = re.compile(r"<[^>]+>")
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _clean_artist(raw: str) -> str:
    if not raw:
        return ""
    text = _STRIP_TAGS.sub("", raw)
    return html_lib.unescape(text).strip()[:80]


async def search_wikimedia(
    query: str,
    orientation: str = "landscape",
    per_page: int = 12,
) -> list[dict]:
    """Return normalized Wikimedia Commons candidates."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": str(per_page),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|mime",
        "iiurlwidth": "1200",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": _UA}) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("[wikimedia] search failed: %s", e)
        return []

    out: list[dict] = []
    for p in (data.get("query") or {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        mime = ii.get("mime") or ""
        if mime and mime not in _ALLOWED_MIME:
            continue
        width = ii.get("width") or 0
        height = ii.get("height") or 0
        if width < 200 or height < 200:
            continue
        url = ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        em = ii.get("extmetadata") or {}
        license_name = (em.get("LicenseShortName") or {}).get("value", "")
        artist = _clean_artist((em.get("Artist") or {}).get("value", ""))
        attr_required = ((em.get("AttributionRequired") or {}).get("value") or "").lower() in (
            "true", "yes", "1",
        )
        out.append({
            "url": url,
            "width": width,
            "height": height,
            "avg_color": "",
            "provider": "wikimedia",
            "photographer": artist,
            "license": license_name,
            "attr_required": attr_required,
        })
    return out
