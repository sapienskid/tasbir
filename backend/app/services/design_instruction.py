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
    "style": {
        "name": "Swiss / International Typographic Style",
        "palette": "monochrome",
        "allowed_grounds": ["white", "black"],
        "default_ground": "white",
        "accent": "none",
        "max_weights_per_family": 2,
        "shadows": False,
        "border_radius": "0px",
        "illustrations": False,
        "icons": False,
        "emoji": False,
        "gradients": False,
    },
    "type_voice": {
        "display": "Space Grotesk (var(--font-display)) is the signature display voice. Use it ONLY for the headline and the footer wordmark.",
        "serif": "Source Serif 4 (var(--font-serif)) is the editorial text voice. It carries the subhead and body copy.",
        "body": "Inter (var(--font-sans)) is the quiet interface voice — category label, metadata, and the footer handle.",
    },
    "type_scale": {
        "base_canvas_width": 1080,
        "roles": {
            "category": {"family": "sans", "size": 22, "weight": 500, "tracking": "0.12em", "case": "uppercase", "line_height": 1.2, "max_chars": 24},
            "headline": {"family": "display", "size": 76, "weight": 700, "tracking": "-0.01em", "case": "sentence", "line_height": 1.0,
                         "max_lines": {"square": 4, "portrait": 4, "story": 4, "landscape": 3}},
            "subhead": {"family": "serif", "size": 36, "weight": 400, "tracking": 0, "case": "sentence", "line_height": 1.3, "max_lines": 3, "measure_px": 600},
            "body": {"family": "serif", "size": 28, "weight": 400, "tracking": 0, "case": "sentence", "line_height": 1.4, "max_lines": 5, "min_size": 24, "measure_px": 600},
            "metadata": {"family": "sans", "size": 20, "weight": 500, "tracking": "0.08em", "case": "uppercase", "line_height": 1.2, "min_size": 18},
        },
    },
    "spacing": {
        "unit": 8,
        "scale": [8, 16, 24, 32, 48, 64, 96, 128],
        "margin": 64,
        "margin_story_vertical": 160,
        "gap_category_label": 24,
        "gap_headline_body": 32,
        "gap_footer_rule": 24,
        "gap_section": 96,
    },
    "format_families": {
        "instagram-square": "square",
        "instagram-portrait": "portrait",
        "instagram-story": "story",
        "linkedin-post": "landscape",
        "twitter-card": "landscape",
        "facebook-post": "landscape",
        "pinterest-pin": "portrait",
    },
    "formats": {
        "square": {"label": "Square post", "margins": [64, 64, 64, 64], "footer_y": 1016},
        "portrait": {"label": "Portrait post (4:5)", "margins": [64, 64, 64, 64]},
        "story": {"label": "Story/Reel (9:16)", "margins": [160, 64, 160, 64], "headline_zone": [160, 700], "footer_y": 1760},
        "landscape": {"label": "Landscape (16:9)", "margins": [64, 64, 64, 64]},
    },
    "footer": {
        "enabled": True,
        "rule": "1px hairline",
        "gap": 24,
        "style": "metadata",
        "wordmark": {
            "family": "display",
            "size": 24,
            "weight": 500,
            "tracking": "-0.01em",
            "case": "uppercase",
        },
    },
    "images": {
        "default_crop": "sharp_rect",
        "text_overlay_fade": "targeted",
    },
    "math": {
        "dedicated_grid_block": True,
        "fallback": "reduce_headline",
    },
    "do_dont": {
        "do": [
            "Left-align everything, always",
            "Use weight and size for hierarchy — never color",
            "THREE VOICES: display (Space Grotesk) for headline + wordmark; serif (Source Serif 4) for subhead + body; sans (Inter) for category, metadata, handle",
            "Constrain subhead/body copy to the measure (~600px at 1080) — never full-width lines",
            "Keep hairline rules exactly 1px: hairline on white-ground, hairline-inverted on black-ground",
            "Use generous whitespace — flexible space is intentional, not empty by accident",
        ],
        "dont": [
            "No hue of any kind — not even 'just a little' blue, amber, or green",
            "No icons, illustrations, or motifs of any kind",
            "No centering",
            "No more than 2 weights per family (Space Grotesk 500+700, Source Serif 4 400, Inter 500)",
            "Never use the display face for body, subhead, category, or metadata text",
            "Never use the serif for headlines, category labels, metadata, or the wordmark",
            "No shadows, gradients, borders-with-radius, or any softening effect",
            "No third color, ever — if a post needs emphasis, use weight or size",
        ],
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


def _yn(val: bool) -> str:
    return "ALLOWED" if val else "FORBIDDEN"


def scaled_type_sizes(config: dict, canvas_width: int) -> dict[str, dict]:
    """Return type roles with sizes scaled to the given canvas width."""
    ts = config.get("type_scale", {})
    base_width = int(ts.get("base_canvas_width", 1080))
    scale = canvas_width / base_width if base_width else 1.0
    roles = ts.get("roles", {})
    out: dict[str, dict] = {}
    for role, r in roles.items():
        out[role] = dict(r)
        out[role]["size"] = round(int(r.get("size", 28)) * scale)
        if r.get("measure_px"):
            out[role]["measure_px"] = round(int(r["measure_px"]) * scale)
        ml = r.get("max_lines")
        if isinstance(ml, dict):
            out[role]["max_lines"] = ml
    return out


_FAMILY_LABEL = {
    "display": "var(--font-display) — Space Grotesk (signature display voice)",
    "serif": "var(--font-serif) — Source Serif 4 (editorial serif text voice)",
    "sans": "var(--font-sans) — Inter (interface sans voice)",
}


def _family_name(r: dict) -> str:
    fam = r.get("family", "sans")
    return _FAMILY_LABEL.get(fam, f"var(--font-{fam})")


_FONT_TOKENS = ("--font-sans", "--font-display", "--font-serif")


def _google_family(font_value: str) -> str:
    """Extract the Google Fonts family name from a --font-* token value."""
    family = re.split(r"[,'\"]", font_value)[0].strip()
    return family.replace(" ", "+") if family else ""


def build_google_fonts_link(tokens: dict, config: dict) -> str:
    """Build a Google Fonts <link> for every family in the type system.

    Each family's weights come from the type-scale roles (matched by the
    role's `family` field) plus the footer wordmark. Only families actually
    referenced are loaded.
    """
    roles = config.get("type_scale", {}).get("roles", {})
    wm = config.get("footer", {}).get("wordmark", {})

    weights: dict[str, set[str]] = {}
    for r in roles.values():
        fam = r.get("family", "sans")
        token = f"--font-{fam}" if fam in ("sans", "display", "serif") else "--font-sans"
        weights.setdefault(token, set())
        w = r.get("weight")
        if isinstance(w, (int, str)):
            weights[token].add(str(w))
    wm_token = f"--font-{wm.get('family', 'display')}"
    weights.setdefault(wm_token, set())
    if wm.get("weight"):
        weights[wm_token].add(str(wm["weight"]))

    families = []
    for token in _FONT_TOKENS:
        fam = _google_family(tokens.get(token, ""))
        if not fam:
            continue
        wght = ";".join(sorted(weights.get(token, {"400", "700"})))
        families.append(f"family={fam}:wght@{wght}")

    if not families:
        families = ["family=Inter:wght@400;500;700"]

    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'<link href="https://fonts.googleapis.com/css2?{"&".join(families)}&display=swap" '
        'rel="stylesheet">'
    )


