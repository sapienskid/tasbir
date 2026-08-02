from typing import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template


class TemplateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        design_system_id: str = "default",
        family: str | None = None,
        include_inactive: bool = False,
    ) -> Sequence[Template]:
        stmt = select(Template).where(Template.design_system_id == design_system_id)
        if family:
            stmt = stmt.where(Template.family == family)
        if not include_inactive:
            stmt = stmt.where(Template.is_active.is_(True))
        stmt = stmt.order_by(Template.created_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, template_id: str) -> Template | None:
        result = await self.session.execute(
            select(Template).where(Template.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Template:
        tpl = Template(**data)
        self.session.add(tpl)
        await self.session.commit()
        await self.session.refresh(tpl)
        return tpl

    async def update(self, template_id: str, data: dict) -> Template | None:
        stmt = (
            update(Template)
            .where(Template.id == template_id)
            .values(**data)
            .returning(Template)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def delete(self, template_id: str) -> None:
        await self.session.execute(delete(Template).where(Template.id == template_id))
        await self.session.commit()

    async def delete_for_design_system(self, ds_id: str) -> int:
        res = await self.session.execute(
            delete(Template).where(Template.design_system_id == ds_id)
        )
        await self.session.commit()
        return res.rowcount or 0
