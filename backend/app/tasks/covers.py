"""Background cover generation, isolated from the social-copy pipeline."""

import asyncio
import logging

from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.services.artifacts import atomic_write, task_output_dir
from app.services.covers import (
    COVER_HEIGHT,
    COVER_WIDTH,
    CoverRequest,
    build_cover_svg,
    cover_html,
    cover_theme,
    generate_cover_image,
    image_prompt,
)
from app.services.dom_extractor import render_to_png
from app.services.ds_context import resolve_ds_context_strict
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(bind=True, acks_late=True)
def cover_task(self, task_id: str):
    asyncio.run(run_covers(task_id))


async def run_covers(task_id: str, pool=None) -> None:
    pool = pool or await get_shared_session_factory()
    async with pool() as session:
        repo = TaskRepository(session)
        task = await repo.get_by_id(task_id)
        if task is None or task.status == "completed":
            return
        source = dict(task.source_data or {})
        if source.get("mode") != "cover":
            return
        previous = task.result or {}
        await repo.update_status(task_id, "running", error="")

    result = {
        "kind": "cover",
        "width": COVER_WIDTH,
        "height": COVER_HEIGHT,
        "platforms": dict(previous.get("platforms") or {}),
        "output_paths": dict(previous.get("output_paths") or {}),
    }
    try:
        request = CoverRequest.model_validate(source)
        result.update(width=request.width, height=request.height)
        ctx = await resolve_ds_context_strict(pool, request.design_system_id)
        out = task_output_dir(task_id)
        out.mkdir(parents=True, exist_ok=True)
        for index in range(request.variations):
            fmt = f"cover-{index + 1}"
            # Resume completed variants without spending image quota twice.
            if (result["platforms"].get(fmt) or {}).get("status") == "rendered":
                if (out / f"{fmt}.png").is_file():
                    continue
            async with pool() as session:
                await TaskRepository(session).save_progress(
                    task_id,
                    {
                        "pct": int(90 * index / request.variations),
                        "node": "cover",
                        "done": index,
                        "total": request.variations,
                    },
                )
            try:
                # A render retry reuses saved HTML; it doesn't regenerate paid artwork.
                html_path = out / f"{fmt}.html"
                motif = cover_theme(request, index)
                if html_path.is_file():
                    html = html_path.read_text(encoding="utf-8")
                else:
                    image = None
                    if request.engine == "ai":
                        image = await generate_cover_image(image_prompt(request, motif))
                    svg = build_cover_svg(request, ctx, index, image)
                    html = cover_html(svg, request.width, request.height)
                    atomic_write(out / f"{fmt}.svg", svg)
                    atomic_write(html_path, html)
                paths = {"html": str(html_path), "svg": str(out / f"{fmt}.svg")}
                result["output_paths"][fmt] = paths
                png = await render_to_png(html, request.width, request.height)
                if not png:
                    raise ValueError("PNG renderer unavailable; retry to render the saved artwork")
                png_path = out / f"{fmt}.png"
                atomic_write(png_path, png)
                paths["png"] = str(png_path)
                result["platforms"][fmt] = {
                    "status": "rendered",
                    "html_path": str(html_path),
                    "quality_score": 0,
                    "quality_issues": [],
                    "motif": motif,
                    "engine": request.engine,
                }
            except Exception as exc:
                log.warning("Cover %s/%s failed: %s", task_id, fmt, exc)
                result["platforms"][fmt] = {
                    "status": "error",
                    "error": str(exc),
                    "quality_score": 0,
                    "quality_issues": [str(exc)],
                }
            async with pool() as session:
                await TaskRepository(session).update_status(task_id, "running", result=result)
        failures = [e for e in result["platforms"].values() if e["status"] == "error"]
        async with pool() as session:
            repo = TaskRepository(session)
            await repo.update_status(
                task_id,
                "failed" if failures else "completed",
                result=result,
                error=(
                    f"{len(failures)} cover variation(s) failed; retry to finish"
                    if failures
                    else ""
                ),
            )
            await repo.save_progress(task_id, {"pct": 100, "node": "done"})
    except Exception as exc:
        log.exception("Cover task %s failed", task_id)
        async with pool() as session:
            await TaskRepository(session).update_status(
                task_id,
                "failed",
                result=result,
                error=str(exc),
            )
