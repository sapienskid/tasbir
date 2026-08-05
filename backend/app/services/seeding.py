"""Seed the database with the ``default`` design system + its templates.

v0.5 moved design systems and templates into SQLite. On first boot (when no
design system rows exist) this imports the existing YAML config
(brand/tokens/campaigns/design-instruction) and the template catalog + files
into the DB. Idempotent — a ``default`` row skips the whole seed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.services.design_instruction import load_design_instruction
from app.services.templates import (
    load_template_catalog,
    scan_template_features,
    templates_dir,
)
from app.services.tokens import (
    DEFAULT_CATEGORIES,
    SEMANTIC_VAR_ROLES,
    load_brand,
    load_brand_design,
    load_platforms,
    load_tokens,
)

log = logging.getLogger(__name__)

_DEFAULT_ID = "default"


def _load_campaigns(path: str | Path) -> dict:
    import yaml

    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        log.warning("[seed] Failed to load campaigns %s: %s", path, e)
        return {}


async def seed_default_design_system(pool: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()

    async with pool() as session:
        from app.db.repositories.design_systems import DesignSystemRepository

        existing = await DesignSystemRepository(session).get_by_id(_DEFAULT_ID)
        if existing is not None:
            return

        from app.db.repositories.templates import TemplateRepository

        brand_data = load_brand(settings.brand_path)
        brand_design = load_brand_design(settings.brand_path)
        tokens = load_tokens(settings.tokens_path)
        campaigns = _load_campaigns(settings.campaigns_path)
        di_config = load_design_instruction(
            Path(settings.design_system_dir) / "design-instruction.yaml"
        )

        categories = (
            brand_design["categories"]
            if isinstance(brand_design["categories"], list)
            else DEFAULT_CATEGORIES
        )
        footer = brand_design.get("footer", {"left": "", "right": ""})
        overrides = brand_data.get("overrides") or {}

        await DesignSystemRepository(session).create(
            _DEFAULT_ID,
            {
                "name": "Default",
                "description": "Migrated Swiss / International Typographic Style "
                "(the original v0.4 design system).",
                "brand": brand_data.get("brand", {}),
                "footer": footer,
                "categories": categories,
                "overrides": overrides,
                "tokens": tokens,
                "token_roles": dict(SEMANTIC_VAR_ROLES),
                "campaigns": campaigns,
                "design_instruction": di_config,
                "source": "seed",
                "is_active": True,
            },
        )

        # Migrate the catalog of Jinja2 template files into Template rows.
        catalog = load_template_catalog().get("templates", {})
        tpl_repo = TemplateRepository(session)
        seeded = 0
        for tid, entry in catalog.items():
            rel_file = entry.get("file", "")
            file_path = templates_dir() / rel_file
            if not file_path.is_file():
                log.warning("[seed] Missing template file %s — skipping", rel_file)
                continue
            html = file_path.read_text(encoding="utf-8")
            image_slots, has_logo = scan_template_features(html)
            await tpl_repo.create(
                {
                    "id": tid,
                    "design_system_id": _DEFAULT_ID,
                    "name": entry.get("name") or tid,
                    "family": entry.get("family", "square"),
                    "grounds": entry.get("grounds", ["white", "black"]),
                    "categories": entry.get("categories", []),
                    "hint_tags": entry.get("hint_tags", []),
                    "weight": float(entry.get("weight", 1.0)),
                    "description": entry.get("description", ""),
                    "html": html,
                    "image_slots": image_slots,
                    "has_logo_slot": has_logo,
                    "source": "seed",
                    "is_active": True,
                }
            )
            seeded += 1

        log.info(
            "[seed] Created default design system + %d templates", seeded
        )


async def sync_seed_design_system(pool: async_sessionmaker[AsyncSession]) -> dict:
    """Reconcile seed-source rows with the canonical YAML + template files.

    The DB is the source of truth at runtime, but the YAML/template files are
    the canonical seed. This upserts the ``default`` design system and every
    ``source == "seed"`` template from those files so file edits are reflected.
    User-created (manual/promoted/ai) rows and ``is_active`` state are preserved.
    Returns a summary of what changed.
    """
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.db.repositories.templates import TemplateRepository

    settings = get_settings()
    summary = {"design_system": [], "templates_updated": [], "templates_created": []}

    brand_data = load_brand(settings.brand_path)
    brand_design = load_brand_design(settings.brand_path)
    tokens = load_tokens(settings.tokens_path)
    campaigns = _load_campaigns(settings.campaigns_path)
    di_config = load_design_instruction(
        Path(settings.design_system_dir) / "design-instruction.yaml"
    )
    categories = (
        brand_design["categories"]
        if isinstance(brand_design["categories"], list)
        else DEFAULT_CATEGORIES
    )

    async with pool() as session:
        ds_repo = DesignSystemRepository(session)
        ds = await ds_repo.get_by_id(_DEFAULT_ID)
        if ds is None:
            await seed_default_design_system(pool)
            summary["design_system"].append("created default")
            return summary

        # The Studio owns the rows after first boot. While the default system
        # is still seed-owned (untouched), re-apply YAML edits on restart;
        # once a user edits it (Studio save / style apply marks it manual),
        # never clobber their changes with the seed.
        if ds.source != "seed":
            summary["design_system"].append("skipped (user-owned)")

        desired = {
            "name": "Default",
            "brand": brand_data.get("brand", {}),
            "footer": brand_design.get("footer", {"left": "", "right": ""}),
            "categories": categories,
            "overrides": brand_data.get("overrides") or {},
            "tokens": tokens,
            "token_roles": dict(SEMANTIC_VAR_ROLES),
            "campaigns": campaigns,
            "design_instruction": di_config,
        }
        if ds.source == "seed":
            changed = {k: v for k, v in desired.items() if getattr(ds, k) != v}
            if changed:
                await ds_repo.update(_DEFAULT_ID, changed)
                summary["design_system"] = list(changed.keys())

        tpl_repo = TemplateRepository(session)
        catalog = load_template_catalog().get("templates", {})
        for tid, entry in catalog.items():
            rel_file = entry.get("file", "")
            file_path = templates_dir() / rel_file
            if not file_path.is_file():
                continue
            html = file_path.read_text(encoding="utf-8")
            image_slots, has_logo = scan_template_features(html)
            desired = {
                "design_system_id": _DEFAULT_ID,
                "family": entry.get("family", "square"),
                "grounds": entry.get("grounds", ["white", "black"]),
                "categories": entry.get("categories", []),
                "hint_tags": entry.get("hint_tags", []),
                "weight": float(entry.get("weight", 1.0)),
                "description": entry.get("description", ""),
                "html": html,
                "image_slots": image_slots,
                "has_logo_slot": has_logo,
            }
            row = await tpl_repo.get_by_id(tid)
            if row is None:
                await tpl_repo.create(
                    {**desired, "id": tid, "name": tid, "source": "seed", "is_active": True}
                )
                summary["templates_created"].append(tid)
                continue
            # Only reconcile rows that came from the seed — never user rows.
            if row.source != "seed":
                continue
            diff = {k: v for k, v in desired.items() if getattr(row, k) != v}
            if diff:
                await tpl_repo.update(tid, diff)
                summary["templates_updated"].append(tid)

    return summary


async def seed_platforms(pool: async_sessionmaker[AsyncSession]) -> int:
    """Seed the platforms table from platforms.yaml (seed-once).

    Family comes from the design-instruction ``format_families`` map (e.g.
    landscape for linkedin) with an aspect heuristic fallback. Only missing
    rows are created; the Studio owns the rows afterward.
    """
    from app.db.repositories.platforms import PlatformRepository
    from app.services.platforms import refresh_platforms

    settings = get_settings()
    dims = load_platforms(settings.platforms_path)
    di = load_design_instruction(
        Path(settings.design_system_dir) / "design-instruction.yaml"
    )
    families = di.get("format_families", {}) if isinstance(di, dict) else {}

    created = 0
    async with pool() as session:
        repo = PlatformRepository(session)
        for i, (pid, (w, h)) in enumerate(sorted(dims.items())):
            if await repo.get_by_id(pid) is not None:
                continue
            fam = families.get(pid)
            if fam not in ("square", "portrait", "story", "landscape"):
                fam = "square" if h <= w else "portrait"
            await repo.create(
                {
                    "id": pid,
                    "name": pid.replace("-", " ").title(),
                    "width": w,
                    "height": h,
                    "family": fam,
                    "is_active": True,
                    "sort_order": i,
                }
            )
            created += 1
    if created:
        log.info("[seed] Created %d platform row(s)", created)
    await refresh_platforms(pool)
    return created


async def seed_fonts(pool: async_sessionmaker[AsyncSession]) -> int:
    """Seed the curated font pool from fonts.yaml (seed-once)."""
    from app.db.repositories.fonts import FontRepository
    from app.services.fonts import _yaml_seed, refresh_font_pool

    created = 0
    async with pool() as session:
        repo = FontRepository(session)
        for i, f in enumerate(_yaml_seed()):
            if await repo.get_by_family(f["family"]) is not None:
                continue
            await repo.create({**f, "sort_order": i})
            created += 1
    if created:
        log.info("[seed] Created %d font row(s)", created)
    await refresh_font_pool(pool)
    return created


async def migrate_stored_design_instructions(
    pool: async_sessionmaker[AsyncSession],
) -> int:
    """Upgrade legacy/imported design-system rows to the modern schema.

    Rows created before design languages / photo policy existed store a
    design_instruction without ``style_language`` or ``photo`` (and possibly
    stale wording). This re-applies the row's active language bundle —
    refreshing language fields (style/type_voice/do_dont/archetypes) while
    preserving the user's structural fields (type_scale/spacing/footer).
    Current rows (which already have both keys) are left untouched. Idempotent.
    """
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_languages import apply_language
    from app.services.styles import normalize_design_instruction

    changed = 0
    async with pool() as session:
        repo = DesignSystemRepository(session)
        rows = await repo.list(include_inactive=True)
        for ds in rows:
            di = ds.design_instruction or {}
            if "style_language" in di and "photo" in di:
                continue
            new_di = normalize_design_instruction(di)
            lang_id = new_di.get("style_language") or "swiss-editorial"
            new_di = await apply_language(session, lang_id, new_di)
            if new_di != di:
                await repo.update(ds.id, {"design_instruction": new_di})
                changed += 1
    if changed:
        log.info("[seed] Migrated %d design-system instruction(s) to the modern schema", changed)
    return changed
