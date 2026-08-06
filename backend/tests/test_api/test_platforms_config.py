"""Generate API tests — per-platform config (post_type + template_id)."""


async def _any_template_id(authed_client, family: str | None = None) -> str:
    r = await authed_client.get(
        "/api/templates?design_system_id=default",
        headers={"x-api-key": "test-key"},
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "default DS must have seeded templates"
    if family:
        rows = [t for t in rows if t["family"] == family]
        assert rows, f"no {family} templates seeded"
    return rows[0]["id"]


async def test_platforms_config_passes_through(authed_client):
    tid = await _any_template_id(authed_client)
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square", "linkedin-post"],
            "platforms_config": {
                "instagram-square": {"post_type": "quote", "template_id": tid},
                "linkedin-post": {"post_type": "tutorial"},
            },
        },
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]
    task = (
        await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
    ).json()
    cfg = task["source_data"]["platforms_config"]
    assert cfg["instagram-square"]["post_type"] == "quote"
    assert cfg["instagram-square"]["template_id"] == tid
    assert cfg["linkedin-post"]["post_type"] == "tutorial"
    # unlisted platforms inherit the global defaults — nothing stored for them
    assert "linkedin-post" not in {k for k in cfg if cfg[k].get("template_id")}


async def test_platforms_config_rejects_unselected_platform(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "platforms_config": {"linkedin-post": {"post_type": "quote"}},
        },
    )
    assert r.status_code == 422
    assert "linkedin-post" in r.json()["detail"]


async def test_platforms_config_rejects_invalid_post_type(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "platforms_config": {"instagram-square": {"post_type": "bogus"}},
        },
    )
    assert r.status_code == 422
    assert "post_type" in r.json()["detail"]


async def test_platforms_config_rejects_unknown_template(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "platforms_config": {"instagram-square": {"template_id": "no-such-template"}},
        },
    )
    assert r.status_code == 422
    assert "no-such-template" in r.json()["detail"]


async def test_platforms_config_rejects_empty_entry(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "platforms_config": {"instagram-square": {}},
        },
    )
    assert r.status_code == 422


async def test_global_unknown_template_rejected(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "template_id": "no-such-template",
        },
    )
    assert r.status_code == 422
    assert "no-such-template" in r.json()["detail"]


async def test_platform_images_passthrough_and_validation(authed_client):
    ok = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "platform_images": {
                "instagram-square": [{"url": "https://example.com/a.png", "alt": "a"}]
            },
        },
    )
    assert ok.status_code == 200, ok.text
    task_id = ok.json()["task_id"]
    task = (
        await authed_client.get(f"/api/tasks/{task_id}", headers={"x-api-key": "test-key"})
    ).json()
    assert task["source_data"]["platform_images"]["instagram-square"][0]["alt"] == "a"

    bad = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-square"],
            "platform_images": {"linkedin-post": [{"url": "https://x/y.png", "alt": "a"}]},
        },
    )
    assert bad.status_code == 422


async def test_invalid_ratio_rejected(authed_client):
    r = await authed_client.post(
        "/api/generate",
        headers={"x-api-key": "test-key"},
        json={
            "content": "Content",
            "title": "Title",
            "platforms": ["instagram-carousel"],
            "ratio": "landscape",
        },
    )
    assert r.status_code == 422
