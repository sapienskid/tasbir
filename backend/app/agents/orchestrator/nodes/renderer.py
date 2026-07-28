"""HTML→Penpot converter node — programmatic, no LLM.

Pipeline:
  1. Inject CSS token values into HTML (so browser resolves var(--color-*))
  2. Call Playwright service to extract computed DOM tree
  3. Map DOM elements → Penpot shapes (frame, text, rect, svg-raw, image)
  4. Build valid .penpot ZIP file
  5. Save to data/output/{task_id}/{task_id}.penpot

Falls back gracefully if Playwright is unavailable (creates a minimal
.penpot file with a placeholder frame).

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
from app.services.dom_extractor import DOMNode, extract_dom_tree, render_to_png
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

# Colors that are "transparent" or "rgba(0,0,0,0)" — skip adding fills
_TRANSPARENT_COLORS = {"transparent", "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)"}


def _css_color_to_hex(color_str: str, fallback: str = "#000000") -> str:
    """Convert a CSS computed color (rgb/rgba/hex) to hex string.

    Examples:
        'rgb(255, 255, 255)' → '#ffffff'
        'rgba(102, 126, 234, 1)' → '#667eea'
        '#667eea' → '#667eea'
        'transparent' → fallback
    """
    if not color_str or color_str in _TRANSPARENT_COLORS:
        return fallback

    if color_str.startswith("#"):
        return color_str.lower()

    # rgb(r, g, b) or rgba(r, g, b, a)
    match = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"

    return fallback


def _parse_px(value: str, fallback: float = 0.0) -> float:
    """Parse a CSS pixel value like '16px' → 16.0."""
    if not value:
        return fallback
    match = re.match(r"([\d.]+)", str(value))
    return float(match.group(1)) if match else fallback


def _font_weight_int(fw: str) -> int:
    """Convert font-weight string ('400', 'bold', 'normal') to int."""
    mapping = {"normal": 400, "bold": 700, "lighter": 300, "bolder": 700}
    if isinstance(fw, int):
        return fw
    cleaned = str(fw).strip()
    if cleaned.isdigit():
        return int(cleaned)
    return mapping.get(cleaned.lower(), 400)


def _is_transparent(color_str: str) -> bool:
    """Check if a color is transparent/invisible."""
    if not color_str or color_str in _TRANSPARENT_COLORS:
        return True
    # Check for rgba with 0 alpha
    match = re.match(r"rgba\(.*,\s*([\d.]+)\)", color_str)
    if match and float(match.group(1)) == 0:
        return True
    return False


def _dom_to_penpot_shape(node: DOMNode, depth: int = 0) -> PenpotShape | None:
    """Recursively convert a DOMNode to a PenpotShape.

    Returns None if the node should be skipped (zero size, hidden, etc.).
    """
    # Skip zero-size elements (unless text)
    is_text_tag = node.tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "a", "strong", "em", "label")
    if node.width < 1 and node.height < 1 and not is_text_tag:
        return None

    # --- SVG raw: .math or .diagram elements ---
    if node.svg_content and ("math" in node.class_list or "diagram" in node.class_list):
        shape = PenpotShape(
            name=f"SVG ({node.tag})",
            shape_type="svg-raw",
            x=node.x,
            y=node.y,
            width=max(node.width, 10),
            height=max(node.height, 10),
            svg_content=node.svg_content,
        )
        return shape

    # --- Text elements ---
    if is_text_tag or (node.text and not node.children and node.tag not in ("div", "section", "article", "main", "body")):
        text_to_use = node.text or " "
        color_hex = _css_color_to_hex(node.color, "#ffffff")
        font_fam = node.font_family.split(",")[0].strip().strip("'\"") if node.font_family else "Inter"

        shape = PenpotShape(
            name=f"Text: {text_to_use[:30]}",
            shape_type="text",
            x=node.x,
            y=node.y,
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
        # Add background fill if present
        if not _is_transparent(node.background_color):
            bg_hex = _css_color_to_hex(node.background_color, "#0f172a")
            shape.fills = [Fill(color=bg_hex)]

        return shape

    # --- Frame/container elements (body, div, section, etc.) ---
    bg_fills = []
    if not _is_transparent(node.background_color):
        bg_hex = _css_color_to_hex(node.background_color, "#0f172a")
        bg_fills = [Fill(color=bg_hex)]

    shape = PenpotShape(
        name=f"{node.tag}#{node.node_id}" if node.node_id else node.tag,
        shape_type="frame",
        x=node.x,
        y=node.y,
        width=max(node.width, 1),
        height=max(node.height, 1),
        fills=bg_fills,
        opacity=node.opacity,
        clip_content=node.overflow == "hidden",
    )

    # Recursively process children
    for child in node.children:
        child_shape = _dom_to_penpot_shape(child, depth + 1)
        if child_shape:
            shape.children.append(child_shape)

    # If no children and has text content (e.g., a div with direct text)
    if not shape.children and node.text:
        color_hex = _css_color_to_hex(node.color, "#ffffff")
        font_fam = node.font_family.split(",")[0].strip().strip("'\"") if node.font_family else "Inter"
        text_shape = PenpotShape(
            name=f"Text: {node.text[:30]}",
            shape_type="text",
            x=node.x,
            y=node.y,
            width=max(node.width, 10),
            height=max(node.height, 10),
            text_content=TextContent(
                text=node.text,
                font_family=font_fam,
                font_size=node.font_size,
                font_weight=_font_weight_int(node.font_weight),
                color=color_hex,
                line_height=1.4,
                letter_spacing=0.0,
                text_align=node.text_align or "left",
            ),
        )
        shape.children.append(text_shape)

    return shape


def _build_placeholder_shape(fmt_id: str, width: int, height: int) -> PenpotShape:
    """Build a minimal placeholder shape when Playwright is unavailable."""
    root = PenpotShape(
        name=f"{fmt_id} (placeholder)",
        shape_type="frame",
        x=0,
        y=0,
        width=float(width),
        height=float(height),
        fills=[Fill(color="#0f172a")],
    )

    # Add a "Design pending" text
    text_shape = PenpotShape(
        name="Placeholder text",
        shape_type="text",
        x=float(width) * 0.1,
        y=float(height) * 0.4,
        width=float(width) * 0.8,
        height=80.0,
        text_content=TextContent(
            text=f"{fmt_id} — Design generated (open HTML in browser to preview)",
            font_family="Inter",
            font_size=24.0,
            font_weight=400,
            color="#94a3b8",
            text_align="center",
        ),
    )
    root.children.append(text_shape)
    return root


async def renderer_node_single(state: GenerationState) -> dict:
    """Convert HTML to Penpot shapes for a single platform."""
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
                fmt_id: {
                    **task,
                    "status": "error",
                    "error": "No HTML to convert",
                }
            }
        }

    # Step 1: Inject CSS token values into HTML
    html_with_tokens = inject_tokens_into_html(html, design_tokens)

    # Step 2: Extract DOM tree via Playwright
    log.info("[html_to_penpot] Extracting DOM for %s (%dx%d)", fmt_id, fmt.width, fmt.height)
    dom_root = await extract_dom_tree(html_with_tokens, fmt.width, fmt.height)

    # Step 3: Map DOM → Penpot shapes (or use placeholder if Playwright unavailable)
    if dom_root:
        root_shape = _dom_to_penpot_shape(dom_root) or _build_placeholder_shape(fmt_id, fmt.width, fmt.height)
        root_shape.name = fmt_id
    else:
        log.warning("[html_to_penpot] DOM extraction failed for %s — using placeholder", fmt_id)
        root_shape = _build_placeholder_shape(fmt_id, fmt.width, fmt.height)

    # Ensure root dimensions match canvas
    root_shape.x = 0.0
    root_shape.y = 0.0
    root_shape.width = float(fmt.width)
    root_shape.height = float(fmt.height)

    # Step 4: Build .penpot ZIP
    output_dir = Path(settings.output_dir) / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    penpot_path = output_dir / f"{task_id}.penpot"

    # If file already exists (from a previous platform), read and extend it
    # For simplicity: create one .penpot per platform in this pass
    # The final merge is handled below
    platform_penpot_path = output_dir / f"{fmt_id}.penpot"

    writer = PenpotWriter(file_name=f"Tasbir — {fmt_id}")
    board_id = writer.add_board(fmt_id, fmt.width, fmt.height, root_shape)
    penpot_bytes = writer.build()

    platform_penpot_path.write_bytes(penpot_bytes)
    log.info("[html_to_penpot] Wrote %s (%d bytes)", platform_penpot_path, len(penpot_bytes))

    # Also save the HTML for debugging/preview
    html_path = output_dir / f"{fmt_id}.html"
    html_path.write_text(html_with_tokens, encoding="utf-8")

    # Update state
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
