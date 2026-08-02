from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.errors import NotFoundError
from app.db.repositories.chat import ChatRepository
from app.db.repositories.tasks import TaskRepository
from app.services.formats import validate_platforms

router = APIRouter()


class ChatSendRequest(BaseModel):
    format: str
    message: str = Field(min_length=1, max_length=4000)
    # Current editor HTML (already token-injected). Optional — falls back to
    # the last saved render.
    html: str | None = Field(default=None, max_length=500_000)


def _msg_dict(m):
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "html": m.html,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/{task_id}/chat")
async def get_chat(
    task_id: str,
    format: str,
    db: AsyncSession = Depends(get_db),
):
    """Get (or lazily create) the chat thread for a (task, format)."""
    repo = TaskRepository(db)
    if not await repo.get_by_id(task_id):
        raise NotFoundError(f"Task {task_id} not found")

    fmt = validate_platforms([format])[0]
    chat = ChatRepository(db)
    thread = await chat.get_or_create_thread(task_id, fmt)
    messages = await chat.list_messages(thread.id)
    return {
        "thread_id": thread.id,
        "format": fmt,
        "messages": [_msg_dict(m) for m in messages],
    }


@router.post("/{task_id}/chat")
async def send_chat_message(
    task_id: str,
    request: ChatSendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run one chat turn with the design assistant."""
    from app.services.chat import run_chat_turn

    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Task is still processing")

    fmt = validate_platforms([request.format])[0]
    result = await run_chat_turn(
        db, task, fmt, request.message, html=request.html
    )
    return result
