#!/usr/bin/env python3
"""Seed default design tokens and brand for playground testing."""
import asyncio
import sys
import uuid
from sqlalchemy import select

sys.path.insert(0, "backend")

from app.config import get_settings
from app.db.session import create_pool
from app.models.tokens import DesignToken


async def seed():
    settings = get_settings()
    engine, pool = await create_pool(settings.database_url)

    async with pool() as session:
        result = await session.execute(select(DesignToken).where(DesignToken.name == "default"))
        existing = result.scalar_one_or_none()
        if not existing:
            dt = DesignToken(
                id=uuid.uuid4(),
                name="default",
                data={
                    "color": {
                        "primary": {"$value": "#CD5B7D"},
                        "secondary": {"$value": "#5B7D7C"},
                        "accent": {"$value": "#6366F1"},
                        "surface": {"$value": "#1E293B"},
                    },
                    "fontFamily": {
                        "sans": {"$value": "Inter, system-ui, sans-serif"},
                        "serif": {"$value": "Instrument Serif, Georgia, serif"},
                        "mono": {"$value": "JetBrains Mono, monospace"},
                    },
                },
                source="seed",
            )
            session.add(dt)
            print("  + DesignToken: default")
        else:
            print("  = DesignToken: default (exists)")

        await session.commit()

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
