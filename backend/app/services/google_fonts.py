"""Google Fonts metadata search — powers the design-system font picker.

The public ``fonts.google.com/metadata/fonts`` endpoint (the same one the
Google Fonts site uses) lists every family with category + variants, needs no
API key, and is cached in memory for a few hours.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request

log = logging.getLogger(__name__)

_METADATA_URL = "https://fonts.google.com/metadata/fonts"
_USER_AGENT = "Mozilla/5.0 (Tasbir; google-fonts-metadata) AppleWebKit/537.36"
_TIMEOUT_SECONDS = 15
_MAX_BYTES = 8 * 1024 * 1024
_CACHE_TTL_SECONDS = 12 * 3600

_cache: list[dict] | None = None
_cache_at = 0.0

_CATEGORY_ALIASES = {
    "sansserif": "sans-serif",
    "serif": "serif",
    "display": "display",
    "monospace": "monospace",
    "handwriting": "handwriting",
}


def _canonical_category(category: str) -> str:
    """Normalize Google's mixed-case category labels ("Sans Serif" etc.)."""
    key = (category or "").lower().replace(" ", "").replace("-", "").replace("_", "")
    return _CATEGORY_ALIASES.get(key, category)


def _fetch_metadata() -> list[dict]:
    global _cache, _cache_at
    now = time.time()
    if _cache is not None and now - _cache_at < _CACHE_TTL_SECONDS:
        return _cache

    req = urllib.request.Request(_METADATA_URL, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
        body = resp.read(_MAX_BYTES + 1)
    if len(body) > _MAX_BYTES:
        raise ValueError("Google Fonts metadata exceeds size cap")

    text = body.decode("utf-8", errors="replace")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Unexpected Google Fonts metadata format")
    data = json.loads(text[start : end + 1])
    fonts = [f for f in data.get("familyMetadataList", []) if isinstance(f, dict)]
    _cache = fonts
    _cache_at = now
    log.info("[fonts] Cached %d Google Font families", len(fonts))
    return fonts


def search_fonts(query: str, limit: int = 25) -> list[dict]:
    """Case-insensitive family-name search over the full Google Fonts catalog."""
    q = (query or "").strip().lower()
    fonts = _fetch_metadata()
    if not q:
        return []
    matches = [f for f in fonts if q in str(f.get("family", "")).lower()]
    matches.sort(
        key=lambda f: (
            not str(f.get("family", "")).lower().startswith(q),
            str(f.get("family", "")),
        )
    )
    out = []
    for f in matches[:limit]:
        out.append(
            {
                "family": f.get("family", ""),
                "category": _canonical_category(f.get("category", "")),
                "variants": f.get("variants", []),
            }
        )
    return out


# Curated popular families shown by default in the picker, grouped by type.
# Categories are resolved from the live metadata; the guess here is only a
# fallback when the catalog is unreachable.
_DEFAULT_FAMILIES: dict[str, list[str]] = {
    "sans-serif": [
        "Inter", "Roboto", "Open Sans", "Work Sans", "DM Sans", "Manrope",
        "Public Sans", "IBM Plex Sans", "Archivo", "Sora", "Montserrat",
        "Poppins", "Space Grotesk", "Figtree", "Barlow",
    ],
    "serif": [
        "Source Serif 4", "Playfair Display", "Lora", "Merriweather",
        "Cormorant Garamond", "Libre Caslon Text", "Newsreader", "Fraunces",
        "Literata", "EB Garamond", "Crimson Pro", "Noto Serif",
    ],
    "display": [
        "Bungee", "Righteous", "Audiowide", "Monoton", "Rye",
        "Alfa Slab One", "Abril Fatface",
    ],
    "monospace": [
        "Space Mono", "IBM Plex Mono", "JetBrains Mono", "Roboto Mono",
        "Source Code Pro", "Fira Mono", "Ubuntu Mono",
    ],
}


def default_fonts() -> list[dict]:
    """The curated default set for the picker (no search needed).

    Family categories are resolved from the live catalog when available;
    falls back to the guessed grouping so the picker still works offline.
    """
    try:
        meta = {f.get("family", ""): f for f in _fetch_metadata()}
    except Exception:
        meta = {}
    out = []
    for cat, families in _DEFAULT_FAMILIES.items():
        for family in families:
            m = meta.get(family)
            out.append(
                {
                    "family": family,
                    "category": _canonical_category(m.get("category", cat)) if m else cat,
                    "variants": m.get("variants", ["regular"]) if m else ["regular"],
                }
            )
    return out
