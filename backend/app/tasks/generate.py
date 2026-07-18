import asyncio
import uuid

from app.agents.orchestrator.graph import run_pipeline
from app.config import get_settings
from app.db.repositories.assets import AssetRepository
from app.db.repositories.tasks import TaskRepository
from app.db.session import create_pool
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, acks_late=True)
def generate_task(self, task_id: str, source_data: dict):
    """Main generation task — runs the LangGraph agent pipeline.

    The pipeline handles everything:
    1. Strategist → Copywriter → Visual Director → Designer → Quality Check
    2. If quality passes, Renderer converts HTML → PNG and uploads to MinIO
    3. If quality fails with refinements left, loops back to Designer
    """
    settings = get_settings()

    async def _run():
        pool = await create_pool(settings.database_url)
        try:
            async with pool() as session:
                task_repo = TaskRepository(session)
                await task_repo.update_status(
                    task_id=uuid.UUID(task_id),
                    status="running",
                    celery_task_id=self.request.id,
                )
        finally:
            await pool.close()

        source_data["_task_id"] = task_id
        state = await run_pipeline(source_data)

        pool = await create_pool(settings.database_url)
        try:
            async with pool() as session:
                task_repo = TaskRepository(session)
                asset_repo = AssetRepository(session)

                quality_score = state.get("quality_score", 0)
                assets_by_format = state.get("assets_by_format", {})

                if quality_score >= 70:
                    result = {
                        "strategic_brief": state.get("strategic_brief", ""),
                        "copy_by_format": state.get("copy_by_format", {}),
                        "background_by_format": state.get("background_by_format", {}),
                        "html_by_format": state.get("html_by_format", {}),
                        "assets_by_format": assets_by_format,
                        "quality_score": quality_score,
                        "quality_issues": state.get("quality_issues", []),
                    }

                    await task_repo.update_status(
                        task_id=uuid.UUID(task_id),
                        status="completed",
                        result=result,
                        progress=100,
                    )

                    for fmt, url in assets_by_format.items():
                        key = f"tasks/{task_id}/{fmt}.png"
                        await asset_repo.create({
                            "key": key,
                            "task_id": uuid.UUID(task_id),
                            "format_id": fmt,
                            "content_type": "image/png",
                            "url": url,
                        })
                else:
                    await task_repo.update_status(
                        task_id=uuid.UUID(task_id),
                        status="failed",
                        error=f"Quality check failed: {', '.join(state.get('quality_issues', []))}",
                        progress=100,
                    )
        finally:
            await pool.close()

    asyncio.run(_run())
