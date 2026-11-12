"""Cover task lifecycle, validation, artifact delivery, and render-only retries."""

from unittest.mock import AsyncMock

import pytest

from app.tasks.covers import cover_task, run_covers

H = {"x-api-key": "test-key"}


@pytest.fixture
def enqueued(monkeypatch):
    calls = []
    monkeypatch.setattr(cover_task, "delay", lambda task_id: calls.append(task_id))
    return calls


async def test_cover_api_requires_auth(authed_client):
    assert (await authed_client.get("/api/covers/meta")).status_code == 401
    assert (await authed_client.post("/api/covers", json={})).status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("motif", "unknown"),
        ("engine", "unknown"),
        ("ground", "pink"),
        ("variations", 0),
        ("variations", 5),
        ("design_system_id", "missing"),
        ("content", "x" * 20_001),
        ("placement", "../bad"),
    ],
)
async def test_validation_happens_before_queueing(authed_client, enqueued, field, value):
    response = await authed_client.post("/api/covers", headers=H, json={field: value})
    assert response.status_code == 422
    assert not enqueued


async def test_preview_and_full_procedural_lifecycle(authed_client, enqueued, monkeypatch):
    from app.tasks import covers

    generate = AsyncMock(side_effect=AssertionError("Procedural covers must stay offline"))
    monkeypatch.setattr(covers, "generate_cover_image", generate)
    monkeypatch.setattr(covers, "render_to_png", AsyncMock(return_value=b"PNG"))
    body = {"title": "The limits of computation", "variations": 2, "seed": "stable"}
    preview = await authed_client.post("/api/covers/preview", headers=H, json=body)
    assert preview.status_code == 200
    assert "<svg" in preview.json()["html"]
    composition = preview.json()["composition"]
    assert composition["seed"] == "stable:0"
    assert composition["layer_count"] == len(composition["layers"])
    assert any(layer["motif"] for layer in composition["layers"])
    response = await authed_client.post("/api/covers", headers=H, json=body)
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert enqueued == [task_id]
    await run_covers(task_id)
    detail = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
    assert detail["status"] == "completed"
    assert detail["source_data"]["mode"] == "cover"
    assert detail["result"]["width"] == 1600
    files = (await authed_client.get(f"/api/tasks/{task_id}/files", headers=H)).json()
    assert len(files) == 6
    svg = await authed_client.get(f"/api/tasks/{task_id}/files/cover-1.svg", headers=H)
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert svg.text.startswith("<svg")
    html = await authed_client.get(f"/api/tasks/{task_id}/files/cover-1.html", headers=H)
    assert html.text == preview.json()["html"]
    listing = (await authed_client.get("/api/tasks", headers=H)).json()
    assert next(t for t in listing if t["id"] == task_id)["mode"] == "cover"
    generate.assert_not_awaited()


async def test_ai_render_retry_reuses_artwork(authed_client, enqueued, monkeypatch):
    from app.api import covers as api
    from app.tasks import covers

    monkeypatch.setattr(api, "providers_configured", lambda: True)
    generate = AsyncMock(return_value=("image/png", "aGVsbG8="))
    render = AsyncMock(side_effect=[b"PNG", None, b"PNG"])
    monkeypatch.setattr(covers, "generate_cover_image", generate)
    monkeypatch.setattr(covers, "render_to_png", render)
    response = await authed_client.post(
        "/api/covers",
        headers=H,
        json={
            "engine": "ai",
            "variations": 2,
        },
    )
    task_id = response.json()["task_id"]
    await run_covers(task_id)
    detail = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
    assert detail["status"] == "failed"
    assert generate.await_count == 2
    retry = await authed_client.post(f"/api/tasks/{task_id}/retry", headers=H)
    assert retry.status_code == 200
    assert enqueued == [task_id, task_id]
    await run_covers(task_id)
    assert generate.await_count == 2
    assert render.await_count == 3
    detail = (await authed_client.get(f"/api/tasks/{task_id}", headers=H)).json()
    assert detail["status"] == "completed"


async def test_ai_configuration_and_queue_failure(authed_client, enqueued, monkeypatch):
    from app.api import covers

    monkeypatch.setattr(covers, "providers_configured", lambda: False)
    response = await authed_client.post("/api/covers", headers=H, json={"engine": "ai"})
    assert response.status_code == 422
    assert not enqueued

    def unavailable(task_id):
        raise RuntimeError("queue down")

    monkeypatch.setattr(cover_task, "delay", unavailable)
    response = await authed_client.post("/api/covers", headers=H, json={})
    assert response.status_code == 503
    tasks = (await authed_client.get("/api/tasks", headers=H)).json()
    assert tasks[0]["status"] == "failed"
