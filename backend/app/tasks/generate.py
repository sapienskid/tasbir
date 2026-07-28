"""Celery generate task — runs the LangGraph pipeline asynchronously.

Loads design tokens from the Design System .penpot file at task start,
injects them into the pipeline state. This is the only place tokens
are loaded — agents never see them directly.
"""

import asyncio
import logging

from app.agents.orchestrator.graph import run_pipeline
from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


def _load_design_tokens() -> dict:
    """Load design tokens from the Design System .penpot file.

    Returns DEFAULT_TOKEN_VALUES if the file doesn't exist yet.
    This is called synchronously at task start (Celery worker context).
    """
    try:
        from app.config import get_settings
        from app.services.penpot_io import PenpotReader

        settings = get_settings()
        reader = PenpotReader(settings.design_system_path)
        tokens = reader.get_tokens()
        reader.close()
        log.info("[generate_task] Loaded %d design tokens", len(tokens))
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

        # Inject task ID and design tokens into pipeline input
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

        # Collect results from final state
        penpot_path = state.get("penpot_file_path", "")
        boards = state.get("boards", {})
        brief = state.get("strategic_brief", {})
        format_tasks = state.get("format_tasks", {})

        # Build per-platform quality summary for the result
        platform_results = {
            fmt_id: {
                "status": ft.get("status", "unknown"),
                "quality_score": ft.get("quality_score", 0),
                "quality_issues": ft.get("quality_issues", []),
                "penpot_file_path": ft.get("penpot_file_path", ""),
                "error": ft.get("error"),
            }
            for fmt_id, ft in format_tasks.items()
        }

        async with pool() as session:
            await TaskRepository(session).update_status(
                task_id=task_id,
                status="completed",
                result={
                    "penpot_file_path": penpot_path,
                    "boards": boards,
                    "strategic_brief": brief,
                    "platforms": platform_results,
                },
            )

        log.info("[generate_task] Task %s completed. Boards: %s", task_id, list(boards.keys()))

    asyncio.run(_run())
