"""``icon_search`` — deterministic search over the vendored Lucide icon library.

The Scene Composer needs content-relevant motifs, but the full 1,756-icon
Lucide catalog can't fit in an LLM prompt. ``icon_search(keywords)`` is a tool
the media-plan director calls: it does a deterministic keyword/tag/category
search over ``data/icons/lucide/icons.yaml`` (built from each icon's JSON
metadata at vendor time) and returns a numbered shortlist of icon names the
LLM can then reference in a ``compose`` illustration.

No LLM is involved in the search itself — it's pure text matching over the
catalog, so results are fast, deterministic, and free. The icon SVGs
(``data/icons/lucide/{name}.svg``) are ``fill="none" stroke="currentColor"``
line art, so the composer renders them with ``color: var(--ill-ink)`` and they
follow the active design system.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import get_settings

log = logging.getLogger(__name__)

_MAX_RESULTS = 10


def icons_catalog_path() -> Path:
    """Path to the vendored Lucide catalog (icons.yaml).

    ``design_system_dir`` is ``<backend>/data/design_system``; the icon library
    lives in the sibling ``<backend>/data/icons/lucide`` directory.
    """
    settings = get_settings()
    return Path(settings.design_system_dir).parent / "icons" / "lucide" / "icons.yaml"


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict]:
    path = icons_catalog_path()
    if not path.exists():
        log.warning("[icon_search] catalog missing: %s", path)
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        icons = raw.get("icons") if isinstance(raw, dict) else None
        if isinstance(icons, dict):
            return icons
    except Exception as e:  # noqa: BLE001
        log.warning("[icon_search] catalog load failed: %s", e)
    return {}


@lru_cache(maxsize=256)
def search_icons(query: str, limit: int = _MAX_RESULTS) -> list[str]:
    """Return icon names whose name/tags/categories match the query keywords.

    Matching is per-keyword token match against the icon id (kebab-cased) and
    every tag/category entry. A single query word like ``launch`` or ``book``
    returns the strongest matches first (name match scores higher than tag
    match). Deterministic — the same query always returns the same shortlist.
    """
    icons = _load_catalog()
    if not icons:
        return []

    tokens = [t for t in re.split(r"[^a-z0-9]+", (query or "").lower()) if t]
    if not tokens:
        return []

    def _score(name: str, meta: dict) -> int:
        score = 0
        id_tokens = set(re.split(r"-", name))
        for t in tokens:
            if t in id_tokens or t in name:
                score += 5
            if any(t in tag.lower() for tag in meta.get("tags", [])):
                score += 3
            if any(t in cat.lower() for cat in meta.get("categories", [])):
                score += 2
        return score

    scored = [(name, _score(name, meta)) for name, meta in icons.items()]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [name for name, s in scored if s > 0][:limit]


def format_icon_shortlist(names: list[str]) -> str:
    """Human/machine-readable shortlist shown to the LLM after icon_search."""
    if not names:
        return (
            "No icons found for those keywords. Try broader, single-word terms "
            "(e.g. 'growth', 'book', 'code') — or decline icon motifs."
        )
    lines = ["Icon motif candidates (reference by name):"]
    for i, name in enumerate(names):
        lines.append(f"[{i}] {name}")
    return "\n".join(lines)


def icon_exists(name: str) -> bool:
    """True if ``name`` is a known icon in the vendored catalog."""
    return name in _load_catalog()


ICON_SEARCH_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "icon_search",
        "description": (
            "Search the vendored line-icon library for content-relevant motifs. "
            "Pass 1-3 short keywords (e.g. 'launch rocket', 'book writing'). "
            "Returns a numbered shortlist of icon names. Use these names in an "
            "illustrate call with style='compose' to compose a scene. Call again "
            "with different keywords if the shortlist is weak."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": (
                        "1-3 short keywords matching the post's subject (e.g. "
                        "'launch rocket', 'growth chart')."
                    ),
                },
            },
            "required": ["keywords"],
        },
    },
}


__all__ = [
    "ICON_SEARCH_TOOL",
    "format_icon_shortlist",
    "icon_exists",
    "icons_catalog_path",
    "search_icons",
]