def inject_fonts_into_html(html: str, link: str) -> str:
    """Guarantee the Google Fonts <link> is present in <head>.

    The designer is asked to include it, but the system injects it anyway so
    fonts always load regardless of LLM output. No-ops if already present.
    """
    if "fonts.googleapis.com/css2" in html:
        return html
    if "</head>" in html:
        return html.replace("</head>", f"{link}\n</head>", 1)
    if "<head>" in html:
        return html.replace("<head>", f"<head>\n{link}", 1)
    return f"{link}\n{html}"


def format_design_instruction_block(config: dict) -> str:
    """Format design instruction YAML into a human-readable prompt block."""
    st = config.get("style", {})
    ts = config.get("type_scale", {})
    sp = config.get("spacing", {})
    ft = config.get("footer", {})
    tv = config.get("type_voice", {})
    dd = config.get("do_dont", {})
    img_rules = config.get("images", {})
    math_rules = config.get("math", {})

    lines = [
        f"DESIGN SYSTEM — {st.get('name', 'SWISS / INTERNATIONAL TYPOGRAPHIC STYLE').upper()}",
        "",
        "--- PALETTE (STRICTLY MONOCHROME) ---",
        f"  Palette: {st.get('palette', 'monochrome')} — pure black/white/gray only, NO hue ever",
        f"  Allowed grounds: {', '.join(st.get('allowed_grounds', ['white', 'black']))}",
        f"  Max weights per family: {st.get('max_weights_per_family', 2)} (Space Grotesk 500+700, Source Serif 4 400, Inter 500)",
        f"  Shadows: {_yn(st.get('shadows', False))}",
        f"  Border radius: {st.get('border_radius', '0px')} — no rounded corners",
        f"  Illustrations/icons: {_yn(st.get('illustrations', False))}",
        f"  Gradients: {_yn(st.get('gradients', False))}",
        "",
        "--- TYPE VOICE (THREE FAMILIES — READ THIS) ---",
    ]
    if tv.get("display"):
        lines.append(f"  DISPLAY: {tv['display']}")
    if tv.get("serif"):
        lines.append(f"  SERIF: {tv['serif']}")
    if tv.get("body"):
        lines.append(f"  SANS: {tv['body']}")

    lines += [
        "",
        "--- TYPE SCALE (sizes at 1080px canvas width; scale by width/1080) ---",
    ]

    roles = ts.get("roles", {})
    for role, r in roles.items():
        tracking = r.get("tracking", 0)
        tracking = f"{tracking}em" if isinstance(tracking, (int, float)) else tracking
        measure = r.get("measure_px")
        measure_txt = f" · max-width {measure}px" if measure else ""
        lines.append(
            f"  {role.upper():10s} {_family_name(r)} · {r.get('size', 28)}px · "
            f"weight {r.get('weight', 400)} · tracking {tracking or '0'} · "
            f"{r.get('case', 'sentence')} · line-height {r.get('line_height', 1.3)}{measure_txt}"
        )

    wm = ft.get("wordmark", {})
    lines += [
        "",
        "--- SPACING (8px base grid — every value a multiple of 8) ---",
        f"  Scale: {', '.join(str(s) for s in sp.get('scale', []))}",
        f"  Canvas margin: {sp.get('margin', 64)}px on every edge",
        f"  Story top/bottom margin: {sp.get('margin_story_vertical', 160)}px",
        f"  Category → headline gap: {sp.get('gap_category_label', 24)}px",
        f"  Headline → body gap: {sp.get('gap_headline_body', 32)}px",
        f"  Rule → footer gap: {sp.get('gap_footer_rule', 24)}px",
        "",
        "--- FOOTER (every format) ---",
        f"  {ft.get('rule', '1px hairline')} above footer, {ft.get('gap', 24)}px gap",
        "  Left: brand NAME as a signature wordmark — display face, tight tracking,",
        f"        {wm.get('size', 24)}px · weight {wm.get('weight', 500)} · tracking {wm.get('tracking', '-0.01em')} · uppercase",
        "  Right: @handle in metadata style (Inter, tracked uppercase, secondary gray)",
        "  No logo, no mark, no icon — typography is the signature.",
        "",
        "--- DO ---",
    ]
    for d in dd.get("do", []):
        lines.append(f"  • {d}")
    lines.append("")
    lines.append("--- DON'T ---")
    for d in dd.get("dont", []):
        lines.append(f"  • {d}")

    lines += [
        "",
        "--- IMAGES ---",
        f"  Default crop: {img_rules.get('default_crop', 'sharp_rect')} (no rounded corners)",
        f"  Text-over-image fade: {img_rules.get('text_overlay_fade', 'targeted')}",
        "",
        "--- MATH ---",
        f"  Dedicated grid block: {'yes' if math_rules.get('dedicated_grid_block', True) else 'no'}",
        f"  If math overflows canvas: {math_rules.get('fallback', 'reduce_headline')}",
    ]
    return "\n".join(lines)


