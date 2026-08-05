"""Stored design-instruction migration for legacy/imported design systems."""

import asyncio
import json

from app.db.repositories.design_systems import DesignSystemRepository
from app.db.session import get_shared_session_factory
from app.services.seeding import migrate_stored_design_instructions

LEGACY_DI = {
    "style": {"name": "Legacy", "palette": "monochrome", "emoji": False},
    "type_voice": {"display": "display face for headline and footer wordmark"},
    "do_dont": {
        "do": ["Left align"],
        "dont": ["Never use serif for the wordmark", "No hue"],
    },
}


def test_migrates_legacy_design_instruction():
    async def _run():
        pool = await get_shared_session_factory()
        async with pool() as s:
            repo = DesignSystemRepository(s)
            if await repo.get_by_id("legacy-ds") is None:
                await repo.create(
                    "legacy-ds",
                    {
                        "name": "Legacy",
                        "design_instruction": json.loads(json.dumps(LEGACY_DI)),
                        "source": "manual",
                        "is_active": True,
                    },
                )
        changed = await migrate_stored_design_instructions(pool)
        async with pool() as s:
            ds = await DesignSystemRepository(s).get_by_id("legacy-ds")
            di = ds.design_instruction
        return changed, di

    changed, di = asyncio.run(_run())
    assert changed >= 1
    assert "style_language" in di
    assert "photo" in di
    assert di["style_language"] == "swiss-editorial"
    assert di["photo"]["grayscale"] is True
    assert di["photo"]["media_policy"] == "photo-forward"
    # Stale footer-wordmark wording is refreshed by the language bundle.
    assert "wordmark" not in json.dumps(di)


def test_migration_is_idempotent_and_skips_current_rows():
    async def _run():
        pool = await get_shared_session_factory()
        before = await migrate_stored_design_instructions(pool)
        again = await migrate_stored_design_instructions(pool)
        async with pool() as s:
            repo = DesignSystemRepository(s)
            ds = await repo.get_by_id("legacy-ds")
            di = ds.design_instruction
        return before, again, di

    before, again, di = asyncio.run(_run())
    assert again == 0  # second pass changes nothing
    assert "style_language" in di and "photo" in di
