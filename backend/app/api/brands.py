import json
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
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
    logo_url: str | None = None
    tone: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


class BrandUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    logo_url: str | None = None
    tone: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    tokens: dict | None = None


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(data: BrandCreate, db: AsyncSession = Depends(get_db)):
    """Create a brand.

    If primary_color is provided (manual setup), saves directly without LLM.
    Otherwise calls LLM to generate identity + design tokens.
    """
    from app.models.brand import Brand

    # If user provided colors manually, skip LLM call (fast path)
    if data.primary_color:
        brand = Brand(
            name=data.name,
            description=data.description or "",
            data={
                "tone": data.tone or "professional",
                "primary_color": data.primary_color,
                "secondary_color": data.secondary_color or "#ffffff",
                "logo_url": data.logo_url or "",
                "style_notes": "",
                "tokens": {},
            },
            source="manual",
        )
        db.add(brand)
        await db.commit()
        await db.refresh(brand)
        return brand

    # AI generation path — call LLM for full brand identity + tokens
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
        raise HTTPException(status_code=502, detail="LLM returned invalid JSON — try again")

    brand_meta = llm_output.get("brand", {})
    tokens = llm_output.get("tokens", {})

    brand = Brand(
        name=data.name,
        description=data.description,
        data={
            "tone": data.tone or brand_meta.get("tone", "professional"),
            "primary_color": data.primary_color or brand_meta.get("primary_color", "#000000"),
            "secondary_color": data.secondary_color or brand_meta.get("secondary_color", "#ffffff"),
            "logo_url": data.logo_url or brand_meta.get("logo_url", ""),
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


@router.put("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: uuid.UUID, data: BrandUpdate, db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select
    from app.models.brand import Brand

    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise NotFoundError(f"Brand {brand_id} not found")

    if data.name is not None:
        brand.name = data.name
    if data.description is not None:
        brand.description = data.description

    brand_data = dict(brand.data or {})
    if data.logo_url is not None:
        brand_data["logo_url"] = data.logo_url
    if data.tone is not None:
        brand_data["tone"] = data.tone
    if data.primary_color is not None:
        brand_data["primary_color"] = data.primary_color
    if data.secondary_color is not None:
        brand_data["secondary_color"] = data.secondary_color
    if data.tokens is not None:
        brand_data["tokens"] = data.tokens

    brand.data = brand_data
    brand.version += 1
    await db.commit()
    await db.refresh(brand)
    return brand


@router.post("/{brand_id}/logo", response_model=BrandResponse)
async def upload_brand_logo(
    brand_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a brand logo image file, save to MinIO, and update brand.data['logo_url']."""
    from sqlalchemy import select
    from app.models.brand import Brand
    from app.services.storage import upload_asset

    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise NotFoundError(f"Brand {brand_id} not found")

    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "png"
    key = f"brands/{brand_id}/logo.{ext}"
    content = await file.read()
    logo_url = await upload_asset(key, content, content_type=file.content_type or "image/png")

    # Create a DB Asset record so GET /assets/{key} can serve it
    from app.models.asset import Asset
    existing = await db.execute(select(Asset).where(Asset.key == key))
    if not existing.scalar_one_or_none():
        asset = Asset(key=key, task_id=brand_id, content_type=file.content_type or "image/png", url=logo_url)
        db.add(asset)
        await db.commit()

    brand_data = dict(brand.data or {})
    brand_data["logo_url"] = logo_url
    brand.data = brand_data
    brand.version += 1

    await db.commit()
    await db.refresh(brand)
    return brand


@router.get("/{brand_id}/logo")
async def get_brand_logo(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Serve a brand logo. Redirects to the stored path (served by GET /assets/{key})."""
    from sqlalchemy import select
    from app.models.brand import Brand
    from fastapi.responses import RedirectResponse

    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand or not brand.data:
        raise NotFoundError(f"Brand {brand_id} or its logo not found")

    logo_url = brand.data.get("logo_url", "")
    if not logo_url:
        raise NotFoundError(f"Brand {brand_id} has no logo")

    return RedirectResponse(url=logo_url)


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
