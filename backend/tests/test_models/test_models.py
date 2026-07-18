"""Tests for SQLAlchemy models."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings
from app.models.format import Format
from app.models.template import Template
from app.models.task import GenerationTask
from app.models.prompt import PromptRegistry
from app.models.tokens import DesignToken


@pytest.mark.asyncio
async def test_create_settings(db_session: AsyncSession):
    s = Settings(id=1, data={"key": "value"})
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    assert s.data["key"] == "value"
    assert s.updated_at is not None


@pytest.mark.asyncio
async def test_create_format(db_session: AsyncSession):
    fmt = Format(id="test-format", name="Test Format", width=800, height=600)
    db_session.add(fmt)
    await db_session.commit()
    await db_session.refresh(fmt)
    assert fmt.width == 800
    assert fmt.height == 600
    assert fmt.enabled is True


@pytest.mark.asyncio
async def test_create_template(db_session: AsyncSession):
    tmpl = Template(name="Test Template", html="<div>Hello</div>")
    db_session.add(tmpl)
    await db_session.commit()
    await db_session.refresh(tmpl)
    assert tmpl.id is not None
    assert isinstance(tmpl.id, uuid.UUID)


@pytest.mark.asyncio
async def test_create_generation_task(db_session: AsyncSession):
    task = GenerationTask(source_data={"content": "test"})
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    assert task.id is not None
    assert task.status == "pending"
    assert task.progress == 0


@pytest.mark.asyncio
async def test_create_prompt(db_session: AsyncSession):
    pr = PromptRegistry(name="test-prompt", system_prompt="You are a test.")
    db_session.add(pr)
    await db_session.commit()
    await db_session.refresh(pr)
    assert pr.temperature == 0.7
    assert pr.is_active is True


@pytest.mark.asyncio
async def test_create_design_token(db_session: AsyncSession):
    token = DesignToken(name="test-brand", data={"color": {"primary": "#000"}})
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    assert token.id is not None
    assert token.version == 1
    assert token.source == "manual"
