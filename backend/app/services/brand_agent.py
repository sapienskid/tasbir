"""Brand Builder agent — form (+ optional images) → complete design system.

Chain:
  1. Brand Vision    — reference image (if any) → palette/type-feel/voice brief
  2. Brand Tokens    — brief + curated font pool + design languages → tokens,
                       token_roles, base style_language, DI overlay
     Brand Campaigns — voice → 3-5 campaign presets (runs concurrently with 2)
  3. Assemble        — sanitize tokens (+ contrast guard), apply the chosen
                       design language, merge the brand's DI additions
  4. Persist         — DesignSystem row (inactive until the run completes)
  5. Starter templates — two distinct square + landscape layouts via the
                       template author, the language's starter pack, and an
                       authored portrait/story starter for uncovered families
  6. Activate        — any failure after step 4 deletes the row + templates
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.templates import TemplateRepository
from app.services import design_systems as ds_service
from app.services.agents import get_agent_config
from app.services.design_languages import (
    LanguageDefinition,
    apply_language,
    get_language,
    list_languages,
)
from app.services.fonts import font_pool_for_prompt
from app.services.llm import call_llm
from app.services.template_author import (
    author_template_html,
    extract_json,
    validate_template_html,
)
from app.services.tokens import (
    DEFAULT_CATEGORIES,
    DEFAULT_TOKEN_VALUES,
    SEMANTIC_VAR_ROLES,
    enforce_text_contrast,
    sanitize_token_value,
)
from app.services.vision import call_vision_llm

log = logging.getLogger(__name__)

# Single taxonomy for every creation path (see tokens.DEFAULT_CATEGORIES) —
# previously the brand builder carried its own 4-entry copy missing
# "THE LIMITS No.{issue}", so AI-built systems diverged from manual ones.

# Monochrome fallback and the closest colorful preset when the agent's
# language choice is missing/unknown or contradicts the brand's accent token.
MONOCHROME_LANGUAGE = "swiss-editorial"
ACCENT_LANGUAGE = "bold-modern"

# Truthy ``style.accent`` value the colorful presets use.
_ACCENT_ON = "accent"


def _region(role: str, x: int, y: int, w: int, h: int, align: str = "left") -> dict:
    return {
        "role": role, "x_pct": x, "y_pct": y,
        "w_pct": w, "h_pct": h, "alignment": align,
    }


# Starter layout specs per family. Variant "a" is headline-led from the top;
# variant "b" is a genuinely different composition so the two starters of a
# family never render as the same layout.
STARTER_SPECS: dict[str, dict[str, dict]] = {
    "square": {
        "a": {
            "family": "square",
            "regions": [
                _region("kicker", 6, 6, 50, 5),
                _region("headline", 6, 18, 88, 30),
                _region("subhead", 6, 52, 70, 18),
                _region("body", 6, 72, 60, 16),
            ],
            "layout_description": (
                "top kicker, large display headline, serif subhead, footer band"
            ),
            "notes": ["left-aligned", "bottom-anchored footer"],
        },
        "b": {
            "family": "square",
            "regions": [
                _region("kicker", 6, 6, 40, 5),
                _region("subhead", 6, 14, 55, 16),
                _region("headline", 6, 48, 88, 36),
            ],
            "layout_description": (
                "kicker + short serif subhead at the top, then a very large "
                "display headline anchored to the bottom of the canvas just "
                "above the footer; the middle is intentional whitespace"
            ),
            "notes": [
                "left-aligned", "bottom-anchored headline",
                "no body copy", "bottom-anchored footer",
            ],
        },
    },
    "landscape": {
        "a": {
            "family": "landscape",
            "regions": [
                _region("kicker", 5, 12, 40, 8),
                _region("headline", 5, 22, 55, 45),
                _region("subhead", 5, 68, 48, 20),
            ],
            "layout_description": (
                "kicker + headline left, subhead below, footer spanning"
            ),
            "notes": ["left-aligned", "bottom-anchored footer"],
        },
        "b": {
            "family": "landscape",
            "regions": [
                _region("kicker", 5, 10, 38, 8),
                _region("headline", 5, 22, 42, 62),
                _region("subhead", 54, 22, 40, 24),
                _region("body", 54, 50, 40, 34),
            ],
            "layout_description": (
                "split composition: display headline in the left column, "
                "subhead + body in a separate right column separated by a "
                "hairline vertical rule; footer spanning the bottom"
            ),
            "notes": ["two columns", "left-aligned text", "bottom-anchored footer"],
        },
    },
    "portrait": {
        "a": {
            "family": "portrait",
            "regions": [
                _region("kicker", 7, 6, 50, 4),
                _region("headline", 7, 16, 86, 34),
                _region("subhead", 7, 54, 72, 16),
                _region("body", 7, 72, 66, 14),
            ],
            "layout_description": (
                "tall editorial stack: kicker, large display headline, serif "
                "subhead and body in a constrained measure, footer band"
            ),
            "notes": ["left-aligned", "bottom-anchored footer"],
        },
    },
    "story": {
        "a": {
            "family": "story",
            "regions": [
                _region("kicker", 8, 10, 60, 3),
                _region("headline", 8, 26, 84, 32),
                _region("subhead", 8, 62, 76, 14),
            ],
            "layout_description": (
                "9:16 story: generous top/bottom safe margins (~160px), "
                "kicker high, a very large display headline in the upper-"
                "middle third, serif subhead below, footer bottom-anchored "
                "above the safe margin"
            ),
            "notes": [
                "left-aligned", "keep text out of the top/bottom 8% safe zones",
                "bottom-anchored footer",
            ],
        },
    },
}

# Palette role (brand vision brief) → token variable.
_PALETTE_ROLE_VARS = {
    "bg": "--color-bg",
    "bg_inverted": "--color-bg-inverted",
    "text": "--color-text",
    "text_inverted": "--color-text-inverted",
    "secondary": "--color-text-secondary",
    "text_secondary": "--color-text-secondary",
    "tertiary": "--color-text-tertiary",
    "border": "--color-border",
    "border_inverted": "--color-border-inverted",
    "accent": "--color-accent",
    "accent_secondary": "--color-accent-secondary",
}

_VAR_NAME_RE = re.compile(r"^--[A-Za-z0-9_-]+$")


async def _brand_vision(payload: dict) -> dict:
    """Brand Vision: brief from text (+ reference image when provided)."""
    form = {
        "name": payload.get("name", ""),
        "tagline": payload.get("tagline", ""),
        "mission": payload.get("mission", ""),
        "industry": payload.get("industry", ""),
        "audience": payload.get("audience", ""),
        "style": payload.get("style", ""),
    }
    image_b64 = payload.get("reference_image") or payload.get("image")
    prompt_cfg = await get_agent_config("brand_vision")

    user_prompt = "Brand form:\n" + json.dumps(form, indent=2) + (
        "\n\nA reference/moodboard image is attached — extract palette, "
        "typography feel, and density from it."
        if image_b64 else
        "\n\nNo image provided — define a coherent palette + aesthetic from the text."
    )

    if image_b64:
        import base64

        raw = await call_vision_llm(
            prompt_cfg.system_prompt,
            user_prompt,
            base64.b64decode(image_b64),
            temperature=prompt_cfg.temperature,
            max_tokens=prompt_cfg.max_tokens,
            model=prompt_cfg.model,
            fallback_models=prompt_cfg.fallback_models,
        )
    else:
        raw = await call_llm(
            agent_role="brand_vision",
            system_prompt=prompt_cfg.system_prompt,
            user_prompt=user_prompt,
            temperature=prompt_cfg.temperature,
            max_tokens=prompt_cfg.max_tokens,
        )
    return extract_json(raw)


async def _language_options(pool: async_sessionmaker[AsyncSession]) -> list[dict]:
    """Design languages the brand can build on: built-in presets + customs."""
    from app.services.styles import STYLE_PRESETS, style_labels

    options = [
        {
            "id": s["id"],
            "label": s["label"],
            "description": s["description"],
            "accent": bool(s["accent"]),
        }
        for s in style_labels()
    ]
    try:
        async with pool() as session:
            for lang in await list_languages(session):
                if lang.id in STYLE_PRESETS:
                    continue
                options.append(
                    {
                        "id": lang.id,
                        "label": lang.name,
                        "description": lang.description,
                        "accent": bool(lang.accent),
                    }
                )
    except Exception as e:  # noqa: BLE001 — presets alone are a valid menu
        log.warning("[brand_agent] custom design languages unavailable: %s", e)
    return options


def _language_menu(languages: list[dict]) -> str:
    lines = []
    for lang in languages:
        accent = "uses --color-accent" if lang["accent"] else "monochrome, no accent"
        lines.append(
            f"  - {lang['id']}: {lang['label']} ({accent}) — {lang['description']}"
        )
    return "\n".join(lines)


async def _brand_tokens(brief: dict, languages: list[dict] | None = None) -> dict:
    """Brand Tokens: brief + font pool + languages → tokens/roles/language/DI overlay."""
    prompt_cfg = await get_agent_config("brand_tokens")
    user_prompt = (
        f"BRAND BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        "AVAILABLE FONTS (choose ONLY from these):\n"
        f"{await font_pool_for_prompt()}\n\n"
    )
    if languages:
        user_prompt += (
            "AVAILABLE DESIGN LANGUAGES (set \"style_language\" to exactly ONE id):\n"
            f"{_language_menu(languages)}\n"
            "Pick a language that uses --color-accent ONLY when you set a "
            "non-empty --color-accent; a strictly monochrome brand (no accent) "
            "must pick a monochrome language.\n\n"
        )
    user_prompt += (
        "Produce the style_language, token map, token_roles, and a partial "
        "design_instruction overlay."
    )
    raw = await call_llm(
        agent_role="brand_tokens",
        system_prompt=prompt_cfg.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
    )
    return extract_json(raw)


async def _brand_campaigns(brief: dict) -> dict:
    """Brand Campaigns: 3-5 presets."""
    prompt_cfg = await get_agent_config("brand_campaigns")
    user_prompt = (
        f"BRAND BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        "Propose 3-5 campaign presets for this brand."
    )
    raw = await call_llm(
        agent_role="brand_campaigns",
        system_prompt=prompt_cfg.system_prompt,
        user_prompt=user_prompt,
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
    )
    return extract_json(raw)


def _build_tokens(brief: dict, tokens_out: dict) -> dict:
    """The brand's own tokens — sanitized (invalid names/values dropped)."""
    raw = tokens_out.get("tokens") or {}
    if not isinstance(raw, dict) or not raw:
        raw = {}
        for p in brief.get("palette") or []:
            if not isinstance(p, dict):
                continue
            role = str(p.get("role") or "").strip().lower().replace("-", "_")
            var = _PALETTE_ROLE_VARS.get(role) or (f"--color-{role}" if role else "")
            if var:
                raw[var] = p.get("hex", "")
    tokens: dict[str, str] = {}
    for var, value in raw.items():
        if not isinstance(var, str) or not _VAR_NAME_RE.match(var):
            log.info("[brand_agent] dropping invalid token name %r", var)
            continue
        clean = sanitize_token_value(var, value)
        if clean is None:
            log.info("[brand_agent] dropping invalid token %s=%r", var, value)
            continue
        tokens[var] = clean
    return tokens


