"""HTML→SVG converter node — outputs editable SVG vector files.

Pipeline:
  1. Inject CSS token values into HTML
  2. Extract computed DOM tree via Playwright (positions, styles, text)
  3. Map DOM elements → SVG elements (rect, text, g, defs)
  4. Save as .svg file with embedded design token CSS variables

SVG output opens in Inkscape, Illustrator, or any browser.
Text remains editable, colors are theme-aware via CSS variables.

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].html: str
  - design_tokens: dict (CSS var → value)
  - _task_id: str

Output (to GenerationState):
  - format_tasks[fmt_id].svg_path: str
  - format_tasks[fmt_id].status: "svg_ready"
  - svg_path: str
"""

from __future__ import annotations

import html as html_mod
import logging
import re
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.services.dom_extractor import DOMNode, extract_dom_tree
from app.services.formats import get_format_info
from app.services.penpot_io import DEFAULT_TOKEN_VALUES, inject_tokens_into_html

log = logging.getLogger(__name__)

_TRANSPARENT_COLORS = {"transparent", "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)"}


def _css_color_to_hex(color_str: str, fallback: str = "#000000") -> str:
    if not color_str or color_str in _TRANSPARENT_COLORS:
        return fallback
    if color_str.startswith("#"):
        return color_str.lower()
    match = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return fallback


def _parse_px(value: str, fallback: float = 0.0) -> float:
    if not value:
        return fallback
    match = re.match(r"(-?[\d.]+)", str(value))
    return float(match.group(1)) if match else fallback


def _font_weight_int(fw: str) -> int:
    mapping = {"normal": 400, "bold": 700, "lighter": 300, "bolder": 700}
    if isinstance(fw, int):
        return fw
    cleaned = str(fw).strip()
    if cleaned.isdigit():
        return int(cleaned)
    return mapping.get(cleaned.lower(), 400)


def _escape_svg_text(text: str) -> str:
    """Escape text for safe inclusion in SVG."""
    return html_mod.escape(text).replace("\n", "&#10;")


def _svg_rect(x: float, y: float, w: float, h: float, fill: str = "none",
              rx: float = 0, opacity: float = 1.0, stroke: str | None = None,
              stroke_width: float = 0) -> str:
    attrs = f'x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" opacity="{opacity}"'
    if rx > 0:
        attrs += f' rx="{rx}" ry="{rx}"'
    if stroke and stroke_width > 0:
        attrs += f' stroke="{stroke}" stroke-width="{stroke_width}"'
    return f"<rect {attrs}/>"


def _node_to_svg(node: DOMNode, depth: int = 0) -> str:
    """Convert a DOMNode to SVG elements. Returns empty string if node should be skipped."""
    if node is None or (node.width < 1 and node.height < 1):
        return ""

    parts: list[str] = []

    is_text_tag = node.tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "a", "strong", "em", "label")
    has_bg = node.background_color and node.background_color not in _TRANSPARENT_COLORS
    indent = "  " * (depth + 2)

    # Background rect for this element
    if has_bg:
        bg_hex = _css_color_to_hex(node.background_color, "#0f172a")
        rx = _parse_px(node.border_radius) if node.border_radius else 0
        parts.append(indent + _svg_rect(node.x, node.y, node.width, node.height, bg_hex, rx, node.opacity))

    # Border rect (if border exists)
    has_border = any([
        node.border_top_width > 0, node.border_right_width > 0,
        node.border_bottom_width > 0, node.border_left_width > 0,
    ])
    if has_border:
        max_w = max(node.border_top_width, node.border_right_width,
                     node.border_bottom_width, node.border_left_width)
        # Use thickest border's color
        colors = []
        for w, c, s in [(node.border_top_width, node.border_top_color, node.border_top_style),
                        (node.border_right_width, node.border_right_color, node.border_right_style),
                        (node.border_bottom_width, node.border_bottom_color, node.border_bottom_style),
                        (node.border_left_width, node.border_left_color, node.border_left_style)]:
            if w > 0 and s != "none":
                colors.append((w, c))
        if colors:
            best = max(colors, key=lambda x: x[0])
            border_color = _css_color_to_hex(best[1], "#000000")
            rx = _parse_px(node.border_radius) if node.border_radius else 0
            parts.append(indent + _svg_rect(node.x, node.y, node.width, node.height,
                                            "none", rx, node.opacity,
                                            border_color, max_w))

    # Text content — render for ANY element that has visible text, including
    # container divs that hold direct text (badge, tagline, etc.)
    has_structural_children = node.children and not node.has_inline_children
    if node.text and node.width > 0 and node.height > 0 and not has_structural_children:
        text = _escape_svg_text(node.text)
        color_hex = _css_color_to_hex(node.color, "#ffffff")
        font_fam = node.font_family.split(",")[0].strip().strip("'\"") if node.font_family else "Inter"
        font_size = node.font_size if node.font_size > 0 else 16
        font_weight = _font_weight_int(node.font_weight)
        text_anchor = "start"
        if node.text_align == "center":
            text_anchor = "middle"
        elif node.text_align == "right":
            text_anchor = "end"

        x_pos = node.x + node.width / 2 if text_anchor == "middle" else (node.x + node.width if text_anchor == "end" else node.x)
        y_pos = node.y + font_size

        parts.append(
            f'{indent}<text x="{x_pos}" y="{y_pos}" '
            f'font-family="{font_fam}" font-size="{font_size}" '
            f'font-weight="{font_weight}" fill="{color_hex}" '
            f'text-anchor="{text_anchor}" opacity="{node.opacity}">'
            f'{text}</text>'
        )

    # Recurse children
    if not node.has_inline_children:
        for child in node.children:
            child_svg = _node_to_svg(child, depth + 1)
            if child_svg:
                parts.append(child_svg)

    return "\n".join(parts)


