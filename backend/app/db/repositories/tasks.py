from typing import Sequence

from sqlalchemy import func, select, update
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

    async def get_by_id(self, task_id: str) -> GenerationTask | None:
        result = await self.session.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, source_data: dict, composition: dict | None = None
    ) -> GenerationTask:
        task = GenerationTask(source_data=source_data, composition=composition)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def save_source_data(self, task_id: str, source_data: dict) -> None:
        """Replace a task's stored source_data (e.g. with a resume_state)."""
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(source_data=source_data)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_status(
        self,
        task_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> GenerationTask | None:
        values: dict = {"status": status}
        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error

        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(**values)
            .returning(GenerationTask)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def save_edited_html(
        self, task_id: str, edited_html: dict
    ) -> GenerationTask | None:
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(edited_html=edited_html)
            .returning(GenerationTask)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def save_progress(
        self, task_id: str, progress: dict
    ) -> GenerationTask | None:
        """Persist live pipeline progress ({pct, node, ...})."""
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(progress=progress)
            .returning(GenerationTask)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def list_by_batch(self, batch_id: str) -> Sequence[GenerationTask]:
        """Tasks of one Manual Compose batch (``source_data.batch_id``), oldest first."""
        stmt = (
            select(GenerationTask)
            .where(func.json_extract(GenerationTask.source_data, "$.batch_id") == batch_id)
            .order_by(GenerationTask.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def save_composition(
        self, task_id: str, composition: dict, source_data: dict | None = None
    ) -> GenerationTask | None:
        """Store a manual task's composition and re-arm it for a fresh compose.

        Resets status to ``pending`` and clears any operator-edited HTML (the
        new composition supersedes it). ``source_data`` is replaced when given.
        """
        values: dict = {
            "composition": composition,
            "status": "pending",
            "edited_html": None,
            "error": None,
        }
        if source_data is not None:
            values["source_data"] = source_data
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(**values)
            .returning(GenerationTask)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()
