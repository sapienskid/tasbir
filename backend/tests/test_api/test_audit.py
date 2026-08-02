"""Task audit timeline endpoint tests."""

from tests.test_api.conftest import seed_task


async def test_audit_timeline_empty_for_new_task(authed_client):
    await seed_task("task-audit-1")
    r = await authed_client.get(
        "/api/tasks/task-audit-1/audit", headers={"x-api-key": "test-key"}
    )
    assert r.status_code == 200, r.text
    assert r.json() == []


async def test_audit_records_and_lists(authed_client):
    await seed_task("task-audit-2")

    from app.services.audit import record_audit

    await record_audit(
        "task-audit-2", "strategist", {"category": "WRITING", "ground": "white"}, "angle"
    )
    await record_audit(
        "task-audit-2",
        "verifier",
        {"format": "instagram-square", "status": "verified", "pass": True, "score": 88},
        "clean",
    )

    r = await authed_client.get(
        "/api/tasks/task-audit-2/audit", headers={"x-api-key": "test-key"}
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2
    assert [row["agent_name"] for row in rows] == ["strategist", "verifier"]
    assert rows[0]["decision"]["category"] == "WRITING"
    assert rows[1]["critique"] == "clean"


async def test_audit_unknown_task_404(authed_client):
    r = await authed_client.get("/api/tasks/nope/audit", headers={"x-api-key": "test-key"})
    assert r.status_code == 404
