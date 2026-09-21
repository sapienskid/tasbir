"""Seed the database with the ``default`` design system + its templates.

v0.5 moved design systems and templates into SQLite. On first boot (when no
design system rows exist) this imports the existing YAML config
(brand/tokens/campaigns/design-instruction) and the template catalog + files
into the DB. Idempotent — a ``default`` row skips the whole seed.
"""

from __future__ import annotations

import copy
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

        created, updated = await _sync_seed_templates(
            session, catalog_template_specs(_DEFAULT_ID)
        )
        summary["templates_created"].extend(created)
        summary["templates_updated"].extend(updated)

    return summary


def catalog_template_specs(
    ds_id: str,
    id_prefix: str = "",
    category_names: set[str] | None = None,
) -> list[dict]:
    """Template row values for every catalog entry, scoped to ``ds_id``.

    The default system uses the catalog ids as-is. A bundled brand system gets
    its own copy of the same layouts under ``{id_prefix}{id}`` (template ids are
    global), keeping only the category affinities its taxonomy actually has.
    """
    specs: list[dict] = []
    for tid, entry in load_template_catalog().get("templates", {}).items():
        file_path = templates_dir() / entry.get("file", "")
        if not file_path.is_file():
            log.warning("[seed] Missing template file %s — skipping", file_path)
            continue
        html = file_path.read_text(encoding="utf-8")
        image_slots, has_logo = scan_template_features(html)
        categories = list(entry.get("categories", []))
        if category_names is not None:
            categories = [c for c in categories if c in category_names]
        specs.append(
            {
                "id": f"{id_prefix}{tid}",
                "name": f"{id_prefix}{tid}",
                "design_system_id": ds_id,
                "family": entry.get("family", "square"),
                "grounds": entry.get("grounds", ["white", "black"]),
                "categories": categories,
                "hint_tags": entry.get("hint_tags", []),
                "weight": float(entry.get("weight", 1.0)),
                "description": entry.get("description", ""),
                "html": html,
                "image_slots": image_slots,
                "has_logo_slot": has_logo,
            }
        )
    return specs


async def _sync_seed_templates(
    session: AsyncSession, specs: list[dict], source: str = "seed"
) -> tuple[list[str], list[str]]:
    """Create missing template rows and refresh ``source == "seed"`` ones.

    Rows the user created or edited in the Studio (any other source) are never
    touched. Returns (created ids, updated ids).
    """
    from app.db.repositories.templates import TemplateRepository

    repo = TemplateRepository(session)
    created: list[str] = []
    updated: list[str] = []
    for spec in specs:
        row = await repo.get_by_id(spec["id"])
        if row is None:
            await repo.create({**spec, "source": source, "is_active": True})
            created.append(spec["id"])
            continue
        if row.source != "seed":
            continue
        diff = {
            k: v for k, v in spec.items() if k not in ("id", "name") and getattr(row, k) != v
        }
        if diff:
            await repo.update(spec["id"], diff)
            updated.append(spec["id"])
    return created, updated


async def seed_starter_templates(
    session: AsyncSession, ds_id: str, category_names: set[str] | None = None
) -> int:
    """Give a design system its own, user-owned copy of the standard layouts.

    Layouts carry no design language (accent, radius and weight follow the
    system's tokens), so a new system is usable straight away. Rows are
    ``source="manual"`` — the Studio owns them; seed-sync never touches them.
    """
    created, _ = await _sync_seed_templates(
        session, catalog_template_specs(ds_id, f"{ds_id}-", category_names), source="manual"
    )
    return len(created)


# ---------------------------------------------------------------------------
# Bundled brand design systems (data/design_system/bundled/<id>/system.yaml)
# ---------------------------------------------------------------------------

# app_settings row remembering which bundled systems were ever seeded, so a
# system the user deleted is not resurrected on the next start.
_BUNDLED_MARKER = "seed.bundled_design_systems"

_LOGO_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp"}


