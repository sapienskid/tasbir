from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt import PromptRegistry, PromptVersion


class PromptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> Sequence[PromptRegistry]:
        result = await self.session.execute(
            select(PromptRegistry).where(PromptRegistry.is_active.is_(True))
        )
        return result.scalars().all()

    async def get_by_name(self, name: str) -> PromptRegistry | None:
        result = await self.session.execute(
            select(PromptRegistry).where(PromptRegistry.name == name)
        )
        return result.scalar_one_or_none()

    async def upsert(self, name: str, data: dict) -> PromptRegistry:
        existing = await self.get_by_name(name)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.version += 1
        else:
            existing = PromptRegistry(name=name, **data)
            self.session.add(existing)

        # Archive previous version
        if existing:
            version_record = PromptVersion(
                prompt_name=existing.name,
                version=existing.version,
                system_prompt=existing.system_prompt,
                user_template=existing.user_template,
                temperature=existing.temperature,
                max_tokens=existing.max_tokens,
            )
            self.session.add(version_record)

        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def get_version_history(
        self, name: str
    ) -> Sequence[PromptVersion]:
        result = await self.session.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_name == name)
            .order_by(PromptVersion.version.desc())
        )
        return result.scalars().all()

    async def restore_version(
        self, name: str, version: int
    ) -> PromptRegistry | None:
        version_record = await self.session.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_name == name,
                PromptVersion.version == version,
            )
        )
        record = version_record.scalar_one_or_none()
        if not record:
            return None

        prompt = await self.get_by_name(name)
        if not prompt:
            return None

        prompt.system_prompt = record.system_prompt
        prompt.user_template = record.user_template
        prompt.temperature = record.temperature
        prompt.max_tokens = record.max_tokens
        prompt.version += 1

        # Create a new version entry for the restored version
        new_version = PromptVersion(
            prompt_name=prompt.name,
            version=prompt.version,
            system_prompt=prompt.system_prompt,
            user_template=prompt.user_template,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        self.session.add(new_version)
        await self.session.commit()
        await self.session.refresh(prompt)
        return prompt
