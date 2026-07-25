"""Renderer node — converts HTML to PNG and uploads to storage.

This node always runs after quality check passes. It renders every
format's HTML to PNG via Playwright and uploads to MinIO.

This is deterministic — not dependent on the LLM calling any tools.
"""

from app.agents.orchestrator.state import GenerationState
from app.services.cleanup import clean_html

_DIMS = {
    "instagram-square": (1080, 1080),
    "instagram-portrait": (1080, 1350),
    "instagram-story": (1080, 1920),
    "linkedin-post": (1200, 627),
    "twitter-card": (1200, 675),
    "facebook-post": (1200, 630),
    "pinterest-pin": (1000, 1500),
    "carousel-post": (1080, 1350),
}


async def renderer_node(state: GenerationState) -> dict:
    from app.services.renderer import render_html
    from app.services.storage import upload_asset

    assets: dict[str, str] = {}
    task_id = state.get("_task_id", "unknown")

    for fmt, html in state.get("html_by_format", {}).items():
        if not html or len(html) < 100:
            continue

        w, h = _DIMS.get(fmt, (1080, 1080))
        png_bytes = await render_html(clean_html(html), format_id=fmt, width=w, height=h)

        if png_bytes is None:
            continue

        key = f"tasks/{task_id}/{fmt}.png"
        url = await upload_asset(key, png_bytes)
        assets[fmt] = url

    return {"assets_by_format": assets}
