import asyncio
import logging

from app.agents.orchestrator.graph import run_pipeline
from app.db.repositories.tasks import TaskRepository
from app.db.session import get_shared_session_factory
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def generate_task(self, task_id: str, source_data: dict):
    async def _run():
        pool = await get_shared_session_factory()

        async with pool() as session:
            repo = TaskRepository(session)
            await repo.update_status(task_id=task_id, status="running")

        source_data["_task_id"] = task_id

        try:
            state = await run_pipeline(source_data)
        except Exception as e:
            log.error("[generate_task] Pipeline failed: %s", e, exc_info=True)
            async with pool() as session:
                await TaskRepository(session).update_status(
                    task_id=task_id, status="failed", error=str(e),
                )
            return

        async with pool() as session:
            repo = TaskRepository(session)
            await repo.update_status(
                task_id=task_id,
                status="completed",
                result={
                    "penpot_file_path": state.get("penpot_file_path", ""),
                    "boards": state.get("boards", {}),
                    "strategic_brief": state.get("strategic_brief", {}),
                },
            )

    asyncio.run(_run())
