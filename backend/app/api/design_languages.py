"""Design languages API — list/create/update/delete manageable style bundles."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.services import design_languages as dl_service

log = logging.getLogger(__name__)

router = APIRouter()


class DesignLanguageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=2000)


class DesignLanguageUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


def _to_dict(d: dl_service.LanguageDefinition) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "emoji": d.emoji,
        "grayscale": d.grayscale,
        "accent": d.accent,
        "media_policy": d.media_policy,
        "accent_tokens": d.accent_tokens,
        "palette_tokens": d.palette_tokens,
    }


@router.get("")
async def list_design_languages(
    include_inactive: bool = False, db: AsyncSession = Depends(get_db)
):
    langs = await dl_service.list_languages(db, include_inactive=include_inactive)
    return [_to_dict(d) for d in langs]


@router.post("")
async def create_design_language(
    request: DesignLanguageCreate, db: AsyncSession = Depends(get_db)
):
    try:
        language_id, definition = await dl_service.create_custom_language(
            db, request.name, request.base, request.description
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": language_id, **_to_dict(definition)}


@router.put("/{language_id}")
async def update_design_language(
    language_id: str, request: DesignLanguageUpdate, db: AsyncSession = Depends(get_db)
):
    from app.db.repositories.design_languages import DesignLanguageRepository

    repo = DesignLanguageRepository(db)
    row = await repo.get_by_id(language_id)
    if not row:
        raise NotFoundError(f"Design language {language_id!r} not found")
    data = request.model_dump(exclude_unset=True)
    updated = await repo.update(language_id, data)
    return {"id": language_id, **_to_dict(dl_service._row_definition(updated))}


@router.delete("/{language_id}", status_code=204)
async def delete_design_language(language_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await dl_service.delete_language(db, language_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
