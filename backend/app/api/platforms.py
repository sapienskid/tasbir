"""Platforms API — CRUD for the DB-backed platform config.

Adding a platform no longer requires a YAML edit or a worker restart: it is
seeded once from platforms.yaml, then owned by the Studio. Writes refresh the
warm cache so the pipeline picks changes up within a TTL.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.platforms import PlatformRepository
from app.services import platforms as platform_service

log = logging.getLogger(__name__)

router = APIRouter()

_VALID_FAMILIES = {"square", "portrait", "story", "landscape"}


class PlatformCreate(BaseModel):
    id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(default="", max_length=128)
    width: int = Field(ge=16, le=8192)
    height: int = Field(ge=16, le=8192)
    family: str = Field(default="square", max_length=32)
    is_active: bool = True
    sort_order: int = 0


class PlatformUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    width: int | None = Field(default=None, ge=16, le=8192)
    height: int | None = Field(default=None, ge=16, le=8192)
    family: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    sort_order: int | None = None


def _validate_family(family: str) -> None:
    if family not in _VALID_FAMILIES:
        raise HTTPException(
            status_code=422,
            detail=f"family must be one of {sorted(_VALID_FAMILIES)}",
        )


async def _refresh() -> None:
    await platform_service.refresh_platforms()


@router.get("")
async def list_platforms(include_inactive: bool = False):
    rows = platform_service.list_platforms(include_inactive=include_inactive)
    return rows


@router.get("/{platform_id}")
async def get_platform(platform_id: str):
    row = platform_service.get_platform(platform_id)
    if row is None:
        raise NotFoundError(f"Platform {platform_id} not found")
    return row


@router.post("", status_code=201)
async def create_platform(body: PlatformCreate, db: AsyncSession = Depends(get_db)):
    _validate_family(body.family)
    repo = PlatformRepository(db)
    if await repo.get_by_id(body.id) is not None:
        raise HTTPException(status_code=409, detail=f"Platform {body.id} exists")
    data = body.model_dump()
    row = await repo.create(data)
    await _refresh()
    return platform_service.platform_to_dict(row)


@router.put("/{platform_id}")
async def update_platform(
    platform_id: str, body: PlatformUpdate, db: AsyncSession = Depends(get_db)
):
    if body.family is not None:
        _validate_family(body.family)
    repo = PlatformRepository(db)
    if await repo.get_by_id(platform_id) is None:
        raise NotFoundError(f"Platform {platform_id} not found")
    row = await repo.update(platform_id, body.model_dump(exclude_unset=True))
    await _refresh()
    return platform_service.platform_to_dict(row)


@router.delete("/{platform_id}", status_code=204)
async def delete_platform(platform_id: str, db: AsyncSession = Depends(get_db)):
    repo = PlatformRepository(db)
    if await repo.get_by_id(platform_id) is None:
        raise NotFoundError(f"Platform {platform_id} not found")
    await repo.delete(platform_id)
    await _refresh()
