"""Prompt registry — loads prompts from database with fallback to defaults.

Prompts are stored in the `prompt_registry` table and can be edited
via the API without redeploying the application.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class PromptVersion:
    system_prompt: str
    user_template: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000


DEFAULT_PROMPTS: dict[str, PromptVersion] = {
    "strategist": PromptVersion(
        system_prompt=(
            "You are a content strategist. Analyze the provided content and "
            "determine its type, key message, target audience, and the best "
            "campaign angle for social media. Output a brief strategic plan."
        ),
        temperature=0.7,
        max_tokens=1000,
    ),
    "copywriter": PromptVersion(
        system_prompt=(
            "You are a social media copywriter. Write platform-native copy "
            "for the given format. Keep it concise, engaging, and specific. "
            "No filler, no generic statements. Each platform has its own voice."
        ),
        temperature=0.8,
        max_tokens=1500,
    ),
    "visual_director": PromptVersion(
        system_prompt=(
            "You are a visual director. Choose a background style for this "
            "post: gradient, pattern, solid color, or stock photo. "
            "Consider the brand's design tokens and content mood."
        ),
        temperature=0.6,
        max_tokens=800,
    ),
    "designer": PromptVersion(
        system_prompt=(
            "You are a social media designer. Generate a complete standalone "
            "HTML document for screenshot rendering. Use Tailwind CSS via CDN. "
            "Make the design visually striking with bold typography, high contrast, "
            "and clean layout. Ensure the design fits exactly within the specified "
            "dimensions. No overflow, no scrollbars. Output ONLY the HTML."
        ),
        temperature=0.7,
        max_tokens=8192,
    ),
    "quality_check": PromptVersion(
        system_prompt=(
            "You are a quality assurance reviewer. Check the generated output "
            "for: text overflow, readability, brand compliance, contrast, "
            "and visual balance. Pass or fail with specific reasons."
        ),
        temperature=0.3,
        max_tokens=500,
    ),
    "token_generator": PromptVersion(
        system_prompt=(
            "You are a design token expert. Generate a complete set of design "
            "tokens in DTCG format based on the described brand identity. "
            "Include colors, typography, spacing, and border radius tokens."
        ),
        temperature=0.8,
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

    Args:
        name: Prompt name (e.g., 'strategist', 'copywriter').
        db: Optional database session for DB-backed lookup.

    Returns:
        The PromptVersion with system_prompt, temperature, etc.
    """
    if db is None:
        try:
            from app.config import get_settings
            from app.db.session import create_pool

            settings = get_settings()
            engine, pool = await create_pool(settings.database_url)
            async with pool() as session:
                db = session
        except Exception:
            pass

    if db is not None:
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
    """List all available prompts.

    Args:
        db: Optional database session. If provided, returns DB prompts
            merged with defaults.

    Returns:
        Dictionary of prompt names to PromptVersion objects.
    """
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
    """Update or create a prompt. Creates a new version entry.

    Args:
        name: Prompt name (e.g., 'strategist', 'copywriter').
        system_prompt: New system prompt text.
        db: Database session (required for DB-backed storage).
        user_template: Optional user message template.
        temperature: Model temperature (0.0-1.0).
        max_tokens: Maximum output tokens.

    Returns:
        The updated PromptVersion.
    """
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