def format_format_layout_block(
    config: dict,
    format_id: str,
    width: int,
    height: int,
) -> str:
    """Per-format layout rules derived from design-instruction.yaml."""
    ff = config.get("format_families", {})
    family = ff.get(format_id, "square")
    fm = config.get("formats", {})
    family_cfg = fm.get(family, {})
    ts = config.get("type_scale", {})
    base_width = int(ts.get("base_canvas_width", 1080))
    scale = width / base_width if base_width else 1.0
    margins = family_cfg.get("margins", [64, 64, 64, 64])

    lines = [
        f"FORMAT LAYOUT — {format_id} ({width}x{height}px) · family: {family}",
        f"  Canvas: EXACTLY {width}px × {height}px — zero scrollbars, zero overflow",
        f"  Margins: top {margins[0]}px · right {margins[1]}px · bottom {margins[2]}px · left {margins[3]}px",
        f"  Type scale factor: ×{round(scale, 3)} (base {base_width}px canvas)",
    ]
    if "footer_y" in family_cfg:
        lines.append(f"  Footer rule baseline: y≈{family_cfg['footer_y']}px (bottom-anchored)")
    if "headline_zone" in family_cfg:
        hz = family_cfg["headline_zone"]
        lines.append(f"  Headline zone: y {hz[0]}–{hz[1]}px (upper third)")

    scaled = scaled_type_sizes(config, width)
    lines.append("  Scaled role sizes (px):")
    for role, r in scaled.items():
        ml = r.get("max_lines")
        ml_txt = ""
        if isinstance(ml, dict):
            ml_txt = f" · max {ml.get(family, 4)} lines"
        measure = r.get("measure_px")
        measure_txt = f" · max-width {measure}px" if measure else ""
        lines.append(
            f"    {role.upper():10s} {_family_name(r)} · {r.get('size', 28)}px · "
            f"weight {r.get('weight', 400)} · tracking "
            f"{r.get('tracking', 0) if r.get('tracking') else 0} · {r.get('case', 'sentence')}"
            f"{ml_txt}{measure_txt}"
        )

    return "\n".join(lines)


def pick_layout_archetype(config: dict, seed: str) -> tuple[str, str]:
    """Deterministically pick a layout archetype from the config.

    The seed (e.g. title + format) makes the choice stable for the same input
    but different across posts, so layouts vary without breaking reproducibility.
    """
    import hashlib

    archetypes = config.get("layout_archetypes", {})
    if not archetypes:
        return "editorial-stack", ""
    keys = list(archetypes.keys())
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    key = keys[int(digest, 16) % len(keys)]
    desc = archetypes.get(key, {}).get("description", "")
    return key, desc


def format_layout_archetype_block(key: str, description: str) -> str:
    """Human-readable layout archetype block for the designer prompt."""
    return (
        "LAYOUT ARCHETYPE (follow this composition — and VARY it from previous\n"
        "posts; do not reproduce the same layout every time):\n"
        f"  [{key}] {description}"
    )


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
