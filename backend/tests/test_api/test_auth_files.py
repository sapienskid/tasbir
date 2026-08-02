"""Auth (fail-closed) + serve-and-delete endpoint tests."""

import uuid
from pathlib import Path

from httpx import AsyncClient

from app.config import get_settings
from tests.test_api.conftest import seed_task


async def _write_output(task_id: str, fmt: str = "instagram-square") -> None:
    out_dir = Path(get_settings().output_dir) / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{fmt}.png").write_bytes(b"PNGDATA")
    (out_dir / f"{fmt}.html").write_text("<!doctype html><html><body>x</body></html>")


class TestAuth:
    async def test_missing_key_rejected(self, authed_client: AsyncClient):
        res = await authed_client.get("/tasks")
        assert res.status_code == 401

    async def test_invalid_key_rejected(self, authed_client: AsyncClient):
        res = await authed_client.get("/tasks", headers={"x-api-key": "wrong"})
        assert res.status_code == 401

    async def test_valid_key_accepted(self, authed_client: AsyncClient):
        res = await authed_client.get("/tasks", headers={"x-api-key": "test-key"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    async def test_health_stays_public(self, authed_client: AsyncClient):
        res = await authed_client.get("/health")
        assert res.status_code == 200


class TestServeAndDelete:
    async def test_files_list_and_one_time_download(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        headers = {"x-api-key": "test-key"}

        res = await authed_client.get(f"/tasks/{task_id}/files", headers=headers)
        assert res.status_code == 200
        names = [f["filename"] for f in res.json()]
        assert "instagram-square.png" in names

        res = await authed_client.get(
            f"/tasks/{task_id}/files/instagram-square.png", headers=headers
        )
        assert res.status_code == 200
        assert res.content == b"PNGDATA"

        # Second download → 404 (file deleted after delivery)
        res = await authed_client.get(
            f"/tasks/{task_id}/files/instagram-square.png", headers=headers
        )
        assert res.status_code == 404

    async def test_download_rejects_traversal(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        res = await authed_client.get(
            f"/tasks/{task_id}/files/../../etc/passwd", headers={"x-api-key": "test-key"}
        )
        assert res.status_code == 404

    async def test_delete_task_removes_files(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        out_dir = Path(get_settings().output_dir) / task_id
        assert out_dir.exists()

        res = await authed_client.delete(f"/tasks/{task_id}", headers={"x-api-key": "test-key"})
        assert res.status_code == 204
        assert not out_dir.exists()

        res = await authed_client.get(f"/tasks/{task_id}", headers={"x-api-key": "test-key"})
        assert res.status_code == 404
