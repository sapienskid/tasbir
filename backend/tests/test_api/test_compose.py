"""Manual Compose API + task tests — validation, batches, re-compose, no-LLM guard."""

import base64

import pytest
from httpx import AsyncClient

from tests.test_api.conftest import seed_task

H = {"x-api-key": "test-key"}
_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode("ascii")
_ILLUSTRATION = {"kind": "illustration", "style": "procedural", "seed": "x"}
_UPLOAD = {"kind": "upload", "data": _PNG, "mime": "image/png"}


def _slide(template_id: str = "square-quote-card", **kw) -> dict:
    return {
        "template_id": template_id,
        "copy": {
            "kicker": "NOTE",
            "headline": kw.get("headline", "Less, but better"),
            "subhead": "Dieter Rams",
            "body": "",
            "tagline": "",
            "extra": {"price": "", "cta": "", "date": "", "location": "", "stat": "", "source": ""},
        },
        "hidden": None,
        "media_position": "auto",
        "media": kw.get("media", {"kind": "none"}),
    }


def _batch(posts: list[dict], **kw) -> dict:
    return {
        "design_system_id": kw.get("design_system_id", "default"),
        "style_language": kw.get("style_language", ""),
        "ground": "white",
        "title": "Quotes",
        "posts": posts,
    }


@pytest.fixture
def enqueued(monkeypatch):
    """Stub compose_task.delay — record the task ids instead of queueing."""
    from app.tasks.compose import compose_task

    calls: list[str] = []
    monkeypatch.setattr(compose_task, "delay", lambda task_id: calls.append(task_id))
    return calls


@pytest.fixture
def _no_render(monkeypatch):
    from app.services import dom_extractor

    async def fake_png(html, width, height):
        return b"PNGRENDERED"

    async def no_issues(html, width, height):
        return []

    monkeypatch.setattr(dom_extractor, "render_to_png", fake_png)
    monkeypatch.setattr(dom_extractor, "detect_overflow", no_issues)
    monkeypatch.setattr(dom_extractor, "detect_low_contrast", no_issues)


class TestValidation:
    async def test_unknown_template(self, authed_client: AsyncClient, enqueued):
        body = _batch([{"platform": "instagram-square", "slides": [_slide("nope")]}])
        r = await authed_client.post("/api/compose", headers=H, json=body)
        assert r.status_code == 422
        assert "unknown template" in r.json()["detail"]
        assert enqueued == []

    async def test_family_mismatch(self, authed_client: AsyncClient, enqueued):
        body = _batch([{"platform": "instagram-portrait", "slides": [_slide()]}])
        r = await authed_client.post("/api/compose", headers=H, json=body)
        assert r.status_code == 422
        assert "portrait" in r.json()["detail"]

    @pytest.mark.parametrize("n", [1, 11])
    async def test_carousel_slide_counts(self, authed_client: AsyncClient, enqueued, n):
        body = _batch([{"platform": "instagram-carousel", "slides": [_slide()] * n}])
        r = await authed_client.post("/api/compose", headers=H, json=body)
        assert r.status_code == 422

    async def test_single_post_takes_one_slide(self, authed_client: AsyncClient, enqueued):
        body = _batch([{"platform": "instagram-square", "slides": [_slide(), _slide()]}])
        r = await authed_client.post("/api/compose", headers=H, json=body)
        assert r.status_code == 422
        assert "exactly 1 slide" in r.json()["detail"]

    async def test_too_many_posts(self, authed_client: AsyncClient, enqueued):
        post = {"platform": "instagram-square", "slides": [_slide()]}
        r = await authed_client.post("/api/compose", headers=H, json=_batch([post] * 21))
        assert r.status_code == 422

    async def test_unknown_design_system_and_language(self, authed_client: AsyncClient, enqueued):
        post = {"platform": "instagram-square", "slides": [_slide()]}
        r = await authed_client.post(
            "/api/compose", headers=H, json=_batch([post], design_system_id="nope")
        )
        assert r.status_code == 422
        r = await authed_client.post(
            "/api/compose", headers=H, json=_batch([post], style_language="nope")
        )
        assert r.status_code == 422

    async def test_bad_upload_and_illustration_style(self, authed_client: AsyncClient, enqueued):
        bad_upload = {"kind": "upload", "data": base64.b64encode(b"not an image").decode()}
        post = {"platform": "instagram-square", "slides": [_slide(media=bad_upload)]}
        r = await authed_client.post("/api/compose", headers=H, json=_batch([post]))
        assert r.status_code == 422
        bad_style = {"kind": "illustration", "style": "crayon", "seed": "x"}
        post = {"platform": "instagram-square", "slides": [_slide(media=bad_style)]}
        r = await authed_client.post("/api/compose", headers=H, json=_batch([post]))
        assert r.status_code == 422


