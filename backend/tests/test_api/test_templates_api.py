"""Templates API tests — list, preview, validate, CRUD, from-image job."""

from unittest.mock import patch

H = {"x-api-key": "test-key"}


def _tiny_html() -> str:
    return (
        "<!DOCTYPE html><html><head><style>"
        "body{width:1080px;height:1080px;overflow:hidden;margin:0}"
        "</style></head><body data-slot=\"headline\">{{ headline }}</body></html>"
    )


async def test_list_and_preview(authed_client):
    r = await authed_client.get("/api/templates?design_system_id=default", headers=H)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 10
    tid = rows[0]["id"]

    r = await authed_client.post(f"/api/templates/{tid}/preview", headers=H)
    assert r.status_code == 200
    assert "<html" in r.json()["html"].lower()

    r = await authed_client.post(f"/api/templates/{tid}/render", headers=H)
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_create_and_delete(authed_client):
    body = {
        "id": "square-test-tpl",
        "name": "Test Template",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white"],
        "html": _tiny_html(),
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 200
    tid = r.json()["id"]

    r = await authed_client.get(f"/api/templates/{tid}", headers=H)
    assert r.status_code == 200
    assert "{{ headline }}" in r.json()["html"]

    r = await authed_client.delete(f"/api/templates/{tid}", headers=H)
    assert r.status_code == 204

    r = await authed_client.get(f"/api/templates/{tid}", headers=H)
    assert r.status_code == 404


async def test_duplicate_id_rejected(authed_client):
    body = {
        "id": "square-test-tpl",
        "name": "Dup",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white"],
        "html": _tiny_html(),
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 200
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 409
    await authed_client.delete("/api/templates/square-test-tpl", headers=H)


async def test_from_image_dispatches_job(authed_client):
    with patch("app.tasks.agent_jobs.run_template_from_image.delay") as delay:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        r = await authed_client.post(
            "/api/templates/from-image",
            headers=H,
            files={"file": ("mock.png", png, "image/png")},
            data={"design_system_id": "default"},
        )
        assert r.status_code == 200
        assert r.json()["job_id"]
        delay.assert_called_once()


def _conditional_html() -> str:
    return (
        "<!DOCTYPE html><html><head><style>"
        "body{width:1080px;height:1080px;overflow:hidden;margin:0;"
        "background:var(--color-bg);color:var(--color-text);font-family:var(--font-sans)}"
        "body[data-ground=\"black\"]{background:var(--color-bg-inverted);color:var(--color-text-inverted)}"
        ".headline{font-family:var(--font-display);font-size:70px}"
        "</style></head>"
        "<body {% if ground == \"black\" %}data-ground=\"black\"{% endif %}>"
        "{% if subhead %}<div class=\"subhead\" data-slot=\"subhead\">"
        "{{ subhead }}</div>{% endif %}"
        "{% if body %}<div class=\"body\" data-slot=\"body\">{{ body }}</div>{% endif %}"
        "<h1 class=\"headline\" data-slot=\"headline\">{{ headline }}</h1>"
        "{% if footer_right %}<span class=\"handle\" data-slot=\"footer_right\">"
        "{{ footer_right }}</span>{% endif %}"
        "</body></html>"
    )


async def test_create_and_update_controls(authed_client):
    body = {
        "id": "square-controls",
        "name": "Controls",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white", "black"],
        "html": _conditional_html(),
        "hidden_elements": ["subhead"],
        "media_position": "left",
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["hidden_elements"] == ["subhead"]
    assert data["media_position"] == "left"

    r2 = await authed_client.put(
        "/api/templates/square-controls",
        headers=H,
        json={"hidden_elements": ["body"], "media_position": "bottom"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["hidden_elements"] == ["body"]
    assert r2.json()["media_position"] == "bottom"

    await authed_client.delete("/api/templates/square-controls", headers=H)


async def test_create_rejects_unknown_hidden_element(authed_client):
    body = {
        "id": "square-bad-hidden",
        "name": "Bad",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white"],
        "html": _conditional_html(),
        "hidden_elements": ["not_a_real_element"],
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 422
    assert "Unknown hidden element" in r.json()["detail"]


async def test_create_rejects_invalid_media_position(authed_client):
    body = {
        "id": "square-bad-pos",
        "name": "Bad",
        "design_system_id": "default",
        "family": "square",
        "grounds": ["white"],
        "html": _conditional_html(),
        "media_position": "diagonal",
    }
    r = await authed_client.post("/api/templates", headers=H, json=body)
    assert r.status_code == 422


async def test_preview_draft_reflects_hidden(authed_client):
    r = await authed_client.post(
        "/api/templates/preview-draft",
        headers=H,
        json={
            "html": _conditional_html(),
            "family": "square",
            "design_system_id": "default",
            "hidden": ["subhead"],
            "media_position": "right",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()["html"]
    assert "White space is the rhythm" not in out  # subhead sample hidden
    assert 'data-slot="footer_right"' in out  # footer still present


async def test_from_image_rejects_bad_ds(authed_client):
    with patch("app.tasks.agent_jobs.run_template_from_image.delay") as delay:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        r = await authed_client.post(
            "/api/templates/from-image",
            headers=H,
            files={"file": ("mock.png", png, "image/png")},
            data={"design_system_id": "nope"},
        )
        assert r.status_code == 422
        delay.assert_not_called()


async def test_from_input_requires_context(authed_client):
    with patch("app.tasks.agent_jobs.run_template_build_task.delay") as delay:
        r = await authed_client.post(
            "/api/templates/from-input",
            headers=H,
            data={"design_system_id": "default", "family": "story"},
        )
        assert r.status_code == 422
        delay.assert_not_called()


async def test_from_input_with_message_dispatches_job(authed_client):
    with patch("app.tasks.agent_jobs.run_template_build_task.delay") as delay:
        r = await authed_client.post(
            "/api/templates/from-input",
            headers=H,
            data={
                "design_system_id": "default",
                "message": "A bold story post with a big serif headline",
                "family": "story",
                "ground": "black",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["job_id"]
        delay.assert_called_once()


async def test_from_input_with_image_dispatches_job(authed_client):
    with patch("app.tasks.agent_jobs.run_template_build_task.delay") as delay:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        r = await authed_client.post(
            "/api/templates/from-input",
            headers=H,
            files={"file": ("mock.png", png, "image/png")},
            data={"design_system_id": "default"},
        )
        assert r.status_code == 200
        assert r.json()["job_id"]
        delay.assert_called_once()


async def test_from_input_with_html_dispatches_job(authed_client):
    with patch("app.tasks.agent_jobs.run_template_build_task.delay") as delay:
        r = await authed_client.post(
            "/api/templates/from-input",
            headers=H,
            data={"design_system_id": "default", "html": _tiny_html()},
        )
        assert r.status_code == 200
        assert r.json()["job_id"]
        delay.assert_called_once()


async def test_from_input_rejects_bad_ds(authed_client):
    with patch("app.tasks.agent_jobs.run_template_build_task.delay") as delay:
        r = await authed_client.post(
            "/api/templates/from-input",
            headers=H,
            data={"design_system_id": "nope", "message": "something"},
        )
        assert r.status_code == 422
        delay.assert_not_called()
