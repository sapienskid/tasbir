import uuid

from fastapi import APIRouter, Depends
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
    brand_name: str, db: AsyncSession = Depends(get_db)
):
    """Generate design tokens from brand name using LLM."""
    from app.models.tokens import DesignToken
    from app.services.llm import call_llm

    system_prompt = (
        "You are a design token generator. Generate a complete set of "
        "DTCG-format design tokens for the given brand name. "
        "Return ONLY valid JSON with color, typography, and spacing tokens."
    )
    user_prompt = f"Generate design tokens for brand: {brand_name}"
    response = await call_llm(
        "token_generator", system_prompt, user_prompt, temperature=0.3
    )

    import json

    data = json.loads(response)
    token = DesignToken(name=brand_name.lower(), data=data, source="ai-generated")
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token
