"""Rerender endpoint tests — render/overflow/QC are mocked, real sanitizer runs."""

import uuid

import pytest
from httpx import AsyncClient

from tests.test_api.conftest import seed_task

_HTML = (
    "<!doctype html><html><head><style>body{width:1080px;height:1080px}</style></head>"
    "<body>content</body></html>"
)


@pytest.fixture
def _mock_services(monkeypatch):
    from app.agents.orchestrator.nodes import quality_check
    from app.services import dom_extractor

    async def fake_render(html, width, height):
        return b"PNGRENDERED"

    async def fake_overflow(html, width, height):
        return []

    monkeypatch.setattr(dom_extractor, "render_to_png", fake_render)
    monkeypatch.setattr(dom_extractor, "detect_overflow", fake_overflow)
    monkeypatch.setattr(quality_check, "_run_deterministic_checks", lambda *a, **k: [])


class TestRerender:
    async def test_rerender_returns_png_and_quality(
        self, authed_client: AsyncClient, _mock_services
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        res = await authed_client.post(
            f"/tasks/{task_id}/formats/instagram-square/rerender",
            headers={"x-api-key": "test-key"},
            json={"html": _HTML},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["format"] == "instagram-square"
        assert data["pass"] is True
        assert data["png_b64"]  # non-empty
        assert "score" in data["quality"]

    async def test_rerender_unknown_format_rejected(
        self, authed_client: AsyncClient, _mock_services
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        res = await authed_client.post(
            f"/tasks/{task_id}/formats/does-not-exist/rerender",
            headers={"x-api-key": "test-key"},
            json={"html": _HTML},
        )
        assert res.status_code == 422

    async def test_rerender_unknown_task_404(
        self, authed_client: AsyncClient, _mock_services
    ):
        res = await authed_client.post(
            f"/tasks/{str(uuid.uuid4())}/formats/instagram-square/rerender",
            headers={"x-api-key": "test-key"},
            json={"html": _HTML},
        )
        assert res.status_code == 404

    async def test_rerender_sanitizes_script(
        self, authed_client: AsyncClient, _mock_services, tmp_path
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        res = await authed_client.post(
            f"/tasks/{task_id}/formats/instagram-square/rerender",
            headers={"x-api-key": "test-key"},
            json={
                "html": (
                    "<!doctype html><html><body>"
                    "<script>alert(1)</script>"
                    "<style>body{width:1080px;height:1080px}</style>x</body></html>"
                )
            },
        )
        assert res.status_code == 200
        out_dir = tmp_path / task_id
        saved = (out_dir / "instagram-square.html").read_text()
        assert "script" not in saved
