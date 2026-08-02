from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class DesignSystem(Base):
    """A complete brand/design system: identity, tokens, campaigns, rules.

    Fully DB-backed (v0.5). The YAML files seed the ``default`` system on first
    boot; everything after lives here.
    """

    __tablename__ = "design_systems"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")

    # brand: {name, tagline, mission, story, url, social}
    brand: Mapped[dict] = mapped_column(JSON, default=dict)
    # footer: {left, right}
    footer: Mapped[dict] = mapped_column(JSON, default=dict)
    # categories: [{name, description, ground?}]
    categories: Mapped[list] = mapped_column(JSON, default=list)
    # overrides: {badge, tagline, category}
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    # tokens: {--color-*, --font-*, --radius-*, --shadow-*} (incl. brand colors)
    tokens: Mapped[dict] = mapped_column(JSON, default=dict)
    # token_roles: {var -> semantic role text} shown to the designer prompt
    token_roles: Mapped[dict] = mapped_column(JSON, default=dict)
    # campaigns: {name -> {label, tone, ground, language}}
    campaigns: Mapped[dict] = mapped_column(JSON, default=dict)
    # design_instruction: full config (style, type_voice, type_scale, spacing, ...)
    design_instruction: Mapped[dict] = mapped_column(JSON, default=dict)
    # logo: {mime, data(base64), filename} | None
    logo: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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
