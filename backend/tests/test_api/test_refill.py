"""Refill endpoint tests — structured slot edits on template-built formats."""
# ruff: noqa: E501

import base64
import json
import uuid

import pytest
from httpx import AsyncClient

from tests.test_api.conftest import seed_task

H = {"x-api-key": "test-key"}

_TPL_HTML = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:1080px;height:1080px;overflow:hidden;margin:0}"
    "</style></head><body>"
    '<h1 data-slot="headline">{{ headline }}</h1>'
    "{% if subhead %}"
    '<p data-slot="subhead">{{ subhead }}</p>'
    "{% endif %}"
    "</body></html>"
)

_RENDERED_HTML = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:1080px;height:1080px;overflow:hidden;margin:0}"
    "</style></head><body>"
    '<h1 data-slot="headline">Old headline</h1>'
    '<p data-slot="subhead">Old subhead</p>'
    "</body></html>"
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


async def _seed_template_task(authed_client: AsyncClient, tmp_path, template_id: str = ""):
    """Create a template + a completed task built from it + its HTML file."""
    body = {
        "id": template_id or f"square-refill-{uuid.uuid4().hex[:8]}",
        "name": "Refill Test",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white"],
        "html": _TPL_HTML,
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    task_id = str(uuid.uuid4())
    copy = json.dumps({"headline": "Old headline", "subhead": "Old subhead", "body": ""})
    await seed_task(
        task_id,
        result={
            "strategic_brief": {"category": "WRITING", "ground": "white"},
            "platforms": {
                "instagram-square": {
                    "status": "verified",
                    "quality_score": 80,
                    "quality_issues": [],
                    "html_path": "",
                    "template_id": tid,
                    "copy": copy,
                }
            },
        },
    )
    out_dir = tmp_path / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "instagram-square.html").write_text(_RENDERED_HTML)
    return task_id, tid


_MEDIA_TPL_HTML = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:1080px;height:1080px;overflow:hidden;margin:0}"
    "</style></head><body>"
    '<h1 data-slot="headline">{{ headline }}</h1>'
    "{% if has_image %}"
    '<img data-image-key="0" alt="">'
    "{% endif %}"
    "{{ illustration }}"
    "</body></html>"
)

_MEDIA_RENDERED_HTML = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:1080px;height:1080px;overflow:hidden;margin:0}"
    "</style></head><body>"
    '<h1 data-slot="headline">Old headline</h1>'
    "</body></html>"
)


async def _seed_media_task(authed_client: AsyncClient, tmp_path):
    """Task built from a template with image + illustration slots."""
    body = {
        "id": f"square-media-{uuid.uuid4().hex[:8]}",
        "name": "Media Test",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white"],
        "html": _MEDIA_TPL_HTML,
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    task_id = str(uuid.uuid4())
    await seed_task(
        task_id,
        result={
            "strategic_brief": {"category": "WRITING", "ground": "white"},
            "platforms": {
                "instagram-square": {
                    "status": "verified",
                    "quality_score": 80,
                    "quality_issues": [],
                    "html_path": "",
                    "template_id": tid,
                    "copy": json.dumps({"headline": "Old headline"}),
                }
            },
        },
    )
    out_dir = tmp_path / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "instagram-square.html").write_text(_MEDIA_RENDERED_HTML)
    return task_id, tid


class TestRefillSlots:
    async def test_slots_only_updates_text(self, authed_client: AsyncClient, tmp_path, _mock_services):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "New headline"}},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["format"] == "instagram-square"
        assert data["pass"] is True
        assert data["png_b64"]

        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "New headline" in saved
        assert "Old subhead" in saved  # untouched slot preserved

        task = await authed_client.get(f"/api/tasks/{task_id}", headers=H)
        edited = task.json()["edited_html"]
        assert "New headline" in edited["instagram-square"]
        copy = json.loads(task.json()["result"]["platforms"]["instagram-square"]["copy"])
        assert copy["headline"] == "New headline"

    async def test_unknown_slot_rejected(self, authed_client: AsyncClient, tmp_path, _mock_services):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"nope": "x"}},
        )
        assert r.status_code == 422

    async def test_non_template_post_rejected(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id = str(uuid.uuid4())
        await seed_task(task_id)  # conftest default has no template_id
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "x"}},
        )
        assert r.status_code == 422

    async def test_unknown_task_404(self, authed_client: AsyncClient, _mock_services):
        r = await authed_client.post(
            f"/api/tasks/{uuid.uuid4()}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "x"}},
        )
        assert r.status_code == 404


class TestRefillFull:
    async def test_hidden_toggle_refills(self, authed_client: AsyncClient, tmp_path, _mock_services):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "Kept"}, "hidden": ["subhead"]},
        )
        assert r.status_code == 200, r.text
        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "Kept" in saved
        assert "Old subhead" not in saved

    async def test_unknown_hidden_rejected(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {}, "hidden": ["nope"]},
        )
        assert r.status_code == 422

    async def test_template_switch(self, authed_client: AsyncClient, tmp_path, _mock_services):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        _, tid2 = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "Switched"}, "template_id": tid2},
        )
        assert r.status_code == 200, r.text
        assert r.json()["template_id"] == tid2
        task = await authed_client.get(f"/api/tasks/{task_id}", headers=H)
        assert task.json()["result"]["platforms"]["instagram-square"]["template_id"] == tid2


