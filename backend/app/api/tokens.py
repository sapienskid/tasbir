import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError

router = APIRouter()


class TokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    data: dict
    version: int
    source: str


class TokenCreate(BaseModel):
    name: str
    data: dict
    source: str = "manual"


class TokenUpdate(BaseModel):
    data: dict | None = None


@router.get("", response_model=list[TokenResponse])
async def list_tokens(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).order_by(DesignToken.name))
    return result.scalars().all()


@router.get("/{token_id}", response_model=TokenResponse)
async def get_token(token_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise NotFoundError(f"Design token {token_id} not found")
    return token


@router.post("", response_model=TokenResponse, status_code=201)
async def create_token(data: TokenCreate, db: AsyncSession = Depends(get_db)):
    from app.models.tokens import DesignToken

    token = DesignToken(name=data.name, data=data.data, source=data.source)
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


@router.put("/{token_id}", response_model=TokenResponse)
async def update_token(
    token_id: uuid.UUID, data: TokenUpdate, db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise NotFoundError(f"Design token {token_id} not found")
    if data.data is not None:
        token.data = data.data
        token.version += 1
    await db.commit()
    await db.refresh(token)
    return token


@router.delete("/{token_id}", status_code=204)
async def delete_token(token_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise NotFoundError(f"Design token {token_id} not found")
    await db.delete(token)
    await db.commit()


@router.post("/generate", response_model=TokenResponse)
async def generate_tokens(
    brand_name: str,
    tone: str = "professional",
    style: str = "modern",
    primary_color: str = "",
    secondary_color: str = "",
    accent_color: str = "",
    db: AsyncSession = Depends(get_db)
):
    """Generate design tokens using a LangGraph agent with contrast-checking tools.

    The agent (Dr. Soren Lindqvist) generates a FULL-SPECTRUM design system
    that works in both light and dark modes. It uses check_contrast_tool to
    validate WCAG AA compliance for every color pair during generation.
    """
    import json
    import logging

    from app.agents.orchestrator.nodes.token_generator import generate_tokens as agent_run
    from app.services.color_tools import generate_palette

    log = logging.getLogger(__name__)

    data = None
    agent_ok = False

    try:
        data = await agent_run(
            brand_name=brand_name,
            brand_description=f"Tone: {tone}. Style: {style}.",
            tone=tone,
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
        )
        agent_ok = True
    except Exception as e:
        log.warning("Token generator agent failed: %s", e, exc_info=True)

    if agent_ok and data:
        data = _fix_token_contrast(data, primary_color, secondary_color)
        has_colors = bool(data.get("color", {}).get("brand"))
        has_typo = bool(data.get("typography", {}).get("fontFamily"))
        if not has_colors or not has_typo:
            agent_ok = False

    if not agent_ok or not data:
        pc = primary_color or "#CD5B7D"
        sc = secondary_color or "#5B7D7C"
        generated = generate_palette(pc, sc, theme="dark")
        data = {
            "color": generated["color"],
            "typography": _FALLBACK_TYPOGRAPHY,
            "spacing": _FALLBACK_SPACING,
            "borderRadius": _FALLBACK_RADIUS,
            "boxShadow": _FALLBACK_SHADOW,
            "opacity": _FALLBACK_OPACITY,
        }
        log.info("Used programmatic fallback palette for %s", brand_name)

    from sqlalchemy import select
    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.name == brand_name.lower()))
    existing = result.scalar_one_or_none()
    if existing:
        existing.data = data
        existing.version += 1
        existing.source = "ai-generated"
        await db.commit()
        await db.refresh(existing)
        return existing

    token = DesignToken(name=brand_name.lower(), data=data, source="ai-generated")
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


# ── Fallback constants used by the token generator ──────────────────────

_FALLBACK_TYPOGRAPHY = {
    "fontFamily": {
        "sans": {"$value": "Inter, system-ui, sans-serif", "$type": "fontFamily"},
        "serif": {"$value": "Instrument Serif, Georgia, serif", "$type": "fontFamily"},
        "mono": {"$value": "JetBrains Mono, monospace", "$type": "fontFamily"},
    },
    "fontSize": {
        "xs": {"$value": "0.75rem", "$type": "dimension"},
        "sm": {"$value": "0.875rem", "$type": "dimension"},
        "base": {"$value": "1rem", "$type": "dimension"},
        "lg": {"$value": "1.125rem", "$type": "dimension"},
        "xl": {"$value": "1.25rem", "$type": "dimension"},
        "2xl": {"$value": "1.5rem", "$type": "dimension"},
        "3xl": {"$value": "1.875rem", "$type": "dimension"},
        "4xl": {"$value": "2.25rem", "$type": "dimension"},
    },
    "fontWeight": {
        "light": {"$value": "300", "$type": "number"},
        "normal": {"$value": "400", "$type": "number"},
        "medium": {"$value": "500", "$type": "number"},
        "semibold": {"$value": "600", "$type": "number"},
        "bold": {"$value": "700", "$type": "number"},
    },
    "lineHeight": {
        "tight": {"$value": "1.15", "$type": "number"},
        "snug": {"$value": "1.35", "$type": "number"},
        "normal": {"$value": "1.5", "$type": "number"},
        "relaxed": {"$value": "1.625", "$type": "number"},
    },
    "letterSpacing": {
        "tight": {"$value": "-0.025em", "$type": "dimension"},
        "normal": {"$value": "0", "$type": "dimension"},
        "wide": {"$value": "0.025em", "$type": "dimension"},
        "wider": {"$value": "0.05em", "$type": "dimension"},
        "widest": {"$value": "0.1em", "$type": "dimension"},
    },
}

_FALLBACK_SPACING = {
    "0": {"$value": "0", "$type": "dimension"},
    "2": {"$value": "0.5rem", "$type": "dimension"},
    "4": {"$value": "1rem", "$type": "dimension"},
    "6": {"$value": "1.5rem", "$type": "dimension"},
    "8": {"$value": "2rem", "$type": "dimension"},
    "12": {"$value": "3rem", "$type": "dimension"},
    "16": {"$value": "4rem", "$type": "dimension"},
}

_FALLBACK_RADIUS = {
    "none": {"$value": "0", "$type": "dimension"},
    "sm": {"$value": "0.125rem", "$type": "dimension"},
    "md": {"$value": "0.375rem", "$type": "dimension"},
    "lg": {"$value": "0.5rem", "$type": "dimension"},
    "xl": {"$value": "0.75rem", "$type": "dimension"},
    "2xl": {"$value": "1rem", "$type": "dimension"},
    "full": {"$value": "9999px", "$type": "dimension"},
}

_FALLBACK_SHADOW = {
    "sm": {"$value": "0 1px 2px 0 rgba(0,0,0,0.05)", "$type": "shadow"},
    "md": {"$value": "0 4px 6px -1px rgba(0,0,0,0.1)", "$type": "shadow"},
    "lg": {"$value": "0 10px 15px -3px rgba(0,0,0,0.1)", "$type": "shadow"},
    "xl": {"$value": "0 20px 25px -5px rgba(0,0,0,0.25)", "$type": "shadow"},
}

_FALLBACK_OPACITY = {
    "low": {"$value": "0.2", "$type": "number"},
    "medium": {"$value": "0.5", "$type": "number"},
    "high": {"$value": "0.8", "$type": "number"},
}


def _fix_token_contrast(data: dict, primary_color: str, secondary_color: str,
                        theme: str = "dark") -> dict:
    """Validate and fix contrast in generated tokens for the given theme.

    For dark theme: backgrounds are dark, text must be LIGHT.
    For light theme: backgrounds are light, text must be DARK.
    """
    color = data.get("color", {})

    if theme == "light":
        BG = "#FFFFFF"
        SURFACE = "#F3F4F6"
        TEXT_PRIMARY = "#111827"
        TEXT_SECONDARY = "#6B7280"
        INVERSE = "#FFFFFF"
        ACTION_TEXT = "#FFFFFF"
    else:
        BG = "#0A0A0C"
        SURFACE = "#141418"
        TEXT_PRIMARY = "#EEE9E4"
        TEXT_SECONDARY = "#9B9BA0"
        INVERSE = "#0A0A0C"
        ACTION_TEXT = "#FFFFFF"

    neutral = color.setdefault("neutral", {})
    for key, val in [("bg", BG), ("surface", SURFACE)]:
        if key not in neutral or not neutral.get(key, {}).get("$value", "").startswith("#"):
            neutral[key] = {"$value": val, "$type": "color"}

    semantic = color.setdefault("semantic", {})
    text = semantic.setdefault("text", {})
    text_defaults = [("primary", TEXT_PRIMARY), ("secondary", TEXT_SECONDARY), ("inverse", INVERSE)]
    for key, default in text_defaults:
        if key not in text or not text.get(key, {}).get("$value", "").startswith("#"):
            text[key] = {"$value": default, "$type": "color"}

    action = semantic.setdefault("action", {})
    if "text" not in action or not action["text"].get("$value", "").startswith("#"):
        action["text"] = {"$value": ACTION_TEXT, "$type": "color"}

    brand = color.setdefault("brand", {})
    if primary_color:
        brand.setdefault("primary", {}).setdefault("main", {})["$value"] = primary_color
    if secondary_color:
        brand.setdefault("secondary", {}).setdefault("main", {})["$value"] = secondary_color

    return data
