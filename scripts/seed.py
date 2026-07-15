#!/usr/bin/env python3
"""Seed default data: formats, prompts, settings.

Run after first migration:
    cd backend && alembic upgrade head && python ../scripts/seed.py
"""

import asyncio
import json

DEFAULT_FORMATS = {
    "instagram-square": {"width": 1080, "height": 1080, "name": "Instagram Square"},
    "instagram-portrait": {"width": 1080, "height": 1350, "name": "Instagram Portrait"},
    "instagram-story": {"width": 1080, "height": 1920, "name": "Instagram Story"},
    "twitter-card": {"width": 1200, "height": 628, "name": "Twitter/X Card"},
    "linkedin-post": {"width": 1200, "height": 627, "name": "LinkedIn Post"},
    "facebook-post": {"width": 1200, "height": 630, "name": "Facebook Post"},
    "pinterest-pin": {"width": 1000, "height": 1500, "name": "Pinterest Pin"},
    "carousel-post": {"width": 1080, "height": 1350, "name": "Carousel Post"},
}

DEFAULT_PROMPTS = {
    "strategist": {
        "system_prompt": "You are a content strategist...",
        "temperature": 0.7,
        "max_tokens": 1000,
    },
    "copywriter": {
        "system_prompt": "You are a social media copywriter...",
        "temperature": 0.8,
        "max_tokens": 1500,
    },
    "visual_director": {
        "system_prompt": "You are a visual director...",
        "temperature": 0.6,
        "max_tokens": 800,
    },
    "designer": {
        "system_prompt": "You are a social media designer...",
        "temperature": 0.7,
        "max_tokens": 2500,
    },
    "quality_check": {
        "system_prompt": "You are a quality assurance reviewer...",
        "temperature": 0.3,
        "max_tokens": 500,
    },
    "token_generator": {
        "system_prompt": "You are a design token expert...",
        "temperature": 0.8,
        "max_tokens": 2000,
    },
}


async def seed():
    print("Seeding default data...")
    # TODO: Insert into database using SQLAlchemy
    print(f"  Formats: {len(DEFAULT_FORMATS)}")
    print(f"  Prompts: {len(DEFAULT_PROMPTS)}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
