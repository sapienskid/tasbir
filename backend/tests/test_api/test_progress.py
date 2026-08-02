"""Task progress endpoint tests — live pipeline {pct, node, per_format}."""

from tests.test_api.conftest import seed_task


async def test_progress_unknown_task_404(authed_client):
    r = await authed_client.get("/api/tasks/nope/progress", headers={"x-api-key": "test-key"})
    assert r.status_code == 404


async def test_progress_running_derived_from_audit(authed_client):
    await seed_task("task-progress-1")

    from app.db.repositories.tasks import TaskRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        await TaskRepository(session).update_status(task_id="task-progress-1", status="running")
        await TaskRepository(session).save_progress(
            "task-progress-1", {"pct": 25, "node": "Writing copy..."}
        )

    from app.services.audit import record_audit

    await record_audit(
        "task-progress-1", "template", {"format": "instagram-square", "used": False}
    )
    await record_audit(
        "task-progress-1",
        "verifier",
        {"format": "instagram-square", "status": "verified", "pass": True},
    )
    await record_audit(
        "task-progress-1",
        "verifier",
        {"format": "linkedin-post", "status": "needs_retry", "pass": False},
    )

    r = await authed_client.get(
        "/api/tasks/task-progress-1/progress", headers={"x-api-key": "test-key"}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pct"] >= 50
    assert data["node"] == "Writing copy..."
    assert data["per_format"]["instagram-square"]["status"] == "verified"
    assert data["per_format"]["linkedin-post"]["status"] == "needs_retry"
    assert data["done"] == 1
    assert data["total"] == 2


async def test_progress_completed_uses_result(authed_client):
    await seed_task("task-progress-2")

    from app.db.repositories.tasks import TaskRepository
    from app.db.session import get_shared_session_factory

    pool = await get_shared_session_factory()
    async with pool() as session:
        await TaskRepository(session).update_status(
            task_id="task-progress-2",
            status="completed",
            result={
                "platforms": {
                    "instagram-square": {"status": "verified"},
                    "linkedin-post": {"status": "failed"},
                }
            },
        )

    r = await authed_client.get(
        "/api/tasks/task-progress-2/progress", headers={"x-api-key": "test-key"}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pct"] == 100
    assert data["total"] == 2
    assert data["done"] == 1
