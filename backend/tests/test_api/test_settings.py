"""Runtime settings API tests."""

H = {"x-api-key": "test-key"}


async def test_settings_seeded_with_defaults(authed_client):
    r = await authed_client.get("/api/settings", headers=H)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["values"]["verifier.max_retries"] == 2
    assert data["values"]["copywriter.concurrency"] == 2
    assert data["values"]["vision.min_interval_seconds"] == 5.0
    assert data["values"]["chat.html_cap_chars"] == 80000
    assert data["values"]["templates.recent_limit"] == 8


async def test_settings_update_and_reset(authed_client):
    r = await authed_client.put(
        "/api/settings",
        headers=H,
        json={"values": {"verifier.max_retries": 5, "copywriter.concurrency": 3}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["values"]["verifier.max_retries"] == 5
    assert r.json()["values"]["copywriter.concurrency"] == 3

    # Runtime readers honor the knob.
    from app.services.settings import get_runtime_setting

    assert await get_runtime_setting("verifier.max_retries") == 5
    assert await get_runtime_setting("copywriter.concurrency") == 3

    r = await authed_client.post("/api/settings/reset", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["values"]["verifier.max_retries"] == 2


async def test_settings_ignores_unknown_keys(authed_client):
    r = await authed_client.put(
        "/api/settings", headers=H, json={"values": {"not.a.knob": 99}}
    )
    assert r.status_code == 200, r.text
    assert "not.a.knob" not in r.json()["values"]
