import json
import uuid

from app.db.session import get_shared_session_factory
from app.services.generation_examples import reference_examples
from app.services.system_export import export_system, import_system
from tests.test_api.conftest import seed_task


async def seed_example_task(ds="default", category="WRITING"):
    task_id = str(uuid.uuid4())
    await seed_task(
        task_id,
        source_data={"design_system_id": ds, "category": category},
        result={
            "platforms": {
                "instagram-square": {
                    "status": "verified",
                    "copy": json.dumps({"headline": "Original", "body": "Original copy"}),
                    "recipe": {
                        "design_system_id": ds,
                        "category": category,
                        "headline": "Approved edited headline",
                        "body": "Edited complete point.",
                    },
                }
            },
        },
    )
    return task_id


async def feedback(client, task_id, **kwargs):
    return await client.post(
        f"/api/tasks/{task_id}/feedback",
        headers={"x-api-key": "test-key"},
        json={"format": "instagram-square", "verdict": "approve", **kwargs},
    )


async def test_feedback_never_learns_without_explicit_opt_in(authed_client):
    task_id = await seed_example_task()
    assert (await feedback(authed_client, task_id, note="Looks good")).status_code == 201
    response = await authed_client.get(
        "/api/generation-examples", headers={"x-api-key": "test-key"}
    )
    assert response.json() == []
    assert (await feedback(authed_client, task_id, curate=True)).status_code == 422
    assert (await feedback(authed_client, task_id, curate=True, note=" ")).status_code == 422
    assert (
        await feedback(authed_client, task_id, curate=True, verdict="reject", note="No")
    ).status_code == 422


async def test_examples_use_edited_copy_and_only_same_brand_category(authed_client):
    task_id = await seed_example_task()
    response = await feedback(
        authed_client, task_id, curate=True, note="Specific hook and complete point"
    )
    assert response.status_code == 201
    example = response.json()["example"]
    assert example["headline"] == "Approved edited headline"
    assert (await reference_examples("default", "WRITING"))[0]["body"] == "Edited complete point."
    assert not await reference_examples("another-brand", "WRITING")
    assert not await reference_examples("default", "NOTE")
    reference = (await reference_examples("default", "WRITING"))[0]
    assert all(key not in reference for key in ("tokens", "html", "task_id"))


async def test_examples_survive_task_deletion_and_config_backup_restore(authed_client):
    from app.models.task import GenerationTask

    task_id = await seed_example_task()
    await feedback(authed_client, task_id, curate=True, note="Clear editorial progression")
    pool = await get_shared_session_factory()
    snapshot = await export_system(pool)
    assert any(row["key"].startswith("generation.example.") for row in snapshot["app_settings"])
    async with pool() as session:
        task = await session.get(GenerationTask, task_id)
        await session.delete(task)
        await session.commit()
    assert len(await reference_examples("default", "WRITING")) == 1
    examples = (
        await authed_client.get("/api/generation-examples", headers={"x-api-key": "test-key"})
    ).json()
    removed = await authed_client.delete(
        f"/api/generation-examples/{examples[0]['id']}", headers={"x-api-key": "test-key"}
    )
    assert removed.status_code == 204
    assert not await reference_examples("default", "WRITING")
    await import_system(pool, snapshot)
    assert len(await reference_examples("default", "WRITING")) == 1


async def test_reject_removes_reference_and_endpoints_require_auth(authed_client):
    task_id = await seed_example_task()
    assert (await authed_client.get("/api/generation-examples")).status_code == 401
    response = await feedback(authed_client, task_id, curate=True, note="Clear hook")
    key = response.json()["example"]["id"]
    assert (await authed_client.delete(f"/api/generation-examples/{key}")).status_code == 401
    assert (await feedback(authed_client, task_id, verdict="reject")).status_code == 201
    assert not await reference_examples("default", "WRITING")