class TestRefillMedia:
    async def test_illustration_refill(self, authed_client: AsyncClient, tmp_path, _mock_services):
        task_id, _ = await _seed_media_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={
                "slots": {"headline": "With figure"},
                "media": {"kind": "illustration", "style": "procedural", "seed": "test-seed"},
            },
        )
        assert r.status_code == 200, r.text
        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "With figure" in saved
        assert "<svg" in saved

    async def test_upload_refill(self, authed_client: AsyncClient, tmp_path, _mock_services):
        task_id, _ = await _seed_media_task(authed_client, tmp_path)
        tiny = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={
                "slots": {"headline": "With photo"},
                "media": {"kind": "upload", "data": tiny, "mime": "image/png", "alt": "test"},
            },
        )
        assert r.status_code == 200, r.text
        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "With photo" in saved
        assert "data:image/png;base64," in saved

    async def test_photo_refill(self, authed_client: AsyncClient, tmp_path, _mock_services, monkeypatch):
        from app.services import composer

        async def fake_fetch(media):
            return {"data": base64.b64encode(b"fakepng").decode(), "mime": "image/png", "alt": ""}

        monkeypatch.setattr(composer, "fetch_photo", fake_fetch)
        task_id, _ = await _seed_media_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={
                "slots": {"headline": "With stock"},
                "media": {"kind": "photo", "url": "https://example.com/a.png", "credit": "c"},
            },
        )
        assert r.status_code == 200, r.text
        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "data:image/png;base64," in saved

    async def test_media_on_text_only_template_rejected(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"media": {"kind": "illustration", "style": "procedural", "seed": "x"}},
        )
        assert r.status_code == 422


_NEWDS_TPL_HTML = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:1080px;height:1080px;overflow:hidden;margin:0}"
    "</style></head><body>"
    "<div>NEWDS-MARKER</div>"
    '<h1 data-slot="headline">{{ headline }}</h1>'
    "</body></html>"
)


async def _make_ds_with_template(authed_client: AsyncClient, name: str = "Switch Test"):
    r = await authed_client.post("/api/design-systems", headers=H, json={"name": name})
    assert r.status_code == 200, r.text
    ds_id = r.json()["id"]
    r = await authed_client.post(
        "/api/templates",
        headers=H,
        json={
            "id": f"square-switch-{uuid.uuid4().hex[:8]}",
            "name": "Switch Template",
            "design_system_id": ds_id,
            "family": "square",
            "grounds": ["white"],
            "html": _NEWDS_TPL_HTML,
        },
    )
    assert r.status_code == 200, r.text
    return ds_id, r.json()["id"]


class TestRefillDesignSystem:
    async def test_switch_remaps_template(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, old_tid = await _seed_template_task(authed_client, tmp_path)
        ds_id, new_tid = await _make_ds_with_template(authed_client)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"design_system_id": ds_id},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["template_id"] != old_tid
        assert data["remapped"] == {"from": old_tid, "to": data["template_id"]}
        assert data["design_system_id"] == ds_id
        t = await authed_client.get(f"/api/templates/{data['template_id']}", headers=H)
        assert t.status_code == 200, t.text
        assert t.json()["design_system_id"] == ds_id
        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "Old headline" in saved  # copy carried over
        # Persisted per-format override surfaces on the editor document.
        g = await authed_client.get(
            f"/api/tasks/{task_id}/formats/instagram-square/editor", headers=H
        )
        assert g.status_code == 200, g.text
        assert g.json()["design_system_id"] == ds_id
        assert g.json()["template_id"] == data["template_id"]

    async def test_switch_with_explicit_template(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        ds_id, new_tid = await _make_ds_with_template(authed_client)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"design_system_id": ds_id, "template_id": new_tid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["template_id"] == new_tid
        assert r.json()["remapped"] is None

    async def test_unknown_design_system_rejected(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"design_system_id": "no-such-ds"},
        )
        assert r.status_code == 422

    async def test_foreign_template_rejected(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, old_tid = await _seed_template_task(authed_client, tmp_path)
        ds_id, _ = await _make_ds_with_template(authed_client)
        # old_tid belongs to "default", not the new system.
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"design_system_id": ds_id, "template_id": old_tid},
        )
        assert r.status_code == 422

    async def test_switch_without_family_template_rejected(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        task_id, _ = await _seed_template_task(authed_client, tmp_path)
        r = await authed_client.post("/api/design-systems", headers=H, json={"name": "Empty"})
        assert r.status_code == 200, r.text
        empty_ds = r.json()["id"]
        existing = await authed_client.get(
            f"/api/templates?design_system_id={empty_ds}&family=square", headers=H
        )
        for row in existing.json():
            d = await authed_client.delete(f"/api/templates/{row['id']}", headers=H)
            assert d.status_code == 204, d.text
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"design_system_id": empty_ds},
        )
        assert r.status_code == 422

    async def test_designer_post_converts_on_switch(
        self, authed_client: AsyncClient, tmp_path, _mock_services
    ):
        ds_id, new_tid = await _make_ds_with_template(authed_client)
        task_id = str(uuid.uuid4())
        copy = json.dumps({"headline": "Designer headline", "subhead": "", "body": ""})
        await seed_task(
            task_id,
            result={
                "strategic_brief": {"category": "WRITING", "ground": "white"},
                "platforms": {
                    "instagram-square": {
                        "status": "needs_review",
                        "quality_score": 40,
                        "quality_issues": [],
                        "html_path": "",
                        "copy": copy,
                    }
                },
            },
        )
        out_dir = tmp_path / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "instagram-square.html").write_text(
            _RENDERED_HTML.replace("Old headline", "Designer headline").replace(
                "<p data-slot=\"subhead\">Old subhead</p>", ""
            )
        )
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"design_system_id": ds_id},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["converted"] is True
        t = await authed_client.get(f"/api/templates/{data['template_id']}", headers=H)
        assert t.status_code == 200, t.text
        assert t.json()["design_system_id"] == ds_id
        saved = (tmp_path / task_id / "instagram-square.html").read_text()
        assert "Designer headline" in saved
