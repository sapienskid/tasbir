
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.models.format import Format

router = APIRouter()


class FormatResponse(BaseModel):
    id: str
    name: str
    width: int
    height: int
    ai_instruction: str
    enabled: bool


class FormatCreate(BaseModel):
    id: str
    name: str
    width: int
    height: int
    ai_instruction: str = ""
    enabled: bool = True


class FormatUpdate(BaseModel):
    name: str | None = None
    width: int | None = None
    height: int | None = None
    ai_instruction: str | None = None
    enabled: bool | None = None


@router.get("", response_model=list[FormatResponse])
async def list_formats(
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Format).order_by(Format.name)
    if enabled_only:
        stmt = stmt.where(Format.enabled.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{format_id}", response_model=FormatResponse)
async def get_format(format_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Format).where(Format.id == format_id))
    fmt = result.scalar_one_or_none()
    if not fmt:
        raise NotFoundError(f"Format {format_id} not found")
    return fmt


@router.post("", response_model=FormatResponse, status_code=201)
async def create_format(data: FormatCreate, db: AsyncSession = Depends(get_db)):
    fmt = Format(**data.model_dump())
    db.add(fmt)
    await db.commit()
    await db.refresh(fmt)
    return fmt


@router.put("/{format_id}", response_model=FormatResponse)
async def update_format(
    format_id: str, data: FormatUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Format).where(Format.id == format_id))
    fmt = result.scalar_one_or_none()
    if not fmt:
        raise NotFoundError(f"Format {format_id} not found")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    for key, value in update_data.items():
        setattr(fmt, key, value)
    await db.commit()
    await db.refresh(fmt)
    return fmt


@router.delete("/{format_id}", status_code=204)
async def delete_format(format_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Format).where(Format.id == format_id))
    fmt = result.scalar_one_or_none()
    if not fmt:
        raise NotFoundError(f"Format {format_id} not found")
    await db.delete(fmt)
    await db.commit()
