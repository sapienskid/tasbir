import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Asset(Base):
    __tablename__ = "assets"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_tasks.id"), nullable=False
    )
    format_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("formats.id"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(100), default="image/png")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
