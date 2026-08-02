from typing import Any, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting


class AppSettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self) -> Sequence[AppSetting]:
        res = await self.session.execute(
            select(AppSetting).order_by(AppSetting.key.asc())
        )
        return res.scalars().all()

    async def get(self, key: str) -> AppSetting | None:
        res = await self.session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        return res.scalar_one_or_none()

    async def create(self, key: str, value: Any, description: str = "") -> AppSetting:
        setting = AppSetting(key=key, value=value, description=description)
        self.session.add(setting)
        await self.session.commit()
        await self.session.refresh(setting)
        return setting

    async def update(
        self, key: str, value: Any, description: str | None = None
    ) -> AppSetting | None:
        values: dict = {"value": value}
        if description is not None:
            values["description"] = description
        stmt = (
            update(AppSetting).where(AppSetting.key == key).values(**values).returning(AppSetting)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one_or_none()

    async def delete(self, key: str) -> None:
        await self.session.execute(delete(AppSetting).where(AppSetting.key == key))
        await self.session.commit()
