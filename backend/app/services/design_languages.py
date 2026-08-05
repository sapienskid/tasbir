"""Design-language service — DB-backed languages + preset fallback.

Built-in languages are seeded once from ``styles.STYLE_PRESETS``; the Studio
owns the rows afterward and can add custom languages (based on a preset) and
delete them. Design systems reference a language by id and keep a merged copy
of its ``di`` + tokens, so removing a language never breaks a system.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)


@dataclass
class LanguageDefinition:
    id: str
    name: str
    description: str
    emoji: bool = False
    grayscale: bool = True
    accent: bool = False
    media_policy: str = "photo-forward"
    accent_tokens: dict = field(default_factory=dict)
    palette_tokens: dict = field(default_factory=dict)
    di: dict = field(default_factory=dict)


def _preset_definition(preset_id: str) -> LanguageDefinition | None:
    from app.services.styles import STYLE_PRESETS

    p = STYLE_PRESETS.get(preset_id)
    if p is None:
        return None
    return LanguageDefinition(
        id=preset_id,
        name=p["label"],
        description=p["description"],
        emoji=p["emoji"],
        grayscale=p["grayscale"],
        accent=p["accent"],
        media_policy=p["media_policy"],
        accent_tokens=dict(p.get("accent_tokens") or {}),
        palette_tokens=dict(p.get("palette_tokens") or {}),
        di=p.get("di") or {},
    )


def _row_definition(row) -> LanguageDefinition:
    return LanguageDefinition(
        id=row.id,
        name=row.name,
        description=row.description,
        emoji=bool(row.emoji),
        grayscale=bool(row.grayscale),
        accent=bool(row.accent),
        media_policy=row.media_policy or "photo-forward",
        accent_tokens=dict(row.accent_tokens or {}),
        palette_tokens=dict(row.palette_tokens or {}),
        di=dict(row.di or {}),
    )


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "language"


async def seed_design_languages(pool: async_sessionmaker[AsyncSession]) -> int:
    """Seed-once the built-in presets into the design_languages table."""
    from app.db.repositories.design_languages import DesignLanguageRepository
    from app.services.styles import STYLE_LANGUAGES

    created = 0
    async with pool() as session:
        repo = DesignLanguageRepository(session)
        for order, pid in enumerate(STYLE_LANGUAGES):
            if await repo.get_by_id(pid) is not None:
                continue
            d = _preset_definition(pid)
            if d is None:
                continue
            await repo.create(
                {
                    "id": d.id,
                    "name": d.name,
                    "description": d.description,
                    "base": d.id,
                    "emoji": d.emoji,
                    "grayscale": d.grayscale,
                    "accent": d.accent,
                    "media_policy": d.media_policy,
                    "accent_tokens": d.accent_tokens,
                    "palette_tokens": d.palette_tokens,
                    "di": d.di,
                    "source": "seed",
                    "is_active": True,
                    "sort_order": order,
                }
            )
            created += 1
    if created:
        log.info("[design_languages] Seeded %d built-in language(s)", created)
    return created


async def list_languages(
    db: AsyncSession, include_inactive: bool = False
) -> list[LanguageDefinition]:
    from app.db.repositories.design_languages import DesignLanguageRepository

    rows = await DesignLanguageRepository(db).list(include_inactive=include_inactive)
    out: list[LanguageDefinition] = []
    for r in rows:
        # Built-ins are code-defined — always the live preset definition so
        # STYLE_PRESETS edits (palette, flags, di) propagate without reseeding.
        preset = _preset_definition(r.id)
        if preset is not None:
            out.append(preset)
        else:
            out.append(_row_definition(r))
    return out


async def get_language(db: AsyncSession, language_id: str) -> LanguageDefinition | None:
    """A language by id — built-in presets (live) first, custom DB row fallback."""
    preset = _preset_definition(language_id)
    if preset is not None:
        return preset
    from app.db.repositories.design_languages import DesignLanguageRepository

    row = await DesignLanguageRepository(db).get_by_id(language_id)
    if row is not None:
        return _row_definition(row)
    return None


async def create_custom_language(
    db: AsyncSession, name: str, base: str, description: str = ""
) -> tuple[str, LanguageDefinition]:
    """Create a custom language derived from a preset (its di/tokens/flags)."""
    from app.db.repositories.design_languages import DesignLanguageRepository

    base_def = await get_language(db, base)
    if base_def is None:
        raise ValueError(f"Unknown base design language {base!r}")

    repo = DesignLanguageRepository(db)
    base_id = _slugify(name)
    language_id = base_id
    suffix = 2
    while await repo.get_by_id(language_id):
        language_id = f"{base_id}-{suffix}"
        suffix += 1

    row = await repo.create(
        {
            "id": language_id,
            "name": name.strip(),
            "description": description.strip(),
            "base": base_def.id,
            "emoji": base_def.emoji,
            "grayscale": base_def.grayscale,
            "accent": base_def.accent,
            "media_policy": base_def.media_policy,
            "accent_tokens": dict(base_def.accent_tokens),
            "palette_tokens": dict(base_def.palette_tokens),
            "di": dict(base_def.di),
            "source": "manual",
            "is_active": True,
            "sort_order": 999,
        }
    )
    return language_id, _row_definition(row)


async def delete_language(db: AsyncSession, language_id: str) -> None:
    """Delete a language. Built-in presets are immutable."""
    from app.db.repositories.design_languages import DesignLanguageRepository

    repo = DesignLanguageRepository(db)
    row = await repo.get_by_id(language_id)
    if row is None:
        return
    if row.source == "seed":
        raise ValueError(
            f"'{row.name}' is a built-in design language and cannot be deleted"
        )
    await repo.delete(language_id)


async def apply_language(db: AsyncSession, language_id: str, di: dict | None = None) -> dict:
    """Merge a language's ``di`` bundle into a design-instruction dict.

    Mirrors ``apply_style_preset`` but for any language (DB row or preset):
    the language owns style/type_voice/do_dont/layout_archetypes/default_ground
    + photo; structural fields (type_scale/spacing/footer/...) are preserved.
    """
    from app.services.styles import apply_style_preset

    lang = await get_language(db, language_id)
    if lang is None:
        language_id = "swiss-editorial"
        lang = await get_language(db, language_id)
    result = apply_style_preset(language_id, di or {})
    # Overlay the language's own bundle (covers custom languages not in presets).
    bundle = dict(lang.di or {})
    for key in ("style", "type_voice", "do_dont", "layout_archetypes", "default_ground"):
        if bundle.get(key) is not None:
            result[key] = bundle[key]
    photo = dict(bundle.get("photo") or {})
    photo.setdefault("grayscale", lang.grayscale)
    photo.setdefault("media_policy", lang.media_policy)
    result["photo"] = photo
    result["style_language"] = lang.id
    return result


__all__ = [
    "LanguageDefinition",
    "apply_language",
    "create_custom_language",
    "delete_language",
    "get_language",
    "list_languages",
    "seed_design_languages",
]
