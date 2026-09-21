"""Design-system context — the ONE place a DS is loaded and restyled.

Every render path (AI pipeline setup, manual compose, rerender, the
``POST /design-systems/{id}/style`` switch) needs the same thing: a design
system row resolved from the DB (falling back to ``default``), turned into the
pipeline-ready dicts, optionally with a design language applied on top.
``resolve_ds_context`` does that once; ``apply_language_tokens`` is the single
"apply a language's palette + accent to a token map" rule.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)

# Accent tokens a colorful language provisions; a monochrome language strips them.
ACCENT_TOKEN_VARS = ("--color-accent", "--color-accent-secondary")


def pick_logo(logo: str, variants: dict | None, ground: str) -> str:
    """The logo data URI for a ground: its variant when the DS defines one."""
    return (variants or {}).get(ground) or logo or ""


@dataclass
class DSContext:
    """Pipeline-ready view of a design system (optionally restyled)."""

    ds_id: str
    tokens: dict = field(default_factory=dict)
    token_roles: dict = field(default_factory=dict)
    design_instruction: dict = field(default_factory=dict)
    footer: dict = field(default_factory=lambda: {"left": "", "right": ""})
    logo: str = ""
    # {ground: data URI} — per-ground logo variants (light vs dark ground).
    logo_variants: dict = field(default_factory=dict)
    categories: list = field(default_factory=list)
    campaigns: dict = field(default_factory=dict)
    brand: dict = field(default_factory=dict)
    overrides: dict = field(default_factory=dict)
    # The language override actually applied ("" = the DS's own language).
    style_language: str = ""

    def logo_for(self, ground: str) -> str:
        """The logo to render on ``ground`` (variant when defined, else primary)."""
        return pick_logo(self.logo, self.logo_variants, ground)

    @classmethod
    def from_payload(cls, payload: dict) -> DSContext:
        """Build a context from a ``build_pipeline_payload``-shaped dict."""
        from app.services.tokens import DEFAULT_TOKEN_VALUES

        return cls(
            ds_id=payload.get("design_system_id") or "default",
            tokens=dict(payload.get("design_tokens") or DEFAULT_TOKEN_VALUES),
            token_roles=dict(payload.get("token_roles") or {}),
            design_instruction=dict(payload.get("design_instruction") or {}),
            footer=dict(payload.get("footer") or {"left": "", "right": ""}),
            logo=payload.get("logo") or "",
            logo_variants=dict(payload.get("logo_variants") or {}),
            categories=list(payload.get("categories") or []),
            campaigns=dict(payload.get("campaigns") or {}),
            brand=dict(payload.get("brand_info") or {}),
            overrides=dict(payload.get("overrides") or {}),
        )


def apply_language_tokens(tokens: dict, lang) -> dict:
    """Apply a design language's palette + accent tokens to a token map.

    The language's core palette (bg/text/border/radius/shadow) replaces the
    color tokens; fonts are user-owned and preserved. A colorful language
    provisions its accent tokens; a monochrome one (no accent tokens) strips
    any accent left behind by a previous colorful style. Returns a new dict.
    """
    out = dict(tokens or {})
    for var, value in (lang.palette_tokens or {}).items():
        out[var] = value
    accent = lang.accent_tokens or {}
    if accent:
        for var, value in accent.items():
            out[var] = value
    else:
        for var in ACCENT_TOKEN_VARS:
            out.pop(var, None)
    return out


async def _load(session: AsyncSession, ds_id: str, style_language: str) -> DSContext | None:
    from app.db.repositories.design_systems import DesignSystemRepository
    from app.services.design_systems import DEFAULT_ID, build_pipeline_payload

    repo = DesignSystemRepository(session)
    ds = await repo.get_by_id(ds_id or DEFAULT_ID)
    if ds is None:
        log.warning("[ds_context] Design system %r not found — falling back to default", ds_id)
        ds = await repo.get_by_id(DEFAULT_ID)
    if ds is None:
        return None

    ctx = DSContext.from_payload(build_pipeline_payload(ds))
    if style_language:
        await _apply_override(session, ctx, style_language)
    return ctx


async def _apply_override(session: AsyncSession, ctx: DSContext, language_id: str) -> None:
    """Restyle ``ctx`` in-memory with a design language (the DS row is untouched)."""
    from app.services.design_languages import apply_language, get_language
    from app.services.styles import normalize_design_instruction

    lang = await get_language(session, language_id)
    if lang is None:
        log.warning("[ds_context] unknown style_language override %r ignored", language_id)
        return
    base_style = (ctx.design_instruction or {}).get("style") or {}
    di = normalize_design_instruction(
        await apply_language(session, language_id, ctx.design_instruction or {})
    )
    # The DS's illustration style is user-owned, not part of the language.
    if base_style.get("illustration_style") and not di["style"].get("illustration_style"):
        di["style"]["illustration_style"] = base_style["illustration_style"]
    ctx.design_instruction = di
    ctx.tokens = apply_language_tokens(ctx.tokens, lang)
    ctx.style_language = lang.id


def effective_design_system_id(task, fmt_id: str) -> str:
    """The design system a format renders under: its per-format editor
    override (set by a design-system switch in the structured editor), else
    the task's, else ``"default"``."""
    source = getattr(task, "source_data", None) or {}
    result = getattr(task, "result", None) or {}
    entry = (result.get("platforms") or {}).get(fmt_id) or {}
    editor = entry.get("editor") or {}
    override = editor.get("design_system_id") if isinstance(editor, dict) else None
    return str(override or source.get("design_system_id") or "default")


async def resolve_ds_context(
    db_or_pool: AsyncSession | async_sessionmaker[AsyncSession] | None,
    ds_id: str,
    style_language_override: str = "",
) -> DSContext:
    """Load a design system (DB, ``default`` fallback) + optional language override.

    Accepts an open session or a session factory. When not even the default
    row exists (pre-seed), falls back to the YAML-seeded default payload.
    """
    override = str(style_language_override or "")
    ctx: DSContext | None = None
    try:
        if isinstance(db_or_pool, AsyncSession):
            ctx = await _load(db_or_pool, ds_id, override)
        else:
            if db_or_pool is None:
                from app.db.session import get_shared_session_factory

                db_or_pool = await get_shared_session_factory()
            async with db_or_pool() as session:
                ctx = await _load(session, ds_id, override)
    except Exception as e:  # noqa: BLE001 — DB hiccup → default payload below
        log.warning("[ds_context] Design-system load failed (%s) — default payload", e)

    if ctx is None:
        from app.services.design_systems import default_design_system_payload

        pool = db_or_pool if isinstance(db_or_pool, async_sessionmaker) else None
        ctx = DSContext.from_payload(await default_design_system_payload(pool))
    return ctx


__all__ = [
    "ACCENT_TOKEN_VARS",
    "DSContext",
    "apply_language_tokens",
    "resolve_ds_context",
]
