"""Unified ``illustrate`` tool — the illustration director.

One tool the LLM calls for every post that needs a figure. It picks a style:

  - ``anthropic``     → the procedural Anthropic-style SVG generator
  - ``open-peeps``    → a vendored CC0 hand-drawn person (Pablo Stanley)
  - ``open-doodles``  → a vendored CC0 hand-drawn scene (Pablo Stanley)

Hand-drawn kit SVGs ship with their own palette, so they are **recolored to
the brand's monochrome tokens** (luminance → ink / mid / light / paper) using
only ``var(--color-*)`` — verifier-safe and ground-adaptive. Both kit families
are CC0 (public domain), vendored under ``backend/data/illustrations/``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# role custom properties (defined by the figure wrapper, ground-adaptive)
_INK, _MID, _LIGHT, _PAPER = "--ill-ink", "--ill-mid", "--ill-light", "--ill-paper"

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "illustrations"

_TAG_RE = re.compile(r"<([A-Za-z][\w:.-]*)([^>]*)>")
_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3}|[0-9a-fA-F]{8})")
_ATTR_RE = re.compile(r'([\w:.-]+)="([^"]*)"')
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]"
)
_TITLE_DESC_RE = re.compile(
    r"<\s*(?:title|desc)\b[^>]*>.*?<\s*/\s*(?:title|desc)\s*>", re.IGNORECASE | re.DOTALL
)
_SKIP_NAMES = ("page-", "icon-", "logo-", "footer-", "cover-", "mix-", "sit-stand-walk")

ILLUSTRATE_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "illustrate",
        "description": (
            "Create a monochrome editorial illustration for the post. Call "
            "exactly once. Choose a style: 'anthropic' (abstract procedural, "
            "best for general subjects), 'open-peeps' (a naive hand-drawn "
            "person, good when the post is about people/work), or 'open-doodles' "
            "(a hand-drawn scene). Returns an SVG fragment for the template's "
            "illustration slot."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "enum": ["anthropic", "open-peeps", "open-doodles"],
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
            },
            "required": ["style", "theme"],
        },
    },
}


# ---------------------------------------------------------------------------
# Kit manifest
# ---------------------------------------------------------------------------


def _kit_files(kit: str) -> list[Path]:
    base = _DATA_DIR / kit
    if not base.is_dir():
        return []
    files = sorted(p for p in base.glob("*.svg"))
    out = []
    for p in files:
        name = p.name.lower()
        if any(name.startswith(s) for s in _SKIP_NAMES):
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        if "url(" in body or "<style" in body.lower():
            continue  # gradients/clips/styles complicate monochrome recolor
        out.append(p)
    return out


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
    lum = _luminance(hex_color)
    if lum >= 0.86:
        return _PAPER
    if lum >= 0.68:
        return _LIGHT
    if lum >= 0.38:
        return _MID
    return _INK


def _recolor_svg(svg: str) -> str:
    """Rewrite every hex fill/stroke to a brand token via inline styles."""

    def repl(m: re.Match) -> str:
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
            if name in ("fill", "stroke") and _HEX.fullmatch(value.strip()):
                styles.append(f"{name}: var({_role_for(value.strip())})")
                continue
            kept.append(f'{name}="{value}"')
        out = f"<{tag}"
        if kept:
            out += " " + " ".join(kept)
        if styles:
            out += f' style="{"; ".join(styles)}"'
        return out + ("/>" if self_close else ">")

    return _TAG_RE.sub(repl, svg)


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


def compose_handdrawn(kit: str, seed: str, ground: str, theme: str = "") -> str:
    """Compose a vendored CC0 figure recolored to the brand monochrome."""
    if kit not in ("open-peeps", "open-doodles"):
        kit = "open-peeps"
    files = _kit_files(kit)
    if not files:
        log.warning("[illustrate] no %s kit files found under %s", kit, _DATA_DIR)
        return ""
    digest = hashlib.sha1(f"{seed}|{theme}|{kit}".encode("utf-8")).hexdigest()
    path = files[int(digest[:8], 16) % len(files)]
    try:
        svg = path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("[illustrate] failed to read %s: %s", path, e)
        return ""
    svg = _recolor_svg(svg)
    # Kit files carry emoji in <title>/<desc> metadata and stray unicode —
    # strip them so the verifier's no-emoji rule stays satisfied.
    svg = _TITLE_DESC_RE.sub("", svg)
    svg = _EMOJI_RE.sub("", svg)
    return _figure_wrapper(svg)


def run_illustrate(args: dict, seed: str = "") -> str:
    """Execute an ``illustrate`` tool call → figure/svg HTML fragment."""
    from app.services.illustration import generate_illustration_svg

    style = str(args.get("style") or "anthropic")
    theme = str(args.get("theme") or "")[:60]
    ground = str(args.get("ground") or "white")
    if ground not in ("white", "black"):
        ground = "white"
    if style in ("open-peeps", "open-doodles"):
        fig = compose_handdrawn(style, seed or "figure", ground, theme)
        if fig:
            return fig
        log.warning("[illustrate] %s kit unavailable — falling back to anthropic", style)
    return generate_illustration_svg(seed or "figure", ground, theme=theme)
