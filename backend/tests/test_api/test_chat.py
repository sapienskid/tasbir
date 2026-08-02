"""Agent chat endpoint tests — LLM + render are mocked, DB thread persists."""

import uuid

import pytest
from httpx import AsyncClient

from tests.test_api.conftest import seed_task

_HTML = (
    "<!doctype html><html><head><style>body{width:1080px;height:1080px}</style></head>"
    "<body>content</body></html>"
)


@pytest.fixture
def _mock_chat_llm(monkeypatch):
    """Return a canned assistant JSON reply without calling any model."""
    from app.services import chat as chat_mod

    async def fake_render(html, width, height):
        return b"PNGRENDERED"

    async def fake_overflow(html, width, height):
        return []

    async def fake_vision(system_prompt, user_prompt, image_bytes, temperature, max_tokens):
        return (
            '{"reply": "Done — headline tightened.", "changed": true, '
            '"html": "<!DOCTYPE html><html><head><style>body{width:1080px;'
            'height:1080px;overflow:hidden}</style></head><body>x</body></html>"}'
        )

    async def fake_text(agent_role, system_prompt, user_prompt, temperature, max_tokens):
        return '{"reply": "Sure.", "changed": false, "html": null}'

    monkeypatch.setattr(chat_mod, "render_to_png", fake_render)
    monkeypatch.setattr(chat_mod, "detect_overflow", fake_overflow)
    monkeypatch.setattr(chat_mod, "_run_deterministic_checks", lambda *a, **k: [])
    monkeypatch.setattr(chat_mod, "_call_vision_llm", fake_vision)
    monkeypatch.setattr(chat_mod, "call_llm", fake_text)


class TestChat:
    async def test_get_chat_creates_empty_thread(
        self, authed_client: AsyncClient, _mock_chat_llm
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        res = await authed_client.get(
            f"/api/tasks/{task_id}/chat?format=instagram-square",
            headers={"x-api-key": "test-key"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["thread_id"]
        assert data["format"] == "instagram-square"
        assert data["messages"] == []

    async def test_send_persists_thread_and_messages(
        self, authed_client: AsyncClient, _mock_chat_llm
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        headers = {"x-api-key": "test-key"}

        res = await authed_client.post(
            f"/api/tasks/{task_id}/chat",
            headers=headers,
            json={
                "format": "instagram-square",
                "message": "tighten the headline",
                "html": _HTML,
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "tighten" in data["reply"]
        assert data["html"] and data["html"].startswith("<!DOCTYPE html>")
        assert "qc" in data

        # The thread persists across requests.
        res = await authed_client.get(
            f"/api/tasks/{task_id}/chat?format=instagram-square", headers=headers
        )
        assert res.status_code == 200
        msgs = res.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "tighten the headline"
        assert msgs[1]["html"] and msgs[1]["html"].startswith("<!DOCTYPE html>")

    async def test_chat_unknown_task_404(
        self, authed_client: AsyncClient, _mock_chat_llm
    ):
        res = await authed_client.post(
            f"/api/tasks/{uuid.uuid4()}/chat",
            headers={"x-api-key": "test-key"},
            json={"format": "instagram-square", "message": "hi"},
        )
        assert res.status_code == 404

    async def test_chat_running_task_409(
        self, authed_client: AsyncClient, _mock_chat_llm
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id, status="running")
        res = await authed_client.post(
            f"/api/tasks/{task_id}/chat",
            headers={"x-api-key": "test-key"},
            json={"format": "instagram-square", "message": "hi"},
        )
        assert res.status_code == 409

    async def test_chat_persists_to_db_row(
        self, authed_client: AsyncClient, _mock_chat_llm
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        res = await authed_client.post(
            f"/api/tasks/{task_id}/chat",
            headers={"x-api-key": "test-key"},
            json={"format": "linkedin-post", "message": "make it calmer"},
        )
        assert res.status_code == 200
        thread_id = res.json()["thread_id"]

        from app.db.session import get_shared_session_factory
        from app.models.chat import ChatMessage

        pool = await get_shared_session_factory()
        async with pool() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ChatMessage).where(ChatMessage.thread_id == thread_id)
            )
            rows = list(result.scalars().all())
        assert len(rows) == 2
        assert {r.role for r in rows} == {"user", "assistant"}
