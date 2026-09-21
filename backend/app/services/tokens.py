"""Design token loader — reads CSS variable → value mappings from YAML.

Tokens define brand colors, fonts, and spacing for the design system.
"""

from __future__ import annotations

import logging
import re
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
    "--font-weight-display": "700",
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
    "--color-accent": "optional single accent hue for emphasis — defined only for non-monochrome design languages",
    "--color-accent-secondary": "optional secondary accent hue — used with --color-accent only",
    "--font-sans": "interface sans — Inter (category, metadata, handle only)",
    "--font-display": "signature display typeface — for the headline ONLY",
    "--font-serif": "editorial serif text face — for the subhead and body copy ONLY",
    "--font-weight-display": "headline weight for the display face — templates read it; light brands set 300",
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


# Token value sanitizing
#
# Token values are injected verbatim into a <style> block, so a value like
# ``red}</style><script>`` (or an empty LLM value producing ``--x: ;``) must
# never reach the page. Each family of variables gets a conservative grammar;
# unknown variables fall back to a deny-list of CSS/HTML breakout sequences.

_NUM = r"-?(?:\d+\.?\d*|\.\d+)"
_LENGTH_RE = re.compile(
    rf"^(?:0|{_NUM}(?:px|rem|em|%|vw|vh|vmin|vmax|pt|ch|ex)?)$", re.IGNORECASE
)
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_COLOR_FN_RE = re.compile(
    rf"^(?:rgba?|hsla?)\(\s*{_NUM}(?:%|deg)?"
    rf"(?:\s*[,/]?\s*{_NUM}(?:%|deg)?){{2,3}}\s*\)$",
    re.IGNORECASE,
)
_NAMED_COLOR_RE = re.compile(r"^[A-Za-z]{3,30}$")
_VAR_REF_RE = re.compile(r"^var\(--[A-Za-z0-9-]+\)$")
_FONT_FAMILY_RE = re.compile(r"^[A-Za-z0-9 '\"-]+$")
_SHADOW_ITEM_RE = re.compile(r"(?:rgba?|hsla?)\([^()]*\)|[^\s,()]+", re.IGNORECASE)
_UNSAFE_SUBSTRINGS = (";", "{", "}", "<", ">", "\\", "/*", "url(", "expression")
_SIZE_PREFIXES = (
    "--radius", "--space", "--spacing", "--size", "--gap", "--margin",
    "--padding", "--width", "--height", "--font-size", "--font-weight",
    "--line-height", "--leading", "--tracking", "--letter-spacing",
)


def _is_color(value: str) -> bool:
    return bool(
        _HEX_RE.match(value)
        or _COLOR_FN_RE.match(value)
        or _NAMED_COLOR_RE.match(value)
        or _VAR_REF_RE.match(value)
    )


def _is_font_stack(value: str) -> bool:
    families = [f.strip() for f in value.split(",")]
    return all(f and _FONT_FAMILY_RE.match(f) for f in families)


def _is_size(value: str) -> bool:
    parts = value.split()
    return 1 <= len(parts) <= 4 and all(
        _LENGTH_RE.match(p) or _VAR_REF_RE.match(p) for p in parts
    )


def _is_shadow(value: str) -> bool:
    if value.lower() == "none":
        return True
    items = _SHADOW_ITEM_RE.findall(value)
    if not items or _SHADOW_ITEM_RE.sub("", value).strip(" \t,"):
        return False
    return all(
        i.lower() == "inset" or _LENGTH_RE.match(i) or _is_color(i) for i in items
    )


