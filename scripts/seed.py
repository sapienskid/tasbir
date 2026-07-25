#!/usr/bin/env python3
"""Seed default data: formats, prompts, settings.

Run after first migration:
    cd backend && alembic upgrade head && python ../scripts/seed.py
"""

import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from app.config import get_settings
from app.db.session import create_pool
from app.models.format import Format
from app.models.prompt import PromptRegistry
from app.models.settings import Settings


async def seed():
    settings = get_settings()
    pool = await create_pool(settings.database_url)

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
        prompts = [
            PromptRegistry(
                name="strategist",
                system_prompt=(
                    "You are a content strategist. Analyze the provided content and "
                    "determine its type, key message, target audience, and the best "
                    "campaign angle for social media. Output a brief strategic plan."
                ),
                temperature=0.7, max_tokens=1000,
            ),
            PromptRegistry(
                name="copywriter",
                system_prompt=(
                    "You are a social media copywriter. Write platform-native copy "
                    "for the given format. Keep it concise, engaging, and specific. "
                    "No filler, no generic statements. Each platform has its own voice."
                ),
                temperature=0.8, max_tokens=1500,
            ),
            PromptRegistry(
                name="visual_director",
                system_prompt=(
                    "You are a visual director. Choose a background style for this "
                    "post: gradient, pattern, solid color, or stock photo. "
                    "Consider the brand's design tokens and content mood."
                ),
                temperature=0.6, max_tokens=800,
            ),
            PromptRegistry(
                name="designer",
                system_prompt=(
                    "You are a social media designer. Generate a complete standalone "
                    "HTML document for screenshot rendering. Use Tailwind CSS via CDN. "
                    "Apply the provided design tokens. Ensure the design fits exactly "
                    "within the specified dimensions. No overflow, no scrollbars."
                ),
                temperature=0.7, max_tokens=2500,
            ),
            PromptRegistry(
                name="quality_check",
                system_prompt=(
                    "You are a quality assurance reviewer. Check the generated output "
                    "for: text overflow, readability, brand compliance, contrast, "
                    "and visual balance. Pass or fail with specific reasons."
                ),
                temperature=0.3, max_tokens=500,
            ),
            PromptRegistry(
                name="token_generator",
                system_prompt=(
                    "You are a design token expert. Generate a complete set of design "
                    "tokens in DTCG format based on the described brand identity. "
                    "Include colors, typography, spacing, and border radius tokens."
                ),
                temperature=0.8, max_tokens=2000,
            ),
        ]

        for pr in prompts:
            existing = await session.get(PromptRegistry, pr.name)
            if not existing:
                session.add(pr)
                print(f"  + Prompt: {pr.name}")
            else:
                print(f"  = Prompt: {pr.name} (exists)")

        # ── Settings ─────────────────────────────────────────────
        existing_settings = await session.get(Settings, 1)
        if not existing_settings:
            session.add(Settings(id=1, data={}))
            print("  + Settings: initialized")
        else:
            print("  = Settings: (exists)")

        await session.commit()

    await pool.sync_engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
