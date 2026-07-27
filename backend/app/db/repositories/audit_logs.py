from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        task_id: str,
        agent_name: str,
        decision: dict,
        critique: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            task_id=task_id,
            agent_name=agent_name,
            decision=decision,
            critique=critique,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def list_by_task(self, task_id: str) -> Sequence[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.task_id == task_id)
            .order_by(AuditLog.created_at)
        )
        return result.scalars().all()

    async def list_by_agent(
        self, agent_name: str, limit: int = 50
    ) -> Sequence[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.agent_name == agent_name)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
