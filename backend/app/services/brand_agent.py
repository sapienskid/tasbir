"""Brand Builder agent — form (+ optional images) → complete design system.

Chain:
  1. Brand Vision    — reference image (if any) → palette/type-feel/voice brief
  2. Brand Tokens    — brief + curated font pool → tokens, token_roles, DI overlay
  3. Brand Campaigns — voice → 3-5 campaign presets
  4. Starter templates — reuse the template author for square + landscape
  5. Persist         — DesignSystem row (logo attached) + templates
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.prompts.registry import load_prompt
from app.db.repositories.design_systems import DesignSystemRepository
from app.db.repositories.templates import TemplateRepository
from app.services import design_systems as ds_service
from app.services.design_instruction import _deep_merge, load_design_instruction
from app.services.fonts import font_pool_for_prompt
from app.services.llm import call_llm
from app.services.template_author import (
    author_template_html,
    extract_json,
    validate_template_html,
)
from app.services.vision import call_vision_llm

log = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    {"name": "PORTFOLIO", "description": "Project posts"},
    {"name": "PROJECT", "description": "Individual build/ship updates"},
    {"name": "WRITING", "description": "Blog posts"},
    {"name": "NOTE", "description": "Short-form/thought posts", "ground": "black"},
]

STARTER_SPECS: dict[str, dict] = {
    "square": {
        "family": "square",
        "ground": "white",
        "regions": [
            {
                "role": "kicker", "x_pct": 6, "y_pct": 6,
                "w_pct": 50, "h_pct": 5, "alignment": "left",
            },
            {
                "role": "headline", "x_pct": 6, "y_pct": 18,
                "w_pct": 88, "h_pct": 30, "alignment": "left",
            },
            {
                "role": "subhead", "x_pct": 6, "y_pct": 52,
                "w_pct": 70, "h_pct": 18, "alignment": "left",
            },
            {
                "role": "body", "x_pct": 6, "y_pct": 72,
                "w_pct": 60, "h_pct": 16, "alignment": "left",
            },
        ],
        "layout_description": "top kicker, large display headline, serif subhead, footer band",
        "notes": ["left-aligned", "bottom-anchored footer"],
    },
    "landscape": {
        "family": "landscape",
        "ground": "white",
        "regions": [
            {
                "role": "kicker", "x_pct": 5, "y_pct": 12,
                "w_pct": 40, "h_pct": 8, "alignment": "left",
            },
            {
                "role": "headline", "x_pct": 5, "y_pct": 22,
                "w_pct": 55, "h_pct": 45, "alignment": "left",
            },
            {
                "role": "subhead", "x_pct": 5, "y_pct": 68,
                "w_pct": 48, "h_pct": 20, "alignment": "left",
            },
        ],
        "layout_description": "kicker + headline left, subhead below, footer spanning",
        "notes": ["left-aligned", "bottom-anchored footer"],
    },
}


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
    prompt_cfg = load_prompt("brand_vision")

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


async def _brand_tokens(brief: dict) -> dict:
    """Brand Tokens: brief + font pool → tokens/token_roles/DI overlay."""
    prompt_cfg = load_prompt("brand_tokens")
    user_prompt = (
        f"BRAND BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        "AVAILABLE FONTS (choose ONLY from these):\n"
        f"{font_pool_for_prompt()}\n\n"
        "Produce the token map, token_roles, and a partial design_instruction overlay."
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
    prompt_cfg = load_prompt("brand_campaigns")
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


def _build_design_instruction(brief: dict, tokens_out: dict) -> dict:
    """Deep-merge the agent's DI overlay over the base Swiss config."""
    from app.config import get_settings

    base = load_design_instruction(
        __import__("pathlib").Path(get_settings().design_system_dir)
        / "design-instruction.yaml"
    )
    overlay = tokens_out.get("design_instruction") or {}
    if isinstance(overlay, dict):
        base = _deep_merge(base, overlay)
    style = base.setdefault("style", {})
    style.setdefault("palette", brief.get("aesthetic", "clean editorial"))
    style.setdefault("name", f"{brief.get('identity', {}).get('name', 'Brand')} Design System")
    return base


def _build_tokens(brief: dict, tokens_out: dict) -> dict:
    tokens = tokens_out.get("tokens") or {}
    if not tokens:
        palette = brief.get("palette") or []
        tokens = {
            f"--color-{p.get('role', '')}": p.get("hex", "")
            for p in palette
            if p.get("role")
        }
    return tokens


async def create_design_system_from_input(
    pool: async_sessionmaker[AsyncSession],
    payload: dict,
) -> dict:
    """Run the full brand builder chain; returns {design_system_id, templates}."""
    brief = await _brand_vision(payload)
    tokens_out = await _brand_tokens(brief)
    campaigns_out = await _brand_campaigns(brief)

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
    token_roles = tokens_out.get("token_roles") or {}
    di = _build_design_instruction(brief, tokens_out)
    campaigns = campaigns_out.get("campaigns") or {
        "default": {
            "label": "Default",
            "tone": "professional",
            "ground": ground,
            "language": "",
        }
    }

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
                "is_active": True,
            },
        )

    # Starter templates: square + landscape (2 each).
    tpl_repo = TemplateRepository
    templates: list[str] = []
    async with pool() as session:
        repo = tpl_repo(session)
        for family in ("square", "landscape"):
            for i, suffix in enumerate(("a", "b"), start=1):
                spec = dict(STARTER_SPECS[family])
                spec["ground"] = ground
                template_id = f"{ds_id}-{family}-{suffix}"
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
                        "[brand_agent] starter template %s failed validation: %s",
                        template_id, result["issues"][:3],
                    )
                    continue
                from app.services.templates import scan_template_features

                image_slots, has_logo = scan_template_features(html)
                await repo.create(
                    {
                        "id": template_id,
                        "design_system_id": ds_id,
                        "name": f"{name} {family} {i}",
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
                templates.append(template_id)

    return {"design_system_id": ds_id, "templates": templates}
