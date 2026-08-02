from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, include_inactive: bool = False) -> list[Agent]:
        stmt = select(Agent).order_by(Agent.name.asc())
        if not include_inactive:
            stmt = stmt.where(Agent.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(Agent.name == name)
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, data: dict) -> Agent:
        agent = Agent(name=name, **data)
        self.session.add(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return agent

    async def update(self, name: str, data: dict) -> Agent | None:
        stmt = (
            update(Agent)
            .where(Agent.name == name)
            .values(**data)
            .returning(Agent)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()
