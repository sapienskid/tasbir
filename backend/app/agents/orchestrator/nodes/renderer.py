"""HTML→Penpot converter node — hybrid approach.

Pipeline:
  1. Inject CSS token values into HTML (so browser resolves var(--color-*))
  2. Render HTML to PNG via Playwright (pixel-perfect visual copy)
  3. Extract DOM text elements with computed positions from Playwright
  4. Build .penpot ZIP:
     - Embed the rendered PNG as a full-size background image
     - Overlay editable text shapes at correct DOM positions
  5. Save to data/output/{task_id}/{fmt_id}.penpot

Falls back gracefully if Playwright is unavailable.

Input (from GenerationState via _processing_format_id):
  - format_tasks[fmt_id].html: str
  - design_tokens: dict (CSS var → value)
  - _task_id: str

Output (to GenerationState):
  - format_tasks[fmt_id].penpot_file_path: str
  - format_tasks[fmt_id].status: "penpot_ready"
  - penpot_file_path: str (path to the combined file)
  - boards: dict (fmt_id → board ID)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.agents.orchestrator.state import GenerationState
from app.services.dom_extractor import extract_dom_tree, render_to_png
from app.services.formats import get_format_info
from app.services.penpot_io import (
    DEFAULT_TOKEN_VALUES,
    Fill,
    PenpotShape,
    PenpotWriter,
    TextContent,
    inject_tokens_into_html,
)

log = logging.getLogger(__name__)

# Colors that are "transparent" or "rgba(0,0,0,0)"
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


def _extract_text_shapes_from_dom(node: "DOMNode", shapes: list[PenpotShape]) -> None:
    """Walk the DOM tree and extract text elements as Penpot text shapes.

    Each visible text node becomes an editable text layer in the Penpot output.
    Text elements are placed at their DOM positions, overlaying the PNG background.
    """
    if node is None:
        return

    is_text_tag = node.tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "a", "strong", "em", "label")

    # Only create text shapes for actual text-bearing elements, not containers
    # whose innerText is derived from child elements (to avoid duplicates).
    is_empty_container = node.tag in ("div", "section", "article", "main", "body", "header", "footer") and node.children and not node.has_inline_children

    if not is_empty_container and node.text and node.width > 0 and node.height > 0:
        text_to_use = node.text
        color_hex = _css_color_to_hex(node.color, "#ffffff")
        font_fam = node.font_family.split(",")[0].strip().strip("'\"") if node.font_family else "Inter"

        if is_text_tag:
            shape = PenpotShape(
                name=f"Text: {text_to_use[:30]}",
                shape_type="text",
                x=node.x, y=node.y,
                width=max(node.width, 10),
                height=max(node.height, 10),
                opacity=node.opacity,
                text_content=TextContent(
                    text=text_to_use,
                    font_family=font_fam,
                    font_size=node.font_size,
                    font_weight=_font_weight_int(node.font_weight),
                    color=color_hex,
                    line_height=_parse_px(node.line_height, node.font_size * 1.4) / node.font_size
                    if node.font_size > 0 else 1.4,
                    letter_spacing=_parse_px(node.letter_spacing, 0.0),
                    text_align=node.text_align or "left",
                ),
            )
        else:
            shape = PenpotShape(
                name=f"Text: {text_to_use[:30]}",
                shape_type="text",
                x=node.x, y=node.y,
                width=max(node.width, 10),
                height=max(node.height, 10),
                text_content=TextContent(
                    text=text_to_use,
                    font_family=font_fam,
                    font_size=node.font_size,
                    font_weight=_font_weight_int(node.font_weight),
                    color=color_hex,
                    line_height=1.4,
                    letter_spacing=0.0,
                    text_align=node.text_align or "left",
                ),
            )
        shapes.append(shape)

    # Recurse into children (unless this node has inline children that were merged)
    if not node.has_inline_children:
        for child in node.children:
            _extract_text_shapes_from_dom(child, shapes)


async def renderer_node_single(state: GenerationState) -> dict:
    """Render HTML to PNG + overlay editable text shapes in Penpot."""
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
        log.warning("[html_to_penpot] No HTML for %s, skipping", fmt_id)
        return {
            "format_tasks": {
                fmt_id: {**task, "status": "error", "error": "No HTML to convert"}
            }
        }

    # Step 1: Inject CSS token values into HTML
    html_with_tokens = inject_tokens_into_html(html, design_tokens)

    output_dir = Path(settings.output_dir) / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    platform_penpot_path = output_dir / f"{fmt_id}.penpot"

    # Step 2: Render HTML → PNG
    log.info("[html_to_penpot] Rendering %s to PNG", fmt_id)
    png_bytes = await render_to_png(html_with_tokens, fmt.width, fmt.height)

    # Also save HTML for debugging
    html_path = output_dir / f"{fmt_id}.html"
    html_path.write_text(html_with_tokens, encoding="utf-8")

    # Step 3: Extract DOM text elements
    dom_root = await extract_dom_tree(html_with_tokens, fmt.width, fmt.height)

    # Step 4: Build Penpot file
    writer = PenpotWriter(file_name=f"Tasbir — {fmt_id}")

    # 4a: Create root board frame
    root = PenpotShape(
        name=fmt_id,
        shape_type="frame",
        x=0, y=0,
        width=float(fmt.width),
        height=float(fmt.height),
        fills=[],
    )

    if png_bytes:
        # 4b: Embed PNG as SVG with foreignObject + CSS background image.
        # This renders correctly in Penpot's SVG engine and avoids media/object
        # import limitations.
        import base64
        b64 = base64.b64encode(png_bytes).decode("ascii")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{fmt.width}" height="{fmt.height}">'
            f'<foreignObject width="{fmt.width}" height="{fmt.height}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" '
            f'style="width:{fmt.width}px;height:{fmt.height}px;'
            f'background:url(data:image/png;base64,{b64});'
            f'background-size:cover"/>'
            f'</foreignObject>'
            f'</svg>'
        )
        img_shape = PenpotShape(
            name="Design Preview (PNG)",
            shape_type="svg-raw",
            x=0, y=0,
            width=float(fmt.width),
            height=float(fmt.height),
            svg_content=svg,
        )
        root.children.append(img_shape)

        # 4c: Overlay editable text shapes on top of the image
        text_shapes: list[PenpotShape] = []
        if dom_root:
            _extract_text_shapes_from_dom(dom_root, text_shapes)
        for ts in text_shapes:
            root.children.append(ts)

        log.info(
            "[html_to_penpot] %s — PNG %d bytes, %d text layers",
            fmt_id, len(png_bytes), len(text_shapes),
        )
    else:
        log.warning("[html_to_penpot] PNG render failed for %s — using placeholder", fmt_id)
        text_shape = PenpotShape(
            name="Placeholder",
            shape_type="text",
            x=float(fmt.width) * 0.1,
            y=float(fmt.height) * 0.4,
            width=float(fmt.width) * 0.8,
            height=80.0,
            text_content=TextContent(
                text=f"{fmt_id} — Design generated (open HTML to preview)",
                font_family="Inter", font_size=24.0, font_weight=400,
                color="#94a3b8", text_align="center",
            ),
        )
        root.children.append(text_shape)

    # Step 5: Write .penpot file
    board_id = writer.add_board(fmt_id, fmt.width, fmt.height, root)
    penpot_bytes = writer.build()
    platform_penpot_path.write_bytes(penpot_bytes)
    log.info("[html_to_penpot] Wrote %s (%d bytes)", platform_penpot_path, len(penpot_bytes))

    boards = dict(state.get("boards", {}))
    boards[fmt_id] = board_id

    return {
        "format_tasks": {
            fmt_id: {
                **task,
                "penpot_file_path": str(platform_penpot_path),
                "status": "penpot_ready",
            }
        },
        "boards": boards,
        "penpot_file_path": str(platform_penpot_path),
    }
