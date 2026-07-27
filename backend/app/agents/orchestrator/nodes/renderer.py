"""Renderer node (single format) — converts HTML to PNG and uploads to storage.

This node runs inside the per-format subgraph after quality check passes.
It renders a single format's HTML to PNG via Playwright, uploads to MinIO,
and saves the asset record to the DB incrementally.
"""

from app.agents.orchestrator.state import GenerationState
from app.services.cleanup import clean_html
from app.services.formats import get_format_info


async def _save_asset(task_id: str, fmt_id: str, url: str) -> None:
    if task_id in ("unknown", "") or not url:
        return
    import uuid
    import logging
    from sqlalchemy import text
    from app.db.repositories.tasks import TaskRepository
    from app.db.session import get_shared_session_factory
    log = logging.getLogger(__name__)
    try:
        pool = await get_shared_session_factory()
        async with pool() as session:
            key = f"tasks/{task_id}/{fmt_id}.png"
            await session.execute(
                text("""
                    INSERT INTO assets (key, task_id, format_id, content_type, url, created_at)
                    VALUES (:key, :task_id, :fmt_id, 'image/png', :url, NOW())
                    ON CONFLICT (key) DO NOTHING
                """),
                {
                    "key": key,
                    "task_id": uuid.UUID(task_id),
                    "fmt_id": fmt_id,
                    "url": url,
                }
            )
            task_obj = await TaskRepository(session).get_by_id(uuid.UUID(task_id))
            if task_obj:
                res = dict(task_obj.result or {})
                assets_map = dict(res.get("assets_by_format", {}))
                assets_map[fmt_id] = url
                res["assets_by_format"] = assets_map
                task_obj.result = res
                await session.commit()
    except Exception:
        logging.getLogger(__name__).warning("[renderer] DB asset save failed for %s", fmt_id, exc_info=True)


async def _render_and_upload(fmt_id: str, html: str, task_id: str) -> str | None:
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
        return None

    key = f"tasks/{task_id}/{fmt_id}.png"
    url = await upload_asset(key, png_bytes)
    return url


async def renderer_node_single(state: GenerationState) -> dict:
    task_id = state.get("_task_id", "unknown")
    fmt_id = state["_processing_format_id"]
    task = dict(state["format_tasks"].get(fmt_id, {}))
    html = task.get("html", "")

    if not html or len(html) < 100:
        updated_task = dict(task)
        updated_task["status"] = "failed"
        updated_task["error"] = "HTML too short or empty for rendering"
        return {"format_tasks": {fmt_id: updated_task}}

    url = await _render_and_upload(fmt_id, html, task_id)

    if url:
        await _save_asset(task_id, fmt_id, url)

    updated_task = dict(task)
    updated_task["png_url"] = url
    updated_task["status"] = "done" if url else "failed"
    if url:
        updated_task["error"] = None
    else:
        updated_task["error"] = "Rendering failed"

    return {"format_tasks": {fmt_id: updated_task}}
