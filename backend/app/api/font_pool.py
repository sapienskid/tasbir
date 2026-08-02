"""Curated font pool API — CRUD for the DB-backed pool.

The pool is seeded once from fonts.yaml and owned by the Studio. The
brand_tokens agent and the design-system editor read it through the
DB-backed fonts service.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.fonts import FontRepository
from app.services import fonts as font_service

log = logging.getLogger(__name__)

router = APIRouter()

_VALID_ROLES = {"sans", "serif", "display", "mono"}


class FontCreate(BaseModel):
    family: str = Field(min_length=1, max_length=128)
    role: str = Field(default="sans", max_length=32)
    weights: list[int] = Field(default_factory=list)
    style: str = Field(default="", max_length=256)
    is_active: bool = True
    sort_order: int = 0


class FontUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=32)
    weights: list[int] | None = None
    style: str | None = Field(default=None, max_length=256)
    is_active: bool | None = None
    sort_order: int | None = None


def _validate_role(role: str) -> None:
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=422, detail=f"role must be one of {sorted(_VALID_ROLES)}"
        )


async def _refresh() -> None:
    await font_service.refresh_font_pool()


@router.get("")
async def list_pool(include_inactive: bool = False):
    from app.services.fonts import _fonts

    rows = _fonts()
    if not include_inactive:
        rows = [r for r in rows if r.get("is_active", True)]
    return rows


@router.post("", status_code=201)
async def create_font(body: FontCreate, db: AsyncSession = Depends(get_db)):
    _validate_role(body.role)
    repo = FontRepository(db)
    if await repo.get_by_family(body.family) is not None:
        raise HTTPException(status_code=409, detail=f"Font {body.family} exists")
    row = await repo.create(body.model_dump())
    await _refresh()
    return font_service.font_to_dict(row)


@router.put("/{family}")
async def update_font(
    family: str, body: FontUpdate, db: AsyncSession = Depends(get_db)
):
    if body.role is not None:
        _validate_role(body.role)
    repo = FontRepository(db)
    if await repo.get_by_family(family) is None:
        raise NotFoundError(f"Font {family} not found")
    row = await repo.update(family, body.model_dump(exclude_unset=True))
    await _refresh()
    return font_service.font_to_dict(row)


@router.delete("/{family}", status_code=204)
async def delete_font(family: str, db: AsyncSession = Depends(get_db)):
    repo = FontRepository(db)
    if await repo.get_by_family(family) is None:
        raise NotFoundError(f"Font {family} not found")
    await repo.delete(family)
    await _refresh()
