"""Design instruction loader — reads compositional constraints from YAML.

Design instructions define grid, type scale, decoration rules, shadow,
image, and math constraints that shape how the designer agent composes
each card. Values are brand-configurable in design-instruction.yaml.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULT_DESIGN_INSTRUCTION: dict = {
    "grid": {
        "columns": 12,
        "margin": "6%",
        "gutter": "2%",
        "baseline": "8px",
        "max_violations": 1,
    },
    "type_scale": {
        "base": "16px",
        "ratio": 1.333,
        "sizes_px": [12, 16, 21, 28, 38, 51, 68],
        "weights": {
            "headline": [700, 800, 900],
            "body": [400, 500],
        },
        "headline_tracking": "-0.02em",
        "headline_leading": "0.95",
        "body_leading": "1.5",
        "uppercase_tracking": "0.10em",
    },
    "decoration": {
        "unicode_symbols": False,
        "gradients_as_bg": False,
        "glassmorphism": False,
        "badges_pills": False,
        "decorative_buttons": False,
        "max_border_radius": "4px",
        "corner_marks": False,
        "dividers": "hairline",
    },
    "shadow": {
        "style": "hard_offset",
        "default": "4px 4px 0 var(--color-text)",
    },
    "images": {
        "default_crop": "sharp_rect",
        "text_overlay_fade": "targeted",
    },
    "math": {
        "dedicated_grid_block": True,
        "fallback": "reduce_headline",
    },
}


def load_design_instruction(path: str | Path) -> dict:
    """Load design instructions from YAML, falling back to defaults."""
    path = Path(path)
    if not path.exists():
        log.info("[design_instruction] File not found: %s — using defaults", path)
        return dict(DEFAULT_DESIGN_INSTRUCTION)

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            merged = _deep_merge(dict(DEFAULT_DESIGN_INSTRUCTION), raw)
            return merged
        log.warning("[design_instruction] Invalid format — using defaults")
        return dict(DEFAULT_DESIGN_INSTRUCTION)
    except Exception as e:
        log.warning("[design_instruction] Failed to load %s: %s", path, e)
        return dict(DEFAULT_DESIGN_INSTRUCTION)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, recursing on dict values."""
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def format_design_instruction_block(config: dict) -> str:
    """Format design instruction YAML into a human-readable prompt block."""
    g = config.get("grid", {})
    ts = config.get("type_scale", {})
    dec = config.get("decoration", {})
    sh = config.get("shadow", {})
    img_rules = config.get("images", {})
    math_rules = config.get("math", {})

    def _yn(val: bool) -> str:
        return "ALLOWED" if val else "FORBIDDEN"

    lines = [
        "DESIGN SYSTEM — COMPOSITION RULES",
        "",
        "--- GRID ---",
        f"  {g.get('columns', 12)}-column grid",
        f"  Margin: {g.get('margin', '6%')} each side",
        f"  Gutter: {g.get('gutter', '2%')} between columns",
        f"  Baseline unit: {g.get('baseline', '8px')}",
        f"  Max deliberate grid violations per card: {g.get('max_violations', 1)}",
        "",
        "--- TYPE SCALE (locked — use only these sizes) ---",
        f"  Base: {ts.get('base', '16px')}, ratio {ts.get('ratio', 1.333)}",
        f"  Available sizes (px): {', '.join(str(s) for s in ts.get('sizes_px', []))}",
        f"  Allowed weights — headline: {ts.get('weights', {}).get('headline', [])}",
        f"  Allowed weights — body/support: {ts.get('weights', {}).get('body', [])}",
        f"  Headline tracking: {ts.get('headline_tracking', '-0.02em')}",
        f"  Headline leading: {ts.get('headline_leading', '0.95')}",
        f"  Body leading: {ts.get('body_leading', '1.5')}",
        f"  Uppercase text: reserved for labels/eyebrows only",
        f"  Uppercase tracking: {ts.get('uppercase_tracking', '0.10em')}",
        "",
        "--- DECORATION ---",
        f"  Unicode symbols: {_yn(dec.get('unicode_symbols', False))}",
        f"  Gradients as backgrounds: {_yn(dec.get('gradients_as_bg', False))}",
        f"  Glassmorphism (backdrop-filter blur): {_yn(dec.get('glassmorphism', False))}",
        f"  Badges/pills: {_yn(dec.get('badges_pills', False))}",
        f"  Decorative button shapes: {_yn(dec.get('decorative_buttons', False))}",
        f"  Max border radius: {dec.get('max_border_radius', '4px')}",
        f"  Dividers: {dec.get('dividers', 'hairline')} — 1-2px solid rule, no gradients",
        f"  Corner crop marks: {_yn(dec.get('corner_marks', False))}",
        "",
        "--- SHADOW ---",
        f"  Style: {sh.get('style', 'hard_offset')}",
        f"  Default: {sh.get('default', '4px 4px 0 var(--color-text)')}",
        "",
        "--- IMAGES ---",
        f"  Default crop: {img_rules.get('default_crop', 'sharp_rect')}",
        f"  Text-over-image fade: {img_rules.get('text_overlay_fade', 'targeted')}",
        "",
        "--- MATH & DIAGRAMS ---",
        f"  Dedicated grid block: {'yes' if math_rules.get('dedicated_grid_block', True) else 'no'}",
        f"  If math/diagram content overflows canvas: {math_rules.get('fallback', 'reduce_headline')}",
    ]
    return "\n".join(lines)


