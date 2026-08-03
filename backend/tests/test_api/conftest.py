"""Shared API test fixtures — authed client with lifespan + tmp output dir."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def authed_client(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.db.session import close_shared_engine
    from app.main import app

    settings = get_settings()
    settings.api_keys = "test-key"
    settings.output_dir = str(tmp_path)
    # Isolate tests from the live dev DB: every test runs against its own
    # throwaway SQLite file so no row ever lands in data/tasbir.db.
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    assert str(tmp_path) in settings.database_url, "test DB must live in tmp_path"
    await close_shared_engine()

    # Never enqueue real jobs from tests — no worker side-effects, no LLM cost.
    from app.tasks.agent_jobs import (
        run_design_system_from_input,
        run_template_build_task,
        run_template_from_image,
    )
    from app.tasks.generate import generate_task

    monkeypatch.setattr(generate_task, "delay", lambda *a, **k: None)
    monkeypatch.setattr(run_template_from_image, "delay", lambda *a, **k: None)
    monkeypatch.setattr(run_design_system_from_input, "delay", lambda *a, **k: None)
    monkeypatch.setattr(run_template_build_task, "delay", lambda *a, **k: None)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    await close_shared_engine()


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
