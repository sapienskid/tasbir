import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.tasks import TaskRepository

router = APIRouter()


@router.get("")
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    repo = TaskRepository(db)
    tasks = await repo.list(limit=limit, offset=offset, status=status)
    return [
        {
            "id": str(t.id),
            "status": t.status,
            "progress": t.progress,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    return {
        "id": str(task.id),
        "celery_task_id": task.celery_task_id,
        "status": task.status,
        "source_data": task.source_data,
        "result": task.result,
        "error": task.error,
        "progress": task.progress,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@router.get("/{task_id}/stream")
async def stream_task(task_id: uuid.UUID):
    """SSE stream for task progress updates.
    Polls the database for task status changes and yields events.
    """
    import asyncio

    from app.config import get_settings
    from app.db.session import create_pool

    async def event_generator():
        settings = get_settings()
        pool = await create_pool(settings.database_url)

        last_status = None
        last_progress = -1

        try:
            while True:
                async with pool() as session:
                    repo = TaskRepository(session)
                    task = await repo.get_by_id(task_id)

                    if not task:
                        yield {"event": "error", "data": "Task not found"}
                        break

                    if task.status != last_status or task.progress != last_progress:
                        last_status = task.status
                        last_progress = task.progress
                        yield {
                            "event": "progress",
                            "data": {
                                "status": task.status,
                                "progress": task.progress,
                                "error": task.error,
                            },
                        }

                    if task.status in ("completed", "failed"):
                        if task.status == "completed":
                            yield {
                                "event": "complete",
                                "data": {
                                    "status": "completed",
                                    "result": task.result,
                                },
                            }
                        break

                await asyncio.sleep(1)
        finally:
            await pool.close()

    return EventSourceResponse(event_generator())
