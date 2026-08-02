"""Auth (fail-closed) + serve-and-delete endpoint tests."""

import io
import uuid
import zipfile
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
        res = await authed_client.get("/api/tasks")
        assert res.status_code == 401

    async def test_invalid_key_rejected(self, authed_client: AsyncClient):
        res = await authed_client.get("/api/tasks", headers={"x-api-key": "wrong"})
        assert res.status_code == 401

    async def test_valid_key_accepted(self, authed_client: AsyncClient):
        res = await authed_client.get("/api/tasks", headers={"x-api-key": "test-key"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    async def test_health_stays_public(self, authed_client: AsyncClient):
        res = await authed_client.get("/health")
        assert res.status_code == 200


class TestServeAndDelete:
    async def test_files_persist_by_default(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        headers = {"x-api-key": "test-key"}

        res = await authed_client.get(f"/api/tasks/{task_id}/files", headers=headers)
        assert res.status_code == 200
        names = [f["filename"] for f in res.json()]
        assert "instagram-square.png" in names

        # Default: files persist — a second download still succeeds.
        first = await authed_client.get(
            f"/api/tasks/{task_id}/files/instagram-square.png", headers=headers
        )
        assert first.status_code == 200
        assert first.content == b"PNGDATA"
        second = await authed_client.get(
            f"/api/tasks/{task_id}/files/instagram-square.png", headers=headers
        )
        assert second.status_code == 200
        assert second.content == b"PNGDATA"

    async def test_consume_deletes_after_download(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        headers = {"x-api-key": "test-key"}

        res = await authed_client.get(
            f"/api/tasks/{task_id}/files/instagram-square.png?consume=true", headers=headers
        )
        assert res.status_code == 200
        assert res.content == b"PNGDATA"

        # Consumed → gone.
        res = await authed_client.get(
            f"/api/tasks/{task_id}/files/instagram-square.png", headers=headers
        )
        assert res.status_code == 404

    async def test_download_rejects_traversal(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        res = await authed_client.get(
            f"/api/tasks/{task_id}/files/../../etc/passwd", headers={"x-api-key": "test-key"}
        )
        assert res.status_code == 404

    async def test_delete_task_removes_files(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        out_dir = Path(get_settings().output_dir) / task_id
        assert out_dir.exists()

        res = await authed_client.delete(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
        assert res.status_code == 204
        assert not out_dir.exists()

        res = await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
        assert res.status_code == 404


class TestArchive:
    async def test_archive_zips_all_files(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        await _write_output(task_id)
        await _write_output(task_id, fmt="linkedin-post")
        headers = {"x-api-key": "test-key"}

        res = await authed_client.get(f"/api/tasks/{task_id}/files/archive", headers=headers)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/zip")
        assert f'filename="{task_id}.zip"' in res.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = sorted(zf.namelist())
            assert names == sorted(
                ["instagram-square.html", "instagram-square.png",
                 "linkedin-post.html", "linkedin-post.png"]
            )
            assert zf.read("instagram-square.png") == b"PNGDATA"

    async def test_archive_missing_task_404(self, authed_client: AsyncClient):
        res = await authed_client.get(
            f"/api/tasks/{uuid.uuid4()}/files/archive", headers={"x-api-key": "test-key"}
        )
        assert res.status_code == 404

    async def test_archive_empty_task_404(self, authed_client: AsyncClient):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)
        res = await authed_client.get(
            f"/api/tasks/{task_id}/files/archive", headers={"x-api-key": "test-key"}
        )
        assert res.status_code == 404
