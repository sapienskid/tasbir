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


# YAML loaders for platforms and campaigns

def load_platforms(path: str | Path) -> dict[str, tuple[int, int]]:
    """Load platform dimensions from platforms.yaml."""
    path = Path(path)
    if not path.exists():
        log.warning("[tokens] Platforms file not found: %s", path)
        return {}
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            result = {}
            for k, v in raw.items():
                if isinstance(v, list) and len(v) == 2:
                    result[k] = (int(v[0]), int(v[1]))
            return result
    except Exception as e:
        log.warning("[tokens] Failed to load platforms: %s", e)
    return {}


def load_campaign(name: str, campaigns_path: str | Path) -> dict:
    """Load a single campaign preset by key name."""
    path = Path(campaigns_path)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            return raw.get(name, raw.get("default", {}))
    except Exception as e:
        log.warning("[tokens] Failed to load campaign '%s': %s", name, e)
    return {}


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


def inject_katex_into_html(html: str) -> str:
    """Inject KaTeX CDN links for LaTeX rendering if math spans are present."""
    if '<span class="math"' not in html:
        return html

    katex_css = (
        '<link rel="stylesheet" '
        'href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" '
        'crossorigin="anonymous">'
    )
    katex_js = (
        '<script defer '
        'src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js" '
        'crossorigin="anonymous"></script>'
    )
    katex_auto = (
        '<script defer '
        'src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/'
        'auto-render.min.js" crossorigin="anonymous" '
        'onload="renderMathInElement(document.body,{'
        "delimiters:[{left:'$$',right:'$$',display:true},"
        "{left:'$',right:'$',display:false},"
        "{left:'\\\\\\\\[',right:'\\\\\\\\]',display:true},"
        "{left:'(',right:')',display:false}]"
        '})"></script>'
    )

    head_tag = katex_css + katex_js + katex_auto
    if "</head>" in html:
        return html.replace("</head>", f"{head_tag}\n</head>", 1)
    if "<head>" in html:
        return html.replace("<head>", f"<head>\n{head_tag}", 1)
    return html


def inject_images_into_html(html: str, images: list[dict]) -> str:
    """Inject base64-embedded images into HTML body as preloaded resources."""
    if not images:
        return html

    img_tags = []
    for img in images:
        b64 = img.get("data")
        alt = img.get("alt", "")
        placement = img.get("placement", "auto")
        style = 'style="display:none"' if placement == "background" else ""
        if b64:
            img_tags.append(f'<img src="data:image/png;base64,{b64}" '
                           f'alt="{alt}" {style}/>')

    if not img_tags:
        return html

    injected = "\n".join(img_tags)
    if "<body" in html:
        idx = html.index("<body") + 6
        end = html.index(">", idx) + 1
        return html[:end] + "\n" + injected + html[end:]

    return html