def _has_accent(tokens: dict) -> bool:
    return bool((tokens.get("--color-accent") or "").strip())


async def _resolve_language(
    session: AsyncSession, requested, has_accent: bool
) -> LanguageDefinition:
    """The base design language: the agent's pick, kept consistent with the accent.

    Unknown/missing → Swiss (no accent) or the closest colorful preset
    (accent). A pick that contradicts the tokens (accent language without an
    accent token, or monochrome language with one) is corrected the same way
    so the style rules never disagree with the palette.
    """
    lang = None
    if isinstance(requested, str) and requested.strip():
        lang = await get_language(session, requested.strip())
    if lang is not None and bool(lang.accent) == has_accent:
        return lang
    fallback = ACCENT_LANGUAGE if has_accent else MONOCHROME_LANGUAGE
    if requested:
        log.info(
            "[brand_agent] style_language %r %s — using %s",
            requested,
            "unknown" if lang is None else "contradicts the accent token",
            fallback,
        )
    resolved = await get_language(session, fallback)
    assert resolved is not None  # built-in preset
    return resolved


def _complete_tokens(tokens: dict, lang: LanguageDefinition) -> dict:
    """Brand tokens win; fill missing core tokens from the language, then defaults."""
    out = dict(tokens)
    for source in (lang.palette_tokens or {}, DEFAULT_TOKEN_VALUES):
        for var, value in source.items():
            out.setdefault(var, value)
    if _has_accent(out):
        # The language may reference a secondary accent the brand didn't set.
        for var, value in (lang.accent_tokens or {}).items():
            out.setdefault(var, value)
    else:
        out.pop("--color-accent", None)
        out.pop("--color-accent-secondary", None)
    return enforce_text_contrast(out)