def bundled_dir() -> Path:
    return Path(get_settings().design_system_dir) / "bundled"


def load_bundled_specs() -> list[dict]:
    """Parse every ``bundled/*/system.yaml`` (sorted by folder); bad files are skipped."""
    import yaml

    specs: list[dict] = []
    root = bundled_dir()
    if not root.is_dir():
        return specs
    for path in sorted(root.glob("*/system.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("[seed] Bundled system %s unreadable: %s", path, e)
            continue
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("name"):
            log.warning("[seed] Bundled system %s needs an id and a name — skipped", path)
            continue
        raw["_dir"] = path.parent
        specs.append(raw)
    return specs


def _logo_entry(base: Path, filename: str) -> dict | None:
    import base64

    path = base / filename
    if not path.is_file():
        log.warning("[seed] Bundled logo %s missing", path)
        return None
    return {
        "mime": _LOGO_MIME.get(path.suffix.lower(), "image/png"),
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        "filename": path.name,
    }


def _load_bundled_logo(spec: dict) -> dict | None:
    """``logo: file.svg`` or ``logo: {file, grounds: {white: f, black: f}}``."""
    raw = spec.get("logo")
    if not raw:
        return None
    base = Path(spec["_dir"])
    if isinstance(raw, str):
        return _logo_entry(base, raw)
    logo = _logo_entry(base, str(raw.get("file") or ""))
    if logo is None:
        return None
    grounds = {
        g: e
        for g, fn in (raw.get("grounds") or {}).items()
        if g in ("white", "black") and (e := _logo_entry(base, str(fn)))
    }
    if grounds:
        logo["grounds"] = grounds
    return logo


def bundled_language_values(spec: dict) -> dict | None:
    """design_languages row values for a bundled system's own language."""
    lang = spec.get("language")
    if not isinstance(lang, dict) or not lang.get("id"):
        return None
    return {
        "id": str(lang["id"]),
        "name": str(lang.get("name") or lang["id"]),
        "description": " ".join(str(lang.get("description") or "").split()),
        "base": str(lang.get("base") or ""),
        "emoji": bool(lang.get("emoji", False)),
        "grayscale": bool(lang.get("grayscale", True)),
        "accent": bool(lang.get("accent", False)),
        "media_policy": str(lang.get("media_policy") or "photo-forward"),
        "accent_tokens": dict(lang.get("accent_tokens") or {}),
        "palette_tokens": dict(lang.get("palette_tokens") or {}),
        "di": copy.deepcopy(lang.get("di") or {}),
    }


def bundled_row_values(spec: dict) -> dict:
    """DesignSystem column values for a bundled spec (pure — no DB access).

    The design instruction starts from the default system's structural rules
    (type scale, spacing, formats), takes the base language's rules, then the
    brand's own overlay on top.
    """
    from app.services.design_instruction import _deep_merge
    from app.services.styles import apply_style_preset

    settings = get_settings()
    base_di = load_design_instruction(
        Path(settings.design_system_dir) / "design-instruction.yaml"
    )
    lang = spec.get("language")
    if isinstance(lang, dict) and lang.get("id"):
        # The brand's own language: its rules replace the language-owned parts
        # of the structural base (same ownership split as apply_style_preset).
        ldi = lang.get("di") or {}
        di = copy.deepcopy(base_di)
        for key in ("style", "type_voice", "do_dont", "layout_archetypes", "default_ground"):
            if ldi.get(key) is not None:
                di[key] = copy.deepcopy(ldi[key])
        di["photo"] = {
            "grayscale": bool(lang.get("grayscale", True)),
            "media_policy": lang.get("media_policy") or "photo-forward",
        }
        di["style_language"] = str(lang["id"])
    else:
        di = apply_style_preset(spec.get("style_language") or "swiss-editorial", base_di)
    di = _deep_merge(di, spec.get("design_instruction") or {})

    logo = _load_bundled_logo(spec)

    return {
        "name": spec["name"],
        "description": " ".join(str(spec.get("description") or "").split()),
        "brand": spec.get("brand") or {},
        "footer": spec.get("footer") or {"left": "", "right": ""},
        "categories": spec.get("categories") or [],
        "overrides": spec.get("overrides") or {},
        "tokens": dict(spec.get("tokens") or {}),
        "token_roles": {**SEMANTIC_VAR_ROLES, **(spec.get("token_roles") or {})},
        "campaigns": spec.get("campaigns") or {},
        "design_instruction": di,
        "logo": logo,
    }


async def sync_bundled_design_systems(pool: async_sessionmaker[AsyncSession]) -> dict:
    """Create the bundled brand systems on first boot and keep untouched ones current.

    - missing + never seeded → created (design system + its own copy of the
      template library);
    - ``source == "seed"`` → refreshed from the files on restart (like the
      default system);
    - edited in the Studio (any other source) → left alone;
    - deleted by the user → not recreated (remembered in ``app_settings``).
    """
    from app.db.repositories.app_settings import AppSettingRepository
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_systems import validate_design_system

    summary: dict = {"created": [], "updated": [], "skipped": [], "templates": 0}
    specs = load_bundled_specs()
    if not specs:
        return summary

    async with pool() as session:
        settings_repo = AppSettingRepository(session)
        marker = await settings_repo.get(_BUNDLED_MARKER)
        seeded: set[str] = set(marker.value or []) if marker and marker.value else set()
        seeded_before = set(seeded)
        ds_repo = DesignSystemRepository(session)

        for spec in specs:
            ds_id = str(spec["id"])
            values = bundled_row_values(spec)
            issues = validate_design_system(values)
            if issues:
                log.error("[seed] Bundled system %r is invalid: %s", ds_id, issues[:3])
                summary["skipped"].append(f"{ds_id} (invalid)")
                continue

            ds = await ds_repo.get_by_id(ds_id)
            just_created = False
            if ds is None:
                if ds_id in seeded:
                    summary["skipped"].append(f"{ds_id} (deleted by user)")
                    continue
                ds = await ds_repo.create(
                    ds_id, {**values, "source": "seed", "is_active": True}
                )
                summary["created"].append(ds_id)
                just_created = True
            elif ds.source == "seed":
                changed = {k: v for k, v in values.items() if getattr(ds, k) != v}
                if changed:
                    await ds_repo.update(ds_id, changed)
                    summary["updated"].append(ds_id)
            seeded.add(ds_id)

            # The brand's own design language. Created with the system (or on
            # upgrade, while the system is still seed-owned); kept current while
            # untouched (source "bundled"); a Studio edit is respected and the
            # system keeps its merged copy if the language is deleted.
            lang_values = bundled_language_values(spec)
            if lang_values:
                from app.db.repositories.design_languages import DesignLanguageRepository

                lang_repo = DesignLanguageRepository(session)
                row = await lang_repo.get_by_id(lang_values["id"])
                if row is None and (just_created or ds.source == "seed"):
                    await lang_repo.create(
                        {**lang_values, "source": "bundled", "is_active": True, "sort_order": 100}
                    )
                elif row is not None and row.source == "bundled":
                    diff = {k: v for k, v in lang_values.items() if getattr(row, k) != v}
                    if diff:
                        await lang_repo.update(lang_values["id"], diff)

            names = {str(c.get("name")) for c in values["categories"] if c.get("name")}
            created, updated = await _sync_seed_templates(
                session, catalog_template_specs(ds_id, f"{ds_id}-", names)
            )
            summary["templates"] += len(created) + len(updated)

        if seeded != seeded_before:
            if marker is None:
                await settings_repo.create(
                    _BUNDLED_MARKER,
                    sorted(seeded),
                    "Bundled design systems already seeded (internal).",
                )
            else:
                await settings_repo.update(_BUNDLED_MARKER, sorted(seeded))

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
