"""Shared fixtures for tests."""

import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import async_sessionmaker


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _shared_db():
    """Bootstrap the shared SQLite engine (schema + seed) once per session.

    Tests in test_agents/ hit the pipeline through ``get_shared_session_factory()``
    directly. Locally that silently reused the dev ``data/tasbir.db``; in CI no
    such file exists and the tables are only created by the app lifespan. Point
    the shared engine at a session-scoped temp DB, create the schema, and seed
    the default design system + agents + platforms + fonts + settings.
    """
    from app.config import get_settings
    from app.db.session import close_shared_engine, get_shared_session_factory
    from app.models import Base

    tmpdir = tempfile.mkdtemp(prefix="tasbir-test-")
    db_path = Path(tmpdir) / "shared.db"
    settings = get_settings()
    settings.database_url = f"sqlite+aiosqlite:///{db_path}"
    # Point the rate limiter at a dead Redis port so it FAILS OPEN (its designed
    # behavior when Redis is unavailable). A locally running dev Redis would
    # otherwise share the per-key token bucket and 429 the whole suite. The
    # explicit rate-limit test mocks Redis itself, so it still exercises the
    # 429 path.
    settings.redis_url = "redis://127.0.0.1:1/0"
    await close_shared_engine()

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    from app.services.agents import seed_agents
    from app.services.seeding import seed_default_design_system, seed_fonts, seed_platforms
    from app.services.settings import seed_app_settings

    pool = await get_shared_session_factory()
    await seed_default_design_system(pool)
    await seed_agents(pool)
    await seed_platforms(pool)
    await seed_fonts(pool)
    await seed_app_settings(pool)

    yield

    await close_shared_engine()


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
