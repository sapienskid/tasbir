"""Whole-task retry tests — resume-from-failure re-enqueues with resume_state."""

from tests.test_api.conftest import seed_task

H = {"x-api-key": "test-key"}

_RESULT = {
    "strategic_brief": {"category": "WRITING", "ground": "white", "angle": "a"},
    "post_plan": {
        "post_type": "single", "ratio": "square", "slides": 0,
        "platforms": ["instagram-square", "linkedin-post"],
    },
    "platforms": {
        "instagram-square": {
            "status": "verified", "quality_score": 90, "html_path": "/o/instagram-square.html",
            "copy": '{"headline":"H","body":"B"}',
        },
        "linkedin-post": {
            "status": "needs_retry", "quality_score": 20, "html_path": "",
            "copy": '{"headline":"H2","body":"B2"}',
        },
    },
    "carousel_bases": {},
}


async def test_retry_rejects_running_task(authed_client):
    await seed_task("retry-running", status="running")
    r = await authed_client.post("/api/tasks/retry-running/retry", headers=H)
    assert r.status_code == 409


async def test_retry_resets_to_pending_and_resumes(authed_client):
    await seed_task(
        "retry-failed",
        status="failed",
        error="boom",
        source_data={
            "title": "T", "content": "C",
            "platforms": ["instagram-square", "linkedin-post"],
            "category": "WRITING",
        },
        result=_RESULT,
    )

    r = await authed_client.post("/api/tasks/retry-failed/retry", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"

    task = (
        await authed_client.get("/api/tasks/retry-failed", headers=H)
    ).json()
    assert task["status"] == "pending"
    resume = task["source_data"]["resume_state"]
    assert resume["strategic_brief"]["category"] == "WRITING"
    assert resume["post_plan"]["platforms"] == ["instagram-square", "linkedin-post"]
    # verified format carries its copy + html_path; unverified keeps copy
    assert resume["format_tasks"]["instagram-square"]["html_path"] == "/o/instagram-square.html"
    assert resume["format_tasks"]["linkedin-post"]["status"] == "needs_retry"
    assert '"body":"B"' in resume["format_tasks"]["instagram-square"]["copy"]


async def test_resume_state_skips_carousel_slides(authed_client):
    result = {
        **_RESULT,
        "post_plan": {
            "post_type": "carousel", "ratio": "square", "slides": 2,
            "platforms": ["instagram-carousel"],
        },
        "platforms": {
            "instagram-carousel-1": {
                "status": "verified", "quality_score": 90,
                "html_path": "/o/instagram-carousel-1.html",
                "copy": '{"headline":"S1"}',
            },
            "instagram-carousel-2": {
                "status": "needs_retry", "quality_score": 20, "html_path": "",
                "copy": '{"headline":"S2"}',
            },
        },
        "carousel_bases": {
            "instagram-carousel": '[{"headline":"S1"},{"headline":"S2"}]',
        },
    }
    await seed_task(
        "retry-carousel",
        status="failed",
        source_data={"title": "T", "content": "C", "platforms": ["instagram-carousel"]},
        result=result,
    )
    r = await authed_client.post("/api/tasks/retry-carousel/retry", headers=H)
    assert r.status_code == 200, r.text

    task = (await authed_client.get("/api/tasks/retry-carousel", headers=H)).json()
    resume = task["source_data"]["resume_state"]
    # slide entries are dropped; the base carousel copy is present for re-expansion
    assert "instagram-carousel-1" not in resume["format_tasks"]
    assert resume["format_tasks"]["instagram-carousel"]["copy"].startswith("[")
