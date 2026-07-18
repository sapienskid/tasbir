from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> Settings | None:
        result = await self.session.execute(select(Settings).where(Settings.id == 1))
        return result.scalar_one_or_none()

    async def upsert(self, data: dict) -> Settings:
        settings = await self.get()
        if settings:
            settings.data = data
        else:
            settings = Settings(id=1, data=data)
            self.session.add(settings)
        await self.session.commit()
        await self.session.refresh(settings)
        return settings
