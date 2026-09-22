"""Design system service — DB CRUD, validation, and pipeline payload building.

Design systems are fully DB-backed (v0.5). The YAML files only seed the
``default`` system. ``build_pipeline_payload`` turns a row into the dicts the
LangGraph pipeline consumes (tokens, brand, campaign, footer, categories,
design_instruction, logo).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import iso_utc
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.templates import TemplateRepository
from app.models.design_system import DesignSystem
from app.services.templates import template_to_dict
from app.services.tokens import DEFAULT_TOKEN_VALUES, invalid_token_issues

log = logging.getLogger(__name__)

DEFAULT_ID = "default"

_VALID_GROUNDS = {"white", "black"}


def _has_logo(logo: dict | None) -> bool:
    if not isinstance(logo, dict):
        return False
    if logo.get("data"):
        return True
    grounds = logo.get("grounds") or {}
    return bool(isinstance(grounds, dict) and any(
        isinstance(v, dict) and v.get("data") for v in grounds.values()
    ))


def _logo_uri(entry: dict | None) -> str:
    entry = entry or {}
    data = entry.get("data") or ""
    mime = entry.get("mime") or "image/png"
    return f"data:{mime};base64,{data}" if data else ""


def logo_data_uri(ds: DesignSystem, ground: str | None = None) -> str:
    """Return the design system's logo as a data URI ('' when none).

    A logo may carry per-ground variants under ``logo["grounds"]`` (keys
    ``white`` / ``black``) — e.g. a lime mark for a dark ground and a carbon
    mark for a light one. With ``ground`` given, that variant wins; otherwise
    (or when the ground has no variant) the primary logo is used.
    """
    logo = ds.logo or {}
    if ground:
        variant = _logo_uri((logo.get("grounds") or {}).get(ground))
        if variant:
            return variant
    return _logo_uri(logo)


def logo_variant_uris(ds: DesignSystem) -> dict[str, str]:
    """{ground: data URI} for every ground that has its own logo variant."""
    variants = (ds.logo or {}).get("grounds") or {}
    out = {g: _logo_uri(variants.get(g)) for g in ("white", "black")}
    return {g: uri for g, uri in out.items() if uri}


def _is_nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def validate_design_system(data: dict) -> list[str]:
    """Return a list of validation problems (empty = valid).

    Validates every field the Studio can PATCH (partial dicts are fine —
    only keys present in ``data`` are checked): tokens, token_roles, brand,
    footer, categories, overrides, campaigns, and design_instruction.
    """
    issues: list[str] = []

    if "tokens" in data:
        tokens = data.get("tokens")
        if not isinstance(tokens, dict):
            issues.append("tokens must be an object")
        else:
            for key, value in tokens.items():
                if not isinstance(key, str) or not key.startswith("--"):
                    issues.append(f"token key {key!r} must start with '--'")
                if not isinstance(value, str):
                    issues.append(f"token {key} value must be a string")
            # Values are injected verbatim into <style> — reject empty / unsafe /
            # malformed values (e.g. ``--color-accent: ""`` or ``red}</style>``).
            issues.extend(invalid_token_issues(tokens))

    if "token_roles" in data:
        roles = data.get("token_roles")
        if not isinstance(roles, dict):
            issues.append("token_roles must be an object")
        else:
            for key, value in roles.items():
                if not isinstance(key, str) or not key.startswith("--"):
                    issues.append(f"token_roles key {key!r} must start with '--'")
                elif not isinstance(value, str) or not value.strip():
                    issues.append(f"token_roles {key} description must be a non-empty string")

    if "brand" in data:
        brand = data.get("brand")
        if not isinstance(brand, dict):
            issues.append("brand must be an object")
        else:
            for field in ("name", "tagline", "mission", "story", "url"):
                if field in brand and not isinstance(brand[field], str):
                    issues.append(f"brand.{field} must be a string")
            if "social" in brand and not isinstance(brand["social"], dict):
                issues.append("brand.social must be an object")

    if "footer" in data:
        footer = data.get("footer")
        if not isinstance(footer, dict):
            issues.append("footer must be an object")
        else:
            for field in ("left", "right"):
                if field in footer and not isinstance(footer[field], str):
                    issues.append(f"footer.{field} must be a string")

    if "categories" in data:
        categories = data.get("categories")
        if not isinstance(categories, list):
            issues.append("categories must be a list")
        else:
            seen: set[str] = set()
            for i, c in enumerate(categories):
                where = f"categories[{i}]"
                if not isinstance(c, dict):
                    issues.append(f"{where} must be an object")
                    continue
                name = c.get("name")
                if not _is_nonempty_str(name):
                    issues.append(f"{where}.name must be a non-empty string")
                else:
                    lowered = str(name).strip().lower()
                    if lowered in seen:
                        issues.append(f"{where}.name {name!r} is duplicated")
                    seen.add(lowered)
                if "description" in c and not isinstance(c["description"], str):
                    issues.append(f"{where}.description must be a string")
                ground = c.get("ground", "")
                if ground not in ("", "white", "black"):
                    issues.append(
                        f"{where}.ground must be 'white' or 'black' (got {ground!r})"
                    )

    if "overrides" in data:
        overrides = data.get("overrides")
        if not isinstance(overrides, dict):
            issues.append("overrides must be an object")
        else:
            for key, value in overrides.items():
                if not isinstance(key, str) or not key.strip():
                    issues.append(f"overrides key {key!r} must be a non-empty string")
                elif not isinstance(value, str):
                    issues.append(f"overrides.{key} must be a string")

    if "campaigns" in data:
        campaigns = data.get("campaigns")
        if not isinstance(campaigns, dict):
            issues.append("campaigns must be an object")
        else:
            for name, c in campaigns.items():
                if not _is_nonempty_str(name):
                    issues.append(f"campaign key {name!r} must be a non-empty string")
                if not isinstance(c, dict):
                    issues.append(f"campaign {name!r} must be an object")
                    continue
                for field in ("label", "tone", "language"):
                    if field in c and not isinstance(c[field], str):
                        issues.append(f"campaign {name!r}.{field} must be a string")
                ground = c.get("ground", "")
                if ground not in ("", "white", "black"):
                    issues.append(
                        f"campaign {name!r} ground must be 'white' or 'black' (got {ground!r})"
                    )

    if "design_instruction" in data:
        di = data.get("design_instruction")
        if not isinstance(di, dict):
            issues.append("design_instruction must be an object")
        else:
            style = di.get("style", {})
            if "style" in di and not isinstance(style, dict):
                issues.append("design_instruction.style must be an object")
            allowed = (style or {}).get("allowed_grounds") if isinstance(style, dict) else None
            if isinstance(allowed, list):
                bad = [g for g in allowed if g not in _VALID_GROUNDS]
                if bad:
                    issues.append(f"design_instruction allowed_grounds {bad} invalid")
            if "default_ground" in di:
                dg = di.get("default_ground")
                if dg not in ("", "white", "black"):
                    issues.append(
                        f"design_instruction default_ground must be 'white' or 'black' (got {dg!r})"
                    )
            language = di.get("style_language") or ""
            if language and not isinstance(language, str):
                issues.append("design_instruction style_language must be a string")

    return issues


def neutral_design_instruction(di: dict | None = None) -> dict:
    """A design instruction with the structure but no design language.

    Keeps the structural fields (type scale, spacing, formats, footer) and
    blanks everything a language owns, so a new design system starts empty:
    ``style_language`` is ``""`` (the picker shows "Select a design language"),
    no accent, no decoration, generic voice, no layout archetypes.
    """
    import copy

    out = copy.deepcopy(di) if isinstance(di, dict) else {}
    out["style_language"] = ""
    out["default_ground"] = "white"
    out["style"] = {
        "name": "",
        "palette": "custom",
        "accent": "none",
        "shadows": False,
        "gradients": False,
        "emoji": False,
        "border_radius": "0px",
        "illustrations": True,
    }
    out["photo"] = {"grayscale": False, "media_policy": "photo-forward"}
    out["type_voice"] = {
        "display": "The display voice (var(--font-display)) — the headline only.",
        "serif": "The text voice (var(--font-serif)) — subhead and body copy.",
        "body": "The interface voice (var(--font-sans)) — category, metadata, handle.",
    }
    out["do_dont"] = {"do": [], "dont": []}
    out["layout_archetypes"] = {}
    return out


def new_design_system_defaults(name: str) -> dict:
    """A complete, immediately-usable baseline for a newly created design system.

    A bare create (name only) is NOT usable: no brand identity, no categories,
    no campaigns, no design instruction. This seeds the structural baseline
    (type scale, spacing, formats) + starter taxonomy, but NO design language:
    the user picks one (or builds their own) in the Design language picker.
    """
    import yaml

    from app.config import get_settings
    from app.services.design_instruction import load_design_instruction
    from app.services.tokens import (
        DEFAULT_CATEGORIES,
        DEFAULT_TOKEN_VALUES,
        SEMANTIC_VAR_ROLES,
        load_tokens,
    )

    settings = get_settings()
    tokens = load_tokens(settings.tokens_path) or dict(DEFAULT_TOKEN_VALUES)
    di = load_design_instruction(
        Path(settings.design_system_dir) / "design-instruction.yaml"
    )
    di = neutral_design_instruction(di)

    campaigns: dict = {}
    try:
        with open(settings.campaigns_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            campaigns = raw
    except Exception:  # noqa: BLE001 — missing file → empty campaigns
        campaigns = {}

    return {
        "brand": {"name": name},
        "footer": {"left": "", "right": ""},
        "categories": [dict(c) for c in DEFAULT_CATEGORIES],
        "overrides": {},
        "tokens": tokens,
        "token_roles": dict(SEMANTIC_VAR_ROLES),
        "campaigns": campaigns,
        "design_instruction": di,
    }


def build_pipeline_payload(ds: DesignSystem) -> dict:
    """Build the dicts the pipeline consumes from a design system row."""
    from app.services.styles import normalize_design_instruction

    tokens = dict(DEFAULT_TOKEN_VALUES)
    tokens.update(ds.tokens or {})
    brand = ds.brand or {}
    return {
        "design_system_id": ds.id,
        "design_tokens": tokens,
        "token_roles": ds.token_roles or {},
        "brand_info": brand,
        "footer": ds.footer or {"left": "", "right": ""},
        "categories": ds.categories or [],
        "overrides": ds.overrides or {},
        "campaigns": ds.campaigns or {},
        "design_instruction": normalize_design_instruction(ds.design_instruction),
        "logo": logo_data_uri(ds),
        "logo_variants": logo_variant_uris(ds),
    }


def resolve_illustration_style(di: dict, api_override: str = "") -> str:
    """Resolve the effective illustration style (API → DS default → 'procedural').

    ``di`` is the design_instruction dict from a design system row; the DS
    default lives under ``style.illustration_style`` (DB-backed, Studio-
    editable). An explicit API override wins; unknown values fall back to the
    DS default. Empty everywhere → ``procedural`` (the clean Anthropic-style
    organic mark, the premium editorial default).
    """
    from app.services.tools.illustrator import ILLUSTRATE_TOOL

    enum = ILLUSTRATE_TOOL["function"]["parameters"]["properties"]["style"]["enum"]
    ds_default = (di.get("style") or {}).get("illustration_style") or ""
    for candidate in (api_override, ds_default, "procedural"):
        if candidate in enum:
            return candidate
    return "procedural"


def ds_to_dict(ds: DesignSystem, template_count: int | None = None) -> dict:
    """Serialize a design system for API responses."""
    return {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description,
        "brand": ds.brand,
        "footer": ds.footer,
        "categories": ds.categories,
        "overrides": ds.overrides,
        "tokens": ds.tokens,
        "token_roles": ds.token_roles,
        "campaigns": ds.campaigns,
        "design_instruction": ds.design_instruction,
        "logo": ds.logo,
        "has_logo": _has_logo(ds.logo),
        "source": ds.source,
        "is_active": bool(ds.is_active),
        "template_count": template_count,
        "created_at": iso_utc(ds.created_at),
        "updated_at": iso_utc(ds.updated_at),
    }


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or DEFAULT_ID


async def get_or_create_default(pool: async_sessionmaker[AsyncSession]) -> str:
    """Ensure a default design system exists (e.g. old task paths)."""
    async with pool() as session:
        ds = await DesignSystemRepository(session).get_by_id(DEFAULT_ID)
    if ds is None:
        from app.services.seeding import seed_default_design_system

        await seed_default_design_system(pool)
    return DEFAULT_ID


async def default_design_system_payload(pool=None) -> dict:
    """The ``default`` design system payload from the DB.

    Used by runtime fallback paths (rerender, chat, renderer/designer/
    verifier empty-state) so nothing reads the YAML files at runtime. The
    YAML seed is only consulted before the default row exists (pre-seed).
    """
    from app.db.session import get_shared_session_factory

    pool = pool or (await get_shared_session_factory())
    async with pool() as session:
        ds = await DesignSystemRepository(session).get_by_id(DEFAULT_ID)
    if ds is not None:
        return build_pipeline_payload(ds)

    from app.config import get_settings
    from app.services.design_instruction import load_design_instruction
    from app.services.tokens import DEFAULT_TOKEN_VALUES, load_brand_design, load_tokens

    settings = get_settings()
    tokens = load_tokens(settings.tokens_path) or dict(DEFAULT_TOKEN_VALUES)
    di = load_design_instruction(
        os.path.join(settings.design_system_dir, "design-instruction.yaml")
    )
    brand_design = load_brand_design(settings.brand_path)
    return {
        "design_system_id": DEFAULT_ID,
        "design_tokens": tokens,
        "token_roles": {},
        "brand_info": {},
        "footer": brand_design.get("footer", {"left": "", "right": ""}),
        "categories": brand_design.get("categories", []),
        "overrides": {},
        "campaigns": {},
        "design_instruction": di,
        "logo": "",
    }


async def load_ds_templates(
    pool: async_sessionmaker[AsyncSession], ds_id: str
) -> list[dict]:
    """Load a design system's active templates as selection-ready dicts."""
    async with pool() as session:
        rows = await TemplateRepository(session).list(ds_id)
        return [template_to_dict(r) for r in rows]


