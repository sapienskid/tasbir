"""DOM extractor service — Playwright-based HTML-to-computed-styles extractor.

Communicates with the Playwright Docker service at playwright:4000.
Extracts a structured DOM tree with computed CSS properties for each element,
used for generating SVG output or extracting text positions.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

PLAYWRIGHT_SERVICE_URL = "http://playwright:4000"
RENDER_TIMEOUT = 45.0  # seconds


@dataclass
class DOMNode:
    """Represents a single DOM element with computed styles."""

    tag: str = "div"
    node_id: str = ""
    class_list: list[str] = field(default_factory=list)
    pseudo: str = ""  # "before", "after", or empty for real elements
    text: str = ""
    has_inline_children: bool = False
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    # Computed CSS properties
    background_color: str = "transparent"
    color: str = "#000000"
    font_family: str = "Inter, sans-serif"
    font_size: float = 16.0
    font_weight: str = "400"
    line_height: str = "normal"
    letter_spacing: str = "0px"
    text_align: str = "left"
    border_radius: str = "0px"
    # Per-corner border radius (extracted individually for asymmetric values)
    border_top_left_radius: float = 0.0
    border_top_right_radius: float = 0.0
    border_bottom_right_radius: float = 0.0
    border_bottom_left_radius: float = 0.0

    opacity: float = 1.0
    overflow: str = "visible"

    # Background image / gradient
    background_image: str = ""
    has_gradient: bool = False

    # Per-side border properties
    border_top_width: float = 0.0
    border_right_width: float = 0.0
    border_bottom_width: float = 0.0
    border_left_width: float = 0.0
    border_top_color: str = "transparent"
    border_right_color: str = "transparent"
    border_bottom_color: str = "transparent"
    border_left_color: str = "transparent"
    border_top_style: str = "none"
    border_right_style: str = "none"
    border_bottom_style: str = "none"
    border_left_style: str = "none"

    # Shadow & effects
    box_shadow: str = ""
    filter: str = ""
    background_clip: str = ""

    # SVG content (for .math and .diagram elements)
    svg_content: str | None = None

    # Parent reference (set during parsing, used by contrast resolution)
    parent: "DOMNode | None" = None

    # Children
    children: list["DOMNode"] = field(default_factory=list)


async def extract_dom_tree(
    html: str,
    width: int = 1080,
    height: int = 1080,
) -> DOMNode | None:
    """Send HTML to the Playwright service and get back a DOM tree.

    Args:
        html: Complete standalone HTML document.
        width: Canvas width in pixels.
        height: Canvas height in pixels.

    Returns:
        Root DOMNode with full tree, or None if extraction failed.
    """
    settings = get_settings()
    renderer_url = getattr(settings, "renderer_url", PLAYWRIGHT_SERVICE_URL)

    payload = {
        "html": html,
        "width": width,
        "height": height,
    }

    headers = {}
    if settings.render_service_key:
        headers["X-Render-Key"] = settings.render_service_key

    try:
        async with httpx.AsyncClient(timeout=RENDER_TIMEOUT) as client:
            response = await client.post(
                f"{renderer_url}/extract-dom",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return _parse_dom_node(data.get("dom", {}))
    except Exception as e:
        log.warning("[dom_extractor] DOM extraction failed: %s", e)
        return None


async def render_to_png(
    html: str,
    width: int = 1080,
    height: int = 1080,
) -> bytes | None:
    """Render HTML to PNG via the Playwright service.

    Args:
        html: Complete standalone HTML document.
        width: Viewport width.
        height: Viewport height.

    Returns:
        PNG bytes, or None if rendering failed.
    """
    settings = get_settings()
    renderer_url = getattr(settings, "renderer_url", PLAYWRIGHT_SERVICE_URL)

    has_mermaid = "mermaid.run()" in html or "data-mermaid-ready" in html

    payload: dict[str, Any] = {
        "html": html,
        "width": width,
        "height": height,
        "format": "png",
        "wait_until": "networkidle",
    }

    if has_mermaid:
        payload["wait_for_selector"] = "body[data-mermaid-ready='true']"
        payload["wait_for_timeout"] = 3000

    headers = {}
    if settings.render_service_key:
        headers["X-Render-Key"] = settings.render_service_key

    # Retry transient render-service failures — a single hiccup shouldn't
    # fail a save or a pipeline step.
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=RENDER_TIMEOUT) as client:
                response = await client.post(
                    f"{renderer_url}/render",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            last_error = e
            log.warning(
                "[dom_extractor] PNG render failed (attempt %d/3): %s", attempt + 1, e
            )
            if attempt < 2:
                await asyncio.sleep(1 + attempt)
    log.error("[dom_extractor] PNG render failed after 3 attempts: %s", last_error)
    return None


async def detect_overflow(
    html: str,
    width: int = 1080,
    height: int = 1080,
) -> list[str]:
    """Detect content overflow past the canvas bounds.

    Calls the Playwright extract-dom endpoint, which reports the amount the
    document scrolls past the viewport. Returns human-readable issues for any
    element text that overflows (clipped by overflow:hidden).
    """
    settings = get_settings()
    renderer_url = getattr(settings, "renderer_url", PLAYWRIGHT_SERVICE_URL)

    payload = {"html": html, "width": width, "height": height}

    headers = {}
    if settings.render_service_key:
        headers["X-Render-Key"] = settings.render_service_key

    try:
        async with httpx.AsyncClient(timeout=RENDER_TIMEOUT) as client:
            response = await client.post(
                f"{renderer_url}/extract-dom",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        log.warning("[dom_extractor] Overflow check failed: %s", e)
        return []

    overflow = data.get("overflow") or []
    issues: list[str] = []
    for off in overflow if isinstance(overflow, list) else []:
        text = (off.get("text") or "").strip()
        over_y = int(off.get("overflowY") or 0)
        over_x = int(off.get("overflowX") or 0)
        where = []
        if over_x > 0:
            where.append(f"{over_x}px past the right edge")
        if over_y > 0:
            where.append(f"{over_y}px past the bottom edge")
        if not where:
            continue
        cls = off.get("cls") or off.get("tag") or "element"
        issues.append(
            f"Element '.{cls}' ('{text[:40]}') overflows the {width}x{height} canvas "
            f"({' and '.join(where)}) — reduce sizes or shorten copy so everything fits."
        )
    return issues


# --- Contrast (legibility) ----------------------------------------------------

# WCAG contrast floor for "clearly broken" text — near-invisible copy that is
# the same colour as its background. Intentional decorative grays (e.g. a large
# index numeral) sit above this; body text that blends into the background does
# not.
_MIN_CONTRAST = 1.8
# Skip text this short (decorative glyphs, "i/N" counters, single letters).
_MIN_TEXT_LEN = 3


def _parse_rgba(color: str):
    """Parse 'rgb()/rgba()/#RRGGBB/#RGB' -> (r, g, b, a) or None."""
    m = re.match(r"rgba?\(([^)]+)\)", color.strip())
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        try:
            a = float(parts[3]) if len(parts) > 3 else 1.0
            return int(parts[0]), int(parts[1]), int(parts[2]), a
        except ValueError:
            return None
    m = re.match(r"#([0-9a-fA-F]{6})\b", color.strip())
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    m = re.match(r"#([0-9a-fA-F]{3})\b", color.strip())
    if m:
        h = m.group(1)
        return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0
    return None


def _relative_luminance(r: int, g: int, b: int) -> float:
    def _f(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _f(r) + 0.7152 * _f(g) + 0.0722 * _f(b)


def _contrast_ratio(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _blend(
    fg: tuple[int, int, int, float], bg: tuple[int, int, int, float]
) -> tuple[int, int, int, float]:
    """Overlay fg (with alpha) onto bg; return the resulting color (alpha=1)."""
    a = fg[3] + bg[3] * (1 - fg[3])
    if a <= 0:
        return (0, 0, 0, 0.0)
    r = (fg[0] * fg[3] + bg[0] * bg[3] * (1 - fg[3])) / a
    g = (fg[1] * fg[3] + bg[1] * bg[3] * (1 - fg[3])) / a
    b = (fg[2] * fg[3] + bg[2] * bg[3] * (1 - fg[3])) / a
    return (int(r), int(g), int(b), 1.0)


def _effective_background(node: DOMNode) -> tuple[int, int, int, float] | None:
    """Walk node + ancestors for the nearest solid background color.

    Returns None when the effective background is a gradient/image/transparent
    chain (contrast can't be computed — the vision verifier covers those).
    """
    cur: DOMNode | None = node
    while cur is not None:
        if cur.has_gradient or (cur.background_image or "").strip() not in ("", "none"):
            return None
        parsed = _parse_rgba(cur.background_color)
        if parsed and parsed[3] > 0.01:
            return parsed
        cur = cur.parent
    return None


def _collect_contrast_issues(node: DOMNode, issues: list[str]) -> None:
    if node.tag in ("svg", "path", "circle", "rect", "line"):
        return
    text = (node.text or "").strip()
    if len(text) >= _MIN_TEXT_LEN and not text.isdigit():
        bg = _effective_background(node)
        if bg is not None:
            fg = _parse_rgba(node.color)
            if fg is not None:
                # Blend the text's own alpha onto the background.
                fg = _blend(fg, bg)
                if fg[3] > 0.01:
                    ratio = _contrast_ratio(
                        _relative_luminance(*fg[:3]), _relative_luminance(*bg[:3])
                    )
                    if ratio < _MIN_CONTRAST:
                        cls = ".".join(node.class_list) or node.tag
                        issues.append(
                            f"Low-contrast text: '{text[:40]}' ('.{cls}') is nearly "
                            f"the same colour as its background (contrast "
                            f"{ratio:.2f}:1) — text must be clearly legible."
                        )
    for child in node.children:
        _collect_contrast_issues(child, issues)


async def detect_low_contrast(
    html: str,
    width: int = 1080,
    height: int = 1080,
) -> list[str]:
    """Detect text that is nearly the same colour as its background.

    Uses the DOM extractor's computed styles. Text over images/gradients is
    skipped (the vision verifier audits those); only solid-background text that
    is effectively invisible is reported.
    """
    root = await extract_dom_tree(html, width, height)
    if root is None:
        return []
    issues: list[str] = []
    _collect_contrast_issues(root, issues)
    return issues


def _parse_dom_node(data: dict) -> DOMNode:
    """Recursively parse a raw DOM dict into DOMNode objects."""
    node = DOMNode(
        tag=data.get("tag", "div"),
        node_id=data.get("id", ""),
        class_list=data.get("classList", []),
        pseudo=data.get("pseudo", ""),
        text=data.get("text", ""),
        has_inline_children=bool(data.get("hasInlineChildren", False)),
        x=float(data.get("x", 0)),
        y=float(data.get("y", 0)),
        width=float(data.get("width", 0)),
        height=float(data.get("height", 0)),
        background_color=data.get("backgroundColor", "transparent"),
        color=data.get("color", "#000000"),
        font_family=data.get("fontFamily", "Inter, sans-serif"),
        font_size=float(data.get("fontSize", 16)),
        font_weight=str(data.get("fontWeight", "400")),
        line_height=str(data.get("lineHeight", "normal")),
        letter_spacing=str(data.get("letterSpacing", "0px")),
        text_align=data.get("textAlign", "left"),
        border_radius=str(data.get("borderRadius", "0px")),
        border_top_left_radius=float(data.get("borderTopLeftRadius", 0)),
        border_top_right_radius=float(data.get("borderTopRightRadius", 0)),
        border_bottom_right_radius=float(data.get("borderBottomRightRadius", 0)),
        border_bottom_left_radius=float(data.get("borderBottomLeftRadius", 0)),
        opacity=float(data.get("opacity", 1.0)),
        overflow=data.get("overflow", "visible"),
        background_image=data.get("backgroundImage", ""),
        has_gradient=bool(data.get("hasGradient", False)),
        border_top_width=float(data.get("borderTopWidth", 0)),
        border_right_width=float(data.get("borderRightWidth", 0)),
        border_bottom_width=float(data.get("borderBottomWidth", 0)),
        border_left_width=float(data.get("borderLeftWidth", 0)),
        border_top_color=data.get("borderTopColor", "transparent"),
        border_right_color=data.get("borderRightColor", "transparent"),
        border_bottom_color=data.get("borderBottomColor", "transparent"),
        border_left_color=data.get("borderLeftColor", "transparent"),
        border_top_style=data.get("borderTopStyle", "none"),
        border_right_style=data.get("borderRightStyle", "none"),
        border_bottom_style=data.get("borderBottomStyle", "none"),
        border_left_style=data.get("borderLeftStyle", "none"),
        box_shadow=data.get("boxShadow", ""),
        filter=data.get("filter", ""),
        background_clip=data.get("backgroundClip", ""),
        svg_content=data.get("svgContent"),
    )

    for child_data in data.get("children", []):
        child = _parse_dom_node(child_data)
        child.parent = node
        node.children.append(child)

    return node
