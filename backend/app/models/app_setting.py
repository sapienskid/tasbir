from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AppSetting(Base):
    """A runtime tuning knob — DB-backed (seed-once), Studio-owned.

    Replaces hardcoded constants in the pipeline: verifier retries, copywriter
    concurrency, vision min-interval, chat HTML cap, template anti-repeat.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON, default=None
    )
    description: Mapped[str] = mapped_column(Text, default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
