"""Seed default formats + fix assets.task_id FK to allow brand logos.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default format seed data — matches DEFAULT_FORMAT_DIMS + ai_instruction guidelines
DEFAULT_FORMATS = [
    {
        "id": "instagram-square",
        "name": "Instagram Square",
        "width": 1080,
        "height": 1080,
        "ai_instruction": (
            "Centered or 2-zone split canvas. Strong typographic hero with visual anchor at center. "
            "Use bold headline at top 30%, supporting visual in middle 50%, CTA/tagline at bottom 20%. "
            "Thick padding (p-12 to p-16). Clean, high-contrast layout. Avoid clutter."
        ),
    },
    {
        "id": "instagram-portrait",
        "name": "Instagram Portrait",
        "width": 1080,
        "height": 1350,
        "ai_instruction": (
            "Vertical editorial layout. Magazine-style composition: large headline at top 25%, "
            "visual/graphic element fills center 50%, body copy and badge at bottom 25%. "
            "Use generous vertical rhythm. Font sizes: headline 5xl-6xl, body base-lg."
        ),
    },
    {
        "id": "instagram-story",
        "name": "Instagram Story",
        "width": 1080,
        "height": 1920,
        "ai_instruction": (
            "Full-screen immersive vertical canvas. Safe zone: keep content between y=150px and y=1770px. "
            "Headline occupies top 20%, bold visual or background fills center 55%, "
            "CTA/tagline anchored at bottom 25%. Use overlay text with high contrast. "
            "Font: headline 5xl-6xl bold, subhead xl-2xl."
        ),
    },
    {
        "id": "linkedin-post",
        "name": "LinkedIn Post",
        "width": 1200,
        "height": 627,
        "ai_instruction": (
            "Professional horizontal layout. Two-zone split recommended: "
            "text content on left 55% (headline + subhead + key points), "
            "visual/graphic element on right 45%. "
            "Clean typography, ample whitespace. Headline 3xl-4xl semibold, body sm-base. "
            "Brand logo top-left. Conveys authority and expertise."
        ),
    },
    {
        "id": "twitter-card",
        "name": "Twitter / X Card",
        "width": 1200,
        "height": 675,
        "ai_instruction": (
            "Bold single-message horizontal card. One dominant headline (4xl-5xl bold) centered or left-aligned. "
            "Minimal body text — 1 punchy line max. Strong visual background or single graphic element. "
            "High contrast. No clutter. Immediate visual hook within 1 second of viewing."
        ),
    },
    {
        "id": "facebook-post",
        "name": "Facebook Post",
        "width": 1200,
        "height": 630,
        "ai_instruction": (
            "Warm, approachable horizontal layout. Engaging visual left or center, "
            "supporting headline and 1-2 lines of copy right or below. "
            "Use rounded elements and warm tones. Headline 3xl-4xl, body sm-base. "
            "Feels conversational and shareable."
        ),
    },
    {
        "id": "pinterest-pin",
        "name": "Pinterest Pin",
        "width": 1000,
        "height": 1500,
        "ai_instruction": (
            "Tall vertical flow optimised for discovery. Title at top (3xl-4xl bold), "
            "large visual fills center 55%, detail text and CTA at bottom. "
            "Use rich imagery, elegant typography, and clear visual hierarchy. "
            "Think editorial magazine cover meets infographic. Font contrast is critical."
        ),
    },
    {
        "id": "carousel-post",
        "name": "Carousel Post",
        "width": 1080,
        "height": 1350,
        "ai_instruction": (
            "Single carousel slide — treat as a self-contained portrait card. "
            "Large number or step indicator top-left (2xl bold), "
            "headline fills center, key point or stat at bottom. "
            "Consistent visual style across slides implied. Clean, swipeable design."
        ),
    },
]


def upgrade() -> None:
    # 1. Make assets.task_id nullable so brand logos don't require a generation_tasks FK.
    op.alter_column(
        "assets",
        "task_id",
        nullable=True,
        existing_type=postgresql.UUID(as_uuid=True),
    )

    # 2. Seed default formats (skip if already present — idempotent).
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    conn = op.get_bind()
    for fmt in DEFAULT_FORMATS:
        existing = conn.execute(
            sa.text("SELECT id FROM formats WHERE id = :id"),
            {"id": fmt["id"]},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO formats (id, name, width, height, ai_instruction, enabled, created_at) "
                    "VALUES (:id, :name, :width, :height, :ai_instruction, :enabled, :created_at)"
                ),
                {**fmt, "enabled": True, "created_at": now},
            )


def downgrade() -> None:
    op.alter_column(
        "assets",
        "task_id",
        nullable=False,
        existing_type=postgresql.UUID(as_uuid=True),
    )
    for fmt in DEFAULT_FORMATS:
        op.execute(f"DELETE FROM formats WHERE id = '{fmt['id']}'")
