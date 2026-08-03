from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_job import AgentJob


class AgentJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, job_id: str) -> AgentJob | None:
        result = await self.session.execute(
            select(AgentJob).where(AgentJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50, kind: str | None = None) -> list[AgentJob]:
        stmt = select(AgentJob).order_by(AgentJob.created_at.desc())
        if kind:
            stmt = stmt.where(AgentJob.kind == kind)
        result = await self.session.execute(stmt.limit(limit))
        return list(result.scalars().all())

    async def delete(self, job_id: str) -> bool:
        result = await self.session.execute(delete(AgentJob).where(AgentJob.id == job_id))
        await self.session.commit()
        return result.rowcount > 0

    async def create(self, kind: str, payload: dict) -> AgentJob:
        job = AgentJob(kind=kind, status="pending", payload=payload)
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def update_status(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> AgentJob | None:
        values: dict = {"status": status}
        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error
        stmt = (
            update(AgentJob)
            .where(AgentJob.id == job_id)
            .values(**values)
            .returning(AgentJob)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()
