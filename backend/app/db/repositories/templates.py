import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template


class TemplateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, enabled_only: bool = True) -> Sequence[Template]:
        stmt = select(Template).order_by(Template.created_at.desc())
        if enabled_only:
            stmt = stmt.where(Template.enabled.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, template_id: uuid.UUID) -> Template | None:
        result = await self.session.execute(
            select(Template).where(Template.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Template:
        template = Template(**data)
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def update(self, template_id: uuid.UUID, data: dict) -> Template | None:
        stmt = (
            update(Template)
            .where(Template.id == template_id)
            .values(**data)
            .returning(Template)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def delete(self, template_id: uuid.UUID) -> bool:
        template = await self.get_by_id(template_id)
        if template:
            await self.session.delete(template)
            await self.session.commit()
            return True
        return False
