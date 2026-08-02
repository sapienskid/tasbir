"""Design systems API tests — CRUD, logo, preview, delete protection, jobs."""

from unittest.mock import patch

H = {"x-api-key": "test-key"}


async def _make_temp_ds(client) -> str:
    r = await client.post("/api/design-systems", headers=H, json={"name": "Acme Test"})
    assert r.status_code == 200
    return r.json()["id"]


async def test_list_and_default(authed_client):
    r = await authed_client.get("/api/design-systems", headers=H)
    assert r.status_code == 200
    rows = r.json()
    assert any(row["id"] == "default" for row in rows)
    default = next(row for row in rows if row["id"] == "default")
    assert default["template_count"] >= 16


async def test_crud_and_validation(authed_client):
    dsid = await _make_temp_ds(authed_client)

    r = await authed_client.put(
        f"/api/design-systems/{dsid}",
        headers=H,
        json={"tokens": {"--color-accent": "#00FF00"}},
    )
    assert r.status_code == 200
    assert r.json()["tokens"]["--color-accent"] == "#00FF00"

    r = await authed_client.put(
        f"/api/design-systems/{dsid}",
        headers=H,
        json={"campaigns": {"x": {"ground": "pink"}}},
    )
    assert r.status_code == 422

    r = await authed_client.delete(f"/api/design-systems/{dsid}", headers=H)
    assert r.status_code == 204


async def test_default_delete_protected(authed_client):
    r = await authed_client.delete("/api/design-systems/default", headers=H)
    assert r.status_code == 422


async def test_logo_upload_and_remove(authed_client):
    dsid = await _make_temp_ds(authed_client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = await authed_client.post(
        f"/api/design-systems/{dsid}/logo",
        headers=H,
        files={"file": ("logo.png", png, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["has_logo"] is True

    r = await authed_client.get(f"/api/design-systems/{dsid}", headers=H)
    assert r.json()["has_logo"] is True

    r = await authed_client.delete(f"/api/design-systems/{dsid}/logo", headers=H)
    assert r.status_code == 204
    r = await authed_client.get(f"/api/design-systems/{dsid}", headers=H)
    assert r.json()["has_logo"] is False

    await authed_client.delete(f"/api/design-systems/{dsid}", headers=H)


async def test_preview(authed_client):
    r = await authed_client.post("/api/design-systems/default/preview", headers=H)
    assert r.status_code == 200
    assert "<html" in r.json()["html"].lower()


async def test_from_input_dispatches_job(authed_client):
    with patch("app.tasks.agent_jobs.run_design_system_from_input.delay") as delay:
        r = await authed_client.post(
            "/api/design-systems/from-input", headers=H, data={"name": "Brand X"}
        )
        assert r.status_code == 200
        assert r.json()["job_id"]
        delay.assert_called_once()


async def test_agent_job_lookup(authed_client):
    from app.db.repositories.agent_jobs import AgentJobRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        job = await AgentJobRepository(session).create("template", {"image": "x"})
    r = await authed_client.get(f"/api/agent-jobs/{job.id}", headers=H)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
