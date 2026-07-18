from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.prompts import PromptRepository

router = APIRouter()


class PromptResponse(BaseModel):
    name: str
    version: int
    system_prompt: str
    user_template: str | None
    temperature: float
    max_tokens: int
    is_active: bool


class PromptUpdate(BaseModel):
    system_prompt: str
    user_template: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2000


class PromptVersionResponse(BaseModel):
    id: str
    prompt_name: str
    version: int
    system_prompt: str
    created_at: str


@router.get("", response_model=list[PromptResponse])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    repo = PromptRepository(db)
    return await repo.list_active()


@router.get("/{name}", response_model=PromptResponse)
async def get_prompt(name: str, db: AsyncSession = Depends(get_db)):
    repo = PromptRepository(db)
    prompt = await repo.get_by_name(name)
    if not prompt:
        raise NotFoundError(f"Prompt '{name}' not found")
    return prompt


@router.put("/{name}", response_model=PromptResponse)
async def update_prompt(
    name: str, data: PromptUpdate, db: AsyncSession = Depends(get_db)
):
    repo = PromptRepository(db)
    return await repo.upsert(name, data.model_dump())


@router.get("/{name}/versions", response_model=list[PromptVersionResponse])
async def get_prompt_versions(name: str, db: AsyncSession = Depends(get_db)):
    repo = PromptRepository(db)
    versions = await repo.get_version_history(name)
    return [
        {
            "id": str(v.id),
            "prompt_name": v.prompt_name,
            "version": v.version,
            "system_prompt": v.system_prompt,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


@router.post("/{name}/restore", response_model=PromptResponse)
async def restore_prompt(
    name: str, version: int, db: AsyncSession = Depends(get_db)
):
    repo = PromptRepository(db)
    prompt = await repo.restore_version(name, version)
    if not prompt:
        raise NotFoundError(
            f"Prompt '{name}' version {version} not found"
        )
    return prompt
