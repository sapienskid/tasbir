"""Agent jobs API tests — list, delete, and result-title derivation."""

H = {"x-api-key": "test-key"}


async def _seed_template_job(db, **overrides) -> str:
    from app.db.repositories.agent_jobs import AgentJobRepository

    payload = {"design_system_id": "default", "family": "square", "message": "hi"}
    job = await AgentJobRepository(db).create("template", payload)
    await AgentJobRepository(db).update_status(
        job.id, "completed", result={"template_id": None, "family": "square"}
    )
    return job.id


async def test_list_jobs(authed_client):
    # seeded jobs? list should at least return an array
    r = await authed_client.get("/api/agent-jobs", headers=H)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_filtered_by_kind(authed_client):
    from app.db.repositories.agent_jobs import AgentJobRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        await _seed_template_job(session)
        await AgentJobRepository(session).create(
            "design_system", {"name": "Brand"}
        )

    r = await authed_client.get("/api/agent-jobs?kind=template", headers=H)
    kinds = {row["kind"] for row in r.json()}
    assert kinds == {"template"}


async def test_get_job_title_and_delete(authed_client):
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        job_id = await _seed_template_job(session)

    r = await authed_client.get(f"/api/agent-jobs/{job_id}", headers=H)
    assert r.status_code == 200
    assert r.json()["title"]  # derived title present

    r = await authed_client.delete(f"/api/agent-jobs/{job_id}", headers=H)
    assert r.status_code == 200

    r = await authed_client.get(f"/api/agent-jobs/{job_id}", headers=H)
    assert r.status_code == 404


async def test_template_job_title_uses_result(authed_client):
    from app.db.repositories.agent_jobs import AgentJobRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        job = await AgentJobRepository(session).create(
            "template", {"design_system_id": "default", "message": "hi"}
        )
        await AgentJobRepository(session).update_status(
            job.id, "completed", result={"template_id": "default-my-tpl", "family": "square"}
        )

    r = await authed_client.get(f"/api/agent-jobs/{job.id}", headers=H)
    assert r.status_code == 200
    assert r.json()["title"] == "default-my-tpl"
