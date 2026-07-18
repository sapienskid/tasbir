import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_key(self, key: str) -> Asset | None:
        result = await self.session.execute(
            select(Asset).where(Asset.key == key)
        )
        return result.scalar_one_or_none()

    async def list_by_task(self, task_id: uuid.UUID) -> Sequence[Asset]:
        result = await self.session.execute(
            select(Asset).where(Asset.task_id == task_id)
        )
        return result.scalars().all()

    async def create(self, data: dict) -> Asset:
        asset = Asset(**data)
        self.session.add(asset)
        await self.session.commit()
        await self.session.refresh(asset)
        return asset
