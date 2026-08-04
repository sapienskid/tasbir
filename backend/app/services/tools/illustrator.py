"""Unified ``illustrate`` tool — the illustration director.

One tool the LLM calls for every post that needs a figure:

  - ``anthropic``  → the procedural Anthropic-style SVG generator
  - curated styles → DiceBear avatar generators (people / creatures / faces /
                     abstract shapes / landscape), fully offline + deterministic

DiceBear styles ship their own palettes (hex + named ``black``/``white``), so
the SVG is **recolored to the brand's monochrome tokens** using only
``var(--color-*)`` — verifier-safe and ground-adaptive. The default ``line``
palette collapses every fill to pure ink/paper (bold 2-tone); ``mono`` keeps
the 4-tone luminance map; ``original`` leaves DiceBear colors untouched
(preview only, not verifier-safe). Mask fills are recolored with the
ground-stable ``--ill-light``/``--ill-mid`` tokens so their luminance
structure survives both grounds. DiceBear part ids are prefixed (``z-``) so
``#face-…``-style references can't be read as raw hex by the verifier. The
curated allowlist, AI-facing descriptions and pinnable parts live in
``peep_styles.py``.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# role custom properties (defined by the figure wrapper, ground-adaptive)
_INK, _MID, _LIGHT, _PAPER = "--ill-ink", "--ill-mid", "--ill-light", "--ill-paper"

_TAG_RE = re.compile(r"<([A-Za-z][\w:.-]*)([^>]*)>")
_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3}|[0-9a-fA-F]{8})")
_ATTR_RE = re.compile(r'([\w:.-]+)="([^"]*)"')
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]"
)
_TITLE_DESC_RE = re.compile(
    r"<\s*(?:title|desc)\b[^>]*>.*?<\s*/\s*(?:title|desc)\s*>", re.IGNORECASE | re.DOTALL
)
# DiceBear wraps output in an RDF metadata block (creator/license) — strip it
# wholesale so no attribution text or stray unicode reaches the verifier.
_METADATA_RE = re.compile(r"<metadata\b[^>]*>.*?</metadata\s*>", re.IGNORECASE | re.DOTALL)
# Mask definitions are structural (white = visible region). Recoloring them
# would break rendering on a black ground, so they are excluded from recolor.
_MASK_BLOCK_RE = re.compile(r"<mask\b[^>]*>.*?</mask\s*>", re.IGNORECASE | re.DOTALL)
# DiceBear comment banner.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# DiceBear part ids like "face-default-…" begin with valid hex runs ("face"),
# so `href="#face-…"` trips the verifier's raw-hex regex. Prefix every id and
# its references with a non-hex-safe marker so they can never be read as a
# colour.
_ID_DEF_RE = re.compile(r'\bid="([^"]+)"')
_HREF_RE = re.compile(r'\bhref="#([^"]+)"')
_URL_REF_RE = re.compile(r"url\(#([^)]+)\)")
_ID_PREFIX = "z-"


def _safe_ids(svg: str) -> str:
    svg = _ID_DEF_RE.sub(lambda m: f'id="{_ID_PREFIX}{m.group(1)}"', svg)
    svg = _HREF_RE.sub(lambda m: f'href="#{_ID_PREFIX}{m.group(1)}"', svg)
    svg = _URL_REF_RE.sub(lambda m: f"url(#{_ID_PREFIX}{m.group(1)})", svg)
    return svg


def _build_illustrate_tool() -> dict:
    """ILLUSTRATE_TOOL schema built from the curated style registry."""
    from app.services.tools.peep_styles import CURATED_STYLES

    style_desc = []
    for sid in sorted(CURATED_STYLES):
        info = CURATED_STYLES[sid]
        style_desc.append(f"{sid}: {info.description}")
    style_enum = ["anthropic"] + sorted(CURATED_STYLES)

    def part_desc(part: str, sid: str) -> str:
        from app.services.tools.peep_styles import list_style_values

        vals = list_style_values(sid, part)
        if vals:
            return f"Pin a specific {part} (e.g. {vals[:6]}). Omit for a random match."
        return "Not available for this style — omit."

    return {
        "type": "function",
        "function": {
            "name": "illustrate",
            "description": (
                "Create a monochrome editorial illustration for the post. Call "
                "exactly once. Choose 'anthropic' (abstract procedural) or a "
                "curated DiceBear style. Style options:\n" + "\n".join(style_desc)
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "style": {
                        "type": "string",
                        "enum": style_enum,
                        "description": "Which illustration style to use.",
                    },
                    "theme": {
                        "type": "string",
                        "description": (
                            "Short abstract theme steering the composition — e.g. "
                            "'growth', 'flow', 'focus'. No objects, no text, no "
                            "colour words."
                        ),
                    },
                    "ground": {
                        "type": "string",
                        "enum": ["white", "black"],
                        "description": "Card background.",
                    },
                    "facial_hair": {
                        "type": "string",
                        "description": part_desc("facial_hair", "open-peeps"),
                    },
                    "hair": {
                        "type": "string",
                        "description": part_desc("hair", "open-peeps"),
                    },
                    "expression": {
                        "type": "string",
                        "description": part_desc("expression", "open-peeps"),
                    },
                    "accessory": {
                        "type": "string",
                        "description": part_desc("accessory", "open-peeps"),
                    },
                },
                "required": ["style", "theme"],
            },
        },
    }


ILLUSTRATE_TOOL: dict = _build_illustrate_tool()


# ---------------------------------------------------------------------------
# Monochrome recolor
# ---------------------------------------------------------------------------


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:
        h = h[:6]
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return 1.0
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _role_for(hex_color: str) -> str:
    v = hex_color.strip()
    if v == "black":
        return _INK
    if v == "white":
        return _PAPER
    lum = _luminance(hex_color)
    if lum >= 0.86:
        return _PAPER
    if lum >= 0.68:
        return _LIGHT
    if lum >= 0.38:
        return _MID
    return _INK


def _line_role_for(hex_color: str) -> str:
    """Crisp 2-tone mapping — every fill collapses to ink or paper.

    Better contrast than the 4-tone map: no muddy mid-grays, bold silhouette.
    Outlines/lines stay dark, large light fills stay light.
    """
    v = hex_color.strip()
    if v == "black":
        return _INK
    if v == "white":
        return _PAPER
    lum = _luminance(hex_color)
    return _PAPER if lum >= 0.5 else _INK


def _mask_role(hex_color: str) -> str:
    """Role for a fill inside a luminance <mask>.

    Masks use the *luminance* of their content (white = visible, black =
    hidden), so the ground-inverting ink/paper tokens would break them on a
    black ground. ``--ill-light`` / ``--ill-mid`` are ground-stable (same
    value on both grounds), so remapping light→light, dark→mid preserves the
    mask's light/dark structure without leaking raw hex.
    """
    v = hex_color.strip()
    if v == "black":
        return _MID
    if v == "white":
        return _LIGHT
    lum = _luminance(hex_color)
    return _LIGHT if lum >= 0.5 else _MID


def _recolor_block(m: re.Match, role_for: callable) -> str:
    """Recolor a single tag, using ``role_for(value) -> token role | None``."""
    tag, attrs = m.group(1), m.group(2).rstrip()
    self_close = attrs.endswith("/")
    if self_close:
        attrs = attrs[:-1].rstrip()
    kept: list[str] = []
    styles: list[str] = []
    for e in _ATTR_RE.finditer(attrs):
        name, value = e.group(1), e.group(2)
        if name == "style":
            if value.strip():
                styles.append(value)
            continue
        if name in ("fill", "stroke"):
            v = value.strip()
            role = None
            if _HEX.fullmatch(v) or v in ("black", "white"):
                role = role_for(v)
            if role is not None:
                styles.append(f"{name}: var({role})")
                continue
        kept.append(f'{name}="{value}"')
    out = f"<{tag}"
    if kept:
        out += " " + " ".join(kept)
    if styles:
        out += f' style="{"; ".join(styles)}"'
    return out + ("/>" if self_close else ">")


def _recolor_svg(svg: str, palette: str = "mono") -> str:
    """Rewrite every hex/named fill+stroke to a brand token via inline styles.

    ``palette``:
      - ``mono``      → 4-tone luminance (ink/mid/light/paper) — ground-adaptive
      - ``line``      → 2-tone ink/paper — bold, high contrast, no mid-grays
      - ``original``  → leave DiceBear colors untouched (NOT verifier-safe —
                        only for preview/comparison, never in the pipeline)

    Mask definitions are recolored with ``_mask_role`` (ground-stable tokens)
    so their luminance structure survives both grounds; ``fill="none"`` /
    ``stroke="none"`` are preserved.
    """
    if palette == "original":
        return svg

    body_role = _line_role_for if palette == "line" else _role_for

    def repl(m: re.Match) -> str:
        return _recolor_block(m, body_role)

    def repl_mask(m: re.Match) -> str:
        return _recolor_block(m, _mask_role)

    # Process <mask> blocks with the luminance-stable role; the rest with the
    # normal ground-adaptive role.
    parts = _MASK_BLOCK_RE.split(svg)
    masks = _MASK_BLOCK_RE.findall(svg)
    out: list[str] = []
    for i, part in enumerate(parts):
        out.append(_TAG_RE.sub(repl, part))
        if i < len(masks):
            out.append(_TAG_RE.sub(repl_mask, masks[i]))
    return "".join(out)


def _clean_svg(svg: str) -> str:
    """Strip DiceBear metadata/comment banner and any emoji/title/desc."""
    svg = _METADATA_RE.sub("", svg)
    svg = _COMMENT_RE.sub("", svg)
    svg = _TITLE_DESC_RE.sub("", svg)
    svg = _EMOJI_RE.sub("", svg)
    svg = _safe_ids(svg)
    return svg


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def _figure_wrapper(svg_body: str) -> str:
    style = (
        ".figure{--ill-ink:var(--color-text);--ill-mid:var(--color-text-secondary);"
        "--ill-light:var(--color-text-tertiary);--ill-paper:var(--color-bg);"
        "width:100%;height:100%}"
        'body[data-ground="black"] .figure{--ill-ink:var(--color-text-inverted);'
        "--ill-mid:var(--color-text-secondary);--ill-light:var(--color-text-tertiary);"
        "--ill-paper:var(--color-bg-inverted)}"
        ".figure svg{width:100%;height:100%;display:block}"
    )
    return f'<div class="figure"><style>{style}</style>{svg_body}</div>'


def _map_parts(style_id: str, parts: dict) -> dict:
    """Translate generic part keys → the style's DiceBear variant options.

    Returns ``{}`` when no parts (or none match the style). Each pinned part is
    forced via ``<part>Variant=<value>&<part>Probability=100``. A value outside
    the style's allowed list is dropped (graceful fallback to seeded random).
    """
    from app.services.tools.peep_styles import CURATED_STYLES

    info = CURATED_STYLES.get(style_id)
    if info is None or not info.parts:
        return {}
    options: dict = {}
    for key, value in (parts or {}).items():
        entry = info.parts.get(key)
        if entry is None:
            continue
        opt_name, allowed = entry
        if value not in allowed:
            log.warning("[illustrate] %s invalid for %s — ignoring", value, key)
            continue
        options[opt_name] = value
        options[opt_name.replace("Variant", "Probability")] = 100
    return options


def compose_peep(
    seed: str,
    ground: str = "white",
    style: str = "open-peeps",
    theme: str = "",
    parts: dict | None = None,
    palette: str = "line",
) -> str:
    """Compose a curated DiceBear avatar, recolored to the brand monochrome.

    ``palette``: ``line`` (2-tone ink/paper, default), ``mono`` (4-tone), or
    ``original`` (DiceBear colors kept — NOT verifier-safe; preview only).
    """
    from dicebear import Avatar

    from app.services.tools.peep_styles import CURATED_STYLES, load_style

    if style not in CURATED_STYLES:
        log.warning("[illustrate] unknown style %s — defaulting to open-peeps", style)
        style = "open-peeps"
    if palette not in ("mono", "line", "original"):
        palette = "mono"
    style_def = load_style(style)
    options = {"seed": seed or "figure"}
    options.update(_map_parts(style, parts or {}))
    try:
        svg = Avatar(style_def, options).to_string()
    except Exception as e:  # noqa: BLE001 — bad part/option combo → seeded random
        log.warning("[illustrate] %s render failed (%s) — retrying unpinned", style, e)
        svg = Avatar(style_def, {"seed": seed or "figure"}).to_string()
    svg = _clean_svg(svg)
    svg = _recolor_svg(svg, palette)
    return _figure_wrapper(svg)


def run_illustrate(args: dict, seed: str = "") -> str:
    """Execute an ``illustrate`` tool call → figure/svg HTML fragment."""
    from app.services.illustration import generate_illustration_svg

    style = str(args.get("style") or "anthropic")
    theme = str(args.get("theme") or "")[:60]
    ground = str(args.get("ground") or "white")
    if ground not in ("white", "black"):
        ground = "white"
    if style == "anthropic":
        return generate_illustration_svg(seed or "figure", ground, theme=theme)
    parts = {
        key: args[key]
        for key in ("facial_hair", "hair", "expression", "accessory")
        if args.get(key)
    }
    return compose_peep(
        seed or "figure",
        ground=ground,
        style=style,
        theme=theme,
        parts=parts or None,
        palette="line",
    )
