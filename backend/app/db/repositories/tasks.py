import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import GenerationTask


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> Sequence[GenerationTask]:
        stmt = (
            select(GenerationTask)
            .order_by(GenerationTask.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(GenerationTask.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, task_id: uuid.UUID) -> GenerationTask | None:
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_by_celery_id(self, celery_task_id: str) -> GenerationTask | None:
        result = await self.session.execute(
            select(GenerationTask).where(
                GenerationTask.celery_task_id == celery_task_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, source_data: dict) -> GenerationTask:
        task = GenerationTask(source_data=source_data)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def update_status(
        self,
        task_id: uuid.UUID,
        status: str,
        result: dict | None = None,
        error: str | None = None,
        progress: int | None = None,
        celery_task_id: str | None = None,
    ) -> GenerationTask | None:
        values: dict = {"status": status}
        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error
        if progress is not None:
            values["progress"] = progress
        if celery_task_id is not None:
            values["celery_task_id"] = celery_task_id

        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(**values)
            .returning(GenerationTask)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()
