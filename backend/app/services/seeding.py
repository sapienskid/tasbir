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