class TestBatch:
    async def test_batch_creates_tasks_sharing_batch_id(
        self, authed_client: AsyncClient, enqueued
    ):
        posts = [
            {"platform": "instagram-square", "slides": [_slide(headline="One")]},
            {"platform": "instagram-square", "slides": [_slide(headline="Two")]},
            {
                "platform": "instagram-carousel",
                "slides": [_slide("square-slide"), _slide("square-editorial-stack")],
            },
        ]
        r = await authed_client.post("/api/compose", headers=H, json=_batch(posts))
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["task_ids"]) == 3
        assert enqueued == data["task_ids"]

        task = (await authed_client.get(f"/api/tasks/{data['task_ids'][2]}", headers=H)).json()
        assert task["status"] == "pending"
        src = task["source_data"]
        assert src["mode"] == "manual" and src["batch_id"] == data["batch_id"]
        assert src["platforms"] == ["instagram-carousel"]
        assert task["composition"]["post"]["slides"][1]["template_id"] == "square-editorial-stack"

        batch = await authed_client.get(f"/api/compose/batches/{data['batch_id']}", headers=H)
        assert batch.status_code == 200
        tasks = batch.json()["tasks"]
        assert [t["task_id"] for t in tasks] == data["task_ids"]
        assert tasks[2]["platform"] == "instagram-carousel"
        assert tasks[0]["composition"]["post"]["slides"][0]["copy"]["headline"] == "One"

    async def test_unknown_batch_404(self, authed_client: AsyncClient):
        r = await authed_client.get("/api/compose/batches/nope", headers=H)
        assert r.status_code == 404


class TestComposition:
    async def test_put_composition_reenqueues(self, authed_client: AsyncClient, enqueued):
        post = {"platform": "instagram-square", "slides": [_slide()]}
        created = (await authed_client.post("/api/compose", headers=H, json=_batch([post]))).json()
        task_id = created["task_ids"][0]

        # Pending tasks can't be re-composed yet.
        body = {"design_system_id": "default", "style_language": "", "ground": "black"}
        body["post"] = post
        r = await authed_client.put(f"/api/tasks/{task_id}/composition", headers=H, json=body)
        assert r.status_code == 409

        from app.db.repositories.tasks import TaskRepository
        from app.db.session import get_shared_session_factory

        pool = await get_shared_session_factory()
        async with pool() as s:
            repo = TaskRepository(s)
            await repo.update_status(task_id, "completed")
            await repo.save_edited_html(task_id, {"instagram-square": "<html>old</html>"})

        new_post = {"platform": "instagram-square", "slides": [_slide("square-pull-quote")]}
        body["post"] = new_post
        r = await authed_client.put(f"/api/tasks/{task_id}/composition", headers=H, json=body)
        assert r.status_code == 200, r.text
        assert r.json() == {"task_id": task_id, "status": "pending"}
        assert enqueued[-1] == task_id

        task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
        assert task["status"] == "pending"
        assert task["edited_html"] is None
        assert task["composition"]["ground"] == "black"
        assert task["source_data"]["ground"] == "black"
        assert task["composition"]["post"]["slides"][0]["template_id"] == "square-pull-quote"

    async def test_put_composition_rejects_ai_task(self, authed_client: AsyncClient, enqueued):
        await seed_task("ai-task-compose")
        body = {
            "design_system_id": "default",
            "style_language": "",
            "ground": "white",
            "post": {"platform": "instagram-square", "slides": [_slide()]},
        }
        r = await authed_client.put("/api/tasks/ai-task-compose/composition", headers=H, json=body)
        assert r.status_code == 422

    async def test_retry_manual_task_reruns_compose(
        self, authed_client: AsyncClient, enqueued, monkeypatch
    ):
        from app.tasks.generate import generate_task

        ai_calls = []
        monkeypatch.setattr(generate_task, "delay", lambda *a, **k: ai_calls.append(a))
        await seed_task("manual-retry", status="failed", source_data={"mode": "manual"})
        r = await authed_client.post("/api/tasks/manual-retry/retry", headers=H)
        assert r.status_code == 200
        assert enqueued == ["manual-retry"] and ai_calls == []
        # Per-format "retry designer" is an AI step — refused for manual posts.
        await seed_task("manual-retry-fmt", status="completed", source_data={"mode": "manual"})
        r = await authed_client.post(
            "/api/tasks/manual-retry-fmt/formats/instagram-square/retry", headers=H
        )
        assert r.status_code == 422