def sanitize_token_value(var: str, value) -> str | None:
    """Return a safe, trimmed token value — or None when it must be dropped.

    ``--color-*`` accepts hex / rgb[a]() / hsl[a]() / a named color word /
    ``var(--x)``; ``--font-*`` a comma-separated family stack; sizes
    (``--radius-*``, ``--space-*``, ``--font-size-*``, ...) one to four CSS
    lengths/numbers; ``--shadow-*`` ``none`` or a conservative box-shadow.
    Any other variable is accepted unless it carries a CSS/HTML breakout
    sequence. Empty values are dropped (they would emit ``--x: ;``).
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(s in value.lower() for s in _UNSAFE_SUBSTRINGS):
        return None
    var = (var or "").lower()
    if var.startswith("--color"):
        ok = _is_color(value)
    elif var.startswith(_SIZE_PREFIXES):
        ok = _is_size(value)
    elif var.startswith("--font"):
        ok = _is_font_stack(value)
    elif var.startswith("--shadow"):
        ok = _is_shadow(value)
    else:
        ok = "\n" not in value and "\r" not in value
    return value if ok else None


def invalid_token_issues(tokens: dict) -> list[str]:
    """Human-readable problems for token values that fail sanitizing."""
    issues: list[str] = []
    for var, value in (tokens or {}).items():
        if not isinstance(var, str) or not isinstance(value, str):
            continue
        if sanitize_token_value(var, value) is None:
            shown = value if len(value) <= 60 else value[:57] + "..."
            issues.append(f"token {var} has an invalid value {shown!r}")
    return issues


# WCAG contrast helpers (hex colors only — other formats are left untouched).

def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        return None
    h = value.strip().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    h = h[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float | None:
    """WCAG 2.x contrast ratio of two hex colors (None if either isn't hex)."""
    a, b = _hex_to_rgb(fg), _hex_to_rgb(bg)
    if a is None or b is None:
        return None
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mix_hex(a: str, b: str, t: float) -> str:
    ra, rb = _hex_to_rgb(a), _hex_to_rgb(b)
    assert ra is not None and rb is not None
    return "#" + "".join(
        f"{round(x + (y - x) * t):02X}" for x, y in zip(ra, rb, strict=True)
    )


def enforce_text_contrast(tokens: dict[str, str]) -> dict[str, str]:
    """Return tokens with unreadable text colors replaced (hex values only).

    ``--color-text`` on ``--color-bg`` and ``--color-text-inverted`` on
    ``--color-bg-inverted`` must reach 4.5:1, else they fall back to black or
    white (whichever reads on that ground). ``--color-text-secondary`` must
    reach 3:1 on ``--color-bg``, else it is mixed toward ``--color-text``.
    """
    out = dict(tokens)
    for text_var, bg_var in (
        ("--color-text", "--color-bg"),
        ("--color-text-inverted", "--color-bg-inverted"),
    ):
        bg = out.get(bg_var, DEFAULT_TOKEN_VALUES[bg_var])
        ratio = contrast_ratio(out.get(text_var, ""), bg)
        if ratio is None or ratio >= 4.5:
            continue
        on_black = contrast_ratio("#000000", bg) or 0.0
        on_white = contrast_ratio("#FFFFFF", bg) or 0.0
        fallback = "#000000" if on_black >= on_white else "#FFFFFF"
        log.info(
            "[tokens] %s contrast %.2f on %s < 4.5 — using %s",
            text_var, ratio, bg_var, fallback,
        )
        out[text_var] = fallback

    secondary = out.get("--color-text-secondary", "")
    bg = out.get("--color-bg", DEFAULT_TOKEN_VALUES["--color-bg"])
    text = out.get("--color-text", DEFAULT_TOKEN_VALUES["--color-text"])
    ratio = contrast_ratio(secondary, bg)
    if ratio is not None and ratio < 3.0 and _hex_to_rgb(text) is not None:
        fixed = text
        for step in range(1, 11):
            candidate = _mix_hex(secondary, text, step / 10)
            if (contrast_ratio(candidate, bg) or 0.0) >= 3.0:
                fixed = candidate
                break
        log.info(
            "[tokens] --color-text-secondary contrast %.2f < 3.0 — using %s",
            ratio, fixed,
        )
        out["--color-text-secondary"] = fixed
    return out


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
    """Build a CSS :root block with all token values for injection into HTML.

    Defense in depth: tokens whose name or value fails sanitizing are dropped
    (never emitted raw into the ``<style>`` block).
    """
    lines = [":root {"]
    for var, raw in tokens.items():
        value = sanitize_token_value(var, raw)
        if (
            value is None
            or not isinstance(var, str)
            or not re.fullmatch(r"--[A-Za-z0-9_-]+", var)
        ):
            log.debug("[tokens] dropping invalid token %r: %r", var, raw)
            continue
        if var.startswith("--font") and not var.startswith(_SIZE_PREFIXES):
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
