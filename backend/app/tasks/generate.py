import asyncio
import uuid
import logging

from socketio import RedisManager

from app.agents.orchestrator.graph import run_pipeline
from app.config import get_settings
from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)
NODE_LABELS = {
    10: "strategist",
    25: "copywriter",
    40: "visual_director",
    55: "designer",
    72: "quality_check",
    90: "renderer",
}


def _init_emitter():
    settings = get_settings()
    return RedisManager(settings.redis_url, write_only=True)


def _emit_progress(emitter, task_id: str, pct: int, status: str = "running", node: str = ""):
    try:
        emitter.emit("progress", {
            "task_id": task_id,
            "percent": pct,
            "node": node,
            "status": status,
        }, room=task_id)
    except Exception:
        log.warning("[generate] Socket.IO emit failed", exc_info=True)


def _emit_format_progress(emitter, task_id: str, format_id: str, stage: str, status: str = "running", url: str | None = None):
    try:
        payload = {
            "task_id": task_id,
            "format_id": format_id,
            "stage": stage,
            "status": status,
        }
        if url:
            payload["url"] = url
        emitter.emit("format_progress", payload, room=task_id)
    except Exception:
        log.warning("[generate] format_progress emit failed", exc_info=True)


def _node_for_progress(pct: int) -> str:
    for threshold in sorted(NODE_LABELS, reverse=True):
        if pct >= threshold:
            return NODE_LABELS[threshold]
    return "strategist"


def _build_result(state: dict) -> dict:
    """Extract backward-compatible result dict from format_tasks state."""
    format_tasks = state.get("format_tasks", {})
    copy_by_format = {}
    background_by_format = {}
    html_by_format = {}
    assets_by_format = {}
    quality_score = 100
    quality_issues = []

    for fmt, task in format_tasks.items():
        if task.get("copy"):
            copy_by_format[fmt] = task["copy"]
        if task.get("background"):
            background_by_format[fmt] = task["background"]
        if task.get("html"):
            html_by_format[fmt] = task["html"]
        if task.get("png_url"):
            assets_by_format[fmt] = task["png_url"]
        if task.get("quality_score", 100) < quality_score:
            quality_score = task["quality_score"]
        if task.get("quality_issues"):
            quality_issues.extend(task["quality_issues"])

    return {
        "strategic_brief": state.get("strategic_brief", ""),
        "copy_by_format": copy_by_format,
        "background_by_format": background_by_format,
        "html_by_format": html_by_format,
        "assets_by_format": assets_by_format,
        "quality_score": quality_score,
        "quality_issues": quality_issues,
    }


@celery_app.task(bind=True, max_retries=3, acks_late=True)
def generate_task(self, task_id: str, source_data: dict):
    settings = get_settings()
    emitter = _init_emitter()
    task_uuid = uuid.UUID(task_id)

    async def _set_progress(pct: int, label: str = "Running...", status: str = "running"):
        node = _node_for_progress(pct)
        _emit_progress(emitter, task_id, pct, status, node)
        pool = await get_shared_session_factory()
        async with pool() as session:
            await TaskRepository(session).update_status(
                task_id=task_uuid,
                status=status,
                progress=pct,
            )

    async def _run():
        pool = await get_shared_session_factory()

        async with pool() as session:
            await TaskRepository(session).update_status(
                task_id=task_uuid,
                status="running",
                celery_task_id=self.request.id,
                progress=5,
            )

        _emit_progress(emitter, task_id, 5, "running", "strategist")

        source_data["_task_id"] = task_id

        if not source_data.get("design_tokens"):
            brand_name = (source_data.get("brand") or {}).get("name", "")
            if brand_name:
                try:
                    from app.db.repositories.brands import BrandRepository
                    async with pool() as session:
                        repo = BrandRepository(session)
                        db_brand = await repo.get_by_name(brand_name)
                        if db_brand and db_brand.data:
                            brand_tokens = db_brand.data.get("tokens") or {}
                            if brand_tokens:
                                source_data["design_tokens"] = brand_tokens
                        if not source_data.get("design_tokens"):
                            from sqlalchemy import select
                            from app.models.tokens import DesignToken
                            result = await session.execute(
                                select(DesignToken).where(DesignToken.name == brand_name.lower())
                            )
                            dt = result.scalar_one_or_none()
                            if dt and dt.data:
                                source_data["design_tokens"] = dt.data
                except Exception as exc:
                    log.warning("[generate_task] Could not pre-load design tokens for brand '%s': %s", brand_name, exc)

        try:
            state = await run_pipeline(source_data, progress_callback=_set_progress)
        except Exception as e:
            log.error("[generate_task] Pipeline failed: %s", e, exc_info=True)
            await _set_progress(100, "failed", "failed")
            _emit_progress(emitter, task_id, 100, "failed", "failed")
            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=task_uuid, status="failed", error=str(e), progress=100,
                )
            return

        result = _build_result(state)

        async with pool() as session:
            task_repo = TaskRepository(session)

            if result["quality_score"] >= 50:
                await task_repo.update_status(
                    task_id=task_uuid, status="completed", result=result, progress=100,
                )

                _emit_progress(emitter, task_id, 100, "completed", "renderer")
                emitter.emit("complete", {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result,
                }, room=task_id)

                for fmt, url in result["assets_by_format"].items():
                    _emit_format_progress(emitter, task_id, fmt, "done", "completed", url)
            else:
                error_msg = f"Quality check failed: {', '.join(result['quality_issues'])}"
                await task_repo.update_status(
                    task_id=task_uuid, status="failed", error=error_msg, progress=100,
                )
                _emit_progress(emitter, task_id, 100, "failed", "failed")

    asyncio.run(_run())
