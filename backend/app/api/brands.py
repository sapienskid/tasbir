import json
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.services.llm import call_llm

router = APIRouter()


class BrandResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    data: dict
    version: int
    source: str


class BrandCreate(BaseModel):
    name: str
    description: str


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(data: BrandCreate, db: AsyncSession = Depends(get_db)):
    """Create a brand — name + description → LLM generates identity + tokens."""
    from app.agents.prompts.registry import get_prompt

    prompt = await get_prompt("token_generator")

    system_prompt = (
        f"{prompt.system_prompt}\n\n"
        f"Generate a complete brand identity JSON for the brand described below."
    )
    user_prompt = (
        f"Brand name: {data.name}\n"
        f"Brand description: {data.description}\n\n"
        f"Return a JSON object with 'brand' (metadata) and 'tokens' (DTCG tokens) keys."
    )

    response = await call_llm(
        "token_generator", system_prompt, user_prompt, temperature=0.3, max_tokens=8192
    )

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        llm_output = json.loads(cleaned)
    except json.JSONDecodeError:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="LLM returned invalid JSON — try again")

    brand_meta = llm_output.get("brand", {})
    tokens = llm_output.get("tokens", {})

    from app.models.brand import Brand

    brand = Brand(
        name=data.name,
        description=data.description,
        data={
            "tone": brand_meta.get("tone", "professional"),
            "primary_color": brand_meta.get("primary_color", "#000000"),
            "secondary_color": brand_meta.get("secondary_color", "#ffffff"),
            "style_notes": brand_meta.get("style_notes", ""),
            "tokens": tokens,
        },
        source="ai-generated",
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.get("", response_model=list[BrandResponse])
async def list_brands(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.brand import Brand

    result = await db.execute(select(Brand).order_by(Brand.name))
    return result.scalars().all()


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.brand import Brand

    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise NotFoundError(f"Brand {brand_id} not found")
    return brand


@router.delete("/{brand_id}", status_code=204)
async def delete_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.brand import Brand

    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise NotFoundError(f"Brand {brand_id} not found")
    await db.delete(brand)
    await db.commit()
