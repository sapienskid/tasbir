import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError

router = APIRouter()


class TokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    data: dict
    version: int
    source: str


class TokenCreate(BaseModel):
    name: str
    data: dict
    source: str = "manual"


class TokenUpdate(BaseModel):
    data: dict | None = None


@router.get("", response_model=list[TokenResponse])
async def list_tokens(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).order_by(DesignToken.name))
    return result.scalars().all()


@router.get("/{token_id}", response_model=TokenResponse)
async def get_token(token_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise NotFoundError(f"Design token {token_id} not found")
    return token


@router.post("", response_model=TokenResponse, status_code=201)
async def create_token(data: TokenCreate, db: AsyncSession = Depends(get_db)):
    from app.models.tokens import DesignToken

    token = DesignToken(name=data.name, data=data.data, source=data.source)
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


@router.put("/{token_id}", response_model=TokenResponse)
async def update_token(
    token_id: uuid.UUID, data: TokenUpdate, db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise NotFoundError(f"Design token {token_id} not found")
    if data.data is not None:
        token.data = data.data
        token.version += 1
    await db.commit()
    await db.refresh(token)
    return token


@router.delete("/{token_id}", status_code=204)
async def delete_token(token_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.tokens import DesignToken

    result = await db.execute(select(DesignToken).where(DesignToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise NotFoundError(f"Design token {token_id} not found")
    await db.delete(token)
    await db.commit()


@router.post("/generate", response_model=TokenResponse)
async def generate_tokens(
    brand_name: str,
    tone: str = "professional",
    style: str = "modern",
    primary_color: str = "",
    secondary_color: str = "",
    db: AsyncSession = Depends(get_db)
):
    """Generate design tokens from brand context using LLM (async task)."""
    from app.db.repositories.tasks import TaskRepository
    from app.tasks.brands import generate_token_task

    task_repo = TaskRepository(db)
    source_data = {
        "type": "token_generation",
        "brand_name": brand_name,
        "tone": tone,
        "style": style,
        "primary_color": primary_color,
        "secondary_color": secondary_color,
    }
    task = await task_repo.create(source_data=source_data)
    generate_token_task.delay(
        str(task.id), brand_name, tone, style, primary_color, secondary_color
    )
    raise HTTPException(
        status_code=202,
        detail={
            "task_id": str(task.id),
            "status": "pending",
            "message": f"Token generation queued for '{brand_name}'",
        },
    )
