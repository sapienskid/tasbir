"""Renderer node — converts HTML to PNG and uploads to storage in parallel using dynamic DB formats.

This node always runs after quality check passes. It renders every
format's HTML to PNG via Playwright and uploads to MinIO.
"""

import asyncio
from app.agents.orchestrator.state import GenerationState
from app.services.cleanup import clean_html
from app.services.formats import get_format_info


async def _render_and_upload(fmt_id: str, html: str, task_id: str) -> tuple[str, str | None]:
    from app.services.renderer import render_html
    from app.services.storage import upload_asset

    fmt_info = await get_format_info(fmt_id)
    png_bytes = await render_html(
        clean_html(html),
        format_id=fmt_id,
        width=fmt_info.width,
        height=fmt_info.height,
    )

    if png_bytes is None:
        return fmt_id, None

    key = f"tasks/{task_id}/{fmt_id}.png"
    url = await upload_asset(key, png_bytes)
    return fmt_id, url


async def renderer_node(state: GenerationState) -> dict:
    task_id = state.get("_task_id", "unknown")
    html_by_fmt = state.get("html_by_format", {})

    valid_items = [
        (fmt, html)
        for fmt, html in html_by_fmt.items()
        if html and len(html) >= 100
    ]

    tasks = [_render_and_upload(fmt, html, task_id) for fmt, html in valid_items]
    results = await asyncio.gather(*tasks)

    assets = {fmt: url for fmt, url in results if url is not None}
    return {"assets_by_format": assets}
