"""Curated Google Fonts pool loader — agentic + manual typeface selection."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.config import get_settings

log = logging.getLogger(__name__)


def fonts_pool_path() -> Path:
    return Path(get_settings().design_system_dir) / "fonts.yaml"


def load_font_pool() -> list[dict]:
    """Load the curated font pool → list of {family, role, weights, style}."""
    path = fonts_pool_path()
    if not path.exists():
        return []
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        fonts = raw.get("fonts", []) if isinstance(raw, dict) else []
        if isinstance(fonts, list):
            return [f for f in fonts if isinstance(f, dict) and f.get("family")]
    except Exception as e:
        log.warning("[fonts] Failed to load font pool %s: %s", path, e)
    return []


def font_pool_for_prompt() -> str:
    """Format the pool for the brand_tokens agent (families + roles + weights)."""
    lines = []
    for f in load_font_pool():
        fam = f.get("family", "")
        role = f.get("role", "sans")
        weights = ", ".join(str(w) for w in f.get("weights", [])) or "400"
        lines.append(f"  {fam} [{role}, weights {weights}]")
    return "\n".join(lines) or "  (none)"
