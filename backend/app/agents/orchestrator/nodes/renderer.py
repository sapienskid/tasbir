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


async def _save_incremental_asset(task_id: str, fmt_id: str, url: str) -> None:
    """Save asset record to DB as soon as format renders."""
    if task_id in ("unknown", "") or not url:
        return
    import uuid
    from app.db.session import get_shared_session_factory
    from app.db.repositories.assets import AssetRepository
    from app.db.repositories.tasks import TaskRepository
    try:
        pool = await get_shared_session_factory()
        async with pool() as session:
            asset_repo = AssetRepository(session)
            key = f"tasks/{task_id}/{fmt_id}.png"
            existing = await asset_repo.get_by_key(key)
            if not existing:
                await asset_repo.create({
                    "key": key,
                    "task_id": uuid.UUID(task_id),
                    "format_id": fmt_id,
                    "content_type": "image/png",
                    "url": url,
                })
            # Also update task result assets_by_format map
            task_repo = TaskRepository(session)
            task = await task_repo.get_by_id(uuid.UUID(task_id))
            if task:
                res = dict(task.result or {})
                assets_map = dict(res.get("assets_by_format", {}))
                assets_map[fmt_id] = url
                res["assets_by_format"] = assets_map
                task.result = res
                await session.commit()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[renderer] Incremental DB asset save failed for %s: %s", fmt_id, exc)


async def renderer_node(state: GenerationState) -> dict:
    task_id = state.get("_task_id", "unknown")
    html_by_fmt = state.get("html_by_format", {})

    valid_items = [
        (fmt, html)
        for fmt, html in html_by_fmt.items()
        if html and len(html) >= 100
    ]

    semaphore = asyncio.Semaphore(2)

    async def _with_semaphore(fmt: str, html: str):
        async with semaphore:
            fmt_id, url = await _render_and_upload(fmt, html, task_id)
            if url:
                await _save_incremental_asset(task_id, fmt_id, url)
            return fmt_id, url

    results = await asyncio.gather(*[_with_semaphore(f, h) for f, h in valid_items])

    assets = {fmt: url for fmt, url in results if url}
    return {"assets_by_format": assets}
