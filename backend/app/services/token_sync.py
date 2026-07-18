"""Bidirectional token sync — Penpot ↔ database synchronization.

Keeps the local design_tokens table in sync with Penpot's design tokens.
Can run on-demand or on Penpot webhook triggers.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tokens import DesignToken


async def sync_from_penpot(db: AsyncSession) -> list[DesignToken]:
    """Pull latest tokens from Penpot and update local DB.

    Args:
        db: Database session.

    Returns:
        List of updated/created DesignToken records.
    """
    from app.services.penpot import fetch_tokens

    penpot_data = await fetch_tokens()
    if not penpot_data:
        return []

    synced: list[DesignToken] = []

    for name, token_data in penpot_data.items():
        result = await db.execute(
            select(DesignToken).where(DesignToken.name == name)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.data = token_data if isinstance(token_data, dict) else {}
            existing.version += 1
            existing.source = "penpot"
            synced.append(existing)
        else:
            token = DesignToken(
                name=name,
                data=token_data if isinstance(token_data, dict) else {},
                source="penpot",
            )
            db.add(token)
            synced.append(token)

    await db.commit()
    for token in synced:
        await db.refresh(token)

    return synced


async def sync_to_penpot(db: AsyncSession) -> bool:
    """Push local design tokens to Penpot.

    Args:
        db: Database session.

    Returns:
        True if successful.
    """
    from app.services.penpot import push_tokens

    result = await db.execute(select(DesignToken).where(DesignToken.source == "manual"))
    local_tokens = result.scalars().all()

    if not local_tokens:
        return False

    payload = {t.name: t.data for t in local_tokens}
    return await push_tokens(payload)
