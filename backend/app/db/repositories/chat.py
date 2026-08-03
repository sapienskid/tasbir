from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatThread


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_thread(self, task_id: str, format: str) -> ChatThread | None:
        result = await self.session.execute(
            select(ChatThread)
            .where(ChatThread.task_id == task_id, ChatThread.format == format)
            .order_by(ChatThread.created_at.asc())
        )
        return result.scalars().first()

    async def get_or_create_thread(self, task_id: str, format: str) -> ChatThread:
        thread = await self.get_thread(task_id, format)
        if thread:
            return thread
        thread = ChatThread(task_id=task_id, format=format)
        self.session.add(thread)
        await self.session.commit()
        await self.session.refresh(thread)
        return thread

    async def list_messages(self, thread_id: str) -> list[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_message(
        self, thread_id: str, role: str, content: str, html: str | None = None
    ) -> ChatMessage:
        msg = ChatMessage(thread_id=thread_id, role=role, content=content, html=html)
        self.session.add(msg)
        thread = await self.session.get(ChatThread, thread_id)
        if thread:
            from datetime import datetime, timezone
            thread.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def delete_thread(self, task_id: str, format: str) -> None:
        """Delete a thread (and its messages) for a (task_id, format)."""
        thread = await self.get_thread(task_id, format)
        if not thread:
            return
        await self.session.execute(
            ChatMessage.__table__.delete().where(
                ChatMessage.thread_id == thread.id
            )
        )
        await self.session.delete(thread)
        await self.session.commit()
