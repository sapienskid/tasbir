"""DOM extractor service — Playwright-based HTML-to-computed-styles extractor.

Communicates with the Playwright Docker service at playwright:4000.
Extracts a structured DOM tree with computed CSS properties for each element,
which is then mapped to Penpot shapes by the html_to_penpot node.
"""

from __future__ import annotations

import logging
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

    try:
        async with httpx.AsyncClient(timeout=RENDER_TIMEOUT) as client:
            response = await client.post(
                f"{renderer_url}/extract-dom",
                json=payload,
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

    try:
        async with httpx.AsyncClient(timeout=RENDER_TIMEOUT) as client:
            response = await client.post(
                f"{renderer_url}/render",
                json=payload,
            )
            response.raise_for_status()
            return response.content
    except Exception as e:
        log.warning("[dom_extractor] PNG render failed: %s", e)
        return None


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
        node.children.append(_parse_dom_node(child_data))

    return node
