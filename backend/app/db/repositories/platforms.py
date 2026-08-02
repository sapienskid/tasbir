from typing import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import Platform


class PlatformRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self, include_inactive: bool = False
    ) -> Sequence[Platform]:
        stmt = select(Platform).order_by(Platform.sort_order.asc(), Platform.id.asc())
        if not include_inactive:
            stmt = stmt.where(Platform.is_active.is_(True))
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_by_id(self, platform_id: str) -> Platform | None:
        res = await self.session.execute(
            select(Platform).where(Platform.id == platform_id)
        )
        return res.scalar_one_or_none()

    async def create(self, data: dict) -> Platform:
        platform = Platform(**data)
        self.session.add(platform)
        await self.session.commit()
        await self.session.refresh(platform)
        return platform

    async def update(self, platform_id: str, data: dict) -> Platform | None:
        stmt = (
            update(Platform)
            .where(Platform.id == platform_id)
            .values(**data)
            .returning(Platform)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def delete(self, platform_id: str) -> None:
        await self.session.execute(
            delete(Platform).where(Platform.id == platform_id)
        )
        await self.session.commit()
