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

    async def _set_progress(pct: int, status: str = "running"):
        e, p = await create_pool(settings.database_url)
        try:
            async with p() as s:
                await TaskRepository(s).update_status(
                    task_id=uuid.UUID(task_id),
                    status=status,
                    progress=pct,
                )
        finally:
            await e.dispose()

    async def _run():
        engine, pool = await create_pool(settings.database_url)
        try:
            async with pool() as session:
                task_repo = TaskRepository(session)
                await task_repo.update_status(
                    task_id=uuid.UUID(task_id),
                    status="running",
                    celery_task_id=self.request.id,
                    progress=5,
                )
        finally:
            await engine.dispose()

        await _set_progress(10)

        source_data["_task_id"] = task_id
        try:
            state = await run_pipeline(source_data, progress_callback=_set_progress)
        except Exception as e:
            await _set_progress(100, "failed")
            engine, pool = await create_pool(settings.database_url)
            try:
                async with pool() as session:
                    await TaskRepository(session).update_status(
                        task_id=uuid.UUID(task_id),
                        status="failed",
                        error=str(e),
                        progress=100,
                    )
            finally:
                await engine.dispose()
            return

        await _set_progress(95)

        engine, pool = await create_pool(settings.database_url)
        try:
            async with pool() as session:
                task_repo = TaskRepository(session)
                asset_repo = AssetRepository(session)

                quality_score = state.get("quality_score", 0)
                assets_by_format = state.get("assets_by_format", {})

                if quality_score >= 50:
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
        except Exception as e:
            await _set_progress(100, "failed")
            engine, pool = await create_pool(settings.database_url)
            try:
                async with pool() as session:
                    await TaskRepository(session).update_status(
                        task_id=uuid.UUID(task_id),
                        status="failed",
                        error=str(e),
                        progress=100,
                    )
            finally:
                await engine.dispose()
        finally:
            await engine.dispose()

    asyncio.run(_run())
