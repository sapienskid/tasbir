from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Template(Base):
    """A Jinja2 post-composition template, scoped to a design system."""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    design_system_id: Mapped[str] = mapped_column(
        String(64), default="default", index=True
    )
    name: Mapped[str] = mapped_column(String(128), default="")
    family: Mapped[str] = mapped_column(String(16), default="square")
    # grounds: ["white", "black"]
    grounds: Mapped[list] = mapped_column(JSON, default=list)
    # categories: approved category labels this template suits
    categories: Mapped[list] = mapped_column(JSON, default=list)
    # hint_tags: tokens the strategist's hint can match
    hint_tags: Mapped[list] = mapped_column(JSON, default=list)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    description: Mapped[str] = mapped_column(Text, default="")
    # html: the Jinja2 template source (var(--color-*), data-slot, ...)
    html: Mapped[str] = mapped_column(Text, default="")
    # image_slots: [{key, role, hint}] from data-image-key markers
    image_slots: Mapped[list] = mapped_column(JSON, default=list)
    has_logo_slot: Mapped[bool] = mapped_column(Boolean, default=False)
    # hidden_elements: content vars the template always renders empty (e.g.
    # ["body", "footer_right"]) — set in the Studio editor's Elements panel.
    hidden_elements: Mapped[list] = mapped_column(JSON, default=list)
    # media_position: "auto" | "left" | "right" | "top" | "bottom" — how the
    # media slot is placed in placement-parametric templates.
    media_position: Mapped[str] = mapped_column(String(16), default="auto")

    source: Mapped[str] = mapped_column(String(16), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
