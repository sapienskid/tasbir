"""Celery generate task — runs the LangGraph pipeline, outputs SVG files.
"""

import asyncio
import logging

from app.agents.orchestrator.graph import run_pipeline
from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


def _load_design_tokens() -> dict:
    """Load design tokens from the Design System .penpot file."""
    try:
        from app.config import get_settings
        from app.services.penpot_io import PenpotReader

        settings = get_settings()
        reader = PenpotReader(settings.design_system_path)
        tokens = reader.get_tokens()
        reader.close()
        return tokens
    except Exception as e:
        log.warning("[generate_task] Could not load design tokens: %s — using defaults", e)
        from app.services.penpot_io import DEFAULT_TOKEN_VALUES
        return dict(DEFAULT_TOKEN_VALUES)


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def generate_task(self, task_id: str, source_data: dict):
    async def _run():
        pool = await get_shared_session_factory()

        async with pool() as session:
            repo = TaskRepository(session)
            await repo.update_status(task_id=task_id, status="running")

        pipeline_input = dict(source_data)
        pipeline_input["_task_id"] = task_id
        pipeline_input["design_tokens"] = _load_design_tokens()

        try:
            state = await run_pipeline(pipeline_input)
        except Exception as e:
            log.error("[generate_task] Pipeline failed for task %s: %s", task_id, e, exc_info=True)
            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=task_id, status="failed", error=str(e),
                )
            return

        svg_path = state.get("svg_path", "")
        brief = state.get("strategic_brief", {})
        format_tasks = state.get("format_tasks", {})

        platform_results = {
            fmt_id: {
                "status": ft.get("status", "unknown"),
                "quality_score": ft.get("quality_score", 0),
                "quality_issues": ft.get("quality_issues", []),
                "svg_path": ft.get("svg_path", ""),
                "error": ft.get("error"),
            }
            for fmt_id, ft in format_tasks.items()
        }

        async with pool() as session:
            await TaskRepository(session).update_status(
                task_id=task_id,
                status="completed",
                result={
                    "svg_path": svg_path,
                    "strategic_brief": brief,
                    "platforms": platform_results,
                },
            )

        log.info("[generate_task] Task %s completed. SVG: %s", task_id, svg_path)

    asyncio.run(_run())
