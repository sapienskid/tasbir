"""Design token loader — reads CSS variable → value mappings from YAML.

Tokens define brand colors, fonts, and spacing for the design system.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULT_TOKEN_VALUES: dict[str, str] = {
    "--color-bg": "#0f172a",
    "--color-bg-secondary": "#1e293b",
    "--color-text": "#ffffff",
    "--color-text-secondary": "#94a3b8",
    "--color-primary": "#667eea",
    "--color-secondary": "#764ba2",
    "--color-accent": "#6366f1",
    "--color-border": "#334155",
    "--font-sans": "Inter, sans-serif",
    "--font-serif": "Instrument Serif, serif",
    "--font-mono": "JetBrains Mono, monospace",
    "--radius-sm": "4px",
    "--radius-md": "8px",
    "--shadow-md": "0 4px 6px rgba(0,0,0,0.3)",
}


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
