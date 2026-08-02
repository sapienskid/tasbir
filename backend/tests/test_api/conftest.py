"""Shared API test fixtures — authed client with lifespan + tmp output dir."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def authed_client(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.main import app

    settings = get_settings()
    settings.api_keys = "test-key"
    settings.output_dir = str(tmp_path)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client


async def seed_task(task_id: str, **kwargs) -> None:
    """Insert a GenerationTask row through the shared session factory."""
    from app.db.session import get_shared_session_factory
    from app.models.task import GenerationTask

    pool = await get_shared_session_factory()
    defaults = {
        "status": "completed",
        "source_data": {"title": "Test", "category": "WRITING"},
        "result": {
            "strategic_brief": {"category": "WRITING", "ground": "white"},
            "platforms": {
                "instagram-square": {
                    "status": "verified",
                    "quality_score": 80,
                    "quality_issues": [],
                    "html_path": "",
                }
            },
        },
    }
    defaults.update(kwargs)
    async with pool() as session:
        session.add(GenerationTask(id=task_id, **defaults))
        await session.commit()
