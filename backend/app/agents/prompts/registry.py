"""Prompt registry — loads prompts from database with fallback to defaults.

Prompts are stored in the `prompt_registry` table and can be edited
via the API without redeploying the application.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts.copywriter import COPYWRITER_SYSTEM_PROMPT
from app.agents.prompts.designer import DESIGNER_SYSTEM_PROMPT
from app.agents.prompts.quality_check import QUALITY_CHECK_SYSTEM_PROMPT
from app.agents.prompts.strategist import STRATEGIST_SYSTEM_PROMPT
from app.agents.prompts.token_generator import TOKEN_GENERATOR_SYSTEM_PROMPT
from app.agents.prompts.visual_director import VISUAL_DIRECTOR_SYSTEM_PROMPT


@dataclass
class PromptVersion:
    system_prompt: str
    user_template: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000


DEFAULT_PROMPTS: dict[str, PromptVersion] = {
    "strategist": PromptVersion(
        system_prompt=STRATEGIST_SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=1500,
    ),
    "copywriter": PromptVersion(
        system_prompt=COPYWRITER_SYSTEM_PROMPT,
        temperature=0.75,
        max_tokens=2000,
    ),
    "visual_director": PromptVersion(
        system_prompt=VISUAL_DIRECTOR_SYSTEM_PROMPT,
        temperature=0.6,
        max_tokens=1200,
    ),
    "designer": PromptVersion(
        system_prompt=DESIGNER_SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=8192,
    ),
    "quality_check": PromptVersion(
        system_prompt=QUALITY_CHECK_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=800,
    ),
    "token_generator": PromptVersion(
        system_prompt=TOKEN_GENERATOR_SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=2000,
    ),
}


async def get_prompt(
    name: str,
    db: AsyncSession | None = None,
) -> PromptVersion:
    """Get a prompt by name.

    Attempts to load from database first. Falls back to defaults
    if the prompt is not found in the registry or no DB session provided.
    """
    if db is None:
        try:
            from app.config import get_settings
            from app.db.session import create_pool

            settings = get_settings()
            engine, pool = await create_pool(settings.database_url)
            async with pool() as session:
                from app.models.prompt import PromptRegistry

                result = await session.execute(
                    select(PromptRegistry).where(
                        PromptRegistry.name == name,
                        PromptRegistry.is_active.is_(True),
                    )
                )
                record = result.scalar_one_or_none()
            await engine.dispose()

            if record is not None:
                return PromptVersion(
                    system_prompt=record.system_prompt,
                    user_template=record.user_template,
                    temperature=record.temperature,
                    max_tokens=record.max_tokens,
                )
        except Exception:
            pass
    elif db is not None:
        from app.models.prompt import PromptRegistry

        result = await db.execute(
            select(PromptRegistry).where(
                PromptRegistry.name == name,
                PromptRegistry.is_active.is_(True),
            )
        )
        record = result.scalar_one_or_none()

        if record is not None:
            return PromptVersion(
                system_prompt=record.system_prompt,
                user_template=record.user_template,
                temperature=record.temperature,
                max_tokens=record.max_tokens,
            )

    prompt = DEFAULT_PROMPTS.get(name)
    if not prompt:
        msg = f"Unknown prompt: {name}. Available: {list(DEFAULT_PROMPTS.keys())}"
        raise ValueError(msg)
    return prompt


async def list_prompts(
    db: AsyncSession | None = None,
) -> dict[str, PromptVersion]:
    """List all available prompts."""
    prompts = dict(DEFAULT_PROMPTS)

    if db is not None:
        from app.models.prompt import PromptRegistry

        result = await db.execute(
            select(PromptRegistry).where(PromptRegistry.is_active.is_(True))
        )
        for record in result.scalars().all():
            prompts[record.name] = PromptVersion(
                system_prompt=record.system_prompt,
                user_template=record.user_template,
                temperature=record.temperature,
                max_tokens=record.max_tokens,
            )

    return prompts


async def update_prompt(
    name: str,
    system_prompt: str,
    db: AsyncSession,
    user_template: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> PromptVersion:
    """Update or create a prompt. Creates a new version entry."""
    from app.models.prompt import PromptRegistry
    from app.models.prompt import PromptVersion as PromptVersionModel

    result = await db.execute(
        select(PromptRegistry).where(PromptRegistry.name == name)
    )
    record = result.scalar_one_or_none()

    if record:
        record.system_prompt = system_prompt
        if user_template is not None:
            record.user_template = user_template
        record.temperature = temperature
        record.max_tokens = max_tokens
        record.version += 1
    else:
        record = PromptRegistry(
            name=name,
            system_prompt=system_prompt,
            user_template=user_template or "",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        db.add(record)

    version_record = PromptVersionModel(
        prompt_name=name,
        version=record.version,
        system_prompt=system_prompt,
        user_template=user_template,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    db.add(version_record)
    await db.commit()
    await db.refresh(record)

    return PromptVersion(
        system_prompt=record.system_prompt,
        user_template=record.user_template,
        temperature=record.temperature,
        max_tokens=record.max_tokens,
    )
