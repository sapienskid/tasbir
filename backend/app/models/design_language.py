from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class DesignLanguage(Base):
    """A reusable design-language bundle (style rules + palette).

    The built-in presets (swiss-editorial, bold-modern, ...) are seeded on
    first boot from ``styles.STYLE_PRESETS``. Users can create CUSTOM
    languages (based on a preset) and delete them; the Studio owns the rows.
    A design system references a language by ``style_language`` id and keeps a
    merged copy of its ``di`` + tokens, so deleting a language never breaks an
    existing system.
    """

    __tablename__ = "design_languages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # The preset this language is derived from ("" for fully custom).
    base: Mapped[str] = mapped_column(String(64), default="")
    emoji: Mapped[bool] = mapped_column(Boolean, default=False)
    grayscale: Mapped[bool] = mapped_column(Boolean, default=True)
    accent: Mapped[bool] = mapped_column(Boolean, default=False)
    media_policy: Mapped[str] = mapped_column(String(32), default="photo-forward")
    # accent_tokens: {--color-accent, ...}; palette_tokens: core --color-*/--radius-*
    accent_tokens: Mapped[dict] = mapped_column(JSON, default=dict)
    palette_tokens: Mapped[dict] = mapped_column(JSON, default=dict)
    # design-instruction bundle (style, type_voice, do_dont, layout_archetypes,
    # default_ground, photo) applied when a system adopts this language.
    di: Mapped[dict] = mapped_column(JSON, default=dict)

    source: Mapped[str] = mapped_column(String(16), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
