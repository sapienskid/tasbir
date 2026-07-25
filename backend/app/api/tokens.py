import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from fastapi import HTTPException

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
    db: AsyncSession = Depends(get_db)
):
    """Generate design tokens from brand context using LLM."""
    from app.models.settings import Settings
    from sqlalchemy import select
    from app.models.tokens import DesignToken
    from app.services.llm import call_llm

    brand_context = ""
    result = await db.execute(select(Settings).where(Settings.id == 1))
    settings_row = result.scalar_one_or_none()
    if settings_row and settings_row.data:
        brand = settings_row.data.get("brand", {})
        if brand.get("story"):
            brand_context += f"\nBrand story: {brand['story']}"
        if brand.get("tagline"):
            brand_context += f"\nTagline: {brand['tagline']}"

    system_prompt = (
        "You are a design token generator. Generate DTCG-format design tokens "
        "for the given brand. Use nested objects with 'value' and 'type'. "
        "Include: color (neutral palette + semantic colors), "
        "typography (fontFamily with sans, serif, mono, display variants; "
        "fontSize scale; fontWeight; lineHeight; letterSpacing), "
        "spacing (scale + layout gaps), borderRadius, boxShadow, and opacity. "
        "Return ONLY valid JSON with no markdown fences."
    )
    user_prompt = (
        f"Brand name: {brand_name}\n"
        f"Tone: {tone}\n"
        f"Style: {style}\n"
        f"Primary color: {primary_color or 'auto'}\n"
        f"Secondary color: {secondary_color or 'auto'}\n"
        f"{brand_context}\n\n"
        f"Generate a complete set of design tokens."
    )
    response = await call_llm(
        "token_generator", system_prompt, user_prompt, temperature=0.3, max_tokens=8192
    )

    import json

    if not response.strip():
        raise HTTPException(status_code=502, detail="LLM returned empty response — check API key or quota")
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM returned invalid JSON — try again")
    token = DesignToken(name=brand_name.lower(), data=data, source="ai-generated")
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token
