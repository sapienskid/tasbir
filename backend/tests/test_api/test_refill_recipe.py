"""Refill: per-format recipe overrides (ground / language / category) and the
save-vs-render split.

These are the behaviours that let an AI-generated post carry its own ground and
design language (previously frozen in the task's strategic brief), and that stop
every autosave from paying for a headless render.
"""
# ruff: noqa: E501

import json
import uuid

from tests.test_api.conftest import read_entry, seed_task

H = {"x-api-key": "test-key"}

_GROUND_TPL = (
    "<!DOCTYPE html><html><head><style>"
    "body{width:1080px;height:1080px;overflow:hidden;margin:0;"
    "background:var(--color-bg)}"
    'body[data-ground="black"]{background:var(--color-bg-inverted)}'
    "</style></head><body {% if ground == \"black\" %}data-ground=\"black\"{% endif %}>"
    '<h1 data-slot="headline">{{ headline }}</h1>'
    "</body></html>"
)

_RENDERED = (
    "<!DOCTYPE html><html><body>"
    '<h1 data-slot="headline">Old</h1>'
    "</body></html>"
)


async def _seed(authed_client, tmp_path, *, grounds: list[str] | None = None):
    """A template (optionally ground-restricted) plus a task built from it."""
    tid = f"square-recipe-{uuid.uuid4().hex[:8]}"
    r = await authed_client.post(
        "/api/templates",
        headers=H,
        json={
            "id": tid,
            "name": "Recipe",
            "design_system_id": "default",
            "family": "square",
            "grounds": grounds if grounds is not None else ["white", "black"],
            "html": _GROUND_TPL,
        },
    )
    assert r.status_code == 200, r.text

    task_id = str(uuid.uuid4())
    await seed_task(
        task_id,
        source_data={"title": "T", "category": "WRITING", "style_language": ""},
        result={
            "strategic_brief": {"category": "WRITING", "ground": "white"},
            "platforms": {
                "instagram-square": {
                    "status": "verified",
                    "quality_score": 80,
                    "quality_issues": [],
                    "html_path": "",
                    "template_id": tid,
                    "copy": json.dumps({"headline": "Old"}),
                }
            },
        },
    )
    out = tmp_path / task_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "instagram-square.html").write_text(_RENDERED)
    return task_id, tid


class TestGroundIsPerFormat:
    async def test_ground_defaults_to_the_brief(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.get(
            f"/api/tasks/{task_id}/formats/instagram-square/editor", headers=H
        )
        assert r.status_code == 200, r.text
        assert r.json()["ground"] == "white"

    async def test_switching_ground_persists_to_the_recipe(
        self, authed_client, tmp_path, mock_render_services
    ):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"ground": "black", "render": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ground"] == "black"
        # The recipe is the durable record.
        assert (await read_entry(task_id))["recipe"]["ground"] == "black"
        # …and it survives a reload.
        r = await authed_client.get(
            f"/api/tasks/{task_id}/formats/instagram-square/editor", headers=H
        )
        assert r.json()["ground"] == "black"

    async def test_the_rendered_html_actually_switched_ground(
        self, authed_client, tmp_path, mock_render_services
    ):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"ground": "black", "render": False},
        )
        assert r.status_code == 200, r.text
        assert 'data-ground="black"' in r.json()["html"]

    async def test_rejects_an_invalid_ground(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"ground": "grey"},
        )
        assert r.status_code == 422, r.text
        assert "ground must be white or black" in r.json()["detail"]

    async def test_rejects_an_overlong_ground(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"ground": "chartreuse"},
        )
        assert r.status_code == 422, r.text

    async def test_refuses_a_template_that_does_not_support_the_ground(
        self, authed_client, tmp_path, mock_render_services
    ):
        """The bug this closes: a black post refilled onto a white-only template
        used to render black CSS on a white-only layout, silently."""
        task_id, _ = await _seed(authed_client, tmp_path, grounds=["white"])
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"ground": "black"},
        )
        assert r.status_code == 422, r.text
        assert "white ground only" in r.json()["detail"]

    async def test_omitting_ground_keeps_the_recipe_value(
        self, authed_client, tmp_path, mock_render_services
    ):
        task_id, _ = await _seed(authed_client, tmp_path)
        await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"ground": "black", "render": False},
        )
        # No ground in the body → must NOT snap back to the brief's white.
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "kept black"}, "render": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ground"] == "black"
        assert 'data-ground="black"' in r.json()["html"]


class TestStyleLanguageIsPerFormat:
    async def test_switching_language_persists(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"style_language": "dark-luxury", "render": False},
        )
        assert r.status_code == 200, r.text
        assert (await read_entry(task_id))["recipe"]["style_language"] == "dark-luxury"

    async def test_rejects_an_unknown_language(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"style_language": "no-such-language"},
        )
        assert r.status_code == 422, r.text

    async def test_empty_string_means_the_systems_own(self, authed_client, tmp_path, mock_render_services):
        """`""` is a real setting, distinct from "leave it alone"."""
        task_id, _ = await _seed(authed_client, tmp_path)
        await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"style_language": "dark-luxury", "render": False},
        )
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"style_language": "", "render": False},
        )
        assert r.status_code == 200, r.text
        assert (await read_entry(task_id))["recipe"]["style_language"] == ""


class TestCategoryIsPerFormat:
    async def test_switching_category_persists(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"category": "PROJECT", "render": False},
        )
        assert r.status_code == 200, r.text
        assert (await read_entry(task_id))["recipe"]["category"] == "PROJECT"


class TestSaveVersusRender:
    async def test_render_false_skips_the_png_and_qc(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "quick"}, "render": False},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["png_b64"] == "", "no PNG on the autosave path"
        assert body["pass"] is None, "nothing was re-checked"
        assert body["rendered"] is False
        assert "quick" in body["html"]

    async def test_render_false_still_persists_the_html_and_recipe(
        self, authed_client, tmp_path, mock_render_services
    ):
        task_id, _ = await _seed(authed_client, tmp_path)
        await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "persisted"}, "render": False},
        )
        entry = await read_entry(task_id)
        assert entry["recipe"]["headline"] == "persisted"
        assert "persisted" in (tmp_path / task_id / "instagram-square.html").read_text()

    async def test_render_stale_clears_once_rendered(self, authed_client, tmp_path, mock_render_services):
        task_id, _ = await _seed(authed_client, tmp_path)
        url = f"/api/tasks/{task_id}/formats/instagram-square"
        await authed_client.post(f"{url}/refill", headers=H, json={"slots": {"headline": "a"}, "render": False})
        r = await authed_client.get(f"{url}/editor", headers=H)
        assert r.json()["render_stale"] is True
        await authed_client.post(f"{url}/refill", headers=H, json={"slots": {"headline": "b"}, "render": True})
        r = await authed_client.get(f"{url}/editor", headers=H)
        assert r.json()["render_stale"] is False

    async def test_render_true_returns_a_png_and_a_verdict(
        self, authed_client, tmp_path, mock_render_services
    ):
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "full"}, "render": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["png_b64"]
        assert body["pass"] is True
        assert body["rendered"] is True

    async def test_default_is_render_true_for_back_compat(
        self, authed_client, tmp_path, mock_render_services
    ):
        """Existing clients omit `render`; they must keep the old behaviour."""
        task_id, _ = await _seed(authed_client, tmp_path)
        r = await authed_client.post(
            f"/api/tasks/{task_id}/formats/instagram-square/refill",
            headers=H,
            json={"slots": {"headline": "legacy"}},
        )
        assert r.status_code == 200, r.text
        assert r.json()["rendered"] is True
        assert r.json()["png_b64"]
