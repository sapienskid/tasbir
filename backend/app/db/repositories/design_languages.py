from typing import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_language import DesignLanguage


class DesignLanguageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, include_inactive: bool = False) -> Sequence[DesignLanguage]:
        stmt = select(DesignLanguage).order_by(
            DesignLanguage.sort_order.asc(), DesignLanguage.id.asc()
        )
        if not include_inactive:
            stmt = stmt.where(DesignLanguage.is_active.is_(True))
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_by_id(self, language_id: str) -> DesignLanguage | None:
        res = await self.session.execute(
            select(DesignLanguage).where(DesignLanguage.id == language_id)
        )
        return res.scalar_one_or_none()

    async def create(self, data: dict) -> DesignLanguage:
        row = DesignLanguage(**data)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update(self, language_id: str, data: dict) -> DesignLanguage | None:
        stmt = (
            update(DesignLanguage)
            .where(DesignLanguage.id == language_id)
            .values(**data)
            .returning(DesignLanguage)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def delete(self, language_id: str) -> None:
        await self.session.execute(
            delete(DesignLanguage).where(DesignLanguage.id == language_id)
        )
        await self.session.commit()
