from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.db.repositories.tasks import TaskRepository
from app.tasks.generate import generate_task

router = APIRouter()


class CampaignContext(BaseModel):
    name: str = ""
    description: str = ""
    post_type: str = ""  # educational, promotional, announcement, thought_leadership
    series_name: str = ""
    series_part: int = 0
    series_total: int = 0


class GenerateRequest(BaseModel):
    content: str
    title: str = ""
    platforms: list[str] = ["instagram-square"]
    webhook_url: str | None = None

    # Brand & campaign context
    campaign: CampaignContext = Field(default_factory=CampaignContext)
    overrides: dict[str, str] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"


@router.post("", response_model=GenerateResponse)
async def generate(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.create(source_data=request.model_dump())
    generate_task.delay(str(task.id), request.model_dump())
    return GenerateResponse(task_id=str(task.id))
