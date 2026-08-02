from typing import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.font import Font


class FontRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self, include_inactive: bool = False
    ) -> Sequence[Font]:
        stmt = select(Font).order_by(Font.sort_order.asc(), Font.family.asc())
        if not include_inactive:
            stmt = stmt.where(Font.is_active.is_(True))
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_by_family(self, family: str) -> Font | None:
        res = await self.session.execute(
            select(Font).where(Font.family == family)
        )
        return res.scalar_one_or_none()

    async def create(self, data: dict) -> Font:
        font = Font(**data)
        self.session.add(font)
        await self.session.commit()
        await self.session.refresh(font)
        return font

    async def update(self, family: str, data: dict) -> Font | None:
        stmt = (
            update(Font).where(Font.family == family).values(**data).returning(Font)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def delete(self, family: str) -> None:
        await self.session.execute(delete(Font).where(Font.family == family))
        await self.session.commit()
