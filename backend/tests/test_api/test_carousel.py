"""Generate API carousel tests — slides validation + request passthrough."""


async def test_carousel_defaults_to_three_slides(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={"content": "Content", "title": "Title", "platforms": ["instagram-carousel"]},
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]

    task = (
        await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
    ).json()
    assert task["source_data"]["platforms"] == ["instagram-carousel"]
    assert task["source_data"]["slides"] == 3


async def test_carousel_with_explicit_slide_count(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-carousel"],
            "slides": 5,
        },
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]

    task = (
        await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
    ).json()
    assert task["source_data"]["slides"] == 5


async def test_slides_requires_carousel_platform(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "slides": 4,
        },
    )
    assert r.status_code == 422
    assert "carousel" in r.json()["detail"]


async def test_portrait_carousel_accepted(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-carousel-portrait"],
            "slides": 4,
            "ratio": "portrait",
        },
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]
    task = (
        await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
    ).json()
    assert task["source_data"]["platforms"] == ["instagram-carousel-portrait"]
    assert task["source_data"]["slides"] == 4


async def test_auto_platforms_accepted(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={"content": "Content", "title": "Title", "platforms": ["auto"]},
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]
    task = (
        await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
    ).json()
    assert task["source_data"]["platforms"] == ["auto"]


async def test_carousel_rejects_out_of_range_slides(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-carousel"],
            "slides": 99,
        },
    )
    assert r.status_code == 422
