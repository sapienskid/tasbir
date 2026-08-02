"""Design token loader — reads CSS variable → value mappings from YAML.

Tokens define brand colors, fonts, and spacing for the design system.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULT_TOKEN_VALUES: dict[str, str] = {
    "--color-bg": "#FFFFFF",
    "--color-bg-inverted": "#000000",
    "--color-text": "#000000",
    "--color-text-inverted": "#FFFFFF",
    "--color-text-secondary": "#6E6E6E",
    "--color-text-tertiary": "#B0B0B0",
    "--color-border": "#D9D9D9",
    "--color-border-inverted": "#2A2A2A",
    "--font-sans": "Inter, 'Helvetica Neue', Arial, sans-serif",
    "--font-display": "Space Grotesk, Inter, sans-serif",
    "--font-serif": "Source Serif 4, Georgia, serif",
    "--radius-sm": "0px",
    "--radius-md": "0px",
    "--shadow-md": "none",
}

# Semantic roles for each CSS variable — shown to the LLM as the var NAME plus
# role description. Never includes the actual hex value (design tokens stay
# out of prompts). This is what lets the designer know --color-bg is a light
# ground without ever seeing "#FFFFFF".
SEMANTIC_VAR_ROLES: dict[str, str] = {
    "--color-bg": "page background — LIGHT ground (white)",
    "--color-bg-inverted": "page background — BLACK ground (inverted)",
    "--color-text": "primary ink — BLACK (on light ground)",
    "--color-text-inverted": "primary ink — WHITE (on black ground)",
    "--color-text-secondary": "secondary/metadata text — mid-gray",
    "--color-text-tertiary": "tertiary text — light gray, use sparingly",
    "--color-border": "hairline rule on light ground",
    "--color-border-inverted": "hairline rule on black ground",
    "--font-sans": "interface sans — Inter (category, metadata, handle only)",
    "--font-display": "signature display typeface — for the headline and footer wordmark ONLY",
    "--font-serif": "editorial serif text face — for the subhead and body copy ONLY",
}

DEFAULT_CATEGORIES: list[dict] = [
    {"name": "PORTFOLIO", "description": "Project posts"},
    {"name": "PROJECT", "description": "Individual build/ship updates"},
    {"name": "WRITING", "description": "Blog posts"},
    {"name": "THE LIMITS No.{issue}", "description": "Newsletter posts — substitute the real issue number"},
    {"name": "NOTE", "description": "Short-form/thought posts", "ground": "black"},
]

DEFAULT_FOOTER: dict[str, str] = {"left": "", "right": ""}


# Ground → semantic-role variable convention. Lives here in the design-system
# service layer (NOT in any agent node): the designer/verifier never hardcode
# token names — they resolve them through this map, verified against the
# design system's actual token set + role descriptions.
_DEFAULT_GROUND_VARS: dict[str, dict[str, str]] = {
    "white": {
        "background": "--color-bg",
        "text": "--color-text",
        "border": "--color-border",
        "secondary": "--color-text-secondary",
    },
    "black": {
        "background": "--color-bg-inverted",
        "text": "--color-text-inverted",
        "border": "--color-border-inverted",
        "secondary": "--color-text-secondary",
    },
}


def _find_role_var(role: str, ground: str, roles: dict[str, str]) -> str:
    """Derive a ground-role variable from role descriptions (custom systems).

    Matches by the semantic words the roles already carry (e.g. ``background``
    + ``light`` for white ground, ``ink`` + ``black`` for text on black).
    Returns "" when nothing matches.
    """
    ground_words = {"white": ("light", "white"), "black": ("black", "inverted")}
    gw = ground_words.get(ground, ("light", "white"))
    role_words = {
        "background": ("background",),
        "text": ("ink", "text"),
        "border": ("border", "hairline"),
        "secondary": ("secondary",),
    }
    rw = role_words.get(role, ())
    for var, desc in roles.items():
        d = (desc or "").lower()
        if not rw or not all(w in d for w in rw):
            continue
        if any(w in d for w in gw):
            return var
    return ""


def resolve_ground_vars(
    ground: str,
    tokens: dict[str, str] | None = None,
    roles: dict[str, str] | None = None,
) -> dict[str, str]:
    """Resolve {background, text, border, secondary} variable names for a ground.

    Resolution order per role: the design-system convention name (when the
    token actually exists) → a variable derived from the DS ``token_roles``
    descriptions → the convention name as the last resort. Agents receive
    variable NAMES only — never values — and nothing is hardcoded in them.
    """
    ground = ground if ground in ("white", "black") else "white"
    tokens = tokens or {}
    roles = roles or {}
    out: dict[str, str] = {}
    for role, convention in _DEFAULT_GROUND_VARS[ground].items():
        if convention in tokens:
            out[role] = convention
        else:
            out[role] = _find_role_var(role, ground, roles) or convention
    return out


def build_css_var_reference(
    tokens: dict[str, str], roles: dict[str, str] | None = None
) -> str:
    """Build a semantic CSS-variable reference for the designer prompt.

    Lists each load-bearing variable with its role description — variable
    NAMES only, never values. ``roles`` overrides the default semantic roles
    (per-design-system token_roles).
    """
    role_map = roles or SEMANTIC_VAR_ROLES
    lines = [
        "AVAILABLE CSS VARIABLES (use ONLY these for all color/typography —",
        "never hardcode hex values or font names):",
    ]
    for var, value in tokens.items():
        role = role_map.get(var)
        if role is None:
            continue
        lines.append(f"  {var} — {role}")
    return "\n".join(lines)


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


def load_brand_design(brand_path: str | Path) -> dict:
    """Load the brand's footer + category taxonomy from brand.yaml.

    Returns {"footer": {"left", "right"}, "categories": [{name, description,
    ground?}, ...]} with defaults applied for missing sections.
    """
    data = load_brand(brand_path)
    footer = data.get("footer") or {}
    categories = data.get("categories") or DEFAULT_CATEGORIES
    return {
        "footer": {
            "left": str(footer.get("left", "") or DEFAULT_FOOTER["left"]),
            "right": str(footer.get("right", "") or DEFAULT_FOOTER["right"]),
        },
        "categories": categories if isinstance(categories, list) else DEFAULT_CATEGORIES,
    }


def category_matches(value: str, categories: list[dict]) -> bool:
    """Return True if value matches an approved category name.

    Handles the "{issue}" placeholder in names like "THE LIMITS No.{issue}"
    by matching a base prefix followed by digits.
    """
    value = (value or "").strip()
    if not value:
        return False
    upper = value.upper()
    for cat in categories:
        name = (cat.get("name") or "").strip()
        if "{issue}" in name:
            base = name.replace("{issue}", "").upper()
            suffix = upper[len(base):].strip()
            if upper.startswith(base) and suffix.isdigit():
                return True
        elif upper == name.upper():
            return True
    return False


def resolve_ground(
    campaign: dict,
    category: str,
    categories: list[dict],
    default: str = "white",
) -> str:
    """Resolve the post ground. Priority: campaign → category → default.

    Only "white" and "black" are valid (both grounds are monochrome-safe).
    """
    campaign_ground = (campaign or {}).get("ground", "")
    if campaign_ground in ("white", "black"):
        return campaign_ground

    if category:
        for cat in categories:
            if cat.get("name") and category_matches(category, [cat]):
                cat_ground = cat.get("ground")
                if cat_ground in ("white", "black"):
                    return cat_ground

    return default if default in ("white", "black") else "white"


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

def _quote_font_value(value: str) -> str:
    """Quote multi-word font family names for valid CSS.

    Chromium rejects unquoted family names like `Source Serif 4` (contains a
    number / multiple identifiers), silently falling back to the generic
    `serif`. YAML strips the surrounding quotes from token values, so we must
    re-quote any family with spaces.
    """
    families = [fam.strip() for fam in value.split(",")]
    quoted = []
    for fam in families:
        if fam and " " in fam and not (fam.startswith("'") or fam.startswith('"')):
            quoted.append(f"'{fam}'")
        else:
            quoted.append(fam)
    return ", ".join(quoted)


def build_css_variable_block(tokens: dict[str, str]) -> str:
    """Build a CSS :root block with all token values for injection into HTML."""
    lines = [":root {"]
    for var, value in tokens.items():
        if var.startswith("--font") and value:
            value = _quote_font_value(value)
        lines.append(f"  {var}: {value};")
    lines.append("}")
    return "\n".join(lines)


def _strip_root_blocks(html: str) -> str:
    """Remove `:root { ... }` selector rules, keeping the rest of the CSS.

    The designer sometimes combines the (forbidden) :root block with the real
    styles in a single <style> tag. Only the :root rule must be removed —
    deleting the whole block would strip all styling from the design.
    """
    import re
    return re.sub(r":root\s*\{[^}]*\}", "", html, flags=re.IGNORECASE)


def inject_tokens_into_html(html: str, tokens: dict[str, str]) -> str:
    """Inject CSS variable definitions into an HTML document's <head>."""
    # First strip any existing :root blocks to prevent designer overrides
    html = _strip_root_blocks(html)

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
    """Inject KaTeX CDN + auto-render for $ and $$ delimiters."""
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
        "onload=\"renderMathInElement(document.body,{"
        "delimiters:["
        "{left:'$$',right:'$$',display:true},"
        "{left:'$',right:'$',display:false}"
        "],"
        "throwOnError:false"
        '})\"></script>'
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
