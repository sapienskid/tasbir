"""Instant preview + editor state + hardened refill (ADR-0023)."""
# ruff: noqa: E501, F811

import asyncio
import json
import os
import uuid

from httpx import AsyncClient

from tests.test_api.conftest import seed_task
from tests.test_api.test_refill import (
    H,
    _mock_services,  # noqa: F401  (fixture)
    _seed_media_task,
    _seed_template_task,
)

_TPL_WITH_BODY = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:{{ width }}px;height:{{ height }}px;overflow:hidden;margin:0}"
    "</style></head><body>"
    '<h1 data-slot="headline">{{ headline }}</h1>'
    "{% if subhead %}"
    '<p data-slot="subhead">{{ subhead }}</p>'
    "{% endif %}"
    "{% if body %}"
    '<p data-slot="body">{{ body }}</p>'
    "{% endif %}"
    "</body></html>"
)


def _url(task_id, suffix, fmt="instagram-square"):
    return f"/api/tasks/{task_id}/formats/{fmt}/{suffix}"


class TestPreview:
    async def test_preview_matches_persisted_output(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        body = {"slots": {"headline": "Same both ways"}, "hidden": ["subhead"]}
        p = await authed_client.post(_url(task_id, "refill/preview"), headers=H, json=body)
        assert p.status_code == 200, p.text
        r = await authed_client.post(_url(task_id, "refill"), headers=H, json=body)
        assert r.status_code == 200, r.text
        assert p.json()["html"] == r.json()["html"]
        assert (tmp_path / task_id / "instagram-square.html").read_text() == r.json()["html"]
        assert p.json()["slots"]["headline"] == "Same both ways"
        assert p.json()["width"] == 1080 and p.json()["converted"] is False

    async def test_preview_does_not_render_or_write(
        self, authed_client: AsyncClient, tmp_path, monkeypatch, _mock_services
    ):
        from app.services import dom_extractor

        calls = []

        async def png_spy(*a, **k):
            calls.append(a)
            return b"PNG"

        async def overflow_spy(*a, **k):
            calls.append(a)
            return []

        monkeypatch.setattr(dom_extractor, "render_to_png", png_spy)
        monkeypatch.setattr(dom_extractor, "detect_overflow", overflow_spy)
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        before = (tmp_path / task_id / "instagram-square.html").read_text()
        calls.clear()  # seeding the template validated it through the renderer
        r = await authed_client.post(
            _url(task_id, "refill/preview"), headers=H, json={"slots": {"headline": "Draft"}}
        )
        assert r.status_code == 200
        assert not calls
        assert (tmp_path / task_id / "instagram-square.html").read_text() == before
        assert not (tmp_path / task_id / "instagram-square.png").exists()
        task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
        assert not task["edited_html"]
        assert "editor" not in task["result"]["platforms"]["instagram-square"]

    async def test_status_code_parity(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        running = str(uuid.uuid4())
        await seed_task(running, status="running")
        missing = str(uuid.uuid4())
        cases = [
            (missing, {"slots": {"headline": "x"}}, 404),
            (running, {"slots": {"headline": "x"}}, 409),
            (task_id, {"slots": {"nope": "x"}}, 422),
            (task_id, {}, 422),
            (task_id, {"hidden": ["nope"]}, 422),
            (task_id, {"template_id": "does-not-exist", "slots": {"headline": "x"}}, 422),
            (task_id, {"media_position": "diagonal"}, 422),
        ]
        for tid, body, code in cases:
            for suffix in ("refill/preview", "refill"):
                r = await authed_client.post(_url(tid, suffix), headers=H, json=body)
                assert r.status_code == code, (suffix, body, r.status_code, r.text)
                assert r.json()["detail"]

    async def test_bad_media_is_422(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_media_task(authed_client, tmp_path)
        for media in (
            {"kind": "upload", "data": "not base64!!"},
            {"kind": "upload", "data": "QUJD"},  # decodes but is not an image
            {"kind": "photo", "url": "http://insecure.example/a.png"},
            {"kind": "illustration", "style": "nonexistent"},
            {"kind": "video"},
        ):
            r = await authed_client.post(
                _url(task_id, "refill/preview"), headers=H, json={"media": media}
            )
            assert r.status_code == 422, (media, r.text)

    async def test_photo_download_failure_is_422(
        self, authed_client: AsyncClient, tmp_path, monkeypatch, _mock_services
    ):
        from app.services import composer

        async def boom(media):
            raise RuntimeError("provider down")

        monkeypatch.setattr(composer, "fetch_photo", boom)
        task_id, _ = await _seed_media_task(authed_client, tmp_path)
        r = await authed_client.post(
            _url(task_id, "refill/preview"),
            headers=H,
            json={"media": {"kind": "photo", "url": "https://example.com/a.png"}},
        )
        assert r.status_code == 422
        assert "could not be downloaded" in r.json()["detail"]

    async def test_deleted_template_still_allows_text_edit(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, tid = await _seed_template_task(authed_client, tmp_path)
        assert (await authed_client.delete(f"/api/templates/{tid}", headers=H)).status_code == 204
        r = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"slots": {"headline": "Still works"}}
        )
        assert r.status_code == 200, r.text
        r2 = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"hidden": []}
        )
        assert r2.status_code == 422 and "not found" in r2.json()["detail"]
        ed = (await authed_client.get(_url(task_id, "editor"), headers=H)).json()
        assert ed["editable"] is False and ed["reason"] == "template_missing"

    async def test_format_not_in_task_and_missing_platforms(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        tid = str(uuid.uuid4())
        await seed_task(tid, result=None)
        r = await authed_client.post(
            _url(tid, "refill/preview"), headers=H, json={"slots": {"headline": "x"}}
        )
        assert r.status_code == 404
        r = await authed_client.get(_url(tid, "editor"), headers=H)
        assert r.status_code == 404


class TestEditorState:
    async def test_before_and_after_refill(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, tid = await _seed_media_task(authed_client, tmp_path)
        before = (await authed_client.get(_url(task_id, "editor"), headers=H)).json()
        assert before["editable"] is True and before["reason"] is None
        assert before["template_id"] == tid
        assert before["hidden"] is None and before["revision"] == 0
        assert before["media_position"] == "auto" and before["media"]["kind"] == "none"
        assert set(before["media_kinds"]) == {"image", "illustration"}
        assert before["family"] == "square" and before["width"] == 1080

        r = await authed_client.post(
            _url(task_id, "refill"),
            headers=H,
            json={
                "slots": {"headline": "Fig"},
                "hidden": [],
                "media_position": "left",
                "media": {"kind": "illustration", "style": "procedural", "seed": "s1"},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["revision"] == 1 and body["saved_at"] and body["converted"] is False
        assert "Fig" in body["html"] and "<svg" in body["html"]
        assert body["editor"]["media"] == {"kind": "illustration", "style": "procedural", "seed": "s1"}

        after = (await authed_client.get(_url(task_id, "editor"), headers=H)).json()
        assert after["hidden"] == [] and after["media_position"] == "left"
        assert after["media"]["kind"] == "illustration" and after["revision"] == 1
        assert after["slots"]["headline"] == "Fig"
        assert "base64" not in json.dumps(after)

        # A text-only edit keeps the persisted state and bumps the revision.
        r2 = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"slots": {"headline": "Fig 2"}}
        )
        assert r2.json()["revision"] == 2
        state = (await authed_client.get(_url(task_id, "editor"), headers=H)).json()
        assert state["media_position"] == "left" and state["media"]["kind"] == "illustration"
        # A later toggle refill keeps the same figure (seed persisted).
        r3 = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"hidden": []}
        )
        assert r3.status_code == 200 and "<svg" in r3.json()["html"]

    async def test_running_and_manual_reasons(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        running = str(uuid.uuid4())
        await seed_task(running, status="running")
        assert (await authed_client.get(_url(running, "editor"), headers=H)).json()["reason"] == "running"
        manual = str(uuid.uuid4())
        await seed_task(manual, source_data={"title": "m", "mode": "manual"})
        d = (await authed_client.get(_url(manual, "editor"), headers=H)).json()
        assert d["editable"] is False and d["convertible"] is False and d["reason"] == "manual"


class TestConversion:
    async def _designer_task(self, tmp_path):
        task_id = str(uuid.uuid4())
        await seed_task(
            task_id,
            result={
                "strategic_brief": {"category": "WRITING", "ground": "white"},
                "platforms": {
                    "instagram-square": {
                        "status": "verified", "quality_score": 70, "quality_issues": [],
                        "html_path": "",
                        "copy": json.dumps({"headline": "Designer head", "subhead": "Designer sub"}),
                    }
                },
            },
        )
        out = tmp_path / task_id
        out.mkdir(parents=True)
        (out / "instagram-square.html").write_text("<html><body><h1>Designer doc</h1></body></html>")
        return task_id

    async def test_convert_designer_post(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        _, tid = await _seed_template_task(authed_client, tmp_path)
        task_id = await self._designer_task(tmp_path)
        ed = (await authed_client.get(_url(task_id, "editor"), headers=H)).json()
        assert ed["editable"] is False and ed["convertible"] is True and ed["reason"] == "designer"

        p = await authed_client.post(
            _url(task_id, "refill/preview"), headers=H, json={"template_id": tid}
        )
        assert p.status_code == 200 and p.json()["converted"] is True
        assert p.json()["slots"]["headline"] == "Designer head"
        assert not (tmp_path / task_id / "instagram-square.designer.html").exists()

        r = await authed_client.post(_url(task_id, "refill"), headers=H, json={"template_id": tid})
        assert r.status_code == 200, r.text
        assert r.json()["converted"] is True and "Designer head" in r.json()["html"]
        assert "Designer doc" in (tmp_path / task_id / "instagram-square.designer.html").read_text()
        # The backup never surfaces as a phantom format.
        files = (await authed_client.get(f"/api/tasks/{task_id}/files", headers=H)).json()
        assert all(not f["format"].endswith(".designer") for f in files)
        after = (await authed_client.get(_url(task_id, "editor"), headers=H)).json()
        assert after["editable"] is True and after["template_id"] == tid
        # Second edit: normal template post, backup not overwritten.
        r2 = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"slots": {"headline": "Next"}}
        )
        assert r2.json()["converted"] is False
        assert "Designer doc" in (tmp_path / task_id / "instagram-square.designer.html").read_text()


