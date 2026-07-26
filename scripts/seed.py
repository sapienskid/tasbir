#!/usr/bin/env python3
"""Seed default data: formats, prompts, settings.

Run after first migration:
    cd backend && alembic upgrade head && python ../scripts/seed.py
"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.agents.prompts.registry import DEFAULT_PROMPTS
from app.config import get_settings
from app.db.session import create_pool
from app.models.format import Format
from app.models.prompt import PromptRegistry
from app.models.settings import Settings


async def seed():
    settings = get_settings()
    engine, pool = await create_pool(settings.database_url)

    async with pool() as session:
        # ── Formats ──────────────────────────────────────────────
        formats = [
            Format(id="instagram-square", name="Instagram Square", width=1080, height=1080,
                   ai_instruction="Square format for Instagram feed. Bold visual, minimal text overlay."),
            Format(id="instagram-portrait", name="Instagram Portrait", width=1080, height=1350,
                   ai_instruction="Portrait format for Instagram feed. Vertical layout with more text room."),
            Format(id="instagram-story", name="Instagram Story", width=1080, height=1920,
                   ai_instruction="Full-screen vertical story. Top title, bottom CTA, center visual."),
            Format(id="linkedin-post", name="LinkedIn Post", width=1200, height=627,
                   ai_instruction="LinkedIn feed format. Professional tone, clean layout, company branding."),
            Format(id="twitter-card", name="X / Twitter Card", width=1200, height=675,
                   ai_instruction="Twitter card format. Bold headline, single strong visual."),
            Format(id="facebook-post", name="Facebook Post", width=1200, height=630,
                   ai_instruction="Facebook feed format. Engaging visual with supporting text."),
            Format(id="pinterest-pin", name="Pinterest Pin", width=1000, height=1500,
                   ai_instruction="Tall pin format. Vertical layout, top-to-bottom content flow."),
        ]

        for fmt in formats:
            existing = await session.get(Format, fmt.id)
            if not existing:
                session.add(fmt)
                print(f"  + Format: {fmt.id}")
            else:
                print(f"  = Format: {fmt.id} (exists)")

        # ── Prompts ──────────────────────────────────────────────
        for name, pv in DEFAULT_PROMPTS.items():
            existing = await session.get(PromptRegistry, name)
            if not existing:
                session.add(
                    PromptRegistry(
                        name=name,
                        system_prompt=pv.system_prompt,
                        temperature=pv.temperature,
                        max_tokens=pv.max_tokens,
                    )
                )
                print(f"  + Prompt: {name}")
            else:
                existing.system_prompt = pv.system_prompt
                existing.temperature = pv.temperature
                existing.max_tokens = pv.max_tokens
                print(f"  = Prompt: {name} (updated)")

        # ── Settings ─────────────────────────────────────────────
        existing_settings = await session.get(Settings, 1)
        if not existing_settings:
            session.add(Settings(id=1, data={}))
            print("  + Settings: initialized")
        else:
            print("  = Settings: (exists)")

        await session.commit()

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
