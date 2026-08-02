from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.db.repositories.tasks import TaskRepository
from app.services.formats import validate_platforms
from app.tasks.generate import generate_task

router = APIRouter()


class ImageRequest(BaseModel):
    url: str = Field(max_length=2048)
    alt: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=500)
    placement: str = Field(default="auto", max_length=32)


class GenerateRequest(BaseModel):
    content: str = Field(max_length=100_000)
    title: str = Field(default="", max_length=300)
    excerpt: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    platforms: list[str] = Field(default_factory=lambda: ["instagram-square"], max_length=12)
    campaign: str = Field(default="default", max_length=64)
    category: str | None = Field(default=None, max_length=64)
    overrides: dict[str, str] = Field(default_factory=dict)
    images: list[ImageRequest] = Field(default_factory=list, max_length=8)

    @field_validator("tags")
    @classmethod
    def _cap_tag_length(cls, v: list[str]) -> list[str]:
        return [t[:100] for t in v]

    @field_validator("overrides")
    @classmethod
    def _cap_overrides(cls, v: dict[str, str]) -> dict[str, str]:
        limited = {k[:50]: val[:500] for k, val in v.items()}
        if len(limited) > 8:
            raise HTTPException(status_code=422, detail="Too many overrides (max 8)")
        return limited

    @field_validator("platforms")
    @classmethod
    def _validate_platforms(cls, v: list[str]) -> list[str]:
        return validate_platforms(v)


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"


@router.post("", response_model=GenerateResponse)
async def generate(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    data = request.model_dump()
    repo = TaskRepository(db)
    task = await repo.create(source_data=data)
    generate_task.delay(str(task.id), data)
    return GenerateResponse(task_id=str(task.id))
