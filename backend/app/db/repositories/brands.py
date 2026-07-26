import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand


class BrandRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self) -> list[Brand]:
        result = await self.session.execute(
            select(Brand).order_by(Brand.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, brand_id: uuid.UUID) -> Brand | None:
        result = await self.session.execute(
            select(Brand).where(Brand.id == brand_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Brand | None:
        result = await self.session.execute(
            select(Brand).where(Brand.name.ilike(name))
        )
        return result.scalar_one_or_none()

    async def create(
        self, name: str, description: str, data: dict, source: str = "ai-generated"
    ) -> Brand:
        brand = Brand(name=name, description=description, data=data, source=source)
        self.session.add(brand)
        await self.session.commit()
        await self.session.refresh(brand)
        return brand

    async def update(self, brand_id: uuid.UUID, **kwargs) -> Brand | None:
        brand = await self.get_by_id(brand_id)
        if not brand:
            return None
        if "name" in kwargs:
            brand.name = kwargs["name"]
        if "description" in kwargs is not None:
            brand.description = kwargs.get("description")
        if "data" in kwargs:
            brand.data = {**brand.data, **kwargs["data"]}
        brand.version += 1
        await self.session.commit()
        await self.session.refresh(brand)
        return brand

    async def update_fields(self, brand_id: uuid.UUID, fields: dict) -> Brand | None:
        stmt = (
            update(Brand)
            .where(Brand.id == brand_id)
            .values(**fields)
            .returning(Brand)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def delete(self, brand_id: uuid.UUID) -> bool:
        brand = await self.get_by_id(brand_id)
        if not brand:
            return False
        await self.session.delete(brand)
        await self.session.commit()
        return True
