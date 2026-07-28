from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.db.repositories.tasks import TaskRepository
from app.tasks.generate import generate_task

router = APIRouter()


class ImageRequest(BaseModel):
    url: str
    alt: str = ""
    description: str = ""
    placement: str = "auto"  # auto, background, top-left, center, bottom-right


class GenerateRequest(BaseModel):
    content: str
    title: str = ""
    url: str = ""
    excerpt: str = ""
    tags: list[str] = Field(default_factory=list)
    platforms: list[str] = ["instagram-square"]
    webhook_url: str | None = None
    campaign: str = "default"
    overrides: dict[str, str] = Field(default_factory=dict)
    images: list[ImageRequest] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"


@router.post("", response_model=GenerateResponse)
async def generate(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.create(source_data=request.model_dump())
    generate_task.delay(str(task.id), request.model_dump())
    return GenerateResponse(task_id=str(task.id))