def _build_tokens_css(tokens: dict[str, str]) -> str:
    """Build a CSS :root block for design tokens."""
    lines = [":root {"]
    for var, value in tokens.items():
        lines.append(f"  {var}: {value};")
    lines.append("}")
    return "\n".join(lines)


async def renderer_node_single(state: GenerationState) -> dict:
    """Convert HTML to editable SVG via Playwright DOM extraction."""
    from app.config import get_settings

    settings = get_settings()
    fmt_id = state.get("_processing_format_id", "")
    task_id = state.get("_task_id", "default")
    fmt = get_format_info(fmt_id)

    format_tasks = state.get("format_tasks", {})
    task = format_tasks.get(fmt_id, {})
    html = task.get("html", "")
    design_tokens = state.get("design_tokens", DEFAULT_TOKEN_VALUES)

    if not html:
        log.warning("[renderer] No HTML for %s, skipping", fmt_id)
        return {
            "format_tasks": {
                fmt_id: {**task, "status": "error", "error": "No HTML to convert"}
            }
        }

    # Step 1: Inject CSS token values into HTML
    html_with_tokens = inject_tokens_into_html(html, design_tokens)

    output_dir = Path(settings.output_dir) / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save HTML for reference
    html_path = output_dir / f"{fmt_id}.html"
    html_path.write_text(html_with_tokens, encoding="utf-8")

    # Step 2: Extract DOM tree via Playwright
    log.info("[renderer] Extracting DOM for %s (%dx%d)", fmt_id, fmt.width, fmt.height)
    dom_root = await extract_dom_tree(html_with_tokens, fmt.width, fmt.height)

    if not dom_root:
        log.warning("[renderer] DOM extraction failed for %s — fallback to HTML only", fmt_id)
        return {
            "format_tasks": {
                fmt_id: {
                    **task,
                    "svg_path": str(html_path),
                    "status": "svg_ready",
                }
            }
        }

    # Step 3: Generate SVG
    tokens_css = _build_tokens_css(design_tokens)
    body_svg = _node_to_svg(dom_root)

    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{fmt.width}" height="{fmt.height}" '
        f'viewBox="0 0 {fmt.width} {fmt.height}">\n'
        f'<style>\n{tokens_css}\n</style>\n'
        f'<g id="tasbir-design">\n'
        f'{body_svg}\n'
        f'</g>\n'
        f'</svg>'
    )

    svg_path = output_dir / f"{fmt_id}.svg"
    svg_path.write_text(svg_content, encoding="utf-8")
    log.info("[renderer] Wrote SVG %s (%d chars)", svg_path, len(svg_content))

    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "svg_path": str(svg_path),
                "status": "svg_ready",
            }
        },
        "svg_path": str(svg_path),
    }