def _merge_do_dont(base: dict, extra) -> dict:
    out = {k: list(v) for k, v in (base or {}).items() if isinstance(v, list)}
    if not isinstance(extra, dict):
        return out
    for key in ("do", "dont"):
        items = extra.get(key)
        if not isinstance(items, list):
            continue
        bucket = out.setdefault(key, [])
        for item in items:
            if isinstance(item, str) and item.strip() and item not in bucket:
                bucket.append(item.strip())
    return out


async def _build_design_instruction(
    pool: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    brief: dict,
    tokens_out: dict,
    lang: LanguageDefinition,
    has_accent: bool,
    ground: str,
) -> dict:
    """Apply the brand's design language, then merge the brand's own additions.

    Structural rules (type scale, spacing, footer, formats) come from the
    default system; the language owns style/type_voice/do_dont/archetypes;
    the brand's type_voice lines and do/don't additions are layered on top,
    and ``style.accent`` follows the actual ``--color-accent`` token.
    """
    from app.services.design_systems import default_design_system_payload

    payload = await default_design_system_payload(pool)
    base = payload.get("design_instruction") or {}
    di = await apply_language(session, lang.id, base)

    overlay = tokens_out.get("design_instruction") or {}
    if not isinstance(overlay, dict):
        overlay = {}
    voice = overlay.get("type_voice")
    if isinstance(voice, dict):
        merged_voice = dict(di.get("type_voice") or {})
        merged_voice.update(
            {k: v.strip() for k, v in voice.items() if isinstance(v, str) and v.strip()}
        )
        di["type_voice"] = merged_voice
    di["do_dont"] = _merge_do_dont(di.get("do_dont") or {}, overlay.get("do_dont"))

    style = dict(di.get("style") or {})
    overlay_style = overlay.get("style") if isinstance(overlay.get("style"), dict) else {}
    for key in ("name", "palette"):
        value = overlay_style.get(key)
        if isinstance(value, str) and value.strip():
            style[key] = value.strip()
    style.setdefault("palette", brief.get("aesthetic", "clean editorial"))
    style.setdefault(
        "name", f"{(brief.get('identity') or {}).get('name', 'Brand')} Design System"
    )
    style["accent"] = _ACCENT_ON if has_accent else "none"
    di["style"] = style
    di["default_ground"] = ground
    return di