_SAMPLE_COPY = {
    "headline": "The quiet discipline of a well-set column",
    "subhead": "White space is the rhythm between ideas; a grid gives it a voice.",
    "body": "A grid sets order and a measure sets pace. Constrain the line, free "
    "the reader, and let the whitespace do its work.",
    "badge": None,
}


def _generic_preview_html(width: int, height: int, footer: dict) -> str:
    """A minimal sample layout using only var(--color-*) / var(--font-*)."""
    right = (footer or {}).get("right", "")
    footer_block = (
        f'<div class="rule"></div><div class="footer">'
        f'<span class="handle">{right}</span></div>'
        if right
        else ""
    )
    css = "\n".join([
        "* { box-sizing: border-box; margin: 0; padding: 0; }",
        "body {",
        f"  width: {width}px; height: {height}px; overflow: hidden;",
        "  margin: 0; background: var(--color-bg); color: var(--color-text);",
        "  font-family: var(--font-sans); padding: 64px;",
        "  display: flex; flex-direction: column;",
        "  -webkit-font-smoothing: antialiased;",
        "}",
        'body[data-ground="black"] {',
        "  background: var(--color-bg-inverted);",
        "  color: var(--color-text-inverted);",
        "}",
        ".kicker {",
        "  font-size: 22px; font-weight: 500; letter-spacing: 0.12em;",
        "  text-transform: uppercase; color: var(--color-text-secondary);",
        "  margin-bottom: 24px;",
        "}",
        ".headline {",
        "  font-family: var(--font-display); font-size: 76px;",
        "  font-weight: 700; letter-spacing: -0.01em; line-height: 1.0;",
        "  margin-bottom: 32px;",
        "}",
        ".subhead {",
        "  font-family: var(--font-serif); font-size: 32px;",
        "  font-weight: 400; line-height: 1.3;",
        "  color: var(--color-text-secondary); margin-bottom: 32px;",
        "  max-width: 640px;",
        "}",
        ".body {",
        "  font-family: var(--font-serif); font-size: 26px;",
        "  font-weight: 400; line-height: 1.4; max-width: 640px;",
        "}",
        ".spacer { flex: 1; }",
        ".rule { border-top: 1px solid var(--color-border); }",
        ".footer {",
        "  display: flex; justify-content: flex-start;",
        "  align-items: baseline; padding-top: 24px;",
        "}",
        ".handle {",
        "  font-size: 20px; font-weight: 500; letter-spacing: 0.08em;",
        "  text-transform: uppercase; color: var(--color-text-secondary);",
        "}",
        ".logo { margin-bottom: 48px; }",
        ".logo img { height: 72px; width: auto; object-fit: contain; }",
    ])
    body = "\n".join([
        '<div class="kicker">WRITING</div>',
        '<div class="logo" data-logo></div>',
        f"<div class=\"headline\">{_SAMPLE_COPY['headline']}</div>",
        f"<div class=\"subhead\">{_SAMPLE_COPY['subhead']}</div>",
        f"<div class=\"body\">{_SAMPLE_COPY['body']}</div>",
        '<div class="spacer"></div>',
        footer_block,
    ])
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\">"
        f"<style>\n{css}\n</style></head>\n<body>\n{body}\n</body></html>"
    )


async def render_ds_preview(
    ds: DesignSystem, pool: async_sessionmaker[AsyncSession]
) -> str:
    """Render a neutral sample layout with the design system's tokens.

    Uses the generic preview (not a specific template) so the result isolates
    the design system's look — tokens, fonts, logo, footer — without any
    template-specific devices (rules, motifs) confusing the preview.
    """
    from app.services.composer import finalize_html
    from app.services.ds_context import DSContext

    tokens = dict(DEFAULT_TOKEN_VALUES)
    tokens.update(ds.tokens or {})
    footer = ds.footer or {"left": "", "right": ""}

    html = _generic_preview_html(1080, 1080, footer)
    ctx = DSContext(
        ds_id=ds.id,
        tokens=tokens,
        design_instruction=ds.design_instruction or {},
        logo=logo_data_uri(ds),
    )
    return finalize_html(html, ctx, katex=False)