class TestPreviewAndHelpers:
    async def test_preview_returns_finalized_html(self, authed_client: AsyncClient):
        body = {
            "design_system_id": "default",
            "style_language": "",
            "ground": "black",
            "platform": "instagram-carousel",
            "slide_index": 2,
            "slide_total": 3,
            "slide": _slide("square-slide", media=_ILLUSTRATION),
        }
        r = await authed_client.post("/api/compose/preview", headers=H, json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["width"] == 1080 and data["height"] == 1080
        html = data["html"]
        assert ":root {" in html and "--color-bg" in html
        assert "fonts.googleapis.com/css2" in html
        assert "Less, but better" in html and "<svg" in html
        assert 'data-ground="black"' in html

    async def test_preview_unknown_template_422(self, authed_client: AsyncClient):
        body = {
            "platform": "instagram-square",
            "slide": _slide("nope"),
        }
        r = await authed_client.post("/api/compose/preview", headers=H, json=body)
        assert r.status_code == 422

    async def test_illustration_endpoint(self, authed_client: AsyncClient):
        r = await authed_client.get(
            "/api/compose/illustration", headers=H, params={"style": "procedural", "seed": "a"}
        )
        assert r.status_code == 200 and "<svg" in r.json()["svg"]
        r = await authed_client.get(
            "/api/compose/illustration", headers=H, params={"style": "crayon", "seed": "a"}
        )
        assert r.status_code == 422

    async def test_photos_without_keys_is_empty(self, authed_client: AsyncClient, monkeypatch):
        from app.services.tools import photo

        async def no_results(*a, **k):
            return []

        monkeypatch.setattr(photo, "search_photo_candidates", no_results)
        r = await authed_client.get("/api/compose/photos", headers=H, params={"q": "fog"})
        assert r.status_code == 200 and r.json() == {"results": []}

    async def test_template_map(self, authed_client: AsyncClient):
        body = {
            "from_design_system_id": "default",
            "to_design_system_id": "default",
            "template_ids": ["square-quote-card"],
            "platform": "instagram-square",
        }
        r = await authed_client.post("/api/compose/templates/map", headers=H, json=body)
        assert r.status_code == 200
        assert r.json()["mapping"] == {"square-quote-card": "square-quote-card"}

        created = await authed_client.post(
            "/api/design-systems", headers=H, json={"name": "Map Target"}
        )
        target = created.json()["id"]
        body["to_design_system_id"] = target
        r = await authed_client.post("/api/compose/templates/map", headers=H, json=body)
        assert r.status_code == 200
        mapping = r.json()["mapping"]
        if mapping:  # a fresh system may have no square templates yet
            tpls = (
                await authed_client.get(
                    "/api/templates", headers=H, params={"design_system_id": target}
                )
            ).json()
            squares = {t["id"] for t in tpls if t["family"] == "square"}
            assert mapping["square-quote-card"] in squares

    async def test_template_list_exposes_fields_and_media(self, authed_client: AsyncClient):
        tpls = (await authed_client.get("/api/templates", headers=H)).json()
        by_id = {t["id"]: t for t in tpls}
        assert by_id["square-split-media"]["has_media"] is True
        assert "image" in by_id["square-split-media"]["media_kinds"]
        assert "headline" in by_id["square-quote-card"]["fields"]
        assert by_id["square-quote-card"]["has_media"] is False


class TestComposeTask:
    async def test_compose_task_never_calls_an_llm(
        self, authed_client: AsyncClient, enqueued, _no_render, monkeypatch, tmp_path
    ):
        import app.services.llm as llm
        import app.services.vision as vision

        def boom(*a, **k):
            raise AssertionError("Manual compose must never call an LLM")

        for name in ("call_llm", "call_llm_for_tool", "call_llm_tool_loop"):
            monkeypatch.setattr(llm, name, boom)
        monkeypatch.setattr(vision, "call_vision_llm", boom)

        from app.services import composer
        from app.services.tools import photo

        composer._PHOTO_CACHE.clear()

        async def fake_download(candidate):
            return {"data": _PNG, "mime": "image/png", "alt": ""}

        monkeypatch.setattr(photo, "download_photo", fake_download)

        posts = [
            {
                "platform": "instagram-carousel",
                "slides": [
                    _slide("square-slide", media=_ILLUSTRATION),
                    _slide("square-split-media", media=_UPLOAD),
                    _slide(
                        "square-split-media",
                        media={
                            "kind": "photo",
                            "url": "https://images.example.com/p.jpg",
                            "credit": "Photo by X on Pexels",
                            "provider": "pexels",
                            "photographer": "X",
                            "license": "Pexels License",
                        },
                    ),
                ],
            }
        ]
        created = (
            await authed_client.post("/api/compose", headers=H, json=_batch(posts))
        ).json()
        task_id = created["task_ids"][0]

        from app.tasks.compose import run_compose

        await run_compose(task_id)

        task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
        assert task["status"] == "completed", task["error"]
        platforms = task["result"]["platforms"]
        assert set(platforms) == {f"instagram-carousel-{i}" for i in (1, 2, 3)}
        for fmt, p in platforms.items():
            assert p["html_path"].endswith(f"{fmt}.html")
            assert p["status"] in ("verified", "needs_review")
            assert "headline" in p["copy"]
        assert platforms["instagram-carousel-1"]["template_id"] == "square-slide"
        assert task["result"]["media_credits"][0]["credit"] == "Photo by X on Pexels"

        files = (await authed_client.get(f"/api/tasks/{task_id}/files", headers=H)).json()
        names = {f["filename"] for f in files}
        assert "instagram-carousel-3.png" in names and "instagram-carousel-1.html" in names
        html = (tmp_path / task_id / "instagram-carousel-2.html").read_text()
        assert f"data:image/png;base64,{_PNG}" in html and "2/3" in html

        progress = (await authed_client.get(f"/api/tasks/{task_id}/progress", headers=H)).json()
        assert progress["pct"] == 100 and progress["total"] == 3

        # Re-compose with fewer slides replaces every artifact (no stale files).
        post = {
            "platform": "instagram-carousel",
            "slides": [_slide("square-slide"), _slide("square-editorial-stack")],
        }
        body = {"design_system_id": "default", "style_language": "", "ground": "white"}
        body["post"] = post
        r = await authed_client.put(f"/api/tasks/{task_id}/composition", headers=H, json=body)
        assert r.status_code == 200
        await run_compose(task_id)
        files = (await authed_client.get(f"/api/tasks/{task_id}/files", headers=H)).json()
        assert {f["format"] for f in files} == {"instagram-carousel-1", "instagram-carousel-2"}

    async def test_ai_generate_task_unaffected(
        self, authed_client: AsyncClient, enqueued, monkeypatch
    ):
        from app.tasks.generate import generate_task

        ai_calls = []
        monkeypatch.setattr(generate_task, "delay", lambda *a, **k: ai_calls.append(a))
        r = await authed_client.post(
            "/api/generate", headers=H, json={"content": "Hello world", "title": "T"}
        )
        assert r.status_code in (200, 201, 202), r.text
        assert len(ai_calls) == 1 and enqueued == []
