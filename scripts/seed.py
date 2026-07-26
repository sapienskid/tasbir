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
                   ai_instruction="Square 1080x1080. Use asymmetric 2-zone split (left 40% image/color block, right 60% text) OR 3-zone stack (headline top 25%, visual center 50%, tagline bottom 25%). Cards with bg-brand-surface. Never center everything. Bold editorial typography. Strong negative space."),
            Format(id="instagram-portrait", name="Instagram Portrait", width=1080, height=1350,
                   ai_instruction="Portrait 1080x1350. Magazine-style vertical layout. Zone 1 (top 30%): immersive visual or bold headline. Zone 2 (middle 50%): body copy in 2-3 text blocks with breathing room. Zone 3 (bottom 20%): tagline + badge. Use overlapping elements and intentional asymmetry."),
            Format(id="instagram-story", name="Instagram Story", width=1080, height=1920,
                   ai_instruction="Full-screen 1080x1920. Zone 1 (top 20%): bold single-line headline. Zone 2 (20-70%): dominant visual/illustration/photo — fill 50% of canvas. Zone 3 (70-90%): 2-3 key points in cards. Zone 4 (bottom 10%): tagline. Vertical rhythm with varied spacing. Immersive, punchy."),
            Format(id="linkedin-post", name="LinkedIn Post", width=1200, height=627,
                   ai_instruction="Landscape 1200x627. Horizontal split: left 55% headline+subhead stacked, right 45% visual/accent block. OR clean centered headline with bottom key-points strip. Professional, structured, generous whitespace. Use bg-brand-surface cards for key points."),
            Format(id="twitter-card", name="X / Twitter Card", width=1200, height=675,
                   ai_instruction="Card 1200x675. Single bold headline — maximum impact, minimum text. One strong visual element: large illustration, photo panel, or color block. No more than 2 text zones. Tagline bottom-right. Punchy, scannable in <1 second."),
            Format(id="facebook-post", name="Facebook Post", width=1200, height=630,
                   ai_instruction="Feed 1200x630. Warm, approachable layout. Zone 1 (top 30%): headline. Zone 2 (middle 40%): supporting visual or card. Zone 3 (bottom 30%): key takeaway + tagline. Soft visual style with rounded cards and warm spacing."),
            Format(id="pinterest-pin", name="Pinterest Pin", width=1000, height=1500,
                   ai_instruction="Tall pin 1000x1500. Vertical flow: title top, dominant visual center 50%, details in 2-3 stacked cards below. Generous top and bottom padding. Use bg-brand-surface for card elements. Optimize for scroll-stopping visual appeal."),
        ]

        for fmt in formats:
            existing = await session.get(Format, fmt.id)
            if not existing:
                session.add(fmt)
                print(f"  + Format: {fmt.id}")
            else:
                existing.name = fmt.name
                existing.width = fmt.width
                existing.height = fmt.height
                existing.ai_instruction = fmt.ai_instruction
                print(f"  = Format: {fmt.id} (updated)")

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