def substitute_image_keys(html: str, images: list[dict]) -> str:
    """Replace data-image-key markers with base64-embedded <img> tags.

    The designer places <img data-image-key="0"> or any element with
    data-image-key="N" in the layout. This function:
      - If it's already an <img> tag: sets or replaces the src attribute
      - If it's any other element: replaces the entire element with
        <img src="data:..." data-image-key="N" alt="...">

    Args:
        html: The HTML document with data-image-key markers.
        images: List of dicts with 'data', 'alt', 'mime' keys.

    Returns:
        HTML with image src attributes populated.
    """
    if not images:
        return html

    keyed = {}
    for idx, img in enumerate(images):
        b64 = img.get("data")
        mime = img.get("mime", "image/png")
        alt = img.get("alt", "")
        if b64:
            keyed[str(idx)] = {
                "src": f"data:{mime};base64,{b64}",
                "alt": alt,
            }

    if not keyed:
        return html

    def _replace_img(match):
        full_match = match.group(0)
        key = _extract_image_key(full_match)
        info = keyed.get(key)
        if not info:
            return full_match
        if full_match.lstrip().startswith("<img"):
            # Strip any existing src attribute (including malformed inline URLs)
            # Matches src="..." src='...' or src=...unquoted up to >
            full_match = re.sub(
                r'\s+src\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
                "",
                full_match,
                count=1,
            )
            full_match = full_match.replace("<img", f'<img src="{info["src"]}"', 1)
            return full_match
        alt = info["alt"]
        return f'<img src="{info["src"]}" data-image-key="{key}" alt="{alt}" style="width:100%;height:auto;object-fit:cover"/>'

    # Pass 1: full elements with closing tags (span, div, etc.)
    html = re.sub(
        r'<[a-zA-Z]+[^>]*data-image-key=["\'](\d+)["\'][^>]*>.*?</[a-zA-Z]+>',
        _replace_img,
        html,
        flags=re.DOTALL,
    )
    # Pass 2: self-closing or void elements (img, br, etc.)
    html = re.sub(
        r'<[a-zA-Z]+[^>]*data-image-key=["\'](\d+)["\'][^>]*/?>',
        _replace_img,
        html,
    )
    return html


def _extract_image_key(tag: str) -> str:
    """Extract the data-image-key value from an img tag."""
    m = re.search(r'data-image-key=["\'](\d+)["\']', tag)
    return m.group(1) if m else ""
