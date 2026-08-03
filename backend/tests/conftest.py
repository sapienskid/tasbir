"""Shared fixtures for tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import async_sessionmaker


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        gemini_api_key="test-gemini-key",
        database_url="sqlite+aiosqlite:///test.db",
        redis_url="redis://localhost:6379/0",
        log_level="debug",
    )


@pytest.fixture
def mock_llm():
    with patch("app.services.llm.call_llm", new_callable=AsyncMock) as m:
        m.return_value = "Mocked LLM response"
        yield m


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
