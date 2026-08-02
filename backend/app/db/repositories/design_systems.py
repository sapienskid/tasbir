from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_system import DesignSystem


class DesignSystemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, include_inactive: bool = False) -> list[DesignSystem]:
        stmt = select(DesignSystem).order_by(DesignSystem.created_at.asc())
        if not include_inactive:
            stmt = stmt.where(DesignSystem.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, ds_id: str) -> DesignSystem | None:
        result = await self.session.execute(
            select(DesignSystem).where(DesignSystem.id == ds_id)
        )
        return result.scalar_one_or_none()

    async def create(self, ds_id: str, data: dict) -> DesignSystem:
        ds = DesignSystem(id=ds_id, **data)
        self.session.add(ds)
        await self.session.commit()
        await self.session.refresh(ds)
        return ds

    async def update(self, ds_id: str, data: dict) -> DesignSystem | None:
        stmt = (
            update(DesignSystem)
            .where(DesignSystem.id == ds_id)
            .values(**data)
            .returning(DesignSystem)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def delete(self, ds_id: str) -> None:
        ds = await self.get_by_id(ds_id)
        if ds:
            await self.session.delete(ds)
            await self.session.commit()
