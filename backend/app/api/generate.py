
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.db.repositories.tasks import TaskRepository
from app.tasks.generate import generate_task

router = APIRouter()


class GenerateRequest(BaseModel):
    content: str
    title: str = ""
    excerpt: str = ""
    tags: list[str] = []
    source_url: str | None = None
    feature_image: str | None = None
    requested_formats: list[str] = []
    brand: dict = {}
    campaign: dict = {}
    design_tokens: dict = {}
    settings: dict = {}


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"


@router.post("", response_model=GenerateResponse)
async def generate(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.create(source_data=request.model_dump())
    generate_task.delay(str(task.id), request.model_dump())
    return GenerateResponse(task_id=str(task.id))


@router.post("/stream", response_model=GenerateResponse)
async def generate_sse(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.create(source_data=request.model_dump())
    generate_task.delay(str(task.id), request.model_dump())
    return GenerateResponse(task_id=str(task.id))