class TestHardening:
    async def test_concurrent_refills_merge_all_edits(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        for _ in range(3):
            task_id, _tid = await _seed_template_task(authed_client, tmp_path)
            edits = [{"headline": "H-new"}, {"subhead": "S-new"}]
            rs = await asyncio.gather(
                *[
                    authed_client.post(_url(task_id, "refill"), headers=H, json={"slots": e})
                    for e in edits
                ]
            )
            assert [r.status_code for r in rs] == [200, 200], [r.text for r in rs]
            saved = (tmp_path / task_id / "instagram-square.html").read_text()
            assert "H-new" in saved and "S-new" in saved
            revs = sorted(r.json()["revision"] for r in rs)
            assert revs == [1, 2]
            task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
            assert "H-new" in task["edited_html"]["instagram-square"]
            assert "S-new" in task["edited_html"]["instagram-square"]

    async def test_lock_table_does_not_leak(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        from app.api import tasks as tasks_api

        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        await authed_client.post(_url(task_id, "refill"), headers=H, json={"slots": {"headline": "x"}})
        await authed_client.post(_url(uuid.uuid4().hex, "refill"), headers=H, json={"slots": {"a": "b"}})
        assert len(tasks_api._FORMAT_LOCKS) == 0 and len(tasks_api._TASK_LOCKS) == 0

    async def test_different_formats_of_one_task_do_not_clobber(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, tid = await _seed_template_task(authed_client, tmp_path)
        # second format on the same task
        from app.db.session import get_shared_session_factory
        from app.models.task import GenerationTask

        pool = await get_shared_session_factory()
        async with pool() as s:
            t = await s.get(GenerationTask, task_id)
            res = dict(t.result)
            plats = dict(res["platforms"])
            plats["linkedin-post"] = {**plats["instagram-square"]}
            res["platforms"] = plats
            t.result = res
            await s.commit()
        (tmp_path / task_id / "linkedin-post.html").write_text(
            (tmp_path / task_id / "instagram-square.html").read_text()
        )
        # family mismatch (square template on landscape) → use a landscape-free path:
        # only the square format is refilled; the other gets a rerender concurrently.
        r = await asyncio.gather(
            authed_client.post(_url(task_id, "refill"), headers=H, json={"slots": {"headline": "A1"}}),
            authed_client.post(
                _url(task_id, "rerender", "linkedin-post"), headers=H,
                json={"html": "<html><body><h1 data-slot='headline'>B1</h1></body></html>"},
            ),
        )
        assert [x.status_code for x in r] == [200, 200], [x.text for x in r]
        task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
        assert "A1" in task["edited_html"]["instagram-square"]
        assert "B1" in task["edited_html"]["linkedin-post"]

    async def test_atomic_write_failure_keeps_old_file(
        self, authed_client: AsyncClient, tmp_path, monkeypatch, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        html_file = tmp_path / task_id / "instagram-square.html"
        old = html_file.read_text()

        def boom(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", boom)
        r = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"slots": {"headline": "Lost?"}}
        )
        assert r.status_code == 500 and "output files" in r.json()["detail"]
        monkeypatch.undo()
        assert html_file.read_text() == old
        assert not list((tmp_path / task_id).glob("*.tmp"))
        task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
        assert not task["edited_html"]

    async def test_png_service_down_still_saves_html(
        self, authed_client: AsyncClient, tmp_path, monkeypatch, _mock_services
    ):
        from app.services import dom_extractor

        async def down(html, w, h):
            raise ConnectionError("render service down")

        monkeypatch.setattr(dom_extractor, "render_to_png", down)
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            _url(task_id, "refill"), headers=H, json={"slots": {"headline": "Kept anyway"}}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pass"] is False and body["png_b64"] == ""
        assert any("PNG render unavailable" in i for i in body["quality"]["issues"])
        assert "Kept anyway" in (tmp_path / task_id / "instagram-square.html").read_text()
        task = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
        assert "Kept anyway" in task["edited_html"]["instagram-square"]

    async def test_hidden_slot_text_survives_toggle(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        await authed_client.post(_url(task_id, "refill"), headers=H, json={"hidden": ["subhead"]})
        r = await authed_client.post(_url(task_id, "refill"), headers=H, json={"hidden": []})
        assert "Old subhead" in r.json()["html"]