def _clean_campaigns(campaigns_out: dict, ground: str) -> dict:
    campaigns = campaigns_out.get("campaigns")
    if not isinstance(campaigns, dict) or not campaigns:
        campaigns = {}
    out: dict = {}
    for key, c in campaigns.items():
        if not isinstance(c, dict):
            continue
        c = dict(c)
        if c.get("ground") not in ("white", "black"):
            c["ground"] = ground
        out[str(key)] = c
    out.setdefault(
        "default",
        {"label": "Default", "tone": "professional", "ground": ground, "language": ""},
    )
    return out


async def _author_starter(spec: dict, family: str, ds, ground: str) -> str | None:
    """Author + validate one starter (2 critique retries); None when it fails."""
    html = await author_template_html(spec, ds, ground_hint=ground)
    result = await validate_template_html(html, family, ds, ground)
    for _ in range(2):
        if result["ok"]:
            break
        html = await author_template_html(
            spec, ds, critique=result["critique"], ground_hint=ground
        )
        result = await validate_template_html(html, family, ds, ground)
    if not result["ok"]:
        log.warning(
            "[brand_agent] starter %s template failed validation: %s",
            family, result["issues"][:3],
        )
        return None
    return html


async def _save_starter(
    repo: TemplateRepository,
    template_id: str,
    ds_id: str,
    name: str,
    family: str,
    index: int,
    ground: str,
    html: str,
) -> str:
    from app.services.templates import scan_template_features

    base = template_id
    n = 2
    while await repo.get_by_id(template_id):
        template_id = f"{base}-{n}"
        n += 1
    image_slots, has_logo = scan_template_features(html)
    await repo.create(
        {
            "id": template_id,
            "design_system_id": ds_id,
            "name": f"{name} {family} {index}",
            "family": family,
            "grounds": (
                [ground]
                if 'data-ground="black"' not in html
                else ["white", "black"]
            ),
            "categories": ["WRITING"],
            "hint_tags": [family, "starter"],
            "weight": 1.0,
            "description": f"Starter {family} template generated for {name}.",
            "html": html,
            "image_slots": image_slots,
            "has_logo_slot": has_logo,
            "source": "ai",
            "is_active": True,
        },
    )
    return template_id


async def _build_starter_templates(
    pool: async_sessionmaker[AsyncSession],
    ds,
    name: str,
    ground: str,
    style_language: str,
) -> list[str]:
    """Square + landscape (a/b), the language pack, then portrait/story gaps."""
    from app.services.style_templates import seed_style_templates

    templates: list[str] = []
    async with pool() as session:
        repo = TemplateRepository(session)
        for family in ("square", "landscape"):
            for i, (variant, spec) in enumerate(STARTER_SPECS[family].items(), start=1):
                spec = {**spec, "ground": ground}
                html = await _author_starter(spec, family, ds, ground)
                if html is None:
                    continue
                templates.append(
                    await _save_starter(
                        repo, f"{ds.id}-{family}-{variant}", ds.id,
                        name, family, i, ground, html,
                    )
                )

        templates.extend(await seed_style_templates(session, ds.id, style_language))

        # Families no pack covers (story always; portrait for most languages)
        # still get one authored starter so every platform has a template.
        for family in ("portrait", "story"):
            if await repo.list(ds.id, family=family, include_inactive=True):
                continue
            spec = {**STARTER_SPECS[family]["a"], "ground": ground}
            html = await _author_starter(spec, family, ds, ground)
            if html is None:
                continue
            templates.append(
                await _save_starter(
                    repo, f"{ds.id}-{family}-a", ds.id, name, family, 1, ground, html,
                )
            )
    return templates


