import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.templates import TemplateRepository

router = APIRouter()


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    html: str
    slots: dict
    enabled: bool


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    html: str
    slots: dict = {}
    enabled: bool = True


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    html: str | None = None
    slots: dict | None = None
    enabled: bool | None = None


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    repo = TemplateRepository(db)
    return await repo.list(enabled_only=enabled_only)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = TemplateRepository(db)
    template = await repo.get_by_id(template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    return template


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = TemplateRepository(db)
    return await repo.create(data.model_dump())


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = TemplateRepository(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    template = await repo.update(template_id, update_data)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = TemplateRepository(db)
    deleted = await repo.delete(template_id)
    if not deleted:
        raise NotFoundError(f"Template {template_id} not found")
