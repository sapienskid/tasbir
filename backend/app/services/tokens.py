"""Design token loader — reads CSS variable → value mappings from YAML.

Tokens define brand colors, fonts, and spacing for the design system.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULT_TOKEN_VALUES: dict[str, str] = {
    "--color-bg": "#0a0a1a",
    "--color-bg-secondary": "#141428",
    "--color-text": "#e8e8f0",
    "--color-text-secondary": "#9494b8",
    "--color-primary": "#5b8def",
    "--color-secondary": "#7c6df0",
    "--color-accent": "#48c6ef",
    "--color-border": "#2a2a4a",
    "--font-sans": "Inter, system-ui, sans-serif",
    "--font-serif": "Merriweather, Georgia, serif",
    "--font-mono": "JetBrains Mono, Fira Code, monospace",
    "--radius-sm": "4px",
    "--radius-md": "8px",
    "--shadow-md": "0 4px 12px rgba(0,0,0,0.4)",
}


def load_brand(path: str | Path) -> dict:
    """Load brand profile from a YAML file.

    Returns dict with keys: brand (name, tagline, mission, story, url, social),
    overrides (badge, tagline). Falls back to minimal defaults.
    """
    path = Path(path)
    if not path.exists():
        log.info("[tokens] Brand file not found: %s — using minimal defaults", path)
        return {"brand": {"name": "Brand", "tagline": "", "mission": "", "story": "", "url": "", "social": {}}, "overrides": {}}

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            return raw
        log.warning("[tokens] Invalid brand format — using defaults")
        return {"brand": {"name": "Brand"}, "overrides": {}}
    except Exception as e:
        log.warning("[tokens] Failed to load brand: %s — using defaults", e)
        return {"brand": {"name": "Brand"}, "overrides": {}}


def load_tokens(path: str | Path) -> dict[str, str]:
    """Load design tokens from a YAML file.

    Falls back to DEFAULT_TOKEN_VALUES if the file doesn't exist
    or can't be parsed.
    """
    path = Path(path)
    if not path.exists():
        log.info("[tokens] Token file not found: %s — using defaults", path)
        return dict(DEFAULT_TOKEN_VALUES)

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            merged = dict(DEFAULT_TOKEN_VALUES)
            merged.update(raw)
            return merged
        log.warning("[tokens] Invalid token format in %s — using defaults", path)
        return dict(DEFAULT_TOKEN_VALUES)
    except Exception as e:
        log.warning("[tokens] Failed to load %s: %s — using defaults", path, e)
        return dict(DEFAULT_TOKEN_VALUES)


# CSS variable injection helper

def build_css_variable_block(tokens: dict[str, str]) -> str:
    """Build a CSS :root block with all token values for injection into HTML."""
    lines = [":root {"]
    for var, value in tokens.items():
        lines.append(f"  {var}: {value};")
    lines.append("}")
    return "\n".join(lines)


def inject_tokens_into_html(html: str, tokens: dict[str, str]) -> str:
    """Inject CSS variable definitions into an HTML document's <head>."""
    css_block = build_css_variable_block(tokens)
    style_tag = f"<style>\n{css_block}\n</style>"

    if "<head>" in html:
        return html.replace("<head>", f"<head>\n{style_tag}", 1)
    if "</head>" in html:
        return html.replace("</head>", f"{style_tag}\n</head>", 1)
    if "<body" in html:
        idx = html.index("<body")
        return html[:idx] + style_tag + "\n" + html[idx:]

    return style_tag + "\n" + html
