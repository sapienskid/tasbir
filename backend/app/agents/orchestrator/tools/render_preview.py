"""Tool: Render an HTML preview to see how the design looks."""

from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated

from app.services.renderer import render_html
from app.services.storage import upload_asset


async def render_preview(
    state: Annotated[dict, InjectedState],
    html: str,
    format_id: str,
    width: int = 1080,
    height: int = 1080,
) -> str:
    """Render HTML to a PNG image for visual preview.

    Use this after generating HTML to verify the design looks correct
    before finalizing.

    Args:
        html: Complete standalone HTML document to render.
        format_id: Output format identifier (e.g., 'instagram-square').
        width: Viewport width.
        height: Viewport height.

    Returns:
        Asset URL and rendering status.
    """
    png_bytes = await render_html(html, format_id=format_id, width=width, height=height)

    if png_bytes is None:
        return f"Failed to render preview for {format_id}."

    task_id = state.get("_task_id", "preview")
    key = f"previews/{task_id}/{format_id}.png"
    url = await upload_asset(key, png_bytes)

    return f"Preview rendered: {url}"