async def create_design_system_from_input(
    pool: async_sessionmaker[AsyncSession],
    payload: dict,
) -> dict:
    """Run the full brand builder chain; returns {design_system_id, templates}.

    Atomic: the row is created inactive and only activated once every step
    succeeded; any failure after it exists deletes the row + its templates.
    """
    brief = await _brand_vision(payload)
    languages = await _language_options(pool)
    tokens_out, campaigns_out = await asyncio.gather(
        _brand_tokens(brief, languages), _brand_campaigns(brief)
    )

    identity = brief.get("identity") or {}
    name = identity.get("name") or payload.get("name") or "Untitled Brand"
    footer = {
        "left": (name or "").upper(),
        "right": payload.get("handle", ""),
    }
    ground = (
        brief.get("ground")
        if brief.get("ground") in ("white", "black")
        else "white"
    )
    tokens = _build_tokens(brief, tokens_out)
    has_accent = _has_accent(tokens)
    requested = tokens_out.get("style_language") or brief.get("style_language")
    async with pool() as session:
        lang = await _resolve_language(session, requested, has_accent)
        di = await _build_design_instruction(
            pool, session, brief, tokens_out, lang, has_accent, ground
        )
    tokens = _complete_tokens(tokens, lang)

    raw_roles = tokens_out.get("token_roles")
    token_roles = {
        k: v for k, v in (raw_roles if isinstance(raw_roles, dict) else {}).items()
        if isinstance(k, str) and isinstance(v, str) and k in tokens
    }
    for var in ("--color-accent", "--color-accent-secondary"):
        if var in tokens:
            token_roles.setdefault(var, SEMANTIC_VAR_ROLES[var])
    campaigns = _clean_campaigns(campaigns_out, ground)

    issues = ds_service.validate_design_system(
        {"tokens": tokens, "campaigns": campaigns, "design_instruction": di}
    )
    if issues:
        raise ValueError("Generated design system is invalid: " + "; ".join(issues))

    ds_id = ds_service.slugify(name)
    async with pool() as session:
        repo = DesignSystemRepository(session)
        base = ds_id
        suffix = 2
        while await repo.get_by_id(ds_id):
            ds_id = f"{base}-{suffix}"
            suffix += 1

        logo = None
        if payload.get("logo_image"):
            mime = payload.get("logo_mime") or "image/png"
            logo = {
                "mime": mime,
                "data": payload["logo_image"],
                "filename": "logo",
            }

        ds = await repo.create(
            ds_id,
            {
                "name": name,
                "description": f"Agentic brand system ({payload.get('industry') or 'general'}).",
                "brand": {
                    "name": name,
                    "tagline": identity.get("tagline", "") or payload.get("tagline", ""),
                    "mission": identity.get("mission", "") or payload.get("mission", ""),
                    "story": payload.get("mission", ""),
                    "url": "",
                    "social": {},
                },
                "footer": footer,
                "categories": DEFAULT_CATEGORIES,
                "overrides": {},
                "tokens": tokens,
                "token_roles": token_roles,
                "campaigns": campaigns,
                "design_instruction": di,
                "logo": logo,
                "source": "ai",
                # Hidden until the whole chain succeeds (see below).
                "is_active": False,
            },
        )

    try:
        templates = await _build_starter_templates(pool, ds, name, ground, lang.id)
        async with pool() as session:
            await DesignSystemRepository(session).update(ds_id, {"is_active": True})
    except BaseException:
        log.warning("[brand_agent] build of %s failed — removing partial system", ds_id)
        try:
            async with pool() as session:
                await DesignSystemRepository(session).delete_cascade(ds_id)
        except Exception as cleanup_err:  # noqa: BLE001 — surface the original error
            log.error("[brand_agent] cleanup of %s failed: %s", ds_id, cleanup_err)
        raise

    return {
        "design_system_id": ds_id,
        "style_language": lang.id,
        "templates": templates,
    }
